import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
import httpx
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import desc
from app.models.session import Session, Message
from app.models.approval import Approval
from app.models.pending_execution import PendingExecution
from app.core.config import settings
from app.core.trace import generate_trace_id
from app.core.command_security import analyze_command, RiskLevel, get_risk_level_info
from app.services.tool_definitions import TOOLS, SYSTEM_PROMPT

# 当前会话绑定的自定义工具注册表（供 execute / risk / LLM tools 使用）
_ACTIVE_CUSTOM_REGISTRY = None
from app.services.intent_router import intent_router, IntentType
from app.services.performance_telemetry import TraceTelemetry, record_trace
from app.services.security_workflow import _detect_prompt_injection  # 保留兼容

logger = logging.getLogger(__name__)


# ============================================================
# 工具执行器 —— 通过 SSH 在远程麒麟VM上真实执行
# ============================================================
def execute_tool(name: str, args: dict) -> dict:
    """执行工具并返回带 display_summary 的结构化结果。"""
    return _finalize_tool_result(name, _execute_tool_core(name, args))


def set_active_custom_registry(registry) -> None:
    global _ACTIVE_CUSTOM_REGISTRY
    _ACTIVE_CUSTOM_REGISTRY = registry


def _execute_tool_core(name: str, args: dict) -> dict:
    """执行工具调用，通过 MCP 协议转发到远程麒麟VM执行。

    两层调度:
      1. MCP adapter — 标准化协议 + 安全校验 + 审计
      2. remote_executor — SSH 转发 + 沙箱执行
    """
    from app.services.remote_executor import execute_tool as remote_exec
    from app.services.tool_args import normalize_tool_args, resolve_remote_tool_name

    args = normalize_tool_args(name, args)

    global _ACTIVE_CUSTOM_REGISTRY
    if _ACTIVE_CUSTOM_REGISTRY and name in _ACTIVE_CUSTOM_REGISTRY.tools:
        custom_result = _ACTIVE_CUSTOM_REGISTRY.execute(name, args)
        if custom_result is not None:
            return custom_result

    # ── 通过 MCP registry 查找工具定义 ──
    try:
        from app.mcp.registry import get_tool_definition, call_tool
        mcp_def = get_tool_definition(name)
    except Exception:
        mcp_def = None

    # 工具名映射：chat_service 标准名 → remote_executor 内部名
    tool_map = {
        "get_system_info": "get_system_info",
        "get_cpu_info": "get_cpu_info",
        "get_memory_info": "get_memory_info",
        "get_disk_usage": "get_disk_info",
        "list_processes": "get_process_list",
        "get_network_connections": "get_network_connections",
        "get_network_speed": "get_network_speed",
        "get_network_interfaces": "get_network_interfaces",
        "get_process_detail": "get_process_detail",
        "kill_process": "kill_process",
        "get_service_status": "get_service_status",
        "manage_service": "manage_service",
        "get_file_list": "get_file_list",
        "read_file": "read_file",
        "get_logs": "get_logs",
        "get_users": "get_users",
        "get_groups": "get_groups",
    }

    # ── 优先通过 MCP protocol 调用 ──
    if mcp_def:
        try:
            mcp_result = call_tool(name, args)
            # MCP registry 可能返回了结果，也可能没有找到对应实现
            if mcp_result and not isinstance(mcp_result, dict) and mcp_result.get("_not_found"):
                pass  # fall through to remote_exec
            elif mcp_result:
                return mcp_result
        except Exception:
            pass  # MCP 调用失败则回退到远程执行

    # ── 回退：直接调用远程执行器 ──
    if name in tool_map:
        remote_name = tool_map[name]
        return remote_exec(remote_name, **normalize_tool_args(remote_name, args))

    if name == "search_journal_logs":
        service = args.get("service", "")
        priority = args.get("priority", "")
        lines = args.get("lines", 20)
        cmd = "journalctl"
        if service:
            cmd += " -u " + service
        if priority:
            prio_map = {"err": "3", "warning": "4", "info": "6"}
            cmd += " -p " + prio_map.get(priority, "6")
        cmd += " -n " + str(lines) + " --no-pager 2>/dev/null"
        return remote_exec("run_command", command=cmd, timeout=5)

    if name == "execute_command":
        command = args.get("command", "")
        timeout = args.get("timeout", 30)
        return remote_exec("run_command", command=command, timeout=timeout)

    if name == "summarize_task":
        summary = args.get("summary", "")
        return {
            "success": True,
            "data": {
                "summary": summary,
                "task_completed": True,
            }
        }

    return {"success": False, "error": "未知工具: " + name}


def _sse_exploring(step_id: str, title: str, detail: str = "", status: str = "running") -> dict:
    """Exploring 思考过程 SSE 事件（对标 Cursor Exploring 面板）。"""
    return {
        "event": "exploring_step",
        "data": json.dumps({
            "id": step_id,
            "title": title,
            "detail": detail,
            "status": status,
        }, ensure_ascii=False),
    }


def _finalize_tool_result(tool_name: str, result: dict) -> dict:
    """统一格式化工具输出（展示摘要 + LLM 友好结构）。"""
    from app.services.tool_output_formatter import enrich_tool_result
    return enrich_tool_result(tool_name, result)


def _plan_step_result_status(tool_name: str, result: dict, step: dict) -> str:
    """方案步骤终态：结合工具 success 与步骤语义（如「确保服务运行」）。"""
    if not result.get("success"):
        return "failed"
    if tool_name == "execute_command":
        data = result.get("data") or {}
        action = (step.get("action") or "").lower()
        is_check = any(k in action for k in ("检查", "是否", "确认", "查看", "列出", "检测"))
        if data.get("diagnostic_negative") and is_check:
            return "completed"
        return "completed"
    if tool_name != "get_service_status":
        return "completed"
    data = result.get("data") or {}
    if (data.get("state") or "").lower() == "not-found":
        return "failed"
    action = (step.get("action") or "").lower()
    expects_running = any(k in action for k in ("确保", "正常运行", "运行正常", "是否运行", "启动", "广播正常"))
    if expects_running and not data.get("active"):
        return "failed"
    return "completed"


async def _yield_plan_step_progress(
    user_question: str,
    tool_call_records: list,
    plan_data: dict | None = None,
):
    """方案执行中（待确认/待审批/步骤间）推送轻量进度，不写执行结论。"""
    from app.services.response_summarizer import build_plan_step_progress_brief
    from app.services.stream_events import response_phase, PHASE_EXECUTE

    brief = build_plan_step_progress_brief(user_question, tool_call_records, plan_data)
    yield response_phase(PHASE_EXECUTE, brief.get("brief") or "方案执行中…")
    yield {"event": "plan_progress", "data": json.dumps(brief, ensure_ascii=False)}


async def _yield_plan_progress_summary(
    user_question: str,
    tool_call_records: list,
    full_response: str,
    plan_data: dict | None = None,
):
    """方案暂停（待确认/待审批）时输出进度总结（兼容旧前端，新流程请用 _yield_plan_step_progress）。"""
    from app.services.response_summarizer import (
        TOOLS_MARKER,
        build_plan_progress_conclusion,
    )
    from app.services.stream_events import response_phase, stream_token, PHASE_SUMMARY

    progress = build_plan_progress_conclusion(user_question, tool_call_records, plan_data)
    yield response_phase(PHASE_SUMMARY, "正在整理执行进度…")
    yield _sse_exploring("summary", "执行进度", "整理已完成步骤")
    yield {"event": "summary_start", "data": json.dumps({"title": "执行结论"})}
    if TOOLS_MARKER not in full_response:
        yield stream_token(TOOLS_MARKER, PHASE_SUMMARY)
    yield stream_token(progress, PHASE_SUMMARY)
    yield _sse_exploring("summary", "执行进度", "完成", "done")
    yield {"event": "summary_done", "data": json.dumps({})}


async def _yield_plan_final_summary_events(
    user_question: str,
    tool_call_records: list,
    full_response: str,
    plan_data: dict | None = None,
):
    """方案全部步骤完成后，由 LLM 生成详细执行结论。"""
    from app.services.response_summarizer import (
        TOOLS_MARKER,
        stream_final_summary,
        build_plan_final_conclusion,
    )
    from app.services.stream_events import response_phase, stream_token, PHASE_SUMMARY

    if not tool_call_records:
        return

    if _plan_has_pending_actions(tool_call_records):
        logger.info("skip plan final summary: pending approval/confirm still open")
        return
    if _filter_actionable_pending_records(tool_call_records):
        logger.info("skip plan final summary: actionable pending records exist")
        return

    pending_orders = {
        int(r["planStepOrder"]) for r in tool_call_records
        if r.get("planStepOrder") is not None
        and r.get("status") in ("pending_approval", "pending_confirm")
    }
    if pending_orders:
        return

    steps = (plan_data or {}).get("steps") or []
    if steps:
        done = _infer_done_plan_orders(plan_data or {}, tool_call_records)
        if len(done) < len(steps):
            logger.info("skip plan final summary: %s/%s steps done", len(done), len(steps))
            return

    yield response_phase(PHASE_SUMMARY, "正在生成执行结论…")
    yield _sse_exploring("summary", "生成执行结论", "分析工具结果并撰写总结")
    yield {"event": "summary_start", "data": json.dumps({"title": "执行结论"})}
    if TOOLS_MARKER not in full_response:
        yield stream_token(TOOLS_MARKER, PHASE_SUMMARY)

    try:
        async for token in stream_final_summary(user_question, tool_call_records, plan_data):
            yield stream_token(token, PHASE_SUMMARY)
    except Exception as e:
        logger.warning("plan final summary failed: %s", e)
        yield stream_token(
            build_plan_final_conclusion(user_question, tool_call_records, plan_data),
            PHASE_SUMMARY,
        )

    yield _sse_exploring("summary", "生成执行结论", "完成", "done")
    yield {"event": "summary_done", "data": json.dumps({})}
    yield {"event": "plan_progress", "data": json.dumps({
        "phenomenon": (plan_data or {}).get("phenomenon") or user_question[:80],
        "totalSteps": len((plan_data or {}).get("steps") or []),
        "completedSteps": len((plan_data or {}).get("steps") or []),
        "currentStatus": "completed",
        "brief": "方案已全部执行完毕",
    }, ensure_ascii=False)}


async def _yield_final_summary_events(
    user_question: str,
    tool_call_records: list,
    full_response: str,
):
    """工具执行后流式输出最终结论（intro / 工具卡 / 结论 三段式）。"""
    from app.services.response_summarizer import (
        TOOLS_MARKER,
        needs_final_summary,
        stream_final_summary,
        build_rule_based_conclusion,
        enrich_tool_records_for_summary,
        is_network_speed_query,
        build_network_speed_conclusion,
        _network_speed_from_records,
        is_process_cpu_query,
        _processes_from_records,
        build_process_list_conclusion,
    )
    if not tool_call_records or not needs_final_summary(full_response, tool_call_records):
        return

    tool_call_records = enrich_tool_records_for_summary(user_question, tool_call_records)

    from app.services.response_summarizer import _user_requests_write_action, _write_action_satisfied
    from app.services.stream_events import response_phase, stream_token, PHASE_SUMMARY

    # 仅查了状态未执行关闭：规则总结，避免 LLM 幻觉「已成功关闭」
    if _user_requests_write_action(user_question) and not _write_action_satisfied(user_question, tool_call_records):
        yield response_phase(PHASE_SUMMARY, "正在生成执行结论…")
        yield {"event": "summary_start", "data": json.dumps({"title": "执行结论"})}
        if TOOLS_MARKER not in full_response:
            yield stream_token(TOOLS_MARKER, PHASE_SUMMARY)
        yield stream_token(build_rule_based_conclusion(user_question, tool_call_records), PHASE_SUMMARY)
        yield {"event": "summary_done", "data": json.dumps({})}
        return

    if is_process_cpu_query(user_question) and _processes_from_records(tool_call_records):
        yield response_phase(PHASE_SUMMARY, "正在生成执行结论…")
        yield {"event": "summary_start", "data": json.dumps({"title": "执行结论"})}
        if TOOLS_MARKER not in full_response:
            yield stream_token(TOOLS_MARKER, PHASE_SUMMARY)
        yield stream_token(build_process_list_conclusion(user_question, tool_call_records), PHASE_SUMMARY)
        yield {"event": "summary_done", "data": json.dumps({})}
        return

    if is_network_speed_query(user_question) and _network_speed_from_records(tool_call_records):
        yield response_phase(PHASE_SUMMARY, "正在生成执行结论…")
        yield {"event": "summary_start", "data": json.dumps({"title": "执行结论"})}
        if TOOLS_MARKER not in full_response:
            yield stream_token(TOOLS_MARKER, PHASE_SUMMARY)
        yield stream_token(build_network_speed_conclusion(user_question, tool_call_records), PHASE_SUMMARY)
        yield {"event": "summary_done", "data": json.dumps({})}
        return

    yield response_phase(PHASE_SUMMARY, "正在生成执行结论…")
    yield _sse_exploring("summary", "生成执行结论", "整理工具结果")
    yield {"event": "summary_start", "data": json.dumps({"title": "执行结论"})}

    if TOOLS_MARKER not in full_response:
        yield stream_token(TOOLS_MARKER, PHASE_SUMMARY)

    try:
        async for token in stream_final_summary(user_question, tool_call_records):
            yield stream_token(token, PHASE_SUMMARY)
    except Exception as e:
        logger.warning("final summary failed: %s", e)
        fallback = build_rule_based_conclusion(user_question, tool_call_records)
        yield stream_token(fallback, PHASE_SUMMARY)

    yield _sse_exploring("summary", "生成执行结论", "完成", "done")
    yield {"event": "summary_done", "data": json.dumps({})}


def get_tool_risk_level(name: str, args: dict = None) -> str:
    """获取工具调用的风险级别"""
    args = args or {}
    
    risk_map = {
        "get_system_info": "L1",
        "get_cpu_info": "L1",
        "get_memory_info": "L1",
        "get_disk_usage": "L1",
        "list_processes": "L1",
        "get_process_detail": "L1",
        "get_network_connections": "L1",
        "get_network_info": "L1",
        "get_network_interfaces": "L1",
        "get_network_speed": "L1",
        "search_journal_logs": "L1",
        "get_logs": "L1",
        "get_file_list": "L1",
        "read_file": "L1",
        "get_users": "L1",
        "get_groups": "L1",
        "get_service_status": "L1",
        "summarize_task": "L1",
        
        "kill_process": "L2",
        "manage_service": "L2",
    }

    if name == "execute_command":
        from app.core.command_security import analyze_command
        command = args.get("command", "")
        analysis = analyze_command(command)
        if analysis.get("success"):
            return analysis.get("risk_level", "L1")

    if name == "kill_process":
        signal = args.get("signal", "").upper()
        return "L4" if signal in ("KILL", "9") else "L2"

    if name == "manage_service":
        action = args.get("action", "").lower()
        return "L4" if action in ("stop", "restart", "reload") else "L2"

    global _ACTIVE_CUSTOM_REGISTRY
    if _ACTIVE_CUSTOM_REGISTRY and name in _ACTIVE_CUSTOM_REGISTRY.tools:
        return _ACTIVE_CUSTOM_REGISTRY.get_risk_level(name)

    return risk_map.get(name, "L2")


def _pre_state_for_write(
    tool_name: str, tool_args: dict, risk_level: str, server_id: str = None,
) -> dict | None:
    """L2-L4 写操作执行前采集检查点。"""
    from app.services.rollback_engine import ROLLBACK_ELIGIBLE_RISKS, is_write_tool, capture_pre_command_state
    if risk_level not in ROLLBACK_ELIGIBLE_RISKS or not is_write_tool(tool_name):
        return None
    if tool_name in ("execute_command", "run_command"):
        if not ((tool_args or {}).get("command") or (tool_args or {}).get("cmd")):
            return None
    try:
        return capture_pre_command_state(server_id)
    except Exception:
        return None


async def _record_blocked_injection_audit(
    db,
    *,
    trace_id: str,
    session_id: str,
    user_id: str,
    reason: str,
    severity: str = "high",
    stage: str = "prompt_injection",
    extra: dict = None,
) -> None:
    """入口安全闸门阻断时写入 blocked_injection 审计（供审计中心「安全拦截」Tab 展示）。"""
    try:
        from app.models.audit import AuditRecord
        payload = {
            "reason": reason,
            "severity": severity,
            "stage": stage,
            "flow_status": "blocked",
            **(extra or {}),
        }
        audit = AuditRecord(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            event_type="blocked_injection",
            summary=f"注入拦截 [{severity}]: {(reason or '')[:100]}",
            risk_level="L5",
            detail_json=json.dumps(payload, ensure_ascii=False, default=str),
        )
        db.add(audit)
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


async def _record_write_execution(
    db, session_id: str, trace_id: str, tool_name: str, tool_args: dict, result: dict, *,
    tool_call_id: str = None, risk_level: str = None, server_id: str = None, pre_state: dict = None,
) -> None:
    if not result.get("success"):
        return
    try:
        from app.services.human_supervision import record_execution_log
        await record_execution_log(
            db, session_id, trace_id, tool_name, tool_args, result,
            tool_call_id=tool_call_id,
            risk_level=risk_level or get_tool_risk_level(tool_name, tool_args),
            server_id=server_id,
            pre_state=pre_state,
        )
    except Exception:
        pass


# ============================================================
# 安全护栏 —— 工具调用前风险检查
# ============================================================
def _check_tool_safety(tool_name: str, tool_args: dict) -> dict:
    """
    检查工具调用的安全风险，返回:
      {safe, blocked, block_message, require_approval, require_confirm, risk_level}

    分级规则（严格按照产品规范）:
      L1 🟢: 安全操作，直接执行
      L2 🟡: 低风险，用户确认后执行
      L3 🟠: 中等风险，需管理员审批
      L4 🟠→🔴: 高风险，需管理员审批
      L5 🔴: 致命风险，需管理员审批/禁止
    """
    # 自定义工具 run() 仅在本地生成命令/手册，真实风险由后续 execute_command 评估
    if _is_registered_custom_tool(tool_name):
        return {
            "safe": True,
            "blocked": False,
            "block_message": None,
            "require_approval": False,
            "require_confirm": False,
            "risk_level": "L1",
        }

    risk = get_tool_risk_level(tool_name, tool_args)

    result = {
        "safe": True,
        "blocked": False,
        "block_message": None,
        "require_approval": False,
        "require_confirm": False,
        "risk_level": risk,
    }

    # execute_command 必须深入分析，不能因 get_tool_risk_level 返回 L1 而跳过
    if tool_name == "execute_command":
        command = tool_args.get("command", "")
        if not command.strip():
            result["safe"] = False
            result["blocked"] = True
            result["block_message"] = "空命令"
            return result

        analysis = analyze_command(command)

        if analysis.get("blocked"):
            result["safe"] = False
            result["blocked"] = True
            result["block_message"] = analysis.get("block_message", "此命令被安全策略阻止")
            result["risk_level"] = analysis.get("risk_level", risk)
            return result

        ar = analysis.get("risk_level", "L1")
        result["risk_level"] = ar

        # 仅 L4/L5 进管理员审批中心（与产品规则一致）
        if ar in ("L4", "L5") or (
            analysis.get("require_approval") and ar in ("L4", "L5")
        ):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = analysis.get("require_confirm", True)
            return result

        if ar in ("L2", "L3") or analysis.get("require_confirm"):
            result["safe"] = False
            result["require_confirm"] = True
            return result

        return result

    # L1: 只读，直接执行（非 execute_command）
    if risk == "L1":
        return result

    # kill_process: TERM=L2需确认, KILL=L4需审批
    if tool_name == "kill_process":
        signal = tool_args.get("signal", "").upper()
        if signal in ("KILL", "9"):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = True
            result["risk_level"] = "L4"
            return result
        result["safe"] = False
        result["require_confirm"] = True
        result["risk_level"] = "L2"
        return result

    # manage_service: start=L2; restart=L3确认; stop/reload=L4审批+用户执行确认
    if tool_name == "manage_service":
        action = tool_args.get("action", "").lower()
        if action == "restart":
            result["safe"] = False
            result["require_confirm"] = True
            result["risk_level"] = "L3"
            return result
        if action in ("stop", "reload"):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = True
            result["risk_level"] = "L4"
            return result
        result["safe"] = False
        result["require_confirm"] = True
        result["risk_level"] = "L2"
        return result

    # L2: 需确认
    if risk == "L2":
        result["safe"] = False
        result["require_confirm"] = True
        return result

    # L3: 中等风险，需管理员审批
    if risk == "L3":
        result["safe"] = False
        result["require_approval"] = True
        result["require_confirm"] = True
        return result

    # L4~L5: 必须管理员审批
    if risk in ("L4", "L5"):
        result["safe"] = False
        result["require_approval"] = True
        result["require_confirm"] = True
        return result

    return result


def _build_risk_description(tool_name: str, tool_args: dict, risk_level: str) -> str:
    """生成风险描述文本，用于审批单和用户展示"""
    desc_map = {
        "kill_process": f"终止进程 PID={tool_args.get('pid', '?')} (信号: {tool_args.get('signal', 'TERM')})",
        "manage_service": f"{tool_args.get('action', '?')} 服务 {tool_args.get('service_name', '?')}",
        "execute_command": f"执行命令: {tool_args.get('command', '?')}",
    }
    detail = desc_map.get(tool_name, f"调用工具 {tool_name}: {json.dumps(tool_args, ensure_ascii=False)}")

    risk_info = get_risk_level_info(risk_level)
    return f"{risk_info['color']} [{risk_level}] {detail}"


