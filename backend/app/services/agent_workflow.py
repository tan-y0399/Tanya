"""
Agent 工作流路由 — 链路 A/B/C 分流与状态定义

链路 A (link_a): 普通问答 — general_qa / knowledge_qa，无工具
链路 B (link_b): 轻量查询 ReAct — 高置信 ops_query，1-2 条只读命令，跳过方案确认
链路 C (link_c): 深度故障 Plan-Execute — fault_analysis / high_risk / 低置信 ops_query
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.ops_scope import (
    is_disk_cleanup_execution_request,
    is_live_ops_query,
    is_service_control_request,
    is_time_sync_execution_request,
    is_time_sync_request,
)


class WorkflowLink(str, Enum):
    HANDLER_QA = "link_a"
    LIGHTWEIGHT_REACT = "link_b"
    PLAN_EXECUTE = "link_c"


class AgentTaskStatus(str, Enum):
    """全流程统一任务状态"""
    PENDING = "pending"
    SECURITY_BLOCKED = "security_blocked"
    ROUTING = "routing"
    AWAITING_PLAN_CONFIRM = "awaiting_plan_confirm"
    ENV_PRECHECK = "env_precheck"
    EXECUTING = "executing"
    AWAITING_CONFIRM = "awaiting_confirm"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_USER_RUN = "awaiting_user_run"
    ROLLING_BACK = "rolling_back"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


LINK_LABELS = {
    WorkflowLink.HANDLER_QA.value: "普通问答链路",
    WorkflowLink.LIGHTWEIGHT_REACT.value: "轻量查询 ReAct 链路",
    WorkflowLink.PLAN_EXECUTE.value: "深度故障 Plan-Execute 链路",
}

LINK_DESCRIPTIONS = {
    WorkflowLink.HANDLER_QA.value: "纯 LLM 回答，不调用 SSH 工具",
    WorkflowLink.LIGHTWEIGHT_REACT.value: "简单只读运维查询，直接进入 ReAct 快速执行",
    WorkflowLink.PLAN_EXECUTE.value: "环境感知 → 诊断方案 → 用户确认 → 分步执行 → 动态调整",
}

# 故障/复杂运维特征 — 命中则走 Plan-Execute
COMPLEX_OPS_MARKERS = (
    "故障", "异常", "宕机", "无法启动", "crash", "failed", "error",
    "根因", "排查", "诊断", "分析", "为什么", "原因",
    "多个", "一系列", "全面", "彻底",
)

# 轻量只读查询特征
LIGHTWEIGHT_READ_MARKERS = (
    "查看", "查询", "检查", "看看", "列出", "多少", "使用率", "使用情况", "状态",
    "列表", "显示", "获取", "get ", "df", "free", "top", "ps ",
)


def _confidence(intent_result: dict) -> float:
    try:
        return float(intent_result.get("confidence", 0))
    except (TypeError, ValueError):
        return 0.0


def _intent(intent_result: dict) -> str:
    return str(intent_result.get("intent", "general_qa"))


def is_complex_ops_request(content: str) -> bool:
    t = (content or "").lower()
    return any(m in t for m in COMPLEX_OPS_MARKERS)


def is_likely_readonly_query(content: str) -> bool:
    t = (content or "").strip().lower()
    if is_service_control_request(content):
        return False
    if is_disk_cleanup_execution_request(content):
        return False
    if is_time_sync_execution_request(content):
        return False
    return any(m in t for m in LIGHTWEIGHT_READ_MARKERS)


def resolve_workflow_link(content: str, intent_result: dict) -> Dict[str, Any]:
    """
    根据意图、置信度与问题复杂度，分流至链路 A/B/C。

    返回:
      link, link_label, link_description, reason,
      use_diagnostic_plan, env_sensing_mode, file_protection_required
    """
    intent = _intent(intent_result)
    conf = _confidence(intent_result)
    tool_resolution = intent_result.get("tool_resolution") or {}

    high_conf_threshold = getattr(settings, "workflow_lightweight_confidence", 0.9)
    low_conf_threshold = getattr(settings, "workflow_plan_confidence", 0.7)

    # 工具库命中可执行方案 → 优先 Plan-Execute 或轻量 ReAct
    if tool_resolution.get("actionable"):
        reason = tool_resolution.get("reason") or "工具库可执行方案"
        if tool_resolution.get("prefer_plan"):
            return _pack(
                WorkflowLink.PLAN_EXECUTE,
                reason,
                use_plan=True,
                sensing="fault_diagnosis",
            )
        return _pack(
            WorkflowLink.LIGHTWEIGHT_REACT,
            reason + "；单步/轻量工具，直接 ReAct",
            use_plan=False,
            sensing="quick_check",
        )

    # 链路 A
    if intent in ("general_qa", "knowledge_qa"):
        if intent_result.get("requires_react_redirect"):
            pass  # 由上层 react_guard 已改写意图
        else:
            return _pack(
                WorkflowLink.HANDLER_QA,
                f"意图={intent}，无需工具",
                use_plan=False,
                sensing=None,
            )

    # 强制 Plan-Execute 的场景
    force_plan = (
        intent in ("fault_analysis", "high_risk")
        or is_service_control_request(content)
        or is_disk_cleanup_execution_request(content)
        or is_time_sync_request(content)
        or is_time_sync_execution_request(content)
        or (intent == "ops_query" and conf < low_conf_threshold)
        or (intent == "ops_query" and is_complex_ops_request(content))
    )

    if force_plan:
        reason_parts = [f"意图={intent}"]
        if conf < low_conf_threshold:
            reason_parts.append(f"置信度 {conf:.2f} < {low_conf_threshold}")
        if is_complex_ops_request(content):
            reason_parts.append("复杂故障/诊断诉求")
        if is_service_control_request(content):
            reason_parts.append("服务启停操作")
        return _pack(
            WorkflowLink.PLAN_EXECUTE,
            "；".join(reason_parts),
            use_plan=True,
            sensing="fault_diagnosis",
        )

    # 链路 B：轻量 ops_query（明确只读实时查询，直接 ReAct 跳过方案）
    readonly_query = (
        not is_complex_ops_request(content)
        and (is_likely_readonly_query(content) or is_live_ops_query(content))
    )
    if intent == "ops_query" and readonly_query:
        if conf >= high_conf_threshold or (conf >= low_conf_threshold and is_live_ops_query(content)):
            reason = f"意图=ops_query 置信度 {conf:.2f}，实时只读查询，轻量 ReAct"
            return _pack(
                WorkflowLink.LIGHTWEIGHT_REACT,
                reason,
                use_plan=False,
                sensing="quick_check",
            )

    # 默认 ops 走 Plan-Execute（中等复杂度 / 非典型只读查询）
    if intent in ("ops_query", "fault_analysis", "high_risk"):
        return _pack(
            WorkflowLink.PLAN_EXECUTE,
            f"意图={intent}，默认深度 Plan-Execute",
            use_plan=True,
            sensing="fault_diagnosis" if intent == "fault_analysis" else "full_check",
        )

    return _pack(
        WorkflowLink.HANDLER_QA,
        f"兜底路由 intent={intent}",
        use_plan=False,
        sensing=None,
    )


def _pack(
    link: WorkflowLink,
    reason: str,
    use_plan: bool,
    sensing: Optional[str],
) -> Dict[str, Any]:
    return {
        "link": link.value,
        "link_label": LINK_LABELS[link.value],
        "link_description": LINK_DESCRIPTIONS[link.value],
        "reason": reason,
        "use_diagnostic_plan": use_plan and getattr(settings, "enable_diagnostic_plan", True),
        "env_sensing_mode": sensing,
        "file_protection_required": link == WorkflowLink.PLAN_EXECUTE,
    }


# 关键文件保护白名单（禁止删除/覆盖）
CRITICAL_FILE_PATHS = (
    "/etc/passwd", "/etc/shadow", "/etc/group", "/etc/sudoers",
    "/etc/ssh/sshd_config", "/etc/fstab", "/boot", "/etc/grub",
    "/var/lib/mysql", "/var/lib/pgsql", "/var/lib/docker",
)

BUSINESS_DATA_HINTS = (
    "数据目录", "数据库", "业务数据", "生产数据", "备份目录",
)


def build_file_protection_whitelist(
    content: str = "",
    rag_context: str = "",
    env_snapshot: dict = None,
) -> List[str]:
    """基于 RAG 与诉求生成临时文件保护白名单。"""
    protected = set(CRITICAL_FILE_PATHS)
    combined = f"{content}\n{rag_context or ''}".lower()

    path_patterns = re.findall(r"(/[\w./_-]{2,})", combined)
    for p in path_patterns:
        if any(k in p for k in ("data", "mysql", "pgsql", "backup", "db")):
            protected.add(p.rstrip("/"))

    for hint in BUSINESS_DATA_HINTS:
        if hint in combined:
            protected.add(f"/*{hint}*")

    if env_snapshot and env_snapshot.get("metrics"):
        for _tool, result in env_snapshot["metrics"].items():
            text = str(result)
            for p in re.findall(r"(/var/[\w./-]+|/etc/[\w./-]+)", text):
                if "lib" in p or "data" in p:
                    protected.add(p)

    return sorted(protected)


def get_risk_disposition_table() -> List[Dict[str, str]]:
    """L1-L5 全等级风险定义（供前端/文档展示）。"""
    return [
        {"level": "L1", "name": "只读操作", "action": "自动放行，立即执行",
         "examples": "查看状态、查询日志、列出文件"},
        {"level": "L2", "name": "低风险修改", "action": "前端 L2 确认卡片，用户确认后执行",
         "examples": "清理缓存、重载配置、TERM 信号"},
        {"level": "L3", "name": "中风险操作", "action": "用户确认 + 操作日志实时记录",
         "examples": "重启非核心服务、修改非关键配置、强制对时"},
        {"level": "L4", "name": "高风险操作", "action": "管理员审批 → 用户确认执行",
         "examples": "停止服务、删除文件、修改系统参数"},
        {"level": "L5", "name": "极高风险", "action": "直接拦截，禁止执行",
         "examples": "格式化磁盘、rm -rf /、修改内核参数"},
    ]