async def _save_pending_execution(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    tool_name: str,
    tool_args: dict,
    risk_level: str,
    messages_snapshot: list,
    need_approval: bool = False,
    need_confirm: bool = False,
    approval_id: str = None,
) -> PendingExecution:
    approval_ref = approval_id or ""
    pe = PendingExecution(
        session_id=session_id,
        trace_id=trace_id,
        user_id=user_id,
        approval_id=approval_ref,
        tool_name=tool_name,
        tool_params_json=json.dumps(tool_args, ensure_ascii=False),
        risk_level=risk_level,
        messages_snapshot_json=json.dumps(messages_snapshot, ensure_ascii=False),
        need_approval=need_approval,
        need_confirm=need_confirm,
        status="pending",
    )
    db.add(pe)
    await db.commit()
    await db.refresh(pe)
    return pe


def _plan_missing_services(records: list) -> set:
    """从已执行记录中收集未安装/未找到的 systemd 服务。"""
    missing = set()
    for rec in records or []:
        if rec.get("toolName") != "get_service_status" or rec.get("status") != "failed":
            continue
        data = (rec.get("result") or {}).get("data") or {}
        if (data.get("state") or "").lower() != "not-found":
            continue
        svc = (rec.get("params") or {}).get("service_name") or data.get("service")
        if svc:
            missing.add(str(svc))
    return missing


def _plan_skip_reason(step: dict, tool_name: str, tool_args: dict, records: list) -> Optional[str]:
    """前置服务缺失时跳过无意义的安装/重启步骤。"""
    missing = _plan_missing_services(records)
    if not missing:
        return None
    action = (step.get("action") or "").lower()
    if tool_name == "manage_service":
        svc = (tool_args or {}).get("service_name") or (tool_args or {}).get("service")
        if svc in missing:
            return f"{svc} 未安装，无法执行 {tool_args.get('action', '操作')}"
    if tool_name == "execute_command":
        cmd = ((tool_args or {}).get("command") or "").lower()
        if any(k in cmd for k in ("install", "restart", "systemctl")):
            if "cups" in missing and "cups" in cmd:
                return "CUPS 未安装，请先执行 dnf install -y cups 并启用服务"
            if "avahi" in missing and "avahi" in cmd:
                return "avahi-daemon 未安装，请先安装 avahi 服务"
            if missing & {"cups", "avahi-daemon"} and any(k in cmd for k in ("nss-mdns", "libnss", "mdns")):
                return "打印发现依赖服务未就绪，建议先安装 cups、avahi 与 nss-mdns"
    if missing & {"cups", "avahi-daemon"} and any(k in action for k in ("重启", "安装", "添加打印机", "验证修复")):
        if tool_name in ("manage_service", "execute_command"):
            return "前置打印服务未安装，跳过本步；请先安装 cups 与 avahi-daemon"
    return None


SERVICE_PACKAGE_MAP = {
    "gdm": "gdm",
    "gdm3": "gdm",
    "lightdm": "lightdm",
    "sddm": "sddm",
    "cups": "cups",
    "cupsd": "cups",
    "avahi-daemon": "avahi",
    "nginx": "nginx",
}

COMMAND_PACKAGE_MAP = {
    "ifconfig": "net-tools",
    "netstat": "net-tools",
    "semanage": "policycoreutils-python-utils",
    "gcc": "gcc",
    "make": "make",
    "curl": "curl",
    "wget": "wget",
}


def _failure_text(result: dict) -> str:
    data = (result or {}).get("data") or {}
    parts = [
        (result or {}).get("error"),
        (result or {}).get("display_summary"),
        data.get("summary"),
        data.get("stdout"),
        data.get("stderr"),
        data.get("raw"),
        data.get("raw_status"),
    ]
    return "\n".join(str(p) for p in parts if p)


def _package_install_command(packages: list[str]) -> str:
    pkg = " ".join(dict.fromkeys(p for p in packages if p))
    return (
        "if command -v dnf >/dev/null 2>&1; then dnf install -y {pkg}; "
        "elif command -v yum >/dev/null 2>&1; then yum install -y {pkg}; "
        "elif command -v apt-get >/dev/null 2>&1; then apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}; "
        "else echo '未找到 dnf/yum/apt-get，无法自动安装依赖包'; exit 127; fi"
    ).format(pkg=pkg)


def _extract_missing_service(tool_name: str, tool_args: dict, result: dict) -> Optional[str]:
    data = (result or {}).get("data") or {}
    svc = (
        (tool_args or {}).get("service_name")
        or (tool_args or {}).get("service")
        or data.get("service")
    )
    text = _failure_text(result).lower()
    if tool_name == "get_service_status" and (data.get("state") or "").lower() == "not-found":
        return str(svc) if svc else None
    if tool_name == "manage_service":
        if "not-found" in text or "not found" in text or "could not be found" in text or "未找到" in text or "未安装" in text:
            return str(svc) if svc else None
    m = re.search(r"unit\s+([a-zA-Z0-9_.@-]+)\.service\s+(?:not\s+found|could\s+not\s+be\s+found)", text)
    return m.group(1) if m else None


def _extract_missing_command(result: dict) -> Optional[str]:
    text = _failure_text(result)
    patterns = (
        r"([a-zA-Z0-9_.+-]+):\s*command not found",
        r"command not found:\s*([a-zA-Z0-9_.+-]+)",
        r"未找到命令[:：]?\s*([a-zA-Z0-9_.+-]+)",
    )
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1)
    return None


def _build_failure_remediation(tool_name: str, tool_args: dict, result: dict, step: dict, failed_record: dict = None) -> Optional[dict]:
    """将可补救的执行失败转换为一个待确认的修复命令。"""
    if (failed_record or {}).get("planSubStep") == "auto_remediation":
        return None
    original_cmd = str((tool_args or {}).get("command") or "")
    if re.search(r"\b(dnf|yum|apt-get)\s+(install|update)\b", original_cmd, re.I):
        return None

    service = _extract_missing_service(tool_name, tool_args, result)
    if service:
        pkg = SERVICE_PACKAGE_MAP.get(service.lower(), service)
        return {
            "toolName": "execute_command",
            "params": {"command": _package_install_command([pkg]), "timeout": 180},
            "reason": f"检测到服务 {service} 未找到或未安装",
            "action": f"补救：安装 {pkg} 依赖包",
            "expected": f"{pkg} 安装完成后，继续执行原方案后续步骤",
        }

    missing_cmd = _extract_missing_command(result)
    if missing_cmd:
        pkg = COMMAND_PACKAGE_MAP.get(missing_cmd.lower(), missing_cmd)
        return {
            "toolName": "execute_command",
            "params": {"command": _package_install_command([pkg]), "timeout": 180},
            "reason": f"检测到命令 {missing_cmd} 不存在，可能未安装对应工具",
            "action": f"补救：安装 {pkg} 工具包",
            "expected": f"{pkg} 安装完成后，继续执行原方案后续步骤",
        }

    text = _failure_text(result)
    m = re.search(r"(/home/([a-zA-Z_][a-zA-Z0-9_-]{0,31})/\.Xauthority)", text)
    if m and re.search(r"no such file or directory|没有那个文件|不存在|无法访问", text, re.I):
        path, username = m.group(1), m.group(2)
        home = f"/home/{username}"
        cmd = (
            f"id -u {username} >/dev/null 2>&1 && "
            f"install -d -m 700 -o {username} -g {username} {home} && "
            f"touch {path} && chown {username}:{username} {path} && chmod 600 {path}"
        )
        return {
            "toolName": "execute_command",
            "params": {"command": cmd, "timeout": 30},
            "reason": f"检测到 {path} 缺失",
            "action": f"补救：创建并修正 {username} 的 .Xauthority 权限",
            "expected": "文件存在且属主/权限正确后，继续执行原方案后续步骤",
        }

    return None


def _has_same_pending_remediation(records: list, command: str) -> bool:
    for rec in records or []:
        if rec.get("planSubStep") != "auto_remediation":
            continue
        rec_cmd = str((rec.get("params") or {}).get("command") or "")
        if rec_cmd == command and rec.get("status") in ("pending_confirm", "pending_approval", "executing", "completed"):
            return True
    return False


async def _queue_failure_remediation(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    step: dict,
    plan_data: dict,
    messages: list,
    state: dict,
    failed_tool_name: str,
    failed_tool_args: dict,
    failed_result: dict,
    failed_record: dict = None,
):
    remediation = _build_failure_remediation(
        failed_tool_name, failed_tool_args, failed_result, step, failed_record,
    )
    if not remediation:
        return

    tool_name = remediation["toolName"]
    tool_args = remediation["params"]
    command = str(tool_args.get("command") or "")
    if _has_same_pending_remediation(state.get("records") or [], command):
        return

    step_order = step.get("order") or (failed_record or {}).get("planStepOrder") or 0
    step_total = len((plan_data or {}).get("steps") or []) or (failed_record or {}).get("planStepTotal")
    action = remediation.get("action") or "补救：执行依赖修复命令"
    tool_call_id = generate_id()

    safety = _apply_plan_step_safety(_check_tool_safety(tool_name, tool_args), {"risk": "L2"})
    yield {"event": "safety_decision", "data": json.dumps({
        "toolName": tool_name,
        "riskLevel": safety["risk_level"],
        "blocked": safety["blocked"],
        "requireConfirm": safety["require_confirm"],
        "requireApproval": safety["require_approval"],
        "remediation": True,
    }, ensure_ascii=False)}

    record_base = {
        "id": tool_call_id,
        "toolName": tool_name,
        "params": tool_args,
        "riskLevel": safety["risk_level"],
        "planStepOrder": step_order,
        "planStepTotal": step_total,
        "planStepAction": action,
        "planSubStep": "auto_remediation",
        "remediationReason": remediation.get("reason"),
        "remediationFor": (failed_record or {}).get("id"),
        "commandPreview": preview_tool_command(tool_name, tool_args),
    }

    if safety["blocked"]:
        state["records"].append({
            **record_base,
            "status": "blocked",
            "result": {"success": False, "error": safety["block_message"]},
        })
        return

    message = (
        f"Ops Diagnosis Planner 检测到：{remediation.get('reason')}。\n"
        f"建议先执行补救命令：{action}。\n"
        f"预期结果：{remediation.get('expected')}。\n"
        "请确认是否执行；确认完成后系统会继续原方案的后续步骤。"
    )

    if safety["require_approval"]:
        now = datetime.utcnow()
        approval = Approval(
            trace_id=trace_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_params_json=json.dumps(tool_args, ensure_ascii=False),
            risk_level=safety["risk_level"],
            detail=message,
            requested_by=user_id,
            expires_at=now + timedelta(seconds=settings.approval_timeout),
        )
        db.add(approval)
        await db.commit()
        await db.refresh(approval)
        pe = await _save_pending_execution(
            db, session_id, trace_id, user_id,
            tool_name, tool_args, safety["risk_level"],
            messages_snapshot=_append_planned_resume_snapshot(messages, plan_data, state, step_order),
            need_approval=True,
            need_confirm=bool(safety.get("require_confirm")),
            approval_id=approval.id,
        )
        record = {
            **record_base,
            "status": "pending_approval",
            "approvalId": approval.id,
            "pendingExecutionId": pe.id,
        }
        state["records"].append(record)
        state["early_status"] = "awaiting_user_action"
        state["approval_id"] = approval.id
        yield {"event": "tool_call", "data": json.dumps(record, ensure_ascii=False)}
        yield {"event": "need_approval", "data": json.dumps({
            **record,
            "message": message + f"\n请在审批管理页面确认（{settings.approval_timeout}秒超时）。",
        }, ensure_ascii=False)}
        yield _sse_exploring(f"remediate-{tool_call_id}", action, remediation.get("reason", ""), "done")
        return

    pe = await _save_pending_execution(
        db, session_id, trace_id, user_id,
        tool_name, tool_args, safety["risk_level"],
        messages_snapshot=_append_planned_resume_snapshot(messages, plan_data, state, step_order),
        need_confirm=True,
    )
    record = {
        **record_base,
        "status": "pending_confirm",
        "pendingExecutionId": pe.id,
    }
    state["records"].append(record)
    state["early_status"] = "awaiting_user_action"
    yield {"event": "tool_call", "data": json.dumps(record, ensure_ascii=False)}
    yield {"event": "need_confirm", "data": json.dumps({
        **record,
        "message": message,
        "status": "pending_confirm",
    }, ensure_ascii=False)}
    yield _sse_exploring(f"remediate-{tool_call_id}", action, remediation.get("reason", ""), "done")
    return


PASSWORD_CUSTOM_TOOLS = frozenset({
    "check_ssh_connectivity",
    "check_console_access_available",
    "get_user_account_info",
    "check_account_lock_status",
    "get_password_policy",
    "reset_user_password",
    "verify_account_after_reset",
    "get_password_recovery_playbook",
})


def _is_registered_custom_tool(name: str) -> bool:
    global _ACTIVE_CUSTOM_REGISTRY
    if _ACTIVE_CUSTOM_REGISTRY and name in _ACTIVE_CUSTOM_REGISTRY.tools:
        return True
    return name in PASSWORD_CUSTOM_TOOLS


def _extract_password_recovery_context(plan_data: dict) -> dict:
    """从用户诉求中提取密码找回相关参数。"""
    text = " ".join(
        filter(None, [
            plan_data.get("phenomenon"),
            plan_data.get("query_goal"),
        ])
    )
    ctx: dict = {}
    skip_words = {"密码", "忘记", "找回", "重置", "修改", "用户", "账户", "账号", "login", "password", "root", "admin"}
    for pat in (
        r"用户\s*[`'\"]?([a-zA-Z_][a-zA-Z0-9_-]{0,31})[`'\"]?",
        r"[`'\"]?([a-zA-Z_][a-zA-Z0-9_-]{0,31})[`'\"]?\s*(?:用户|账户|账号)",
        r"(?:账户|账号)\s*[`'\"]?([a-zA-Z_][a-zA-Z0-9_-]{0,31})[`'\"]?",
        r"(?:user|account)\s+[`'\"]?([a-zA-Z_][a-zA-Z0-9_-]{0,31})[`'\"]?",
    ):
        m = re.search(pat, text, re.I)
        if m:
            u = m.group(1)
            if u.lower() not in skip_words:
                ctx["username"] = u
                break
    low = text.lower()
    if re.search(r"\broot\b", low) or "root" in text:
        ctx.setdefault("username", "root")
    ctx.setdefault("username", "root")
    return ctx


def _generate_temp_password(username: str = "") -> str:
    import secrets
    suffix = secrets.token_urlsafe(4).replace("-", "")[:6]
    return f"Kylin@{suffix}!1"


def _build_custom_tool_args(tool_name: str, step: dict, plan_data: dict) -> dict:
    """为自定义工具构造 run() 参数。"""
    pw = _extract_password_recovery_context(plan_data or {})
    username = pw.get("username", "root")
    args: dict = {}

    if tool_name in {
        "get_user_account_info",
        "check_account_lock_status",
        "get_password_policy",
        "verify_account_after_reset",
        "get_password_recovery_playbook",
        "reset_user_password",
    }:
        args["username"] = username

    if tool_name == "check_ssh_connectivity":
        args["ssh_user"] = "root"
    elif tool_name == "check_console_access_available":
        args["has_console"] = True
        args["console_type"] = "vmware"
    elif tool_name == "reset_user_password":
        args["new_password"] = _generate_temp_password(username)
        args["dry_run"] = False
    elif tool_name == "get_password_recovery_playbook":
        args["system_type"] = "desktop"
        args["recovery_mode"] = "auto"

    return args


def _custom_tool_remote_commands(result: dict) -> List[str]:
    data = (result or {}).get("data") or {}
    commands: List[str] = []
    for item in data.get("commands") or []:
        if isinstance(item, dict):
            cmd = (item.get("command") or "").strip()
        else:
            cmd = str(item).strip()
        if cmd:
            commands.append(cmd)
    return commands


def _parse_plan_step_to_tool(step: dict, plan_data: dict = None) -> Optional[tuple]:
    """将诊断方案步骤解析为 (tool_name, tool_args)。必须与 tool_hint / action 语义一致。"""
    hint = (step.get("tool_hint") or "").strip()
    if not hint or hint in ("env_precheck", "按意图选择工具", "summary") or step.get("virtual"):
        return None

    action = (step.get("action") or "").lower()

    # 复合 hint：按步骤 action 语义选择工具，避免总是命中第一个 get_service_status
    if re.search(r"\s/\s", hint):
        parts = [p.strip() for p in re.split(r"\s*/\s*", hint) if p.strip()]
        prefer_logs = any(k in action for k in ("日志", "log", "error_log", "journal", "定位"))
        prefer_svc = any(k in action for k in ("服务", "状态", "运行", "cups", "avahi", "nginx"))
        ordered = list(parts)
        if prefer_logs:
            ordered.sort(key=lambda p: 0 if re.search(r"log|journal", p, re.I) else 1)
        elif prefer_svc:
            ordered.sort(key=lambda p: 0 if "service_status" in p.lower() else 1)
        for part in ordered:
            parsed = _parse_plan_step_to_tool({**step, "tool_hint": part})
            if parsed:
                return parsed
        return None

    if hint.startswith("execute_command:"):
        cmd = hint.split(":", 1)[1].strip()
        if re.search(r"tail\s+(-\d+\s+)?(/var/log/cups/error_log|cups/error_log)", cmd, re.I):
            ml = re.search(r"tail\s+-(\d+)", cmd)
            lines = min(int(ml.group(1)), 500) if ml else 50
            return ("get_logs", {"path": "/var/log/cups/error_log", "service": "cups", "lines": lines})
        return ("execute_command", {"command": cmd})
    if hint.startswith("execute_command "):
        cmd = hint[len("execute_command"):].strip()
        if re.search(r"tail\s+(-\d+\s+)?(/var/log/cups/error_log|cups/error_log)", cmd, re.I):
            ml = re.search(r"tail\s+-(\d+)", cmd)
            lines = min(int(ml.group(1)), 500) if ml else 50
            return ("get_logs", {"path": "/var/log/cups/error_log", "service": "cups", "lines": lines})
        return ("execute_command", {"command": cmd})

    if hint.lower().startswith("read_file"):
        path = hint.split(":", 1)[1].strip() if ":" in hint else hint.split(None, 1)[-1].strip()
        return ("read_file", {"file_path": path})

    if hint.lower().startswith("get_logs") or re.match(r"^get_logs\s", hint, re.I):
        rest = re.sub(r"^get_logs\s*:?\s*", "", hint, flags=re.I).strip()
        lines = 50
        ml = re.search(r"lines[=:]?\s*(\d+)", hint, re.I)
        if ml:
            lines = min(int(ml.group(1)), 500)
        if rest and not rest.lower().startswith("lines"):
            target = rest.split()[0]
            if target.startswith("/") or ".log" in target:
                return ("get_logs", {"path": target, "lines": lines})
            return ("get_logs", {"service": target, "lines": lines})
        if re.search(r"cups|cupsd", action):
            return ("get_logs", {"path": "/var/log/cups/error_log", "service": "cups", "lines": lines})
        if re.search(r"nginx", action):
            return ("get_logs", {"path": "/var/log/nginx/error.log", "service": "nginx", "lines": lines})
        return ("get_logs", {"service": "cups", "lines": lines})

    if "search_journal_logs" in hint.lower():
        query = "error"
        mq = re.search(r"query[=:]?\s*(\S+)", hint, re.I)
        if mq:
            query = mq.group(1)
        return ("search_journal_logs", {"query": query, "lines": 50})

    parsed_svc = _parse_get_service_status_hint(hint, step)
    if parsed_svc:
        return parsed_svc

    if hint.startswith("list_processes"):
        sort_by = "mem" if ":mem" in hint.lower() else "cpu"
        top_n = 10
        m = re.search(r"top[_ ]?n[=:]?\s*(\d+)", hint, re.I)
        if m:
            top_n = min(int(m.group(1)), 50)
        return ("list_processes", {"sort_by": sort_by, "top_n": top_n})
    if "get_system_info" in hint:
        return ("get_system_info", {})
    if "get_cpu_info" in hint:
        return ("get_cpu_info", {})
    if "get_memory_info" in hint:
        return ("get_memory_info", {})
    if "get_network_connections" in hint:
        return ("get_network_connections", {})
    if "get_network_speed" in hint:
        args = {"interval": 1.0}
        m = re.search(r"interval[=:]?\s*([\d.]+)", hint, re.I)
        if m:
            args["interval"] = float(m.group(1))
        return ("get_network_speed", args)
    if "get_network_interfaces" in hint:
        return ("get_network_interfaces", {})
    if "get_network_info" in hint:
        return ("get_network_info", {})
    if "get_disk_usage" in hint:
        return ("get_disk_usage", {})
    if "get_users" in hint:
        return ("get_users", {})
    if "get_groups" in hint:
        return ("get_groups", {})

    if "manage_service" in hint.lower() or hint.startswith("systemctl"):
        h = hint
        if ":" in h and "manage_service" in h.lower():
            h = h.split(":", 1)[1].strip()
        h = re.sub(r"^manage_service\s*", "", h, flags=re.I).strip()
        h = h.replace("systemctl", "").strip()
        parts = h.split()
        if len(parts) >= 2:
            if parts[0] in ("start", "stop", "restart", "status", "enable", "disable"):
                return ("manage_service", {"action": parts[0], "service_name": parts[1]})
            if parts[1] in ("start", "stop", "restart", "status", "enable", "disable"):
                return ("manage_service", {"action": parts[1], "service_name": parts[0]})

    hint_name = hint.split()[0].strip("`'\"")
    if _is_registered_custom_tool(hint_name):
        return (hint_name, _build_custom_tool_args(hint_name, step, plan_data or {}))

    return None


def _infer_service_name_from_step(step: dict, hint: str = "") -> Optional[str]:
    """从 step.service_name / action / tool_hint 推断 systemd 服务名。"""
    if step.get("service_name"):
        return str(step["service_name"]).strip()
    text = f"{step.get('action', '')} {hint}"
    patterns = [
        (r"\bcupsd?\b", "cups"),
        (r"avahi", "avahi-daemon"),
        (r"chronyd|chrony", "chronyd"),
        (r"\bnginx\b", "nginx"),
        (r"\bdocker\b", "docker"),
        (r"postgresql|postgres", "postgresql"),
        (r"mysql|mysqld", "mysqld"),
        (r"\bsshd\b", "sshd"),
        (r"firewalld", "firewalld"),
    ]
    for pat, svc in patterns:
        if re.search(pat, text, re.I):
            return svc
    return None


def _parse_get_service_status_hint(hint: str, step: dict) -> Optional[tuple]:
    if "get_service_status" not in hint.lower():
        return None
    m = re.search(r"get_service_status\s*[:\s]+([a-zA-Z0-9_.@-]+)", hint, re.I)
    if m:
        return ("get_service_status", {"service_name": m.group(1).strip("`'\",")})
    svc = _infer_service_name_from_step(step, hint)
    if svc:
        return ("get_service_status", {"service_name": svc})
    return None


PLANNED_RESUME_MARKER = "__PLANNED_RESUME__"


def _append_planned_resume_snapshot(messages: list, plan_data: dict, state: dict, pause_at_order: int) -> list:
    snap = [
        m for m in messages
        if not (
            m.get("role") == "system"
            and isinstance(m.get("content"), str)
            and m["content"].startswith(PLANNED_RESUME_MARKER)
        )
    ]
    snap.append({
        "role": "system",
        "content": PLANNED_RESUME_MARKER + json.dumps({
            "plan_data": plan_data,
            "records": list(state.get("records") or []),
            "pause_at_order": pause_at_order,
        }, ensure_ascii=False),
    })
    return snap


def _parse_planned_resume_snapshot(messages: list) -> Optional[dict]:
    """取最后一条方案快照（多次暂停时以最新为准）。"""
    found = None
    for m in messages or []:
        c = m.get("content") if isinstance(m, dict) else None
        if isinstance(c, str) and c.startswith(PLANNED_RESUME_MARKER):
            try:
                found = json.loads(c[len(PLANNED_RESUME_MARKER):])
            except Exception:
                continue
    return found


def _record_matches_plan_tool(rec: dict, tool_name: str, tool_args: dict) -> bool:
    """判断工具记录是否对应方案某一步（planStepOrder 缺失时用于推断进度）。"""
    if not rec:
        return False
    if rec.get("toolName") != tool_name:
        return False
    rec_params = rec.get("params") or {}
    if tool_name in ("execute_command", "run_command"):
        cmd = (tool_args.get("command") or "").strip()
        rec_cmd = (rec_params.get("command") or "").strip()
        if cmd and rec_cmd:
            return cmd == rec_cmd or cmd in rec_cmd or rec_cmd in cmd
    return rec_params == tool_args


def _infer_done_plan_orders(plan_data: dict, tool_call_records: list) -> set:
    """从工具记录推断已完成的方案步骤序号。"""
    terminal = {"completed", "failed", "blocked", "rejected", "skipped"}
    done: set = set()
    steps = (plan_data or {}).get("steps") or []
    all_orders = {int(s.get("order", 0)) for s in steps if s.get("order")}

    for order in all_orders:
        step_recs = [
            r for r in (tool_call_records or [])
            if r.get("planStepOrder") is not None and int(r["planStepOrder"]) == order
        ]
        if not step_recs:
            continue
        if any(r.get("status") in ("pending_approval", "pending_confirm", "executing") for r in step_recs):
            continue
        if any(r.get("status") in terminal for r in step_recs):
            done.add(order)
            continue
        for step in steps:
            if int(step.get("order", 0)) != order:
                continue
            parsed = _parse_plan_step_to_tool(step, plan_data)
            if parsed and any(
                _record_matches_plan_tool(r, parsed[0], parsed[1]) and r.get("status") in terminal
                for r in step_recs
            ):
                done.add(order)
                break
    return done


def _plan_resume_start_after_order(planned_ctx: dict, tool_call_records: list) -> int:
    pause_at = int((planned_ctx or {}).get("pause_at_order") or 0)
    plan_data = (planned_ctx or {}).get("plan_data") or {}
    done_orders = _infer_done_plan_orders(plan_data, tool_call_records)
    if done_orders:
        return max(max(done_orders), pause_at)
    return pause_at


async def _load_tool_call_records_for_trace(
    db: AsyncSession, session_id: str, trace_id: str,
) -> list:
    row_result = await db.execute(
        select(Message).where(
            Message.session_id == session_id,
            Message.role == "tool_call",
            Message.trace_id == trace_id,
        ).order_by(desc(Message.created_at)).limit(1)
    )
    row = row_result.scalar_one_or_none()
    if not row or not row.tool_calls_json:
        return []
    try:
        return json.loads(row.tool_calls_json)
    except Exception:
        return []


def _risk_rank(level: str) -> int:
    return {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}.get(str(level or "L1").upper(), 0)


def _max_risk_level(*levels: str) -> str:
    best = "L1"
    for lv in levels:
        if _risk_rank(lv) > _risk_rank(best):
            best = str(lv).upper()
    return best


def _apply_plan_step_safety(safety: dict, step: dict) -> dict:
    """合并方案步骤 risk 与命令安全分析：只升不降，禁止 L1 标签绕过 L4 审批。"""
    hint = (step.get("risk") or "L1").upper()
    tool_hint = (step.get("tool_hint") or "").lower()
    if safety.get("blocked"):
        return safety
    # 旧方案可能将 journal 收缩标为 L3；统一为 L2 对话内确认，避免审批中心空挂
    if "journalctl" in tool_hint and "vacuum" in tool_hint:
        return {
            **safety,
            "safe": False,
            "require_approval": False,
            "require_confirm": True,
            "risk_level": "L2",
        }

    cmd_risk = safety.get("risk_level") or "L1"
    merged_risk = _max_risk_level(hint, cmd_risk)
    # 管理员审批：仅 L4/L5（L2/L3 对话内确认）
    require_approval = bool(
        safety.get("require_approval") and merged_risk in ("L4", "L5")
        or merged_risk in ("L4", "L5")
        or hint in ("L4", "L5")
    )
    require_confirm = bool(
        safety.get("require_confirm")
        or require_approval
        or merged_risk in ("L2", "L3", "L4", "L5")
        or hint in ("L2", "L3", "L4", "L5")
    )

    if merged_risk == "L2" and not require_approval:
        require_confirm = True

    if merged_risk == "L1" and not require_approval and not require_confirm:
        return {
            **safety,
            "safe": True,
            "require_approval": False,
            "require_confirm": False,
            "risk_level": "L1",
        }

    out = {
        **safety,
        "safe": False,
        "risk_level": merged_risk,
        "require_approval": require_approval,
        "require_confirm": require_confirm,
    }
    if merged_risk in ("L4", "L5"):
        out["require_approval"] = True
        out["require_confirm"] = True
    return out


def _merge_tool_records(existing: list, incoming: list) -> list:
    by_key: dict = {}
    order_list: list = []
    terminal = {"completed", "failed", "blocked", "rejected", "skipped"}
    priority = {s: i for i, s in enumerate(["pending_confirm", "pending_approval", "executing", "failed", "blocked", "completed", "rejected"])}
    for rec in (existing or []) + (incoming or []):
        key = rec.get("planStepOrder") or rec.get("id") or rec.get("pendingExecutionId")
        if key not in by_key:
            order_list.append(key)
            by_key[key] = rec
            continue
        prev = by_key[key]
        prev_p = priority.get(prev.get("status", ""), -1)
        new_p = priority.get(rec.get("status", ""), -1)
        if rec.get("status") in terminal and prev.get("status") not in terminal:
            by_key[key] = {**prev, **rec}
        elif new_p >= prev_p:
            by_key[key] = {**prev, **rec}
    return [by_key[k] for k in order_list]


async def _load_all_tool_call_records_for_session(db: AsyncSession, session_id: str) -> list:
    """合并会话内全部 tool_call 消息中的工具记录（避免 trace 不一致导致丢步）。"""
    result = await db.execute(
        select(Message).where(
            Message.session_id == session_id,
            Message.role == "tool_call",
            Message.tool_calls_json.isnot(None),
        ).order_by(Message.created_at)
    )
    merged: list = []
    for row in result.scalars().all():
        try:
            merged = _merge_tool_records(merged, json.loads(row.tool_calls_json))
        except Exception:
            continue
    return merged


def _plan_has_pending_actions(tool_call_records: list) -> bool:
    return any(
        r.get("status") in ("pending_approval", "pending_confirm", "executing")
        for r in (tool_call_records or [])
    )


def _plan_has_remaining_steps(planned_ctx: dict) -> bool:
    plan_data = (planned_ctx or {}).get("plan_data") or {}
    steps = plan_data.get("steps") or []
    if not steps:
        return False
    records = (planned_ctx or {}).get("records") or []
    if _plan_has_pending_actions(records):
        return True
    done_orders = _infer_done_plan_orders(plan_data, records)
    for step in steps:
        order = int(step.get("order", 0))
        if order not in done_orders:
            return True
    return False


def _filter_actionable_pending_records(tool_call_records: list) -> list:
    """去掉同一步骤已有终态记录时残留的 pending 快照。"""
    terminal = {"completed", "failed", "blocked", "rejected", "skipped"}
    done_orders = {
        int(r["planStepOrder"]) for r in (tool_call_records or [])
        if r.get("planStepOrder") is not None and r.get("status") in terminal
    }
    pending = []
    for tc in tool_call_records or []:
        if tc.get("status") not in ("pending_confirm", "pending_approval"):
            continue
        # 待管理员审批必须保留，不能被同步骤的「规划类 completed」误过滤
        if tc.get("status") == "pending_approval":
            pending.append(tc)
            continue
        step = tc.get("planStepOrder")
        if step is not None and int(step) in done_orders:
            continue
        pending.append(tc)
    return pending


async def _maybe_auto_queue_time_sync_confirm(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    user_question: str,
    tool_call_records: list,
    messages: Optional[list] = None,
) -> Optional[dict]:
    """时间同步诉求：只读检查完成后自动推送对时命令确认，避免只查不同步就结束。"""
    from app.services.ops_scope import is_time_sync_execution_request
    from app.services.response_summarizer import (
        _time_sync_action_satisfied,
        _is_time_sync_tool,
    )

    if not is_time_sync_execution_request(user_question):
        return None
    if _time_sync_action_satisfied(user_question, tool_call_records):
        return None

    for tc in tool_call_records or []:
        if tc.get("status") != "pending_confirm":
            continue
        cmd = str((tc.get("params") or {}).get("command") or "").lower()
        if any(k in cmd for k in ("makestep", "set-ntp", "set-time", "ntpdate")):
            return None

    read_done = any(
        tc.get("status") == "completed" and _is_time_sync_tool(tc)
        for tc in (tool_call_records or [])
    )
    if not read_done:
        return None

    tool_name = "execute_command"
    tool_args = {"command": "chronyc -a makestep", "timeout": 30}
    safety = _check_tool_safety(tool_name, tool_args)
    if safety.get("blocked"):
        return None

    tool_call_id = generate_id()
    risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
    pe = await _save_pending_execution(
        db, session_id, trace_id, user_id,
        tool_name, tool_args, safety["risk_level"],
        messages_snapshot=messages or [],
        need_confirm=True,
    )
    record = {
        "id": tool_call_id,
        "toolName": tool_name,
        "params": tool_args,
        "riskLevel": safety["risk_level"],
        "status": "pending_confirm",
        "pendingExecutionId": pe.id,
        "commandPreview": preview_tool_command(tool_name, tool_args),
    }
    return {
        "record": record,
        "pendingExecutionId": pe.id,
        "message": (
            f"{risk_desc}\n"
            "检查显示系统时间尚未与 NTP/主机对齐，请确认执行强制对时。"
        ),
    }


def _is_journal_vacuum_record(rec: dict) -> bool:
    cmd = ((rec.get("params") or {}).get("command") or "").lower()
    hint = (rec.get("planStepAction") or "").lower()
    return ("journalctl" in cmd and "vacuum" in cmd) or ("journal" in hint and "日志" in hint)


async def _normalize_journal_step_pending_records(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    plan_data: dict,
    tool_call_records: list,
    messages: Optional[list] = None,
) -> list:
    """旧方案 journal 步骤若误标 L3 待审批，转为 L2 待确认以便对话内继续。"""
    if not tool_call_records:
        return tool_call_records
    normalized: list = []
    changed = False
    for rec in tool_call_records:
        r = dict(rec)
        if r.get("status") == "pending_approval" and _is_journal_vacuum_record(r):
            apv_id = r.get("approvalId")
            if apv_id:
                apv_result = await db.execute(select(Approval).where(Approval.id == apv_id))
                apv = apv_result.scalar_one_or_none()
                if apv and apv.status == "pending":
                    apv.status = "cancelled"
                    changed = True
            pe = await _save_pending_execution(
                db, session_id, trace_id, user_id,
                r.get("toolName", "execute_command"),
                r.get("params") or {},
                "L2",
                messages_snapshot=messages or [],
                need_confirm=True,
            )
            r["status"] = "pending_confirm"
            r["riskLevel"] = "L2"
            r["pendingExecutionId"] = pe.id
            r.pop("approvalId", None)
            changed = True
        normalized.append(r)
    if changed:
        await db.commit()
    return normalized


async def _resolve_planned_ctx(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    messages: Optional[list] = None,
    extra_records: Optional[list] = None,
) -> Optional[dict]:
    planned_ctx = _parse_planned_resume_snapshot(messages or []) if messages else None
    db_records = await _load_all_tool_call_records_for_session(db, session_id)
    if not db_records and trace_id:
        db_records = await _load_tool_call_records_for_trace(db, session_id, trace_id)
    merged_records = _merge_tool_records(db_records, extra_records or [])
    if planned_ctx and merged_records:
        planned_ctx["records"] = _merge_tool_records(planned_ctx.get("records") or [], merged_records)
    if not planned_ctx or not planned_ctx.get("plan_data"):
        fb = await _fallback_planned_ctx(db, session_id, trace_id, merged_records)
        if fb:
            planned_ctx = fb
    elif merged_records and not planned_ctx.get("records"):
        planned_ctx["records"] = merged_records
    return planned_ctx


async def _fallback_planned_ctx(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    tool_call_records: list,
) -> Optional[dict]:
    """快照缺失时从已确认的监督方案恢复执行上下文。"""
    try:
        from app.models.supervision import SupervisionPlan
        row_result = await db.execute(
            select(SupervisionPlan).where(
                SupervisionPlan.session_id == session_id,
                SupervisionPlan.status == "confirmed",
            ).order_by(desc(SupervisionPlan.confirmed_at)).limit(1)
        )
        row = row_result.scalar_one_or_none()
        if not row:
            return None
        plan_data = json.loads(row.plan_json) if row.plan_json else {}
        if not plan_data.get("steps"):
            return None
        records = tool_call_records or await _load_all_tool_call_records_for_session(db, session_id)
        pause_at = _plan_resume_start_after_order({"pause_at_order": 0}, records)
        return {
            "plan_data": plan_data,
            "records": records,
            "pause_at_order": pause_at,
            "intent": row.intent,
        }
    except Exception:
        return None


async def _stream_plan_execute_command_for_step(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    step: dict,
    plan_data: dict,
    messages: list,
    state: dict,
    command: str,
    steps_total: int,
    server_id: str = None,
):
    """在方案步骤下执行单条远程命令（含审批/确认流程）。"""
    tool_name = "execute_command"
    tool_args = {"command": command}
    tool_call_id = generate_id()
    step_order = step.get("order", 0)

    safety = _apply_plan_step_safety(_check_tool_safety(tool_name, tool_args), step)
    yield {"event": "safety_decision", "data": json.dumps({
        "toolName": tool_name,
        "riskLevel": safety["risk_level"],
        "blocked": safety["blocked"],
        "requireConfirm": safety["require_confirm"],
        "requireApproval": safety["require_approval"],
    }, ensure_ascii=False)}

    if safety["blocked"]:
        state["records"].append({
            "id": tool_call_id, "toolName": tool_name, "params": tool_args,
            "riskLevel": safety["risk_level"], "status": "blocked",
            "result": {"success": False, "error": safety["block_message"]},
            "planStepOrder": step_order,
            "planStepTotal": steps_total,
            "planStepAction": step.get("action", ""),
        })
        return

    if safety["require_approval"]:
        risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
        now = datetime.utcnow()
        approval = Approval(
            trace_id=trace_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_params_json=json.dumps(tool_args, ensure_ascii=False),
            risk_level=safety["risk_level"],
            detail=risk_desc,
            requested_by=user_id,
            expires_at=now + timedelta(seconds=settings.approval_timeout),
        )
        db.add(approval)
        await db.commit()
        await db.refresh(approval)
        pe = await _save_pending_execution(
            db, session_id, trace_id, user_id,
            tool_name, tool_args, safety["risk_level"],
            messages_snapshot=_append_planned_resume_snapshot(
                messages, plan_data, state, step_order,
            ),
            need_approval=True,
            need_confirm=bool(safety.get("require_confirm")),
            approval_id=approval.id,
        )
        yield {"event": "need_approval", "data": json.dumps({
            "id": tool_call_id,
            "toolName": tool_name,
            "params": tool_args,
            "riskLevel": safety["risk_level"],
            "approvalId": approval.id,
            "pendingExecutionId": pe.id,
            "message": f"{risk_desc}\n请在审批管理页面确认（{settings.approval_timeout}秒超时）",
            "status": "pending_approval",
            "commandPreview": preview_tool_command(tool_name, tool_args),
            "planStepOrder": step_order,
            "planStepTotal": steps_total,
            "planStepAction": step.get("action", ""),
        }, ensure_ascii=False)}
        state["records"].append({
            "id": tool_call_id, "toolName": tool_name, "params": tool_args,
            "riskLevel": safety["risk_level"], "status": "pending_approval",
            "approvalId": approval.id,
            "pendingExecutionId": pe.id,
            "planStepOrder": step_order,
            "planStepTotal": steps_total,
            "planStepAction": step.get("action", ""),
        })
        state["early_status"] = "awaiting_user_action"
        state["approval_id"] = approval.id
        yield {"event": "tool_call", "data": json.dumps({
            "id": tool_call_id,
            "toolName": tool_name,
            "params": tool_args,
            "riskLevel": safety["risk_level"],
            "status": "pending_approval",
            "approvalId": approval.id,
            "pendingExecutionId": pe.id,
            "commandPreview": preview_tool_command(tool_name, tool_args),
            "planStepOrder": step_order,
            "planStepTotal": steps_total,
            "planStepAction": step.get("action", ""),
        }, ensure_ascii=False)}
        return

    if safety["require_confirm"]:
        risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
        pe = await _save_pending_execution(
            db, session_id, trace_id, user_id,
            tool_name, tool_args, safety["risk_level"],
            messages_snapshot=_append_planned_resume_snapshot(
                messages, plan_data, state, step_order,
            ),
            need_confirm=True,
        )
        yield {"event": "tool_call", "data": json.dumps({
            "id": tool_call_id,
            "toolName": tool_name,
            "params": tool_args,
            "riskLevel": safety["risk_level"],
            "status": "pending_confirm",
            "pendingExecutionId": pe.id,
            "commandPreview": preview_tool_command(tool_name, tool_args),
            "planStepOrder": step_order,
            "planStepTotal": steps_total,
            "planStepAction": step.get("action", ""),
        }, ensure_ascii=False)}
        yield {"event": "need_confirm", "data": json.dumps({
            "id": tool_call_id,
            "toolName": tool_name,
            "params": tool_args,
            "riskLevel": safety["risk_level"],
            "pendingExecutionId": pe.id,
            "message": f"{risk_desc}\n请在下方确认后执行。",
            "status": "pending_confirm",
            "commandPreview": preview_tool_command(tool_name, tool_args),
            "planStepOrder": step_order,
            "planStepTotal": steps_total,
        }, ensure_ascii=False)}
        state["records"].append({
            "id": tool_call_id, "toolName": tool_name, "params": tool_args,
            "riskLevel": safety["risk_level"], "status": "pending_confirm",
            "pendingExecutionId": pe.id,
            "planStepOrder": step_order,
            "planStepTotal": steps_total,
            "planStepAction": step.get("action", ""),
        })
        state["early_status"] = "awaiting_user_action"
        return

    yield {"event": "tool_call", "data": json.dumps({
        "id": tool_call_id,
        "toolName": tool_name,
        "params": tool_args,
        "riskLevel": safety["risk_level"],
        "status": "executing",
        "commandPreview": preview_tool_command(tool_name, tool_args),
        "planStepOrder": step_order,
        "planStepTotal": steps_total,
        "planStepAction": step.get("action", ""),
    }, ensure_ascii=False)}
    pre_state = _pre_state_for_write(tool_name, tool_args, safety["risk_level"], server_id)
    cmd_result = execute_tool(tool_name, tool_args)
    if cmd_result.get("success"):
        await _record_write_execution(
            db, session_id, trace_id, tool_name, tool_args, cmd_result,
            tool_call_id=tool_call_id,
            risk_level=safety["risk_level"],
            server_id=server_id,
            pre_state=pre_state,
        )
    rec_status = _plan_step_result_status(tool_name, cmd_result, step)
    yield {"event": "tool_result", "data": json.dumps({
        "id": tool_call_id,
        "toolName": tool_name,
        "status": rec_status,
        "result": cmd_result,
        "displaySummary": cmd_result.get("display_summary", ""),
    }, ensure_ascii=False)}
    failed_record = {
        "id": tool_call_id, "toolName": tool_name, "params": tool_args,
        "riskLevel": safety["risk_level"], "status": rec_status, "result": cmd_result,
        "displaySummary": cmd_result.get("display_summary", ""),
        "planStepOrder": step_order,
        "planStepTotal": steps_total,
        "planStepAction": step.get("action", ""),
    }
    state["records"].append(failed_record)
    if rec_status == "failed":
        async for ev in _queue_failure_remediation(
            db, session_id, trace_id, user_id, step, plan_data, messages, state,
            tool_name, tool_args, cmd_result, failed_record,
        ):
            yield ev


async def _stream_custom_tool_plan_step(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    step: dict,
    plan_data: dict,
    messages: list,
    state: dict,
    tool_name: str,
    tool_args: dict,
    tool_call_id: str,
    steps_total: int,
    server_id: str = None,
):
    """自定义工具：本地 run() 生成方案，远程命令单独走 execute_command 审批链。"""
    step_order = step.get("order", 0)
    yield {"event": "tool_call", "data": json.dumps({
        "id": tool_call_id,
        "toolName": tool_name,
        "params": tool_args,
        "riskLevel": "L1",
        "status": "executing",
        "commandPreview": preview_tool_command(tool_name, tool_args),
        "planStepOrder": step_order,
        "planStepTotal": steps_total,
        "planStepAction": step.get("action", ""),
    }, ensure_ascii=False)}
    result = execute_tool(tool_name, tool_args)
    rec_status = _plan_step_result_status(tool_name, result, step)
    remote_cmds = _custom_tool_remote_commands(result) if result.get("success") else []
    # 本地规划类 run() 不算步骤终态，避免待审批的远程命令被误判为已完成
    local_status = "planning" if remote_cmds else rec_status
    yield {"event": "tool_result", "data": json.dumps({
        "id": tool_call_id,
        "toolName": tool_name,
        "status": local_status,
        "result": result,
        "displaySummary": result.get("display_summary", ""),
    }, ensure_ascii=False)}
    state["records"].append({
        "id": tool_call_id, "toolName": tool_name, "params": tool_args,
        "riskLevel": "L1", "status": local_status, "result": result,
        "displaySummary": result.get("display_summary", ""),
        "planStepOrder": step_order if not remote_cmds else None,
        "planStepTotal": steps_total,
        "planStepAction": step.get("action", ""),
        "planSubStep": "custom_tool_planning" if remote_cmds else None,
    })

    if not result.get("success"):
        yield _sse_exploring(
            f"plan-{tool_call_id}", f"步骤 {step_order} 失败", tool_name, "error",
        )
        return

    if remote_cmds:
        for cmd in remote_cmds:
            async for ev in _stream_plan_execute_command_for_step(
                db, session_id, trace_id, user_id, step, plan_data, messages, state,
                cmd, steps_total, server_id=server_id,
            ):
                yield ev
            if state.get("early_status"):
                return

    yield _sse_exploring(
        f"plan-{tool_call_id}", f"步骤 {step_order} 完成", tool_name,
        "done" if rec_status == "completed" else "error",
    )


async def _stream_planned_diagnostic_execution(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    plan_data: dict,
    messages: list,
    state: dict,
    start_after_order: int = 0,
    server_id: str = None,
):
    """按方案步骤确定性执行工具（不依赖 LLM function calling）。"""
    from app.services.stream_events import response_phase, PHASE_EXECUTE
    from app.services.custom_tool_registry import load_custom_tool_registry

    global _ACTIVE_CUSTOM_REGISTRY
    if not _ACTIVE_CUSTOM_REGISTRY:
        set_active_custom_registry(await load_custom_tool_registry(db))

    steps = plan_data.get("steps") or []
    yield response_phase(PHASE_EXECUTE, "按诊断方案逐步执行工具…")
    yield _sse_exploring("route", "任务路由", "按方案逐步执行", "done")

    for step in sorted(steps, key=lambda s: s.get("order", 0)):
        if step.get("order", 0) <= start_after_order:
            continue
        parsed = _parse_plan_step_to_tool(step, plan_data)
        if not parsed:
            continue
        tool_name, tool_args = parsed
        tool_call_id = generate_id()
        skip_reason = _plan_skip_reason(step, tool_name, tool_args, state.get("records") or [])
        if skip_reason:
            yield _sse_exploring(
                f"plan-{tool_call_id}", f"方案步骤 {step.get('order')}",
                skip_reason, "done",
            )
            state["records"].append({
                "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                "riskLevel": step.get("risk", "L1"), "status": "skipped",
                "result": {"success": False, "error": skip_reason},
                "planStepOrder": step.get("order", 0),
                "planStepTotal": len(steps),
                "planStepAction": step.get("action", ""),
            })
            continue
        yield _sse_exploring(f"plan-{tool_call_id}", f"方案步骤 {step.get('order')}", tool_name, "running")

        if _is_registered_custom_tool(tool_name):
            async for ev in _stream_custom_tool_plan_step(
                db, session_id, trace_id, user_id, step, plan_data, messages, state,
                tool_name, tool_args, tool_call_id, len(steps), server_id=server_id,
            ):
                yield ev
            if state.get("early_status"):
                return
            continue

        safety = _apply_plan_step_safety(_check_tool_safety(tool_name, tool_args), step)
        yield {"event": "safety_decision", "data": json.dumps({
            "toolName": tool_name,
            "riskLevel": safety["risk_level"],
            "blocked": safety["blocked"],
            "requireConfirm": safety["require_confirm"],
            "requireApproval": safety["require_approval"],
        }, ensure_ascii=False)}

        if safety["blocked"]:
            yield _sse_exploring(
                f"plan-{tool_call_id}", f"方案步骤 {step.get('order')}",
                tool_name, "error",
            )
            yield {"event": "blocked", "data": json.dumps({
                "id": tool_call_id,
                "toolName": tool_name,
                "params": tool_args,
                "riskLevel": safety["risk_level"],
                "message": safety["block_message"],
                "status": "blocked",
            })}
            state["records"].append({
                "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                "riskLevel": safety["risk_level"], "status": "blocked",
                "result": {"success": False, "error": safety["block_message"]},
            })
            continue

        if safety["require_approval"]:
            risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
            now = datetime.utcnow()
            approval = Approval(
                trace_id=trace_id,
                session_id=session_id,
                tool_name=tool_name,
                tool_params_json=json.dumps(tool_args, ensure_ascii=False),
                risk_level=safety["risk_level"],
                detail=risk_desc,
                requested_by=user_id,
                expires_at=now + timedelta(seconds=settings.approval_timeout),
            )
            db.add(approval)
            await db.commit()
            await db.refresh(approval)
            pe = await _save_pending_execution(
                db, session_id, trace_id, user_id,
                tool_name, tool_args, safety["risk_level"],
                messages_snapshot=_append_planned_resume_snapshot(
                    messages, plan_data, state, step.get("order", 0),
                ),
                need_approval=True,
                need_confirm=bool(safety.get("require_confirm")),
                approval_id=approval.id,
            )
            step_order = step.get("order", 0)
            step_total = len(steps)
            yield {"event": "need_approval", "data": json.dumps({
                "id": tool_call_id,
                "toolName": tool_name,
                "params": tool_args,
                "riskLevel": safety["risk_level"],
                "approvalId": approval.id,
                "pendingExecutionId": pe.id,
                "message": f"{risk_desc}\n请在审批管理页面确认（{settings.approval_timeout}秒超时）",
                "status": "pending_approval",
                "commandPreview": preview_tool_command(tool_name, tool_args),
                "planStepOrder": step_order,
                "planStepTotal": step_total,
                "planStepAction": step.get("action", ""),
            }, ensure_ascii=False)}
            state["records"].append({
                "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                "riskLevel": safety["risk_level"], "status": "pending_approval",
                "approvalId": approval.id,
                "pendingExecutionId": pe.id,
                "planStepOrder": step_order,
                "planStepTotal": step_total,
                "planStepAction": step.get("action", ""),
            })
            state["early_status"] = "awaiting_user_action"
            state["approval_id"] = approval.id
            yield {"event": "tool_call", "data": json.dumps({
                "id": tool_call_id,
                "toolName": tool_name,
                "params": tool_args,
                "riskLevel": safety["risk_level"],
                "status": "pending_approval",
                "approvalId": approval.id,
                "pendingExecutionId": pe.id,
                "commandPreview": preview_tool_command(tool_name, tool_args),
                "planStepOrder": step_order,
                "planStepTotal": step_total,
                "planStepAction": step.get("action", ""),
            }, ensure_ascii=False)}
            yield _sse_exploring(
                f"plan-{tool_call_id}", f"方案步骤 {step.get('order')}",
                "待管理员审批", "done",
            )
            return

        if safety["require_confirm"]:
            risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
            pe = await _save_pending_execution(
                db, session_id, trace_id, user_id,
                tool_name, tool_args, safety["risk_level"],
                messages_snapshot=_append_planned_resume_snapshot(
                    messages, plan_data, state, step.get("order", 0),
                ),
                need_confirm=True,
            )
            step_order = step.get("order", 0)
            step_total = len(steps)
            yield {"event": "tool_call", "data": json.dumps({
                "id": tool_call_id,
                "toolName": tool_name,
                "params": tool_args,
                "riskLevel": safety["risk_level"],
                "status": "pending_confirm",
                "pendingExecutionId": pe.id,
                "commandPreview": preview_tool_command(tool_name, tool_args),
                "planStepOrder": step_order,
                "planStepTotal": step_total,
                "planStepAction": step.get("action", ""),
            }, ensure_ascii=False)}
            yield {"event": "need_confirm", "data": json.dumps({
                "id": tool_call_id,
                "toolName": tool_name,
                "params": tool_args,
                "riskLevel": safety["risk_level"],
                "pendingExecutionId": pe.id,
                "message": f"{risk_desc}\n请在下方确认后执行。",
                "status": "pending_confirm",
                "commandPreview": preview_tool_command(tool_name, tool_args),
                "planStepOrder": step_order,
                "planStepTotal": step_total,
            }, ensure_ascii=False)}
            state["records"].append({
                "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                "riskLevel": safety["risk_level"], "status": "pending_confirm",
                "pendingExecutionId": pe.id,
                "planStepOrder": step_order,
                "planStepTotal": step_total,
                "planStepAction": step.get("action", ""),
            })
            state["early_status"] = "awaiting_user_action"
            yield _sse_exploring(
                f"plan-{tool_call_id}", f"方案步骤 {step.get('order')}",
                "待您确认后执行", "done",
            )
            return

        yield {"event": "tool_call", "data": json.dumps({
            "id": tool_call_id,
            "toolName": tool_name,
            "params": tool_args,
            "riskLevel": safety["risk_level"],
            "status": "executing",
            "commandPreview": preview_tool_command(tool_name, tool_args),
            "planStepOrder": step.get("order", 0),
            "planStepTotal": len(steps),
            "planStepAction": step.get("action", ""),
        })}
        pre_state = _pre_state_for_write(tool_name, tool_args, safety["risk_level"], server_id)
        result = execute_tool(tool_name, tool_args)
        if result.get("success"):
            await _record_write_execution(
                db, session_id, trace_id, tool_name, tool_args, result,
                tool_call_id=tool_call_id,
                risk_level=safety["risk_level"],
                server_id=server_id,
                pre_state=pre_state,
            )
        rec_status = _plan_step_result_status(tool_name, result, step)
        yield {"event": "tool_result", "data": json.dumps({
            "id": tool_call_id,
            "toolName": tool_name,
            "status": rec_status,
            "result": result,
            "displaySummary": result.get("display_summary", ""),
        }, ensure_ascii=False)}
        failed_record = {
            "id": tool_call_id, "toolName": tool_name, "params": tool_args,
            "riskLevel": safety["risk_level"], "status": rec_status, "result": result,
            "displaySummary": result.get("display_summary", ""),
            "planStepOrder": step.get("order", 0),
            "planStepTotal": len(steps),
            "planStepAction": step.get("action", ""),
        }
        state["records"].append(failed_record)
        if rec_status == "failed":
            async for ev in _queue_failure_remediation(
                db, session_id, trace_id, user_id, step, plan_data, messages, state,
                tool_name, tool_args, result, failed_record,
            ):
                yield ev
            if state.get("early_status"):
                return

        yield _sse_exploring(
            f"plan-{tool_call_id}", f"步骤 {step.get('order')} 完成", tool_name,
            "done" if rec_status == "completed" else "error",
        )

    from app.services.human_supervision import _is_virtual_plan_step

    terminal = {"completed", "failed", "blocked", "rejected", "skipped"}
    actionable = [s for s in steps if _parse_plan_step_to_tool(s, plan_data)]
    actionable_done = actionable and all(
        any(
            r.get("planStepOrder") == s.get("order") and r.get("status") in terminal
            for r in state["records"]
        )
        for s in actionable
    )
    if actionable_done:
        for step in steps:
            if not _is_virtual_plan_step(step):
                continue
            order = step.get("order", 0)
            if any(r.get("planStepOrder") == order for r in state["records"]):
                continue
            state["records"].append({
                "id": generate_id(),
                "toolName": "plan_summary",
                "params": {},
                "riskLevel": "L1",
                "status": "completed",
                "planStepOrder": order,
                "planStepAction": step.get("action", ""),
                "result": {"success": True, "data": {"summary": "已由执行结论完成"}},
            })


def preview_tool_command(tool_name: str, tool_args: dict) -> str:
    """生成将在虚拟机上执行的命令预览，供前端确认对话框展示。"""
    args = tool_args or {}
    if _is_registered_custom_tool(tool_name):
        summary = args.get("summary") or tool_name
        if tool_name == "reset_user_password":
            user = args.get("username") or "?"
            return f"passwd/chpasswd 重置用户 {user} 的密码"
        return f"自定义工具 {tool_name}: {summary}"
    if tool_name in ("execute_command", "run_command") and args.get("command"):
        return args["command"]
    if tool_name == "manage_service":
        return "systemctl {} {}".format(
            args.get("action", "?"),
            args.get("service_name") or args.get("service") or "?",
        )
    if tool_name == "kill_process":
        return "kill -{} {}".format(args.get("signal", "TERM"), args.get("pid", "?"))
    return json.dumps(args, ensure_ascii=False, indent=2)


async def _repair_stale_tool_calls_in_session(db: AsyncSession, session_id: str) -> None:
    """修复 tool_call 与 PendingExecution / 方案进度不一致的状态，并合并为单条快照。"""
    from sqlalchemy import delete as sql_delete

    result = await db.execute(
        select(Message).where(
            Message.session_id == session_id,
            Message.role == "tool_call",
            Message.tool_calls_json.isnot(None),
        )
    )
    rows = result.scalars().all()
    if not rows:
        return

    merged: list = []
    trace_id = None
    for row in rows:
        if row.trace_id:
            trace_id = row.trace_id
        try:
            merged = _merge_tool_records(merged, json.loads(row.tool_calls_json))
        except Exception:
            continue

    pe_ids: set = set()
    approval_ids: set = set()
    for tc in merged:
        if tc.get("status") == "pending_confirm" and tc.get("pendingExecutionId"):
            pe_ids.add(tc["pendingExecutionId"])
        if tc.get("status") == "pending_approval" and tc.get("approvalId"):
            approval_ids.add(tc["approvalId"])
        if tc.get("status") == "pending_approval" and tc.get("pendingExecutionId"):
            pe_ids.add(tc["pendingExecutionId"])

    pe_map = {}
    if pe_ids:
        pe_result = await db.execute(
            select(PendingExecution).where(PendingExecution.id.in_(pe_ids))
        )
        pe_map = {p.id: p for p in pe_result.scalars().all()}
    pe_by_approval = {}
    if approval_ids:
        apv_result = await db.execute(
            select(PendingExecution).where(PendingExecution.approval_id.in_(approval_ids))
        )
        pe_by_approval = {p.approval_id: p for p in apv_result.scalars().all()}

    fb = await _fallback_planned_ctx(db, session_id, trace_id or "", merged)
    plan_data = (fb or {}).get("plan_data") or {}
    steps = plan_data.get("steps") or []
    step_total = len(steps)

    terminal = {"completed", "failed", "blocked", "rejected", "skipped"}
    changed = False
    fixed: list = []
    for tc in merged:
        rec = dict(tc)
        pe_id = rec.get("pendingExecutionId")
        if rec.get("status") == "pending_confirm" and pe_id and pe_id in pe_map:
            pe = pe_map[pe_id]
            if pe.status == "resolved":
                rec["status"] = "completed"
                rec.pop("pendingExecutionId", None)
                changed = True
            elif pe.status in ("cancelled", "rejected"):
                rec["status"] = "rejected"
                rec.pop("pendingExecutionId", None)
                changed = True
            elif pe.status == "failed":
                pe.status = "pending"
                pe.resolved_at = None
                changed = True

        if rec.get("status") == "pending_approval":
            pe = None
            if pe_id and pe_id in pe_map:
                pe = pe_map[pe_id]
            elif rec.get("approvalId") and rec["approvalId"] in pe_by_approval:
                pe = pe_by_approval[rec["approvalId"]]
                if not rec.get("pendingExecutionId"):
                    rec["pendingExecutionId"] = pe.id
                    changed = True
            if pe:
                if pe.status == "resolved":
                    rec["status"] = "completed"
                    rec.pop("pendingExecutionId", None)
                    rec.pop("approvalId", None)
                    changed = True
                elif pe.status in ("cancelled", "rejected"):
                    rec["status"] = "rejected"
                    rec.pop("pendingExecutionId", None)
                    rec.pop("approvalId", None)
                    changed = True

        if not rec.get("planStepOrder") and steps:
            for step in steps:
                parsed = _parse_plan_step_to_tool(step)
                if parsed and _record_matches_plan_tool(rec, parsed[0], parsed[1]):
                    rec["planStepOrder"] = step.get("order")
                    rec["planStepTotal"] = step_total
                    rec["planStepAction"] = step.get("action", "")
                    changed = True
                    break
        fixed.append(rec)

    sess_row = await db.execute(select(Session).where(Session.id == session_id))
    sess = sess_row.scalar_one_or_none()
    user_id = getattr(sess, "user_id", None) or "system"
    if plan_data:
        journal_norm = await _normalize_journal_step_pending_records(
            db, session_id, trace_id or "", user_id, plan_data, fixed, [],
        )
        if journal_norm != fixed:
            fixed = journal_norm
            changed = True

    done_orders = _infer_done_plan_orders(plan_data, fixed) if plan_data else {
        int(r["planStepOrder"]) for r in fixed
        if r.get("planStepOrder") is not None and r.get("status") in terminal
    }
    normalized: list = []
    for rec in fixed:
        r = dict(rec)
        step = r.get("planStepOrder")
        if (
            r.get("status") in ("pending_confirm", "pending_approval")
            and step is not None
            and int(step) in done_orders
        ):
            r["status"] = "completed"
            r.pop("pendingExecutionId", None)
            r.pop("approvalId", None)
            changed = True
        normalized.append(r)

    if len(rows) > 1:
        changed = True

    if not changed:
        return

    canonical = rows[-1]
    canonical.tool_calls_json = json.dumps(normalized, ensure_ascii=False)
    if trace_id and not canonical.trace_id:
        canonical.trace_id = trace_id
    await db.execute(
        sql_delete(Message).where(
            Message.session_id == session_id,
            Message.role == "tool_call",
            Message.id != canonical.id,
        )
    )
    sess = await db.execute(select(Session).where(Session.id == session_id))
    s = sess.scalar_one_or_none()
    if s:
        s.updated_at = datetime.utcnow()
    await db.commit()


async def get_awaiting_run(db: AsyncSession, session_id: str) -> dict:
    """获取等待用户在对话页确认执行的挂起操作（L2 待确认 / L4 已批准待执行）。"""
    await _repair_stale_tool_calls_in_session(db, session_id)
    items = []

    confirm_result = await db.execute(
        select(PendingExecution).where(
            PendingExecution.session_id == session_id,
            PendingExecution.status == "pending",
            PendingExecution.need_confirm == True,
        ).order_by(desc(PendingExecution.created_at))
    )
    for pe in confirm_result.scalars().all():
        tool_args = {}
        if pe.tool_params_json:
            try:
                tool_args = json.loads(pe.tool_params_json)
            except Exception:
                pass
        items.append({
            "kind": "confirm",
            "pendingExecutionId": pe.id,
            "approvalId": None,
            "toolName": pe.tool_name,
            "toolParams": tool_args,
            "commandPreview": preview_tool_command(pe.tool_name, tool_args),
            "riskLevel": pe.risk_level,
            "traceId": pe.trace_id,
            "createdAt": pe.created_at.isoformat() if pe.created_at else "",
        })

    approved_result = await db.execute(
        select(PendingExecution).where(
            PendingExecution.session_id == session_id,
            PendingExecution.status == "approved",
            PendingExecution.need_approval == True,
        ).order_by(desc(PendingExecution.created_at))
    )
    for pe in approved_result.scalars().all():
        tool_args = {}
        if pe.tool_params_json:
            try:
                tool_args = json.loads(pe.tool_params_json)
            except Exception:
                pass
        items.append({
            "kind": "approved_run",
            "pendingExecutionId": pe.id,
            "approvalId": pe.approval_id,
            "toolName": pe.tool_name,
            "toolParams": tool_args,
            "commandPreview": preview_tool_command(pe.tool_name, tool_args),
            "riskLevel": pe.risk_level,
            "traceId": pe.trace_id,
            "createdAt": pe.created_at.isoformat() if pe.created_at else "",
        })
    return {"items": items, "total": len(items)}


async def get_pending_diagnostic_plan(db: AsyncSession, session_id: str) -> dict:
    """获取待确认的诊断方案。"""
    from app.services.human_supervision import get_pending_supervision_plan_for_session
    row = await get_pending_supervision_plan_for_session(db, session_id)
    return row or {}


async def cancel_awaiting_run(db: AsyncSession, session_id: str, approval_id: str = None,
                              pending_execution_id: str = None) -> bool:
    """用户跳过/取消已批准但未执行的操作。"""
    if approval_id:
        q = select(PendingExecution).where(
            PendingExecution.session_id == session_id,
            PendingExecution.approval_id == approval_id,
            PendingExecution.status == "approved",
        )
    elif pending_execution_id:
        q = select(PendingExecution).where(
            PendingExecution.id == pending_execution_id,
            PendingExecution.session_id == session_id,
            PendingExecution.status.in_(["pending", "approved"]),
        )
    else:
        return False
    result = await db.execute(q)
    pe = result.scalar_one_or_none()
    if not pe:
        return False
    pe.status = "cancelled"
    pe.resolved_at = datetime.utcnow()
    await db.commit()
    return True


# ============================================================
# 会话管理
# ============================================================
async def get_sessions(db: AsyncSession, user_id: str, page: int = 1, size: int = 20) -> dict:
    q = select(Session).where(Session.user_id == user_id).order_by(desc(Session.updated_at))
    total_result = await db.execute(select(func.count()).select_from(Session).where(Session.user_id == user_id))
    total = total_result.scalar() or 0
    rows_result = await db.execute(q.offset((page - 1) * size).limit(size))
    rows = rows_result.scalars().all()

    items = []
    for s in rows:
        msg_result = await db.execute(select(func.count()).select_from(Message).where(Message.session_id == s.id))
        msg_count = msg_result.scalar() or 0
        items.append({
            "id": s.id, "title": s.title,
            "createdAt": s.created_at.isoformat() if s.created_at else "",
            "updatedAt": s.updated_at.isoformat() if s.updated_at else "",
            "messageCount": msg_count,
        })
    return {"items": items, "total": total, "page": page, "size": size}


async def create_session(db: AsyncSession, user_id: str, title: str = "新会话") -> dict:
    s = Session(user_id=user_id, title=title)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": s.id, "title": s.title, "createdAt": s.created_at.isoformat() if s.created_at else ""}


async def delete_session(db: AsyncSession, session_id: str) -> None:
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Message).where(Message.session_id == session_id))
    await db.execute(sql_delete(Session).where(Session.id == session_id))
    await db.commit()


async def clear_session_messages(db: AsyncSession, session_id: str) -> None:
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Message).where(Message.session_id == session_id))
    await db.commit()


async def delete_message(db: AsyncSession, message_id: str) -> None:
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Message).where(Message.id == message_id))
    await db.commit()


async def get_messages(db: AsyncSession, session_id: str, page: int = 1, size: int = 50) -> dict:
    await _repair_stale_tool_calls_in_session(db, session_id)
    q = select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    total_result = await db.execute(select(func.count()).select_from(Message).where(Message.session_id == session_id))
    total = total_result.scalar() or 0
    rows_result = await db.execute(q.offset((page - 1) * size).limit(size))
    rows = rows_result.scalars().all()
    try:
        from app.services.image_store import list_message_attachments
        attachments_by_message = await list_message_attachments(db, [m.id for m in rows])
    except Exception:
        attachments_by_message = {}

    items = []
    for m in rows:
        tool_calls = None
        if m.tool_calls_json:
            try:
                tool_calls = json.loads(m.tool_calls_json)
            except Exception:
                pass
        items.append({
            "id": m.id, "role": m.role, "content": m.content or "",
            "toolCalls": tool_calls, "traceId": m.trace_id,
            "attachments": attachments_by_message.get(m.id, []),
            "createdAt": m.created_at.isoformat() if m.created_at else "",
        })
    return {"items": items, "total": total}


async def save_message(db: AsyncSession, session_id: str, role: str, content: str = "",
                       tool_calls: Optional[list] = None, trace_id: Optional[str] = None) -> str:
    msg = Message(
        session_id=session_id, role=role, content=content,
        tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
        trace_id=trace_id,
    )
    db.add(msg)
    result = await db.execute(select(Session).where(Session.id == session_id))
    s = result.scalar_one_or_none()
    if s:
        from datetime import datetime, timedelta
        s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)
    return msg.id


async def upsert_tool_call_message(
    db: AsyncSession,
    session_id: str,
    tool_calls: list,
    trace_id: Optional[str] = None,
) -> str:
    """会话内方案工具卡合并为单条消息，避免 trace 不一致导致重复 pending 快照。"""
    from sqlalchemy import delete as sql_delete

    existing = await _load_all_tool_call_records_for_session(db, session_id)
    merged = _merge_tool_records(existing, tool_calls or [])

    row_result = await db.execute(
        select(Message).where(
            Message.session_id == session_id,
            Message.role == "tool_call",
        ).order_by(desc(Message.created_at)).limit(1)
    )
    row = row_result.scalar_one_or_none()
    if row:
        row.tool_calls_json = json.dumps(merged, ensure_ascii=False)
        if trace_id:
            row.trace_id = trace_id
        await db.execute(
            sql_delete(Message).where(
                Message.session_id == session_id,
                Message.role == "tool_call",
                Message.id != row.id,
            )
        )
        sess = await db.execute(select(Session).where(Session.id == session_id))
        s = sess.scalar_one_or_none()
        if s:
            s.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return row.id
    return await save_message(
        db, session_id, "tool_call", "", tool_calls=merged, trace_id=trace_id,
    )


# ============================================================
# DeepSeek API 调用
# ============================================================
def prepare_messages_for_llm(messages: List[Dict]) -> List[Dict]:
    """如果 LLM 不支持 system 角色，将 system 消息合并到第一条 user 消息中。"""
    if settings.llm_system_role_support:
        return messages
    system_parts = []
    remaining = []
    for m in messages:
        if m["role"] == "system":
            system_parts.append(m["content"])
        else:
            remaining.append(m)
    if not system_parts:
        return remaining
    prefix = "\n\n".join(system_parts)
    if remaining and remaining[0]["role"] == "user":
        remaining[0] = dict(remaining[0], content=f"{prefix}\n\n---\n\n{remaining[0]['content']}")
    else:
        remaining.insert(0, {"role": "user", "content": prefix})
    return remaining


async def call_deepseek(
    messages: List[Dict],
    stream: bool = True,
    use_tools: bool = True,
    extra_tools: List[Dict] | None = None,
):
    """调用 DeepSeek API，带重试逻辑。use_tools=False 时仅文本总结，不触发 function calling。"""
    messages = prepare_messages_for_llm(messages)
    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "stream": stream,
    }
    if use_tools:
        merged_tools = list(TOOLS)
        existing = {t["function"]["name"] for t in merged_tools}
        for t in extra_tools or []:
            fn = (t.get("function") or {}).get("name")
            if fn and fn not in existing:
                merged_tools.append(t)
                existing.add(fn)
        payload["tools"] = merged_tools
        payload["tool_choice"] = "auto"

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if stream:
                    async with client.stream("POST", url, headers=headers, json=payload) as resp:
                        if resp.status_code >= 400:
                            body = await resp.aread()
                            last_error = Exception(f"DeepSeek HTTP {resp.status_code}: {body.decode()[:200]}")
                            if resp.status_code == 429:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            break
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    return
                                try:
                                    data = json.loads(data_str)
                                    yield data
                                except Exception:
                                    continue
                        return
                else:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    yield resp.json()
                    return
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:
                await asyncio.sleep(2 ** attempt)
                continue
            break
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5 ** attempt)
                continue
            break

    raise last_error or Exception("DeepSeek API call failed")


# ============================================================
# Agent 处理主流程 (ReAct 循环)
# ============================================================
async def process_message(
    db: AsyncSession,
    session_id: str,
    content: str,
    user_id: str,
    user_role: str = "user",
    confirm_plan_id: str = None,
    server_id: str = None,
):
    """Agent 主处理流程 - SSE 流式推送（人类监督分阶段）"""
    from app.services.human_supervision import validate_user_input, resolve_plan_resume_context

    if confirm_plan_id:
        pre = {"valid": True, "sanitized": content or "(resume)"}
    else:
        pre = validate_user_input(content)
        if not pre["valid"]:
            err_id = generate_id()
            yield {"event": "error", "data": json.dumps({"message": pre["message"], "code": pre["code"]})}
            yield {"event": "message_done", "data": json.dumps({
                "messageId": err_id, "traceId": "", "status": "validation_failed",
            })}
            return

    content = pre["sanitized"]
    trace_id = generate_trace_id()
    assistant_msg_id = generate_id()
    telemetry = TraceTelemetry(trace_id, session_id, user_id)

    from app.services.session_memory import get_memory
    memory = get_memory(session_id, user_id)
    memory.total_messages += 1

    if confirm_plan_id:
        plan_ctx = await resolve_plan_resume_context(db, confirm_plan_id, session_id)
        if not plan_ctx:
            yield {"event": "error", "data": json.dumps({"message": "诊断方案不存在或已失效，请重新发起请求"})}
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "plan_failed",
            })}
            return
        trace_id = plan_ctx["trace_id"] or trace_id
        await save_message(db, session_id, "user", "[确认执行方案]", trace_id=trace_id)
    else:
        await save_message(db, session_id, "user", content, trace_id=trace_id)

    try:
        async for event in _process_message_impl(
            db, session_id, content, user_id, trace_id, assistant_msg_id,
            telemetry, memory, user_role=user_role,
            confirm_plan_id=confirm_plan_id, server_id=server_id,
        ):
            yield event
    except Exception as e:
        logger.exception("process_message 致命异常: %s", str(e))
        telemetry.end_step("error", error=str(e)[:200])
        record_trace(telemetry)
        yield {"event": "token", "data": json.dumps({
            "token": "\n\n⚠ 系统处理异常，请重试。Trace: {}".format(trace_id),
        })}
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id, "traceId": trace_id,
            "status": "error", "error": str(e)[:200],
        })}
        try:
            await save_message(db, session_id, "assistant",
                "⚠ 系统处理异常，请重试。Trace: {}".format(trace_id), trace_id=trace_id)
        except Exception:
            pass


async def _process_message_impl(
    db: AsyncSession, session_id: str, content: str, user_id: str,
    trace_id: str, assistant_msg_id: str, telemetry, memory,
    user_role: str = "user",
    confirm_plan_id: str = None,
    server_id: str = None,
):
    """process_message 实现体，由外层 try/except 保护"""
    from app.services.response_summarizer import TOOLS_MARKER
    from app.services.stream_events import (
        intent_resolved, response_phase, stream_token,
        PHASE_PLAN, PHASE_ANSWER, PHASE_EXECUTE, PHASE_SUMMARY,
    )
    from app.services.ops_scope import (
        requires_react_tools, is_service_control_request, is_disk_cleanup_execution_request,
    )
    from app.services.human_supervision import (
        context_injection_recheck,
        build_diagnostic_plan,
        save_supervision_plan,
        confirm_supervision_plan,
        build_structured_ops_report,
        resolve_plan_resume_context,
        build_plan_execution_prompt,
    )

    plan_resume_ctx = None
    route_link = None
    if confirm_plan_id:
        plan_resume_ctx = await resolve_plan_resume_context(db, confirm_plan_id, session_id)
        if not plan_resume_ctx:
            yield {"event": "error", "data": json.dumps({"message": "诊断方案不存在或已失效"})}
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "plan_failed",
            })}
            return
        content = plan_resume_ctx["user_content"]
        trace_id = plan_resume_ctx["trace_id"] or trace_id
        from app.services.intent_classifier import get_intent_metadata
        intent_result = {
            "intent": plan_resume_ctx["intent"],
            "confidence": 0.99,
            "method": "plan_confirm_resume",
            "matched_keywords": [],
            "is_injection": False,
            "metadata": get_intent_metadata(plan_resume_ctx["intent"]),
        }
        intent = plan_resume_ctx["intent"]
        rag_context = (plan_resume_ctx.get("plan_data") or {}).get("rag_reference") or ""
        yield _sse_exploring("route", "恢复诊断方案执行", "环境预检通过", "done")
        yield {"event": "message_start", "data": json.dumps({"messageId": assistant_msg_id, "traceId": trace_id})}
        telemetry.start_step("plan_confirm_resume")
        confirmed = await confirm_supervision_plan(db, confirm_plan_id, session_id, server_id=server_id)
        if not confirmed:
            yield {"event": "error", "data": json.dumps({"message": "方案确认失败或环境检查未通过"})}
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "plan_failed",
            })}
            return
        yield {"event": "env_precheck", "data": json.dumps(confirmed["env"], ensure_ascii=False)}
        if not confirmed["ok"]:
            msg = "环境预检查未通过，请处理后重试。\n" + json.dumps(confirmed["env"], ensure_ascii=False)
            await save_message(db, session_id, "assistant", msg, trace_id=trace_id)
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "env_failed",
            })}
            return
        telemetry.end_step("ok")
        if confirmed.get("plan_data"):
            plan_resume_ctx["plan_data"] = confirmed["plan_data"]
        yield _sse_exploring("route", "任务路由", "方案已确认，开始执行", "done")
        # 直接进入 ReAct（跳过意图分类与 Handler）
        goto_react = True
    else:
        goto_react = False

    if not goto_react:
        yield _sse_exploring("sec", "安全预检", "正则 + LLM + 角色校验")
        telemetry.start_step("1_安全预检")
        from app.services.prompt_guard import security_gate
        security_result = await security_gate(content, use_llm=True, user_role=user_role)
        telemetry.end_step("ok", guard_pass=security_result["pass"])
        yield _sse_exploring("sec", "安全预检", "通过" if security_result["pass"] else "拦截", "done" if security_result["pass"] else "error")

        if not security_result["pass"]:
            yield {"event": "prompt_injection_detected", "data": json.dumps({
                "message": security_result["reason"],
                "severity": security_result["severity"],
                "blocked": True,
            })}
            await save_message(db, session_id, "assistant",
                f"⚠ {security_result['reason']}", trace_id=trace_id)
            await _record_blocked_injection_audit(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                reason=security_result.get("reason", ""),
                severity=security_result.get("severity", "high"),
                stage="security_gate",
                extra=security_result,
            )
            try:
                from app.services.workflow_audit import finalize_workflow_audit
                await finalize_workflow_audit(
                    db,
                    trace_id=trace_id,
                    session_id=session_id,
                    user_id=user_id,
                    question=content,
                    flow_status="blocked",
                    telemetry=telemetry,
                    extra_marks=[{
                        "stage": "prompt_injection",
                        "status": "blocked",
                        "detail": security_result.get("reason", ""),
                        "risk_level": "L5",
                        "meta": {"severity": security_result.get("severity")},
                    }],
                    related_event_types=["blocked_injection"],
                )
            except Exception:
                pass
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "blocked_injection"})}
            return

        content = security_result.get("sanitized_input", content)

    if not goto_react:
        # ── Step 2: 意图分类 ∥ RAG知识检索（并行执行）──
        yield _sse_exploring("intent", "意图识别与知识检索", "并行分析用户诉求")
        telemetry.start_step("2_意图分类+RAG检索(并行)")
        import asyncio
        from app.services.intent_classifier import classify as classify_async, IntentType as NewIntentType
        from app.services.knowledge_rag import knowledge_rag
        from app.models.knowledge import KnowledgeArticle

        if not knowledge_rag._initialized:
            try:
                result = await db.execute(select(KnowledgeArticle))
                articles = [{"id": a.id, "title": a.title, "content": a.content,
                             "category": a.category, "tags": a.tags}
                            for a in result.scalars().all()]
                if articles:
                    knowledge_rag.build_index(articles)
            except Exception:
                pass

        intent_task = asyncio.ensure_future(classify_async(content))

        rag_context = ""
        try:
            if knowledge_rag._initialized:
                rag_context = knowledge_rag.generate_context(content, top_k=3)
        except Exception:
            pass

        intent_result = await intent_task

        # 知识库已命中时不应再礼貌拒绝（RAG 与域外判定并行，需在此对齐）
        if rag_context and intent_result.get("out_of_scope"):
            from app.services.intent_classifier import get_intent_metadata
            intent_result["out_of_scope"] = False
            intent_result["intent"] = NewIntentType.KNOWLEDGE_QA.value
            intent_result["ops_scope"] = "in_scope"
            intent_result["ops_scope_reason"] = "知识库命中"
            intent_result["method"] = (intent_result.get("method") or "") + "+rag_override"
            intent_result["confidence"] = max(float(intent_result.get("confidence", 0.5)), 0.85)
            intent_result["metadata"] = get_intent_metadata(NewIntentType.KNOWLEDGE_QA.value)

        from app.services.agent_intent_context import build_intent_system_addon, get_response_mode

        response_mode = get_response_mode(intent_result["intent"])
        yield intent_resolved(intent_result, response_mode)
        yield {"event": "intent", "data": json.dumps({
            "intent": intent_result["intent"],
            "confidence": intent_result["confidence"],
            "matchedKeywords": intent_result.get("matched_keywords", [])[:5],
            "method": intent_result.get("method", "keyword"),
            "label": intent_result.get("metadata", {}).get("label", intent_result["intent"]),
            "responseMode": response_mode,
        })}
        yield response_phase("intent", intent_result.get("metadata", {}).get("label", "意图识别完成"))

        if rag_context:
            yield {"event": "rag_context", "data": json.dumps({
                "sources": [s["title"] for s in knowledge_rag.search(content, top_k=3)] if knowledge_rag._initialized else [],
            })}

        # ── 工具库检索：判断是否可走可执行方案（而非纯知识问答）──
        from app.services.tool_resolution_planner import evaluate_tool_resolution
        tool_resolution = await evaluate_tool_resolution(db, content, rag_context)
        intent_result["tool_resolution"] = tool_resolution
        if tool_resolution.get("actionable"):
            yield {"event": "tool_resolution", "data": json.dumps({
                "actionable": True,
                "workflow": tool_resolution.get("workflow"),
                "matchedTools": tool_resolution.get("matched_tools") or [],
                "reason": tool_resolution.get("reason"),
            }, ensure_ascii=False)}
            prev_intent = intent_result.get("intent")
            if prev_intent in (NewIntentType.KNOWLEDGE_QA.value, NewIntentType.GENERAL_QA.value):
                intent_result["intent"] = NewIntentType.FAULT_ANALYSIS.value
                intent_result["method"] = (intent_result.get("method") or "") + "+tool_resolution"
                intent_result["confidence"] = max(float(intent_result.get("confidence", 0.5)), 0.88)
                intent = intent_result["intent"]
                from app.services.intent_classifier import get_intent_metadata
                intent_result["metadata"] = get_intent_metadata(NewIntentType.FAULT_ANALYSIS.value)
                yield {"event": "intent", "data": json.dumps({
                    "intent": intent_result["intent"],
                    "confidence": intent_result["confidence"],
                    "method": intent_result.get("method"),
                    "label": intent_result.get("metadata", {}).get("label", intent),
                    "upgradedFrom": prev_intent,
                    "reason": tool_resolution.get("reason"),
                }, ensure_ascii=False)}

        telemetry.end_step("ok", intent=intent_result["intent"],
                           confidence=intent_result.get("confidence", 0),
                           rag_hit=bool(rag_context))
        yield _sse_exploring(
            "intent", "意图分类 + 知识库检索",
            f"intent={intent_result['intent']} confidence={intent_result.get('confidence', 0):.2f} rag={'hit' if rag_context else 'miss'}",
            "done",
        )

        telemetry.start_step("3_注入二次复核")
        recheck = context_injection_recheck(content, intent_result["intent"], rag_context)
        if not recheck["pass"]:
            telemetry.end_step("error", blocked=True)
            yield {"event": "prompt_injection_detected", "data": json.dumps({
                "message": recheck["reason"],
                "severity": recheck["severity"],
                "blocked": True,
            })}
            await save_message(db, session_id, "assistant", f"⚠ {recheck['reason']}", trace_id=trace_id)
            await _record_blocked_injection_audit(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                reason=recheck.get("reason", ""),
                severity=recheck.get("severity", "high"),
                stage="context_recheck",
                extra=recheck,
            )
            try:
                from app.services.workflow_audit import finalize_workflow_audit
                await finalize_workflow_audit(
                    db,
                    trace_id=trace_id,
                    session_id=session_id,
                    user_id=user_id,
                    question=content,
                    flow_status="blocked",
                    telemetry=telemetry,
                    intent_result=intent_result,
                    extra_marks=[{
                        "stage": "context_recheck",
                        "status": "blocked",
                        "detail": recheck.get("reason", ""),
                        "risk_level": "L5",
                        "meta": {"severity": recheck.get("severity")},
                    }],
                    related_event_types=["blocked_injection"],
                )
            except Exception:
                pass
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "blocked_injection"})}
            return

        telemetry.end_step("ok")
        if intent_result.get("is_injection"):
            telemetry.end_step("error", blocked=True, reason="injection_detected")
            record_trace(telemetry)
            yield {"event": "prompt_injection_detected", "data": json.dumps({
                "message": "检测到潜在的提示词注入行为",
                "severity": intent_result.get("injection_severity", "medium"),
                "blocked": True,
            })}
            await save_message(db, session_id, "assistant",
                "⚠ 检测到潜在的提示词注入行为，该请求已被安全系统拦截。", trace_id=trace_id)
            await _record_blocked_injection_audit(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                reason="意图分类检测到注入行为",
                severity=intent_result.get("injection_severity", "medium"),
                stage="intent_injection",
                extra={"intent": intent_result.get("intent"), "is_injection": True},
            )
            try:
                from app.services.workflow_audit import finalize_workflow_audit
                await finalize_workflow_audit(
                    db,
                    trace_id=trace_id,
                    session_id=session_id,
                    user_id=user_id,
                    question=content,
                    flow_status="blocked",
                    telemetry=telemetry,
                    intent_result=intent_result,
                    extra_marks=[{
                        "stage": "context_recheck",
                        "status": "blocked",
                        "detail": "意图分类检测到注入行为",
                        "risk_level": "L5",
                        "meta": {"severity": intent_result.get("injection_severity", "medium")},
                    }],
                    related_event_types=["blocked_injection"],
                )
            except Exception:
                pass
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "blocked_injection"})}
            return

        telemetry.end_step("ok", intent=intent_result["intent"])
        intent = intent_result["intent"]

        if intent in (IntentType.FAULT_ANALYSIS.value, IntentType.HIGH_RISK.value):
            yield _sse_exploring("plan_gen", "生成诊断方案", "正在构建执行步骤…")

        if intent == IntentType.HIGH_RISK.value:
            risk_msg = "您的请求涉及高风险操作，相关指令将需要审批后方可执行。"
            if is_service_control_request(content) and user_role not in ("admin", "operator"):
                risk_msg += " 系统将生成诊断方案；L4 服务启停需管理员审批，批准后由您确认执行。"
            yield {"event": "risk_notice", "data": json.dumps({
                "message": risk_msg,
                "intent": "high_risk",
            })}

        msg_count_result = await db.execute(
            select(func.count()).select_from(Message).where(Message.session_id == session_id)
        )
        if (msg_count_result.scalar() or 0) <= 1:
            title = content[:20] + ("..." if len(content) > 20 else "")
            result = await db.execute(select(Session).where(Session.id == session_id))
            s = result.scalar_one_or_none()
            if s:
                s.title = title
                await db.commit()

        yield {"event": "message_start", "data": json.dumps({"messageId": assistant_msg_id, "traceId": trace_id})}

        from app.services.agent.chains import dispatch_chain

        workflow = dispatch_chain(content, intent_result)
        route_link = workflow.get("link")
        yield {"event": "route_dispatch", "data": json.dumps({
            "link": workflow["link"],
            "linkLabel": workflow["link_label"],
            "linkDescription": workflow["link_description"],
            "reason": workflow["reason"],
            "intent": intent,
            "confidence": float(intent_result.get("confidence", 0)),
        }, ensure_ascii=False)}
        route_detail = workflow["link_label"] + " · " + workflow["reason"]
        yield _sse_exploring("route", "智能路由分发", route_detail, "done")
        telemetry.start_step("5_路由分发")
        telemetry.end_step("ok", link=workflow["link"])
        if requires_react_tools(content, intent_result):
            if intent in (IntentType.GENERAL_QA.value, IntentType.KNOWLEDGE_QA.value):
                intent = IntentType.HIGH_RISK.value if (
                    is_service_control_request(content) or is_disk_cleanup_execution_request(content)
                ) else IntentType.OPS_QUERY.value
                intent_result["intent"] = intent
                intent_result["method"] = (intent_result.get("method") or "") + "+react_guard"
                intent_result["confidence"] = max(float(intent_result.get("confidence", 0.5)), 0.88)

        if intent in (IntentType.GENERAL_QA.value, IntentType.KNOWLEDGE_QA.value):
            history = await get_messages(db, session_id)
            chat_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in history["items"] if m["role"] in ("user", "assistant")
            ]
            phase_msg = "正在检索知识库并组织回答…" if intent == IntentType.KNOWLEDGE_QA.value else "正在生成回答…"
            yield response_phase("answer", phase_msg)
            from app.services.task_router import dispatch
            async for event in dispatch(
                db, session_id, content, user_id, chat_messages,
                intent_result=intent_result, trace_id=trace_id,
                assistant_msg_id=assistant_msg_id, rag_context=rag_context,
                telemetry=telemetry,
            ):
                yield event
            return

        if rag_context is None:
            rag_context = ""
        if intent in (IntentType.KNOWLEDGE_QA.value, IntentType.FAULT_ANALYSIS.value, IntentType.HIGH_RISK.value):
            try:
                from app.services.human_supervision import _build_fault_rag_query, _is_fault_like_content
                if not knowledge_rag._initialized:
                    result = await db.execute(select(KnowledgeArticle))
                    articles = []
                    for a in result.scalars().all():
                        articles.append({"id": a.id, "title": a.title, "content": a.content,
                            "category": a.category, "tags": a.tags})
                    knowledge_rag.build_index(articles)
                if knowledge_rag._initialized:
                    rag_query = (
                        _build_fault_rag_query(content)
                        if intent in (IntentType.FAULT_ANALYSIS.value, IntentType.HIGH_RISK.value)
                        and _is_fault_like_content(content)
                        else content
                    )
                    top_k = 5 if intent == IntentType.FAULT_ANALYSIS.value else 3
                    rag_context = knowledge_rag.generate_context(rag_query, top_k=top_k)
                    if rag_context:
                        yield {"event": "rag_context", "data": json.dumps({
                            "sources": [s["title"] for s in knowledge_rag.search(rag_query, top_k=top_k)],
                        })}
            except Exception as e:
                logger.warning(f"RAG delayed init failed: {e}")

        use_plan_execute = workflow.get("use_diagnostic_plan", False)
        if use_plan_execute:
            from app.services.human_supervision import enrich_diagnostic_plan_with_env, iter_diagnostic_plan_stream

            yield response_phase(PHASE_PLAN, "正在生成诊断与执行方案…")
            plan = None
            async for evt in iter_diagnostic_plan_stream(
                content, intent, rag_context,
                tool_resolution=intent_result.get("tool_resolution"),
            ):
                evt_type = evt.get("type")
                if evt_type == "start":
                    yield {"event": "diagnostic_plan_start", "data": json.dumps({
                        "traceId": trace_id,
                        "title": evt.get("title"),
                        "phenomenon": evt.get("phenomenon"),
                        "intent": evt.get("intent"),
                    }, ensure_ascii=False)}
                elif evt_type == "delta":
                    yield {"event": "diagnostic_plan_delta", "data": json.dumps(
                        {k: v for k, v in evt.items() if k != "type"},
                        ensure_ascii=False,
                    )}
                elif evt_type == "final":
                    plan = evt.get("plan")

            if not plan:
                plan = await build_diagnostic_plan(
                    content, intent, rag_context,
                    tool_resolution=intent_result.get("tool_resolution"),
                )

            plan = await enrich_diagnostic_plan_with_env(
                plan, content, rag_context,
                sensing_mode=workflow.get("env_sensing_mode") or "fault_diagnosis",
                server_id=server_id,
            )
            if plan.get("preliminary_analysis"):
                yield {"event": "diagnostic_plan_delta", "data": json.dumps({
                    "field": "preliminary_analysis",
                    "value": plan["preliminary_analysis"],
                }, ensure_ascii=False)}
            if plan.get("environment_scan"):
                yield {"event": "diagnostic_plan_delta", "data": json.dumps({
                    "field": "environment_scan",
                    "value": plan["environment_scan"],
                }, ensure_ascii=False)}
            whitelist = plan.get("file_protection_whitelist") or []
            if whitelist:
                yield {"event": "diagnostic_plan_delta", "data": json.dumps({
                    "field": "file_protection",
                    "value": whitelist[:8],
                    "count": len(whitelist),
                }, ensure_ascii=False)}

            sp = await save_supervision_plan(db, session_id, trace_id, user_id, intent, plan)
            yield _sse_exploring("plan_gen", "深度环境感知 + 方案生成", "Plan-Execute 方案已就绪", "done")
            plan_intro = (
                "已生成 **Plan-Execute 运维方案**（含环境扫描与文件保护白名单），"
                "请在下方确认后开始分步执行。\n\n"
            )
            if plan.get("preliminary_analysis"):
                plan_intro += plan["preliminary_analysis"] + "\n\n"
            yield stream_token(plan_intro, PHASE_PLAN)
            plan_sse = dict(plan)
            if plan_sse.get("rag_reference"):
                plan_sse["rag_reference"] = str(plan_sse["rag_reference"])[:120] + "…"
            if plan_sse.get("file_protection_whitelist"):
                plan_sse["file_protection_count"] = len(plan_sse["file_protection_whitelist"])
                plan_sse["file_protection_whitelist"] = plan_sse["file_protection_whitelist"][:8]
            yield {"event": "diagnostic_plan", "data": json.dumps({
                "planId": sp.id,
                "traceId": trace_id,
                "plan": plan_sse,
                "workflowLink": workflow["link"],
                "message": "请确认方案；确认后将环境预检并原子化分步执行，支持动态调整与回滚。",
            }, ensure_ascii=False)}
            await save_message(
                db, session_id, "assistant",
                plan_intro.strip(),
                trace_id=trace_id,
            )
            from app.services.audit_service import upsert_chat_audit_record
            await upsert_chat_audit_record(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                question=content,
                answer=plan_intro.strip(),
                flow_status="awaiting_plan_confirm",
                plan_id=sp.id,
                telemetry=telemetry,
                intent=intent,
                intent_confidence=float(intent_result.get("confidence", 0)),
                workflow_link=workflow["link"],
            )
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id,
                "traceId": trace_id,
                "status": "awaiting_plan_confirm",
                "planId": sp.id,
                "workflowLink": workflow["link"],
            })}
            return

        if workflow["link"] == "link_b":
            yield _sse_exploring("route", "轻量 ReAct", "跳过方案确认，直接进入只读查询执行", "done")
            yield response_phase(PHASE_EXECUTE, "轻量运维查询，快速执行…")
    else:
        from app.services.agent_intent_context import build_intent_system_addon
        yield response_phase(PHASE_PLAN, "方案已确认，环境预检通过，开始 ReAct 执行…")

    plan_exec_prompt = None
    if goto_react and plan_resume_ctx:
        plan_exec_prompt = build_plan_execution_prompt(
            content, plan_resume_ctx.get("plan_data") or {},
        )

    # ── 任务编排器（OPS_QUERY / FAULT_ANALYSIS 时启动）──
    orchestrator = None
    if intent in (IntentType.OPS_QUERY.value, IntentType.FAULT_ANALYSIS.value):
        try:
            from app.services.task_orchestrator import TaskOrchestrator, TaskStage
            orchestrator = TaskOrchestrator(
                session_id=session_id, trace_id=trace_id, user_id=user_id)
            orchestrator.transition(TaskStage.PERCEIVING)
            yield {"event": "task_progress", "data": json.dumps(orchestrator.get_progress_event())}
        except Exception as e:
            logger.warning(f"Task orchestrator init failed: {e}")

    # 构建对话历史（含工具调用 + 会话记忆）
    history = await get_messages(db, session_id)
    memory_context = memory.build_memory_prompt()
    system_prompt = SYSTEM_PROMPT + build_intent_system_addon(intent_result, content)

    from app.services.custom_tool_registry import load_custom_tool_registry
    from app.services.tool_resolution_planner import build_tool_resolution_prompt
    custom_registry = await load_custom_tool_registry(db)
    set_active_custom_registry(custom_registry)
    extra_tool_schemas = custom_registry.openai_schemas
    tool_resolution = (intent_result or {}).get("tool_resolution") or {}
    resolution_prompt = build_tool_resolution_prompt(tool_resolution)
    if resolution_prompt:
        system_prompt += resolution_prompt

    if plan_exec_prompt:
        system_prompt += (
            "\n\n## 方案已确认 — 必须调用工具执行\n"
            + plan_exec_prompt
        )
    if memory_context:
        system_prompt += "\n" + memory_context
    if rag_context and intent != IntentType.KNOWLEDGE_QA.value:
        system_prompt += "\n\n" + rag_context
    yield response_phase(PHASE_PLAN, "已理解诉求，开始分析与执行…")
    messages = [{"role": "system", "content": system_prompt}]
    for m in history["items"]:
        if m["role"] == "user":
            uc = m["content"]
            if uc in ("(resume)", "[确认执行方案]"):
                continue
            messages.append({"role": "user", "content": uc})
        elif m["role"] == "assistant":
            messages.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "tool_call" and m.get("toolCalls"):
            for tc in m["toolCalls"]:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["toolName"], "arguments": json.dumps(tc.get("params", {}))},
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tc.get("result", {}), ensure_ascii=False),
                })

    if plan_exec_prompt:
        messages.append({"role": "user", "content": plan_exec_prompt})

    full_response = ""
    max_rounds = min(settings.max_conversation_rounds, settings.react_max_rounds)
    round_count = 0
    tool_call_records = []
    final_status = "completed"
    skip_llm_react = False

    planned_data = (plan_resume_ctx or {}).get("plan_data") if goto_react else {}
    if goto_react and planned_data.get("steps"):
        skip_llm_react = True

        full_response = "已按已确认的诊断方案执行运维操作。\n\n"
        yield stream_token(full_response, PHASE_EXECUTE)
        exec_state = {"records": [], "early_status": None, "approval_id": None}
        async for ev in _stream_planned_diagnostic_execution(
            db, session_id, trace_id, user_id, planned_data, messages, exec_state,
            server_id=server_id,
        ):
            yield ev
        tool_call_records = exec_state["records"]
        if TOOLS_MARKER not in full_response:
            full_response += TOOLS_MARKER
            yield stream_token(TOOLS_MARKER, PHASE_EXECUTE)

        if exec_state.get("early_status"):
            final_status = exec_state["early_status"]
            async for ev in _yield_plan_step_progress(content, tool_call_records, planned_data):
                yield ev
            await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
            if tool_call_records:
                await upsert_tool_call_message(
                    db, session_id, tool_call_records, trace_id=trace_id,
                )
            from app.services.audit_service import upsert_chat_audit_record
            await upsert_chat_audit_record(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                question=content,
                answer=full_response,
                tool_call_records=tool_call_records,
                flow_status=final_status,
                telemetry=telemetry,
                intent=intent,
                intent_confidence=float(intent_result.get("confidence", 0)),
            )
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id,
                "traceId": trace_id,
                "status": final_status,
                "approvalId": exec_state.get("approval_id"),
                "pendingConfirm": any(
                    tc.get("status") == "pending_confirm" for tc in tool_call_records
                ),
                "pendingApproval": any(
                    tc.get("status") == "pending_approval" for tc in tool_call_records
                ),
                "planInProgress": True,
            })}
            return

        if _plan_has_pending_actions(tool_call_records):
            async for ev in _yield_plan_step_progress(content, tool_call_records, planned_data):
                yield ev
            await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
            if tool_call_records:
                await upsert_tool_call_message(
                    db, session_id, tool_call_records, trace_id=trace_id,
                )
            from app.services.audit_service import upsert_chat_audit_record
            await upsert_chat_audit_record(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                question=content,
                answer=full_response,
                tool_call_records=tool_call_records,
                flow_status="awaiting_user_action",
                telemetry=telemetry,
                intent=intent,
                intent_confidence=float(intent_result.get("confidence", 0)),
            )
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id,
                "traceId": trace_id,
                "status": "awaiting_user_action",
                "approvalId": next(
                    (tc.get("approvalId") for tc in tool_call_records if tc.get("status") == "pending_approval"),
                    None,
                ),
                "pendingConfirm": any(
                    tc.get("status") == "pending_confirm" for tc in tool_call_records
                ),
                "pendingApproval": True,
                "planInProgress": True,
            })}
            return

        async for ev in _yield_plan_final_summary_events(
            content, tool_call_records, full_response, planned_data,
        ):
            if ev.get("event") == "token":
                full_response += json.loads(ev["data"])["token"]
            yield ev
        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        if tool_call_records:
            await upsert_tool_call_message(
                db, session_id, tool_call_records, trace_id=trace_id,
            )
        from app.services.audit_service import upsert_chat_audit_record
        await upsert_chat_audit_record(
            db,
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            question=content,
            answer=full_response,
            tool_call_records=tool_call_records,
            flow_status="completed",
            telemetry=telemetry,
            intent=intent,
            intent_confidence=float(intent_result.get("confidence", 0)),
        )
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id,
            "traceId": trace_id,
            "status": "completed",
            "planCompleted": True,
        })}
        return

    if not skip_llm_react:
      while round_count < max_rounds:
        round_count += 1
        current_tool_calls = []
        current_content = ""

        yield _sse_exploring("llm", "智能推理", f"第 {round_count}/{max_rounds} 轮")

        try:
            async for chunk in call_deepseek(messages, stream=True, extra_tools=extra_tool_schemas):
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})

                if "content" in delta and delta["content"]:
                    current_content += delta["content"]
                    full_response += delta["content"]
                    yield stream_token(delta["content"], PHASE_ANSWER)

                if "tool_calls" in delta:
                    for tc_delta in delta["tool_calls"]:
                        idx = tc_delta.get("index", 0)
                        while len(current_tool_calls) <= idx:
                            current_tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                        tc = current_tool_calls[idx]
                        if "id" in tc_delta:
                            tc["id"] = tc_delta["id"]
                        if "function" in tc_delta:
                            fn = tc_delta["function"]
                            if "name" in fn:
                                tc["function"]["name"] = fn["name"]
                            if "arguments" in fn:
                                tc["function"]["arguments"] += fn["arguments"]

            if current_tool_calls:
                # 标记工具区：此前文本为过程说明，其后为最终结论（同步推送到前端以便分段展示）
                if TOOLS_MARKER not in full_response:
                    full_response += TOOLS_MARKER
                    yield stream_token(TOOLS_MARKER, PHASE_ANSWER)

                yield response_phase(PHASE_EXECUTE, "正在执行运维工具…")

                # Agent 决定调用工具 —— 安全护栏前置检查
                messages.append({"role": "assistant", "content": current_content or None, "tool_calls": current_tool_calls})

                blocked_any = False
                pending_approval = None
                pending_confirm = None

                for tc in current_tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_call_id = tc.get("id", generate_id())
                    try:
                        tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                    except json.JSONDecodeError:
                        tool_args = {}

                    risk = get_tool_risk_level(tool_name, tool_args)
                    yield _sse_exploring(
                        f"risk-{tool_call_id}",
                        f"风险评估 · {tool_name}",
                        f"初步等级 {risk}",
                    )
                    safety = _check_tool_safety(tool_name, tool_args)
                    yield {"event": "safety_decision", "data": json.dumps({
                        "toolName": tool_name,
                        "riskLevel": safety["risk_level"],
                        "blocked": safety["blocked"],
                        "requireConfirm": safety["require_confirm"],
                        "requireApproval": safety["require_approval"],
                    }, ensure_ascii=False)}
                    yield _sse_exploring(
                        f"risk-{tool_call_id}",
                        f"风险评估 · {tool_name}",
                        f"→ {safety['risk_level']} "
                        f"{'阻断' if safety['blocked'] else '需审批' if safety['require_approval'] else '需确认' if safety['require_confirm'] else '允许执行'}",
                        "done",
                    )

                    # ── 阻止（高危命令如 mkfs, rm -rf /）──
                    if safety["blocked"]:
                        blocked_any = True
                        block_msg = safety["block_message"]

                        yield {"event": "blocked", "data": json.dumps({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "message": block_msg,
                            "status": "blocked",
                        })}

                        tool_call_records.append({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "status": "blocked",
                            "result": {"success": False, "error": block_msg},
                        })
                        continue

                    # ── 需审批（L4/L5 高危操作：重启服务、用户管理、iptables修改等）──
                    if safety["require_approval"]:
                        risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
                        now = datetime.utcnow()
                        expires_at = now + timedelta(seconds=settings.approval_timeout)

                        approval = Approval(
                            trace_id=trace_id,
                            session_id=session_id,
                            tool_name=tool_name,
                            tool_params_json=json.dumps(tool_args, ensure_ascii=False),
                            risk_level=safety["risk_level"],
                            detail=risk_desc,
                            requested_by=user_id,
                            expires_at=expires_at,
                        )
                        db.add(approval)
                        await db.commit()
                        await db.refresh(approval)

                        # 保存待处理执行记录，审批通过后继续
                        pe = await _save_pending_execution(
                            db, session_id, trace_id, user_id,
                            tool_name, tool_args, safety["risk_level"],
                            messages_snapshot=messages,
                            need_approval=True,
                            approval_id=approval.id,
                        )

                        yield {"event": "need_approval", "data": json.dumps({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "approvalId": approval.id,
                            "message": f"{risk_desc}\n请在审批管理页面确认此操作（{settings.approval_timeout}秒超时）",
                            "status": "pending_approval",
                            "expiresAt": expires_at.isoformat(),
                        })}

                        tool_call_records.append({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "status": "pending_approval",
                            "approvalId": approval.id,
                        })
                        pending_approval = approval.id
                        continue

                    # ── 需确认（L2 可逆操作：kill TERM, service start等）──
                    if safety["require_confirm"]:
                        risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])

                        pe = await _save_pending_execution(
                            db, session_id, trace_id, user_id,
                            tool_name, tool_args, safety["risk_level"],
                            messages_snapshot=messages,
                            need_confirm=True,
                        )

                        yield {"event": "need_confirm", "data": json.dumps({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "pendingExecutionId": pe.id,
                            "message": f"{risk_desc}\n确认执行此操作？",
                            "status": "pending_confirm",
                        })}

                        tool_call_records.append({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "status": "pending_confirm",
                            "pendingExecutionId": pe.id,
                        })
                        pending_confirm = pe.id
                        continue

                    # ── L1 安全操作：直接执行 ──
                    yield _sse_exploring(
                        f"exec-{tool_call_id}",
                        f"远程执行 · {tool_name}",
                        "正在连接目标主机…",
                    )
                    # 权限校验（非阻塞，记录越权操作）
                    try:
                        from app.services.permission_service import validate_operation_scope
                        perm_check = validate_operation_scope(tool_name, tool_args, "admin")
                        if not perm_check["allowed"]:
                            yield {"event": "permission_notice", "data": json.dumps({
                                "toolName": tool_name,
                                "message": perm_check["message"],
                                "restricted": True,
                            })}
                    except Exception:
                        pass  # 权限校验失败不阻塞主流程

                    yield {"event": "tool_call", "data": json.dumps({
                        "id": tool_call_id,
                        "toolName": tool_name,
                        "params": tool_args,
                        "riskLevel": risk,
                        "status": "executing",
                    })}

                    pre_state = _pre_state_for_write(tool_name, tool_args, safety["risk_level"], server_id)
                    result = execute_tool(tool_name, tool_args)
                    if result.get("success"):
                        await _record_write_execution(
                            db, session_id, trace_id, tool_name, tool_args, result,
                            tool_call_id=tool_call_id,
                            risk_level=safety["risk_level"],
                            server_id=server_id,
                            pre_state=pre_state,
                        )
                    yield _sse_exploring(
                        f"exec-{tool_call_id}",
                        f"远程执行 · {tool_name}",
                        result.get("display_summary", "完成")[:80],
                        "done" if result.get("success") else "error",
                    )

                    yield {"event": "tool_result", "data": json.dumps({
                        "toolName": tool_name,
                        "status": "completed",
                        "result": result,
                        "displaySummary": result.get("display_summary", ""),
                    }, ensure_ascii=False)}

                    tool_call_records.append({
                        "id": tool_call_id,
                        "toolName": tool_name,
                        "params": tool_args,
                        "riskLevel": risk,
                        "status": "completed",
                        "result": result,
                        "displaySummary": result.get("display_summary", ""),
                    })

                    from app.services.tool_output_formatter import format_for_llm
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": format_for_llm(tool_name, result),
                    })

                    # ── 任务编排器步骤追踪 ──
                    if orchestrator:
                        step = orchestrator.add_step(tool_name, tool_name, tool_args)
                        step.status = "completed" if result.get("success", False) else "failed"
                        step.result = result
                        from app.services.task_orchestrator import TaskStage
                        if orchestrator.steps and len(orchestrator.steps) >= 2 and orchestrator.current_stage != TaskStage.EXECUTING:
                            orchestrator.transition(TaskStage.EXECUTING)
                        yield {"event": "task_progress", "data": json.dumps(orchestrator.get_progress_event())}

                    # ── 可信度标记 ──
                    try:
                        from app.services.context_credibility import CredibilityTracker
                        tracker = CredibilityTracker()
                        tag = tracker.tag_source("system_tool", tool_name)
                        result["_credibility"] = tag
                    except Exception:
                        pass

                # 时间同步：只读检查完成后自动弹出对时确认
                if not pending_approval and not pending_confirm:
                    ts_follow = await _maybe_auto_queue_time_sync_confirm(
                        db, session_id, trace_id, user_id, content,
                        tool_call_records, messages,
                    )
                    if ts_follow:
                        rec = ts_follow["record"]
                        tool_call_records.append(rec)
                        yield {"event": "tool_call", "data": json.dumps({
                            "id": rec["id"],
                            "toolName": rec["toolName"],
                            "params": rec["params"],
                            "riskLevel": rec["riskLevel"],
                            "status": "pending_confirm",
                            "pendingExecutionId": rec["pendingExecutionId"],
                            "commandPreview": rec.get("commandPreview"),
                        }, ensure_ascii=False)}
                        yield {"event": "need_confirm", "data": json.dumps({
                            "id": rec["id"],
                            "toolName": rec["toolName"],
                            "params": rec["params"],
                            "riskLevel": rec["riskLevel"],
                            "pendingExecutionId": rec["pendingExecutionId"],
                            "message": ts_follow["message"],
                            "status": "pending_confirm",
                            "commandPreview": rec.get("commandPreview"),
                        }, ensure_ascii=False)}
                        pending_confirm = ts_follow["pendingExecutionId"]

                # 如果有待审批/待确认的操作，停止 ReAct 循环等待用户操作
                if pending_approval or pending_confirm:
                    completed_any = any(tc.get("status") == "completed" for tc in tool_call_records)
                    from app.services.ops_scope import is_time_sync_execution_request
                    from app.services.response_summarizer import _time_sync_action_satisfied
                    skip_premature_summary = (
                        pending_confirm
                        and is_time_sync_execution_request(content)
                        and not _time_sync_action_satisfied(content, tool_call_records)
                    )
                    if completed_any and not skip_premature_summary:
                        async for ev in _yield_final_summary_events(content, tool_call_records, full_response):
                            if ev.get("event") == "token":
                                full_response += json.loads(ev["data"])["token"]
                            yield ev
                    yield {"event": "message_done", "data": json.dumps({
                        "messageId": assistant_msg_id,
                        "traceId": trace_id,
                        "status": "awaiting_user_action",
                        "approvalId": pending_approval,
                        "pendingConfirm": bool(pending_confirm),
                    })}
                    return

                # 如果有被阻止的工具但有其他成功的，继续循环
                if blocked_any and not any(
                    tc["status"] == "completed" for tc in tool_call_records
                ):
                    yield {"event": "message_done", "data": json.dumps({
                        "messageId": assistant_msg_id,
                        "traceId": trace_id,
                        "status": "blocked",
                    })}
                    return

                # 提示模型在下一轮必须给出结论（避免只执行工具不回答）
                from app.services.response_summarizer import _has_valid_conclusion
                if not _has_valid_conclusion(full_response):
                    messages.append({
                        "role": "user",
                        "content": (
                            f"请根据上述工具结果，用「## 执行结论」直接回答我的问题：{content[:300]}。"
                            "必须包含关键数据解读；若我问清理/优化/建议，请给出 2～3 条可执行建议。不要再次调用工具。"
                        ),
                    })

                continue
            else:
                # Agent 完成回复，没有工具调用
                from app.services.ops_scope import is_time_sync_execution_request
                from app.services.response_summarizer import _write_action_satisfied
                if (
                    round_count < max_rounds
                    and is_time_sync_execution_request(content)
                    and not _write_action_satisfied(content, tool_call_records)
                ):
                    if current_content:
                        messages.append({"role": "assistant", "content": current_content})
                    messages.append({
                        "role": "user",
                        "content": (
                            "请调用 execute_command 执行 `chronyc -a makestep` 强制对时"
                            "（若不可用则 timedatectl set-ntp true）。"
                            "禁止仅用文字描述已同步。"
                        ),
                    })
                    continue
                if (
                    round_count < max_rounds
                    and is_disk_cleanup_execution_request(content)
                    and not any(tc.get("status") == "completed" for tc in tool_call_records)
                ):
                    if current_content:
                        messages.append({"role": "assistant", "content": current_content})
                    messages.append({
                        "role": "user",
                        "content": (
                            "你尚未调用任何工具。请立即调用 get_disk_usage，"
                            "再依次 execute_command 执行 dnf clean all、journalctl --vacuum-time=3d。"
                            "禁止继续用文字假装已清理。"
                        ),
                    })
                    continue
                break

        except httpx.TimeoutException as e:
            from app.services.fallback_handler import get_fallback, FallbackReason, classify_fallback, build_error_log
            fb = get_fallback(FallbackReason.TIMEOUT)
            yield fb
            full_response += "\n\n⚠ LLM 服务响应超时，请稍后重试。"
            logger.warning(f"Task timeout: {build_error_log(FallbackReason.TIMEOUT, str(e), content, trace_id, session_id)}")
            break
        except httpx.ConnectError as e:
            from app.services.fallback_handler import get_fallback, FallbackReason, build_error_log
            fb = get_fallback(FallbackReason.LLM_UNAVAILABLE)
            yield fb
            full_response += "\n\n⚠ LLM 服务暂时不可用，请检查网络连接。"
            logger.warning(f"LLM unavailable: {build_error_log(FallbackReason.LLM_UNAVAILABLE, str(e), content, trace_id, session_id)}")
            break
        except Exception as e:
            from app.services.fallback_handler import get_fallback, FallbackReason, classify_fallback, build_error_log
            reason = classify_fallback(e)
            fb = get_fallback(reason, str(e)[:200])
            yield fb
            logger.error(f"Agent error: {build_error_log(reason, str(e), content, trace_id, session_id)}")
            has_done_tools = any(tc.get("status") == "completed" for tc in tool_call_records)
            if not has_done_tools:
                full_response += f"\n\n⚠ Agent 处理异常，请联系管理员。Trace: {trace_id}"
            break

    if any(tc.get("status") == "pending_approval" for tc in tool_call_records):
        final_status = "awaiting_approval"

    # 时间同步：循环结束前若仅有检查无对时，自动推送确认框
    ts_follow = await _maybe_auto_queue_time_sync_confirm(
        db, session_id, trace_id, user_id, content, tool_call_records, messages,
    )
    if ts_follow:
        rec = ts_follow["record"]
        tool_call_records.append(rec)
        yield {"event": "tool_call", "data": json.dumps({
            "id": rec["id"],
            "toolName": rec["toolName"],
            "params": rec["params"],
            "riskLevel": rec["riskLevel"],
            "status": "pending_confirm",
            "pendingExecutionId": rec["pendingExecutionId"],
            "commandPreview": rec.get("commandPreview"),
        }, ensure_ascii=False)}
        yield {"event": "need_confirm", "data": json.dumps({
            "id": rec["id"],
            "toolName": rec["toolName"],
            "params": rec["params"],
            "riskLevel": rec["riskLevel"],
            "pendingExecutionId": rec["pendingExecutionId"],
            "message": ts_follow["message"],
            "status": "pending_confirm",
            "commandPreview": rec.get("commandPreview"),
        }, ensure_ascii=False)}
        if TOOLS_MARKER not in full_response:
            full_response += TOOLS_MARKER
            yield stream_token(TOOLS_MARKER, PHASE_EXECUTE)
        await upsert_tool_call_message(db, session_id, tool_call_records, trace_id=trace_id)
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id,
            "traceId": trace_id,
            "status": "awaiting_user_action",
            "pendingConfirm": True,
        })}
        return

    # 工具执行后生成最终总结（流式写入结论段）
    async for ev in _yield_final_summary_events(content, tool_call_records, full_response):
        if ev.get("event") == "token":
            full_response += json.loads(ev["data"])["token"]
        yield ev

    # 结构化运维报告（人类可读的完整报告附录）
    if tool_call_records and intent in (
        IntentType.OPS_QUERY.value, IntentType.FAULT_ANALYSIS.value, IntentType.HIGH_RISK.value,
    ):
        from app.services.response_summarizer import REPORT_MARKER
        report = build_structured_ops_report(content, trace_id, tool_call_records, intent)
        report_marker = REPORT_MARKER
        if "<!--KYLIN_REPORT-->" not in full_response:
            full_response += report_marker + report
            yield stream_token(report_marker + report, PHASE_SUMMARY)
        yield {"event": "ops_report", "data": json.dumps({
            "traceId": trace_id,
            "report": report[:4000],
            "toolCount": len(tool_call_records),
        }, ensure_ascii=False)}
        try:
            from app.services.agent.knowledge_cycle import ingest_ops_report
            title = f"[自动报告] {content[:40]}"
            await ingest_ops_report(db, title=title, content=report, trace_id=trace_id)
        except Exception:
            pass

    # 保存 assistant 消息
    await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)

    # 工具调用记录保存在 assistant 之后，确保前端只显示一个 Agent 头部
    if tool_call_records:
        await save_message(db, session_id, "tool_call", "",
                           tool_calls=tool_call_records, trace_id=trace_id)

    # ── Step 10: 写入审计记录 ──
    telemetry.start_step("10_审计写入")
    from app.services.audit_service import upsert_chat_audit_record
    await upsert_chat_audit_record(
        db,
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
        question=content,
        answer=full_response,
        tool_call_records=tool_call_records,
        flow_status=final_status,
        telemetry=telemetry,
        intent=intent,
        intent_confidence=float(intent_result.get("confidence", 0)),
        workflow_link=route_link,
    )
    telemetry.end_step("ok")

    # ── Step 11: 遥测反馈 —— 记录全链路耗时 ──
    record_trace(telemetry)

    yield {"event": "message_done", "data": json.dumps({
        "messageId": assistant_msg_id,
        "traceId": trace_id,
        "status": final_status,
        "usage": {"outputTokens": len(full_response)},
    })}


def generate_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


# ============================================================
# 审批拒绝/超时 — 生成执行结论
# ============================================================
async def finalize_approval_rejection_in_session(
    db: AsyncSession,
    session_id: str,
    approval_id: str,
) -> dict:
    """管理员拒绝或审批超时后：更新工具卡状态并写入执行结论（幂等）。"""
    from sqlalchemy import select
    from app.models.session import Message
    from app.services.approval_service import get_by_id
    from app.services.response_summarizer import (
        TOOLS_MARKER,
        build_approval_rejection_conclusion,
    )

    approval = await get_by_id(db, approval_id)
    if not approval or approval.session_id != session_id:
        return {"ok": False, "message": "审批记录不存在"}
    if approval.status not in ("rejected", "timeout"):
        return {"ok": False, "message": "审批尚未拒绝或超时"}

    msgs_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    messages = list(msgs_result.scalars().all())

    tool_msg = None
    tool_records = None
    rejected_tc = None
    for m in reversed(messages):
        if m.role != "tool_call" or not m.tool_calls_json:
            continue
        try:
            raw = m.tool_calls_json
            tcs = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if not isinstance(tcs, list):
            continue
        hit = next((tc for tc in tcs if tc.get("approvalId") == approval_id), None)
        if hit:
            tool_msg = m
            tool_records = tcs
            rejected_tc = hit
            break

    if not tool_msg or not tool_records:
        for m in reversed(messages):
            if m.role != "tool_call" or not m.tool_calls_json:
                continue
            try:
                raw = m.tool_calls_json
                tcs = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                continue
            if not isinstance(tcs, list):
                continue
            for tc in tcs:
                if (
                    tc.get("status") == "pending_approval"
                    and tc.get("toolName") == approval.tool_name
                ):
                    tc["approvalId"] = approval_id
                    tool_msg = m
                    tool_records = tcs
                    rejected_tc = tc
                    break
            if tool_msg:
                break

    if not tool_msg or not tool_records:
        return {"ok": False, "message": "未找到关联的工具调用记录"}

    if not rejected_tc:
        rejected_tc = next((tc for tc in tool_records if tc.get("approvalId") == approval_id), None)
    if not rejected_tc:
        return {"ok": False, "message": "未找到待审批工具"}

    reason = (approval.comment or "").strip() or (
        "审批超时，操作未执行" if approval.status == "timeout" else "不予执行"
    )

    assistant_msg = None
    for m in reversed(messages):
        if m.id == tool_msg.id:
            continue
        if m.role == "assistant":
            if not tool_msg.trace_id or m.trace_id == tool_msg.trace_id:
                assistant_msg = m
                break
    if not assistant_msg:
        for m in reversed(messages):
            if m.role == "assistant":
                assistant_msg = m
                break

    user_question = ""
    for m in messages:
        if m.role == "user" and m.content and m.content not in ("(resume)", "[确认执行方案]"):
            user_question = m.content

    already_has_conclusion = bool(
        assistant_msg and "## 执行结论" in (assistant_msg.content or "")
    )

    label = "审批超时" if approval.status == "timeout" else "管理员已拒绝"
    if rejected_tc.get("status") != "rejected":
        rejected_tc["status"] = "rejected"
    rejected_tc["result"] = {
        "success": False,
        "error": f"{label}：{reason}",
    }

    tool_msg.tool_calls_json = json.dumps(tool_records, ensure_ascii=False)

    conclusion_text = ""
    if not already_has_conclusion and assistant_msg:
        conclusion = build_approval_rejection_conclusion(
            user_question,
            tool_records,
            rejected_tc,
            reason,
            approval_status=approval.status,
        )
        full_response = assistant_msg.content or ""
        if TOOLS_MARKER not in full_response:
            full_response += TOOLS_MARKER
        full_response += conclusion
        assistant_msg.content = full_response
        conclusion_text = conclusion

    await db.commit()

    return {
        "ok": True,
        "message": "已生成拒绝说明与执行结论",
        "alreadyFinalized": already_has_conclusion,
        "conclusion": conclusion_text,
        "approvalStatus": approval.status,
        "toolCallMessageId": tool_msg.id,
        "assistantMessageId": assistant_msg.id if assistant_msg else None,
        "toolCalls": tool_records,
    }


async def stream_approval_rejection_finalize(
    db: AsyncSession,
    session_id: str,
    approval_id: str,
):
    """SSE：审批拒绝/超时后推送执行结论。"""
    from app.services.stream_events import stream_token, PHASE_SUMMARY, response_phase

    result = await finalize_approval_rejection_in_session(db, session_id, approval_id)
    if not result.get("ok"):
        yield {"event": "error", "data": json.dumps({"message": result.get("message", "处理失败")})}
        return

    conclusion = result.get("conclusion") or ""
    if conclusion:
        yield response_phase(PHASE_SUMMARY, "正在生成执行结论…")
        yield {"event": "summary_start", "data": json.dumps({"title": "执行结论"})}
        chunk_size = 48
        for i in range(0, len(conclusion), chunk_size):
            yield stream_token(conclusion[i:i + chunk_size], PHASE_SUMMARY)
        yield {"event": "summary_done", "data": json.dumps({})}

    yield {"event": "tool_calls_updated", "data": json.dumps({
        "messageId": result.get("toolCallMessageId"),
        "toolCalls": result.get("toolCalls", []),
    }, ensure_ascii=False)}

    yield {"event": "message_done", "data": json.dumps({
        "status": "completed",
        "approvalStatus": result.get("approvalStatus"),
        "alreadyFinalized": result.get("alreadyFinalized", False),
    })}


async def _stream_plan_continuation(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    planned_ctx: dict,
    latest_record: Optional[dict] = None,
    pe_id: str = None,
    resolved_tool_id: str = None,
    messages: Optional[list] = None,
    intro: str = "",
    assistant_msg_id: str = None,
    server_id: str = None,
    skip_pending_replay: bool = False,
):
    """续跑方案后续步骤（第 N 步完成后自动推进第 N+1 步）。"""
    from app.services.response_summarizer import TOOLS_MARKER
    from app.services.stream_events import stream_token, PHASE_EXECUTE

    plan_data = planned_ctx["plan_data"]
    from app.services.audit_service import infer_intent_from_question, upsert_chat_audit_record
    plan_intent = planned_ctx.get("intent") or ""
    plan_intent_conf = 0.0
    if not plan_intent:
        from app.services.audit_service import _load_supervision_intent
        plan_intent = await _load_supervision_intent(db, trace_id, session_id)
    if not plan_intent:
        plan_intent, plan_intent_conf = infer_intent_from_question(
            (plan_data.get("phenomenon") or "").strip(),
        )
    tool_call_records = list(planned_ctx.get("records") or [])
    if latest_record:
        replaced = False
        for i, rec in enumerate(tool_call_records):
            if (
                (pe_id and rec.get("pendingExecutionId") == pe_id)
                or (resolved_tool_id and rec.get("id") == resolved_tool_id)
                or (
                    latest_record.get("planStepOrder") is not None
                    and rec.get("planStepOrder") == latest_record.get("planStepOrder")
                    and rec.get("status") in ("pending_approval", "pending_confirm", "executing")
                )
            ):
                tool_call_records[i] = {
                    **rec,
                    **latest_record,
                    "id": rec.get("id", latest_record.get("id")),
                }
                replaced = True
                break
        if not replaced:
            tool_call_records.append(latest_record)

    tool_call_records = await _normalize_journal_step_pending_records(
        db, session_id, trace_id, user_id, plan_data, tool_call_records, messages,
    )
    pending = _filter_actionable_pending_records(tool_call_records)
    if pending and not skip_pending_replay:
        user_question = (plan_data.get("phenomenon") or "").strip()
        for tc in pending:
            if tc.get("status") == "pending_confirm":
                yield {"event": "tool_call", "data": json.dumps({
                    "id": tc.get("id"),
                    "toolName": tc.get("toolName"),
                    "params": tc.get("params") or {},
                    "riskLevel": tc.get("riskLevel", "L2"),
                    "status": "pending_confirm",
                    "pendingExecutionId": tc.get("pendingExecutionId"),
                    "commandPreview": preview_tool_command(tc.get("toolName"), tc.get("params") or {}),
                    "planStepOrder": tc.get("planStepOrder"),
                    "planStepTotal": tc.get("planStepTotal"),
                    "planStepAction": tc.get("planStepAction"),
                }, ensure_ascii=False)}
                yield {"event": "need_confirm", "data": json.dumps({
                    "id": tc.get("id"),
                    "toolName": tc.get("toolName"),
                    "params": tc.get("params") or {},
                    "riskLevel": tc.get("riskLevel", "L2"),
                    "pendingExecutionId": tc.get("pendingExecutionId"),
                    "message": f"步骤 {tc.get('planStepOrder')} · {tc.get('planStepAction') or '请在下方确认后执行。'}",
                    "status": "pending_confirm",
                    "commandPreview": preview_tool_command(tc.get("toolName"), tc.get("params") or {}),
                    "planStepOrder": tc.get("planStepOrder"),
                    "planStepTotal": tc.get("planStepTotal"),
                    "planStepAction": tc.get("planStepAction"),
                }, ensure_ascii=False)}
            elif tc.get("status") == "pending_approval":
                yield {"event": "tool_call", "data": json.dumps({
                    "id": tc.get("id"),
                    "toolName": tc.get("toolName"),
                    "params": tc.get("params") or {},
                    "riskLevel": tc.get("riskLevel", "L3"),
                    "status": "pending_approval",
                    "approvalId": tc.get("approvalId"),
                    "commandPreview": preview_tool_command(tc.get("toolName"), tc.get("params") or {}),
                    "planStepOrder": tc.get("planStepOrder"),
                    "planStepTotal": tc.get("planStepTotal"),
                    "planStepAction": tc.get("planStepAction"),
                }, ensure_ascii=False)}
                yield {"event": "need_approval", "data": json.dumps({
                    "id": tc.get("id"),
                    "toolName": tc.get("toolName"),
                    "params": tc.get("params") or {},
                    "riskLevel": tc.get("riskLevel", "L3"),
                    "approvalId": tc.get("approvalId"),
                    "message": tc.get("planStepAction") or "待管理员审批",
                    "status": "pending_approval",
                    "commandPreview": preview_tool_command(tc.get("toolName"), tc.get("params") or {}),
                    "planStepOrder": tc.get("planStepOrder"),
                    "planStepTotal": tc.get("planStepTotal"),
                    "planStepAction": tc.get("planStepAction"),
                }, ensure_ascii=False)}
        async for ev in _yield_plan_step_progress(user_question, tool_call_records, plan_data):
            yield ev
        await upsert_tool_call_message(db, session_id, tool_call_records, trace_id=trace_id)
        await upsert_chat_audit_record(
            db,
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            question=user_question,
            answer=full_response,
            tool_call_records=tool_call_records,
            flow_status="awaiting_user_action",
            intent=plan_intent,
            intent_confidence=plan_intent_conf or None,
        )
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id or generate_id(),
            "traceId": trace_id,
            "status": "awaiting_user_action",
            "approvalId": pending[0].get("approvalId"),
            "pendingConfirm": any(tc.get("status") == "pending_confirm" for tc in tool_call_records),
            "pendingApproval": any(tc.get("status") == "pending_approval" for tc in tool_call_records),
            "planInProgress": True,
        })}
        return

    full_response = intro
    if intro:
        yield stream_token(intro, PHASE_EXECUTE)
    exec_state = {"records": tool_call_records, "early_status": None, "approval_id": None}
    start_after = _plan_resume_start_after_order(planned_ctx, tool_call_records)
    async for ev in _stream_planned_diagnostic_execution(
        db, session_id, trace_id, user_id, plan_data, messages or [], exec_state,
        start_after_order=start_after,
        server_id=server_id,
    ):
        yield ev
    tool_call_records = exec_state["records"]
    if TOOLS_MARKER not in full_response:
        full_response += TOOLS_MARKER
        yield stream_token(TOOLS_MARKER, PHASE_EXECUTE)

    user_question = (plan_data.get("phenomenon") or "").strip()
    for m in messages or []:
        if m.get("role") == "user" and m.get("content") and m["content"] not in ("(resume)", "[确认执行方案]"):
            user_question = m["content"]
            break

    if exec_state.get("early_status"):
        async for ev in _yield_plan_step_progress(user_question, tool_call_records, plan_data):
            yield ev
        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        await upsert_tool_call_message(db, session_id, tool_call_records, trace_id=trace_id)
        await upsert_chat_audit_record(
            db,
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            question=user_question,
            answer=full_response,
            tool_call_records=tool_call_records,
            flow_status=exec_state.get("early_status") or "plan_interrupted",
            intent=plan_intent,
            intent_confidence=plan_intent_conf or None,
        )
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id or generate_id(),
            "traceId": trace_id,
            "status": exec_state["early_status"],
            "approvalId": exec_state.get("approval_id"),
            "pendingConfirm": any(tc.get("status") == "pending_confirm" for tc in tool_call_records),
            "pendingApproval": any(tc.get("status") == "pending_approval" for tc in tool_call_records),
            "planInProgress": True,
        })}
        return

    if _plan_has_pending_actions(tool_call_records) or _filter_actionable_pending_records(tool_call_records):
        async for ev in _yield_plan_step_progress(user_question, tool_call_records, plan_data):
            yield ev
        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        await upsert_tool_call_message(db, session_id, tool_call_records, trace_id=trace_id)
        await upsert_chat_audit_record(
            db,
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            question=user_question,
            answer=full_response,
            tool_call_records=tool_call_records,
            flow_status="awaiting_user_action",
            intent=plan_intent,
            intent_confidence=plan_intent_conf or None,
        )
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id or generate_id(),
            "traceId": trace_id,
            "status": "awaiting_user_action",
            "approvalId": next(
                (tc.get("approvalId") for tc in tool_call_records if tc.get("status") == "pending_approval"),
                None,
            ),
            "pendingConfirm": any(tc.get("status") == "pending_confirm" for tc in tool_call_records),
            "pendingApproval": True,
            "planInProgress": True,
        })}
        return

    async for ev in _yield_plan_final_summary_events(
        user_question, tool_call_records, full_response, plan_data,
    ):
        if ev.get("event") == "token":
            full_response += json.loads(ev["data"])["token"]
        yield ev
    await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
    await upsert_tool_call_message(db, session_id, tool_call_records, trace_id=trace_id)
    await upsert_chat_audit_record(
        db,
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
        question=user_question,
        answer=full_response,
        tool_call_records=tool_call_records,
        flow_status="completed",
        intent=plan_intent,
        intent_confidence=plan_intent_conf or None,
    )
    yield {"event": "message_done", "data": json.dumps({
        "messageId": assistant_msg_id or generate_id(),
        "traceId": trace_id,
        "status": "completed",
        "usage": {"outputTokens": len(full_response)},
        "planCompleted": True,
    })}


async def stream_continue_plan_execution(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    server_id: str = None,
):
    """方案卡壳时：从已确认方案 + 当前工具记录续跑下一步。"""
    from app.models.supervision import SupervisionPlan
    from app.services.custom_tool_registry import load_custom_tool_registry

    set_active_custom_registry(await load_custom_tool_registry(db))

    await _repair_stale_tool_calls_in_session(db, session_id)
    row_result = await db.execute(
        select(SupervisionPlan).where(
            SupervisionPlan.session_id == session_id,
            SupervisionPlan.status == "confirmed",
        ).order_by(desc(SupervisionPlan.confirmed_at)).limit(1)
    )
    row = row_result.scalar_one_or_none()
    if not row:
        yield {"event": "error", "data": json.dumps({"message": "未找到已确认的方案，请重新发起对话"})}
        return

    trace_id = row.trace_id or generate_trace_id()
    planned_ctx = await _resolve_planned_ctx(db, session_id, trace_id, messages=[])
    if not planned_ctx or not planned_ctx.get("plan_data"):
        plan_data = json.loads(row.plan_json) if row.plan_json else {}
        records = await _load_all_tool_call_records_for_session(db, session_id)
        planned_ctx = {
            "plan_data": plan_data,
            "records": records,
            "pause_at_order": _plan_resume_start_after_order({"pause_at_order": 0}, records),
        }

    if not _plan_has_remaining_steps(planned_ctx):
        tool_call_records = list(planned_ctx.get("records") or [])
        if _plan_has_pending_actions(tool_call_records) or _filter_actionable_pending_records(tool_call_records):
            assistant_msg_id = generate_id()
            yield {"event": "message_start", "data": json.dumps({
                "messageId": assistant_msg_id, "traceId": trace_id,
            })}
            async for ev in _stream_plan_continuation(
                db, session_id, trace_id, user_id, planned_ctx,
                intro="",
                assistant_msg_id=assistant_msg_id,
                server_id=server_id,
            ):
                yield ev
            return

        plan_data = planned_ctx.get("plan_data") or {}
        user_question = (plan_data.get("phenomenon") or "").strip()
        plan_intent = planned_ctx.get("intent") or ""
        from app.services.audit_service import upsert_chat_audit_record
        assistant_msg_id = generate_id()
        yield {"event": "message_start", "data": json.dumps({
            "messageId": assistant_msg_id, "traceId": trace_id,
        })}
        full_response = ""
        async for ev in _yield_plan_final_summary_events(
            user_question, tool_call_records, full_response, plan_data,
        ):
            if ev.get("event") == "token":
                full_response += json.loads(ev["data"])["token"]
            yield ev
        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        await upsert_tool_call_message(db, session_id, tool_call_records, trace_id=trace_id)
        await upsert_chat_audit_record(
            db,
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            question=user_question,
            answer=full_response,
            tool_call_records=tool_call_records,
            flow_status="completed",
            intent=plan_intent,
        )
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id,
            "traceId": trace_id,
            "status": "completed",
            "usage": {"outputTokens": len(full_response)},
            "planCompleted": True,
        })}
        return

    planned_ctx["records"] = await _normalize_journal_step_pending_records(
        db, session_id, trace_id, user_id,
        planned_ctx.get("plan_data") or {},
        planned_ctx.get("records") or [],
        [],
    )

    assistant_msg_id = generate_id()
    yield {"event": "message_start", "data": json.dumps({
        "messageId": assistant_msg_id, "traceId": trace_id,
    })}
    async for ev in _stream_plan_continuation(
        db, session_id, trace_id, user_id, planned_ctx,
        intro="",
        assistant_msg_id=assistant_msg_id,
        server_id=server_id,
    ):
        yield ev


# ============================================================
# 审批/确认 后恢复执行
# ============================================================
async def resume_after_approval(db: AsyncSession, session_id: str, user_id: str,
                               approval_id: str = None, pending_execution_id: str = None):
    """用户审批/确认通过后，继续执行被挂起的工具调用并恢复 ReAct 循环"""

    # 查找待处理执行记录
    if approval_id:
        result = await db.execute(
            select(PendingExecution).where(
                PendingExecution.session_id == session_id,
                PendingExecution.approval_id == approval_id,
                PendingExecution.status.in_(["pending", "approved"]),
            )
        )
    elif pending_execution_id:
        result = await db.execute(
            select(PendingExecution).where(
                PendingExecution.id == pending_execution_id,
                PendingExecution.session_id == session_id,
                PendingExecution.status.in_(["pending", "failed"]),
            )
        )
    else:
        yield {"event": "error", "data": json.dumps({
            "message": "缺少 approvalId 或 pendingExecutionId",
        })}
        return

    skip_execute = False
    pe = result.scalar_one_or_none()
    if not pe:
        dead = None
        if pending_execution_id:
            dead_result = await db.execute(
                select(PendingExecution).where(
                    PendingExecution.id == pending_execution_id,
                    PendingExecution.session_id == session_id,
                )
            )
            dead = dead_result.scalar_one_or_none()
        if dead and dead.status == "resolved":
            try:
                snap_msgs = json.loads(dead.messages_snapshot_json or "[]")
            except Exception:
                snap_msgs = []
            if _parse_planned_resume_snapshot(snap_msgs):
                pe = dead
                skip_execute = True
            else:
                yield {"event": "error", "data": json.dumps({
                    "message": "该步骤已执行完成，请刷新页面查看最新进度",
                })}
                return
        elif dead and dead.status in ("cancelled", "rejected"):
            yield {"event": "error", "data": json.dumps({
                "message": "该步骤已取消，无法再次执行",
            })}
            return
        else:
            yield {"event": "error", "data": json.dumps({
                "message": "未找到待处理的执行记录，审批可能已过期或已处理",
            })}
            return
    elif pe.status == "resolved" and pending_execution_id:
        try:
            snap_msgs = json.loads(pe.messages_snapshot_json or "[]")
        except Exception:
            snap_msgs = []
        if _parse_planned_resume_snapshot(snap_msgs):
            skip_execute = True

    if pe.status == "failed" and not skip_execute:
        pe.status = "pending"
        pe.resolved_at = None
        await db.commit()

    # 如果需要审批，验证审批确实通过了
    if pe.need_approval and pe.approval_id:
        approval_result = await db.execute(
            select(Approval).where(Approval.id == pe.approval_id, Approval.status == "approved")
        )
        approval = approval_result.scalar_one_or_none()
        if not approval:
            pe.status = "rejected"
            await db.commit()
            yield {"event": "error", "data": json.dumps({
                "message": "审批未通过，无法继续执行",
            })}
            return

    tool_name = pe.tool_name
    tool_args = json.loads(pe.tool_params_json) if pe.tool_params_json else {}
    trace_id = pe.trace_id
    risk = pe.risk_level

    try:
        messages = json.loads(pe.messages_snapshot_json) if pe.messages_snapshot_json else []
    except Exception:
        messages = []

    resolved_tool_id = pe.id
    planned_ctx = await _resolve_planned_ctx(db, session_id, trace_id, messages)
    if planned_ctx:
        for rec in planned_ctx.get("records") or []:
            if (
                rec.get("pendingExecutionId") == pe.id
                or (pe.approval_id and rec.get("approvalId") == pe.approval_id)
            ):
                resolved_tool_id = rec.get("id", resolved_tool_id)
                break

    assistant_msg_id = generate_id()
    plan_meta = {}
    if planned_ctx:
        for rec in planned_ctx.get("records") or []:
            if rec.get("id") == resolved_tool_id or rec.get("pendingExecutionId") == pe.id:
                plan_meta = {
                    "planStepOrder": rec.get("planStepOrder"),
                    "planStepTotal": rec.get("planStepTotal"),
                    "planStepAction": rec.get("planStepAction"),
                }
                break

    yield {"event": "message_start", "data": json.dumps({
        "messageId": assistant_msg_id, "traceId": trace_id,
    })}

    # 执行被审批/确认通过的工具（SSE id 与方案步骤 tool_call_id 对齐，便于前端更新同一张工具卡）
    yield {"event": "tool_call", "data": json.dumps({
        "id": resolved_tool_id,
        "toolName": tool_name,
        "params": tool_args,
        "riskLevel": risk,
        "status": "executing",
        "approved": True,
        "pendingExecutionId": pe.id,
        "approvalId": pe.approval_id,
        **plan_meta,
    })}

    pre_state = None
    if skip_execute:
        result = {"success": True, "display_summary": "该步骤已执行完成，继续后续方案步骤"}
        exec_ok = True
    else:
        pre_state = _pre_state_for_write(tool_name, tool_args, risk, None)
        result = execute_tool(tool_name, tool_args)
        exec_ok = bool(result.get("success"))
        pe.status = "resolved" if exec_ok else "failed"
        pe.resolved_at = datetime.utcnow()
        await db.commit()

    yield {"event": "tool_result", "data": json.dumps({
        "id": resolved_tool_id,
        "toolName": tool_name,
        "status": "completed" if exec_ok else "failed",
        "result": result,
        "displaySummary": result.get("display_summary", ""),
        "pendingExecutionId": pe.id,
        "approvalId": pe.approval_id,
        **plan_meta,
    }, ensure_ascii=False)}

    if exec_ok and not skip_execute:
        await _record_write_execution(
            db, session_id, trace_id, tool_name, tool_args, result,
            tool_call_id=resolved_tool_id, risk_level=risk, pre_state=pre_state,
        )

    tool_call_record = {
        "id": resolved_tool_id,
        "toolName": tool_name,
        "params": tool_args,
        "riskLevel": risk,
        "status": "completed" if exec_ok else "failed",
        "result": result,
        "displaySummary": result.get("display_summary", ""),
        **plan_meta,
    }
    for rec in (planned_ctx or {}).get("records") or []:
        if (
            rec.get("pendingExecutionId") == pe.id
            or rec.get("id") == resolved_tool_id
            or (pe.approval_id and rec.get("approvalId") == pe.approval_id)
        ):
            tool_call_record = {
                **rec,
                **tool_call_record,
                "id": rec.get("id", resolved_tool_id),
            }
            break

    planned_ctx = await _resolve_planned_ctx(
        db, session_id, trace_id, messages, extra_records=[tool_call_record],
    )
    if not planned_ctx or not planned_ctx.get("plan_data"):
        fb = await _fallback_planned_ctx(db, session_id, trace_id, [tool_call_record])
        if fb:
            planned_ctx = fb

    if not exec_ok and planned_ctx and planned_ctx.get("plan_data"):
        plan_data = planned_ctx.get("plan_data") or {}
        step_order = tool_call_record.get("planStepOrder") or 0
        step = next(
            (s for s in (plan_data.get("steps") or []) if int(s.get("order", 0)) == int(step_order or 0)),
            {
                "order": step_order,
                "action": tool_call_record.get("planStepAction") or tool_name,
                "risk": tool_call_record.get("riskLevel") or risk,
            },
        )
        remediation_state = {
            "records": list(planned_ctx.get("records") or [tool_call_record]),
            "early_status": None,
            "approval_id": None,
        }
        async for ev in _queue_failure_remediation(
            db, session_id, trace_id, user_id, step, plan_data, messages,
            remediation_state, tool_name, tool_args, result, tool_call_record,
        ):
            yield ev
        if remediation_state.get("early_status"):
            user_question = (plan_data.get("phenomenon") or "").strip()
            for m in reversed(messages):
                if m.get("role") == "user" and m.get("content") and m["content"] not in ("(resume)", "[纭鎵ц鏂规]"):
                    user_question = m["content"]
                    break
            tool_call_records = remediation_state["records"]
            full_response = ""
            async for ev in _yield_plan_step_progress(user_question, tool_call_records, plan_data):
                yield ev
            await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
            await upsert_tool_call_message(db, session_id, tool_call_records, trace_id=trace_id)
            from app.services.audit_service import upsert_chat_audit_record
            await upsert_chat_audit_record(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                question=user_question,
                answer=full_response,
                tool_call_records=tool_call_records,
                flow_status=remediation_state.get("early_status") or "awaiting_user_action",
                intent=planned_ctx.get("intent") or "",
            )
            yield {"event": "message_done", "data": json.dumps({
                "messageId": assistant_msg_id,
                "traceId": trace_id,
                "status": remediation_state["early_status"],
                "approvalId": remediation_state.get("approval_id"),
                "pendingConfirm": any(tc.get("status") == "pending_confirm" for tc in tool_call_records),
                "pendingApproval": any(tc.get("status") == "pending_approval" for tc in tool_call_records),
                "planInProgress": True,
            })}
            return

    if planned_ctx and planned_ctx.get("plan_data") and _plan_has_remaining_steps(planned_ctx):
        async for ev in _stream_plan_continuation(
            db, session_id, trace_id, user_id, planned_ctx, tool_call_record,
            pe_id=pe.id, resolved_tool_id=resolved_tool_id, messages=messages,
            intro="",
            assistant_msg_id=assistant_msg_id,
            skip_pending_replay=True,
        ):
            yield ev
        return

    # 单步审批/确认恢复：方案已全部完成时生成最终执行结论
    user_question = ""
    for m in reversed(messages):
        if m.get("role") == "user" and m.get("content") and m["content"] not in ("(resume)", "[确认执行方案]"):
            user_question = m["content"]
            break

    plan_data = (planned_ctx or {}).get("plan_data") if planned_ctx else None
    tool_call_records = list((planned_ctx or {}).get("records") or [tool_call_record])
    from app.services.response_summarizer import is_plan_execution_complete
    plan_completed = bool(
        plan_data and is_plan_execution_complete(plan_data, tool_call_records),
    )
    full_response = ""
    if plan_completed:
        async for ev in _yield_plan_final_summary_events(
            user_question, tool_call_records, full_response, plan_data,
        ):
            if ev.get("event") == "token":
                full_response += json.loads(ev["data"])["token"]
            yield ev
    else:
        tool_call_records = [tool_call_record]
        async for ev in _yield_final_summary_events(user_question, tool_call_records, full_response):
            if ev.get("event") == "token":
                full_response += json.loads(ev["data"])["token"]
            yield ev

    await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
    await upsert_tool_call_message(db, session_id, tool_call_records, trace_id=trace_id)

    try:
        from app.models.audit import AuditRecord
        tools_used = list(set(tc["toolName"] for tc in tool_call_records)) if tool_call_records else []
        risks = [tc.get("riskLevel", "L1") for tc in tool_call_records] if tool_call_records else ["L1"]
        max_risk = "L4" if "L4" in risks else ("L3" if "L3" in risks else ("L2" if "L2" in risks else "L1"))
        audit = AuditRecord(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            event_type="chat_resume",
            summary=f"{'审批' if approval_id else '确认'}恢复: {','.join(tools_used)}",
            risk_level=max_risk,
            detail_json=json.dumps({
                "approval_id": approval_id or pe.approval_id,
                "pending_execution_id": pending_execution_id or pe.id,
                "tools": [{"name": tc["toolName"], "status": tc.get("status"), "risk": tc.get("riskLevel")}
                          for tc in (tool_call_records or [])],
            }, ensure_ascii=False),
        )
        db.add(audit)
        await db.commit()
    except Exception:
        pass

    yield {"event": "message_done", "data": json.dumps({
        "messageId": assistant_msg_id, "traceId": trace_id,
        "status": "completed",
        "usage": {"outputTokens": len(full_response)},
        "planCompleted": plan_completed,
    })}
    return
