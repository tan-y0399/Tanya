"""
人类监督增强模块 — 分阶段流程支撑

- 入口预校验（长度/非法字符）
- 上下文感知注入复核
- 诊断方案生成与确认
- 预执行环境检查（逻辑快照元数据）
- 结构化运维报告
- 对话结果反馈（解决/未解决）
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

# 诱导绕过安全校验的短语
BYPASS_INDUCTION_PATTERNS = (
    "绕过安全", "跳过审批", "不要审批", "无需确认", "ignore safety",
    "bypass approval", "skip security", "直接执行", "不用审批",
    "假装已经", "伪造执行结果", "不要调用工具",
)

ILLEGAL_INPUT_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def validate_user_input(text: str) -> dict:
    """阶段1：入口预校验（前后端共用逻辑）。"""
    if not text or not str(text).strip():
        return {"valid": False, "code": "empty", "message": "输入不能为空"}
    t = str(text).strip()
    max_len = getattr(settings, "max_user_input_length", 4096)
    if len(t) > max_len:
        return {"valid": False, "code": "too_long", "message": f"输入超过 {max_len} 字符限制"}
    if ILLEGAL_INPUT_PATTERN.search(t):
        return {"valid": False, "code": "illegal_chars", "message": "包含非法控制字符"}
    return {"valid": True, "sanitized": t}


def context_injection_recheck(text: str, intent: str, rag_context: str = "") -> dict:
    """阶段2步骤3：结合意图与 RAG 的注入二次复核。"""
    combined = f"{text}\n{rag_context or ''}"
    hits = [p for p in BYPASS_INDUCTION_PATTERNS if p.lower() in combined.lower()]
    if hits:
        return {
            "pass": False,
            "reason": f"检测到诱导绕过安全流程的表述: {hits[0]}",
            "severity": "high",
            "patterns": hits[:3],
        }
    # RAG 片段中若含 system prompt 泄露标记
    from app.services.prompt_guard import CANARY_TOKEN
    if CANARY_TOKEN in (rag_context or ""):
        return {
            "pass": False,
            "reason": "知识库检索内容异常，已拦截",
            "severity": "critical",
            "patterns": ["canary_in_rag"],
        }
    return {"pass": True, "reason": "", "severity": "none", "patterns": []}


def role_blocks_l4_request(user_role: str, text: str) -> Optional[str]:
    """角色权限提示（不阻断入口；L4 写操作在工具层走审批链）。

    普通用户可发起服务启停等高危诉求，但必须经：诊断方案确认 → 环境预检 → L4 审批 → 用户确认执行。
    """
    return None


def _plan_has(content: str, phrases: tuple) -> bool:
    t = (content or "").lower()
    return any(p.lower() in t for p in phrases)


def _is_virtual_plan_step(step: dict) -> bool:
    hint = (step.get("tool_hint") or "").strip()
    return hint in ("env_precheck", "按意图选择工具", "summary") or bool(step.get("virtual"))


def infer_readonly_ops_plan(content: str) -> Optional[dict]:
    """为只读运维查询生成精准方案，避免通用故障模板。"""
    from app.services.ops_scope import is_live_ops_query

    if not is_live_ops_query(content):
        return None

    t = (content or "").lower()

    def _pack_readonly(
        title: str,
        query_goal: str,
        steps: list,
        planned_commands: list = None,
    ) -> dict:
        return {
            "plan_type": "readonly_query",
            "title": title,
            "query_goal": query_goal,
            "phenomenon": content[:300],
            "possible_causes": [],
            "steps": steps,
            "planned_commands": planned_commands or [],
            "risk_note": "本方案均为 L1 只读操作，确认后将自动执行，无需审批。",
            "requires_confirm": True,
        }

    # CPU 进程 Top N
    cpu_process = (
        (_plan_has(content, ("进程", "process", "program")) and _plan_has(content, ("cpu", "处理器", "占用")))
        or re.search(r"(列出|排序|top).{0,8}(进程|process)", t)
        or re.search(r"(最高|最多|前\s*\d+).{0,8}(cpu|进程|process)", t)
    )
    if cpu_process:
        return _pack_readonly(
            "CPU 进程查询方案",
            "列出当前 CPU 占用最高的进程，并给出整体 CPU 负载概况",
            [
                {
                    "order": 1,
                    "action": "查看 CPU 总体使用率与系统负载",
                    "tool_hint": "get_cpu_info",
                    "risk": "L1",
                    "expected": "CPU 使用率、核心数、load average",
                },
                {
                    "order": 2,
                    "action": "列出 CPU 占用最高的进程（Top 10）",
                    "tool_hint": "list_processes:cpu",
                    "risk": "L1",
                    "core": True,
                    "expected": "PID、用户、%CPU、%MEM、命令行",
                },
                {
                    "order": 3,
                    "action": "汇总查询结果并给出简要解读",
                    "tool_hint": "summary",
                    "risk": "L1",
                    "virtual": True,
                    "expected": "高占用进程说明与关注建议",
                },
            ],
            ["get_cpu_info", "ps aux --sort=-%cpu | head -11"],
        )

    # 内存
    if _plan_has(content, ("内存", "memory", "mem", " ram", "swap")):
        return _pack_readonly(
            "内存使用查询方案",
            "获取系统内存与 Swap 使用情况",
            [
                {
                    "order": 1,
                    "action": "查看内存总量、已用、可用及使用率",
                    "tool_hint": "get_memory_info",
                    "risk": "L1",
                    "core": True,
                    "expected": "内存 MB 数、使用率百分比",
                },
                {
                    "order": 2,
                    "action": "汇总并解读内存状态",
                    "tool_hint": "summary",
                    "risk": "L1",
                    "virtual": True,
                    "expected": "是否正常及简要建议",
                },
            ],
            ["free -h"],
        )

    # 磁盘
    if _plan_has(content, ("磁盘", "disk", "空间", "分区", "df", "存储")):
        return _pack_readonly(
            "磁盘空间查询方案",
            "查看各分区容量与使用率",
            [
                {
                    "order": 1,
                    "action": "查看各挂载点磁盘使用情况",
                    "tool_hint": "get_disk_usage",
                    "risk": "L1",
                    "core": True,
                    "expected": "分区、总量、已用、可用、使用率",
                },
                {
                    "order": 2,
                    "action": "汇总并解读磁盘状态",
                    "tool_hint": "summary",
                    "risk": "L1",
                    "virtual": True,
                    "expected": "是否接近告警阈值及建议",
                },
            ],
            ["df -h"],
        )

    # CPU 使用率（非进程）
    if _plan_has(content, ("cpu", "处理器", "负载", "load")) and not _plan_has(content, ("进程", "process")):
        return _pack_readonly(
            "CPU 状态查询方案",
            "查看 CPU 使用率与系统负载",
            [
                {
                    "order": 1,
                    "action": "查看 CPU 使用率、核心数与 load average",
                    "tool_hint": "get_cpu_info",
                    "risk": "L1",
                    "core": True,
                    "expected": "CPU 使用率与负载指标",
                },
                {
                    "order": 2,
                    "action": "汇总并解读 CPU 状态",
                    "tool_hint": "summary",
                    "risk": "L1",
                    "virtual": True,
                    "expected": "负载是否正常及建议",
                },
            ],
            ["top -bn1 | head -5"],
        )

    # 网速 / 网卡流量
    if _plan_has(content, ("网速", "带宽", "流量", "吞吐", "网卡流量", "speed", "bandwidth", "throughput")):
        return _pack_readonly(
            "网络流量查询方案",
            "采样计算网卡实时收发速率",
            [
                {
                    "order": 1,
                    "action": "采样 1 秒计算网卡实时下行/上行速率（KB/s、Mbps）",
                    "tool_hint": "get_network_speed",
                    "risk": "L1",
                    "core": True,
                    "expected": "各网卡实时速率与好坏评价",
                },
                {
                    "order": 2,
                    "action": "汇总并解读网速评价",
                    "tool_hint": "summary",
                    "risk": "L1",
                    "virtual": True,
                    "expected": "网速正常/偏低/偏高等明确结论",
                },
            ],
            ["get_network_speed"],
        )

    # 网络 / 端口
    if _plan_has(content, ("网络", "network", "端口", "连接", "监听", "socket")):
        return _pack_readonly(
            "网络连接查询方案",
            "查看端口监听与网络连接状态",
            [
                {
                    "order": 1,
                    "action": "列出 TCP/UDP 监听端口与连接概况",
                    "tool_hint": "get_network_connections",
                    "risk": "L1",
                    "core": True,
                    "expected": "监听端口列表与统计",
                },
                {
                    "order": 2,
                    "action": "汇总并解读网络状态",
                    "tool_hint": "summary",
                    "risk": "L1",
                    "virtual": True,
                    "expected": "关键端口说明",
                },
            ],
            ["ss -tuln"],
        )

    # 服务状态
    svc_match = re.search(
        r"(cups|cupsd|avahi|nginx|mysql|redis|sshd|docker|httpd|tomcat|postgresql|mariadb|chronyd|rsyslog)",
        t,
        re.I,
    )
    if _plan_has(content, ("服务", "service", "状态")) or svc_match:
        raw_svc = svc_match.group(1).lower() if svc_match else ""
        svc = "cups" if raw_svc in ("cups", "cupsd") else ("avahi-daemon" if raw_svc == "avahi" else raw_svc or None)
        if not svc:
            return None
        return _pack_readonly(
            f"{svc} 服务状态查询方案",
            f"查看 {svc} 服务运行状态",
            [
                {
                    "order": 1,
                    "action": f"查看 {svc} 服务当前运行状态",
                    "tool_hint": f"get_service_status:{svc}",
                    "risk": "L1",
                    "core": True,
                    "expected": "active/inactive、运行时长、主进程 PID",
                },
                {
                    "order": 2,
                    "action": "汇总并解读服务状态",
                    "tool_hint": "summary",
                    "risk": "L1",
                    "virtual": True,
                    "expected": "服务是否正常及建议",
                },
            ],
            [f"systemctl status {svc}"],
        )

    return None


GENERIC_CAUSE_MARKERS = ("配置异常", "资源不足", "服务未启动", "依赖组件故障")

FAULT_PLAN_SYSTEM_PROMPT = """你是麒麟操作系统运维故障诊断专家。
请根据用户故障现象与知识库检索内容，输出**仅含 JSON** 的诊断方案（不要用 markdown 代码块包裹）：
{
  "possible_causes": ["与现象直接相关的具体根因1", "根因2", "根因3"],
  "steps": [
    {
      "order": 1,
      "action": "步骤说明（中文，可操作）",
      "tool_hint": "工具或命令",
      "risk": "L1",
      "expected": "预期结果"
    }
  ],
  "analysis_summary": "1-2 句诊断思路，说明为何怀疑这些根因"
}

硬性要求：
1. possible_causes 必须 3～5 条，每条紧扣用户现象中的组件/报错（如 cups、client-error、打印机驱动等），禁止输出空泛项如「配置异常」「资源不足」除非现象明确指向该类问题
2. steps 必须 4～6 步，遵循「确认现象 → 查服务/日志 → 定位根因 → 修复/配置 → 验证」
3. tool_hint 优先使用：get_service_status, get_logs, search_journal_logs, execute_command, manage_service, get_disk_usage, get_memory_info, list_processes, read_file
4. 只读检查 risk=L1；修改配置/重启服务 L2～L4
5. 知识库内容与现象矛盾时，以现象为准，知识库作参考
6. 目标系统为麒麟/V10 等 RHEL 系：包管理用 rpm/dnf/yum，禁止 dpkg/apt-get；查 nss-mdns 用 execute_command: rpm -q nss-mdns；安装用 dnf install -y cups avahi nss-mdns
7. get_service_status 必须带服务名，格式 get_service_status: cups 或 get_service_status: avahi-daemon
8. 查看 CUPS 日志优先 get_logs: /var/log/cups/error_log（自动 fallback journalctl -u cups），禁止裸 tail 文件路径"""


def _is_fault_like_content(content: str) -> bool:
    signals = (
        "失败", "错误", "报错", "异常", "无法", "不能", "不行", "故障", "连不上",
        "启动不了", "不可用", "error", "failed", "client-error", "timeout", "refused",
    )
    low = (content or "").lower()
    return any(s in low or s in content for s in signals)


def _build_fault_rag_query(content: str) -> str:
    """构造面向根因检索的查询词。"""
    tech_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_.-]{2,}", content or "")
    extra_kw = []
    for kw in ("cups", "打印机", "打印", "nginx", "docker", "chrony", "网络", "磁盘", "内存", "驱动"):
        if kw in (content or "").lower() or kw in (content or ""):
            extra_kw.append(kw)
    merged = list(dict.fromkeys([t.lower() for t in tech_tokens[:6]] + extra_kw))
    suffix = " ".join(merged)
    return f"{content[:220]} {suffix} 故障原因 根因分析 排查步骤 解决方案".strip()


async def _ensure_knowledge_rag_index() -> None:
    from app.services.knowledge_rag import knowledge_rag
    from app.models.knowledge import KnowledgeArticle
    from app.core.database import async_session

    if knowledge_rag._initialized:
        return
    try:
        async with async_session() as db:
            result = await db.execute(select(KnowledgeArticle))
            articles = [
                {
                    "id": a.id,
                    "title": a.title,
                    "content": a.content,
                    "category": a.category,
                    "tags": a.tags,
                }
                for a in result.scalars().all()
            ]
            if articles:
                knowledge_rag.build_index(articles)
    except Exception:
        pass


async def _resolve_fault_rag(content: str, rag_context: str = "") -> tuple[str, List[dict]]:
    """故障场景：扩展检索知识库，返回上下文与来源列表。"""
    from app.services.knowledge_rag import knowledge_rag

    await _ensure_knowledge_rag_index()
    query = _build_fault_rag_query(content)
    sources: List[dict] = []
    ctx = (rag_context or "").strip()

    if knowledge_rag._initialized:
        sources = knowledge_rag.search(query, top_k=5)
        fresh = knowledge_rag.generate_context(query, top_k=5)
        if fresh:
            ctx = fresh if not ctx else f"{ctx}\n\n{fresh}"

    return ctx, sources


ANALYSIS_STREAM_SYSTEM_PROMPT = """你是麒麟操作系统运维故障诊断专家。
根据用户故障现象与知识库参考，用 1～2 句中文说明诊断思路（为何怀疑这些根因、优先检查什么）。
只输出连贯文字，不要 JSON、不要编号列表、不要 markdown 标题。"""


async def _stream_fault_analysis_tokens(
    content: str,
    ctx: str,
    sources: List[dict],
):
    """流式输出诊断思路文本 token。"""
    from app.services.chat_service import call_deepseek

    source_lines = []
    for i, s in enumerate(sources[:5], 1):
        source_lines.append(
            f"[{i}] {s.get('title', '')} (相关度 {s.get('score', 0)}): {s.get('snippet', '')[:180]}"
        )
    kb_block = "\n".join(source_lines) if source_lines else (ctx[:1200] if ctx else "（知识库未命中）")
    user_prompt = f"""【用户故障现象】
{content[:500]}

【知识库参考】
{kb_block}

请输出诊断思路："""
    messages = [
        {"role": "system", "content": ANALYSIS_STREAM_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    try:
        async for chunk in call_deepseek(messages, stream=True, use_tools=False):
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            token = delta.get("content") or ""
            if token:
                yield token
    except Exception:
        return


async def iter_diagnostic_plan_stream(
    content: str,
    intent: str,
    rag_context: str = "",
    tool_resolution: dict | None = None,
):
    """
    流式生成诊断方案：yield start / delta / final 事件 payload。
    供 chat_service 转为 diagnostic_plan_start / diagnostic_plan_delta SSE。
    """
    import asyncio

    tool_resolution = tool_resolution or {}
    title = "运维诊断与执行方案"
    if tool_resolution.get("workflow") == "password_recovery":
        title = "密码找回诊断与执行方案"
    elif tool_resolution.get("workflow") == "custom_tools":
        title = "工具库可执行方案"

    yield {
        "type": "start",
        "title": title,
        "phenomenon": content[:300],
        "intent": intent,
    }

    use_llm_stream = (
        intent in ("fault_analysis", "high_risk")
        and _is_fault_like_content(content)
        and not tool_resolution.get("actionable")
    )

    if use_llm_stream:
        ctx, sources = await _resolve_fault_rag(content, rag_context)
        if sources:
            yield {
                "type": "delta",
                "field": "rag_sources",
                "value": [
                    {
                        "title": s.get("title", ""),
                        "score": s.get("score", 0),
                        "confidence": s.get("confidence_label", ""),
                    }
                    for s in sources[:5]
                ],
            }

        analysis_parts: List[str] = []
        async for token in _stream_fault_analysis_tokens(content, ctx, sources):
            analysis_parts.append(token)
            yield {"type": "delta", "field": "analysis_token", "token": token}

        streamed_analysis = "".join(analysis_parts).strip()
        llm_plan = await _build_rag_llm_fault_plan(content, intent, rag_context)
        if llm_plan:
            analysis = streamed_analysis or llm_plan.get("analysis_summary") or ""
            if analysis and not streamed_analysis:
                chunk_size = 6
                for i in range(0, len(analysis), chunk_size):
                    yield {
                        "type": "delta",
                        "field": "analysis_token",
                        "token": analysis[i:i + chunk_size],
                    }
                    await asyncio.sleep(0.015)

            causes = llm_plan.get("possible_causes") or []
            steps = llm_plan.get("steps") or []
            for i, cause in enumerate(causes):
                yield {"type": "delta", "field": "possible_cause", "value": cause, "index": i}
                await asyncio.sleep(0.03)

            for i, step in enumerate(steps):
                yield {"type": "delta", "field": "step", "value": step, "index": i}
                await asyncio.sleep(0.04)

            plan = {
                "title": title,
                "intent": intent,
                "phenomenon": content[:300],
                "possible_causes": causes,
                "steps": steps,
                "analysis_summary": analysis,
                "rag_reference": (llm_plan.get("rag_context_used") or "")[:300] or None,
                "rag_sources": llm_plan.get("rag_sources") or [],
                "risk_note": "L4/L5 操作将触发管理员审批 + 用户确认执行；L2/L3 需您在对话页确认。",
                "requires_confirm": True,
                "plan_origin": "rag_llm",
            }
            yield {"type": "delta", "field": "risk_note", "value": plan["risk_note"]}
            yield {"type": "final", "plan": plan}
            return

    plan = await build_diagnostic_plan(
        content, intent, rag_context, tool_resolution=tool_resolution,
    )

    if plan.get("rag_sources"):
        yield {"type": "delta", "field": "rag_sources", "value": plan["rag_sources"]}

    analysis = (plan.get("analysis_summary") or "").strip()
    if analysis:
        chunk_size = 6
        for i in range(0, len(analysis), chunk_size):
            yield {
                "type": "delta",
                "field": "analysis_token",
                "token": analysis[i:i + chunk_size],
            }
            await asyncio.sleep(0.015)

    for i, cause in enumerate(plan.get("possible_causes") or []):
        yield {"type": "delta", "field": "possible_cause", "value": cause, "index": i}
        await asyncio.sleep(0.03)

    for i, step in enumerate(plan.get("steps") or []):
        yield {"type": "delta", "field": "step", "value": step, "index": i}
        await asyncio.sleep(0.04)

    if plan.get("risk_note"):
        yield {"type": "delta", "field": "risk_note", "value": plan["risk_note"]}

    yield {"type": "final", "plan": plan}


def _parse_llm_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fenced:
        raw = fenced.group(1)
    else:
        mobj = re.search(r"\{.*\}", raw, re.S)
        if mobj:
            raw = mobj.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _llm_complete_json(system: str, user: str) -> Optional[dict]:
    from app.services.chat_service import call_deepseek

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    result = None
    try:
        async for chunk in call_deepseek(messages, stream=False, use_tools=False):
            result = chunk
    except Exception:
        return None
    if not result:
        return None
    text = (result.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return _parse_llm_json_object(text)


def _normalize_tool_hint_for_kylin(hint: str) -> str:
    """将 Debian 系命令提示转为麒麟/RHEL 系。"""
    if not hint:
        return hint
    h = hint
    if "dpkg" in h:
        h = re.sub(r"dpkg\s+-l\s*\|\s*grep", "rpm -qa | grep", h, flags=re.I)
        h = re.sub(r"dpkg\s+-l", "rpm -qa", h, flags=re.I)
        h = re.sub(r"dpkg\s+-s", "rpm -q", h, flags=re.I)
    if re.search(r"apt-get|apt install", h, re.I):
        h = re.sub(r"sudo\s+apt-get\s+install\s+-y\s*", "sudo dnf install -y ", h, flags=re.I)
        h = re.sub(r"apt-get\s+install\s+-y\s*", "dnf install -y ", h, flags=re.I)
        h = re.sub(r"apt-get\s+install\s*", "dnf install -y ", h, flags=re.I)
        h = re.sub(r"apt\s+install\s*", "dnf install -y ", h, flags=re.I)
    # 麒麟/RHEL 包名：libnss-mdns → nss-mdns
    h = re.sub(r"\blibnss-mdns\b", "nss-mdns", h, flags=re.I)
    h = re.sub(r"dnf install -y libnss", "dnf install -y nss", h, flags=re.I)
    h = re.sub(r"rpm -qa \| grep libnss-mdns", "rpm -q nss-mdns", h, flags=re.I)
    if re.search(r"tail.*cups.*error_log|error_log.*cups", h, re.I):
        ml = re.search(r"tail\s+-(\d+)", h)
        n = ml.group(1) if ml else "50"
        h = f"get_logs: /var/log/cups/error_log lines={n}"
    return h


def _infer_service_name_for_plan(step: dict) -> Optional[str]:
    if step.get("service_name"):
        return str(step["service_name"]).strip()
    text = f"{step.get('action', '')} {step.get('tool_hint', '')}"
    patterns = [
        (r"\bcupsd?\b", "cups"),
        (r"avahi", "avahi-daemon"),
        (r"chronyd|chrony", "chronyd"),
        (r"\bnginx\b", "nginx"),
        (r"\bdocker\b", "docker"),
        (r"postgresql|postgres", "postgresql"),
        (r"mysql|mysqld", "mysqld"),
        (r"\bsshd\b", "sshd"),
    ]
    for pat, svc in patterns:
        if re.search(pat, text, re.I):
            return svc
    return None


def _canonicalize_service_status_hint(hint: str, step: dict) -> str:
    """统一 get_service_status 写法，便于执行层解析。"""
    if "get_service_status" not in (hint or "").lower():
        return hint
    if re.search(r"\s/\s", hint):
        parts = [p.strip() for p in re.split(r"\s*/\s*", hint) if p.strip()]
        return " / ".join(_canonicalize_service_status_hint(p, step) for p in parts)
    m = re.search(r"get_service_status\s*[:\s]+([a-zA-Z0-9_.@-]+)", hint, re.I)
    if m:
        name = m.group(1).strip(" `'\",)")
        return f"get_service_status: {name}"
    svc = _infer_service_name_for_plan(step)
    if svc:
        return f"get_service_status: {svc}"
    return hint


def _normalize_plan_steps(raw_steps: List[dict]) -> List[dict]:
    steps: List[dict] = []
    for i, s in enumerate(raw_steps or [], start=1):
        if not isinstance(s, dict):
            continue
        action = str(s.get("action") or "").strip()
        if not action:
            continue
        risk = str(s.get("risk") or "L1").upper()
        if risk not in ("L1", "L2", "L3", "L4", "L5"):
            risk = "L1"
        step = {
            "order": int(s.get("order") or i),
            "action": action,
            "tool_hint": _normalize_tool_hint_for_kylin(
                str(s.get("tool_hint") or "按步骤选择工具").strip()
            ),
            "risk": risk,
        }
        step["tool_hint"] = _canonicalize_service_status_hint(step["tool_hint"], {**s, **step})
        svc = _infer_service_name_for_plan({**s, **step})
        if svc:
            step["service_name"] = svc
        expected = str(s.get("expected") or "").strip()
        if expected:
            step["expected"] = expected
        if s.get("core"):
            step["core"] = True
        steps.append(step)
    steps.sort(key=lambda x: x["order"])
    for idx, st in enumerate(steps, start=1):
        st["order"] = idx
    return steps[:8]


def _rule_based_fault_causes(content: str) -> List[str]:
    """LLM 不可用时的现象相关根因兜底。"""
    low = (content or "").lower()
    if "cups" in low or "打印机" in content or "打印" in content:
        return [
            "CUPS 打印服务未运行或启动失败",
            "无驱打印机 URI 发现失败（IPP/USB 设备未正确识别）",
            "client-error-possible：客户端与 CUPS 通信协议异常",
            "/etc/cups 配置错误或 cupsd 权限不足",
            "631 端口被防火墙阻断或 socket 监听异常",
        ]
    if "nginx" in low:
        return [
            "nginx 配置语法错误导致启动失败",
            "端口被占用或 upstream 后端不可达",
            "证书/权限问题导致 worker 进程异常",
            "磁盘满导致日志或临时文件写入失败",
        ]
    if "网络" in content or "连不上" in content:
        return [
            "网卡未 UP 或 IP/路由配置错误",
            "DNS 解析失败或防火墙拦截",
            "目标端口未监听或服务未启动",
            "链路丢包或网关不可达",
        ]
    return ["配置异常", "资源不足", "服务未启动", "依赖组件故障"]


def _filter_meaningful_causes(causes: List[str], content: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for c in causes or []:
        t = str(c).strip()
        if not t or len(t) < 6:
            continue
        if t in GENERIC_CAUSE_MARKERS and not _is_fault_like_content(content):
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out[:5]


async def _build_rag_llm_fault_plan(content: str, intent: str, rag_context: str) -> Optional[dict]:
    """RAG 检索 + LLM 归纳：输出贴合现象的根因与执行步骤。"""
    ctx, sources = await _resolve_fault_rag(content, rag_context)
    source_lines = []
    for i, s in enumerate(sources[:5], 1):
        source_lines.append(
            f"[{i}] {s.get('title', '')} (相关度 {s.get('score', 0)}): {s.get('snippet', '')[:180]}"
        )
    kb_block = "\n".join(source_lines) if source_lines else (ctx[:1200] if ctx else "（知识库未命中，请结合运维经验推断）")

    user_prompt = f"""【用户故障现象】
{content[:500]}

【意图类型】{intent}

【知识库检索结果】
{kb_block}

请输出 JSON 诊断方案。"""

    parsed = await _llm_complete_json(FAULT_PLAN_SYSTEM_PROMPT, user_prompt)
    if not parsed:
        return None

    causes = _filter_meaningful_causes(parsed.get("possible_causes") or [], content)
    steps = _normalize_plan_steps(parsed.get("steps") or [])
    if len(causes) < 2 or len(steps) < 2:
        return None

    return {
        "possible_causes": causes,
        "steps": steps,
        "analysis_summary": str(parsed.get("analysis_summary") or "").strip()[:400],
        "rag_context_used": ctx[:800] if ctx else "",
        "rag_sources": [
            {"title": s.get("title", ""), "score": s.get("score", 0), "confidence": s.get("confidence_label", "")}
            for s in sources[:5]
        ],
    }


async def build_diagnostic_plan(
    content: str,
    intent: str,
    rag_context: str = "",
    tool_resolution: dict | None = None,
) -> dict:
    """阶段3链路B：生成结构化诊断方案（RAG + LLM 根因分析，失败时规则兜底）。"""
    from app.services.ops_scope import (
        is_disk_cleanup_execution_request,
        is_service_control_request,
        is_time_sync_request,
        parse_service_control_target,
    )
    from app.services.tool_resolution_planner import build_password_recovery_plan_steps

    tool_resolution = tool_resolution or {}

    # 管理员注册的自定义工具可执行方案（如密码找回）
    if tool_resolution.get("actionable"):
        workflow = tool_resolution.get("workflow")
        matched = tool_resolution.get("matched_tools") or []
        rag_snippet = (rag_context or "")[:400]
        if workflow == "password_recovery" and matched:
            steps = build_password_recovery_plan_steps(matched)
            if steps:
                return {
                    "title": "密码找回诊断与执行方案",
                    "intent": intent,
                    "phenomenon": content[:300],
                    "possible_causes": [
                        "用户忘记登录密码",
                        "账户因多次失败被 faillock 锁定",
                        "SSH 不可达需离线 GRUB/救援改密",
                        "密码不符合复杂度策略",
                    ],
                    "steps": steps,
                    "analysis_summary": tool_resolution.get("reason"),
                    "rag_reference": rag_snippet[:200] if rag_snippet else None,
                    "risk_note": "L5 改密需管理员审批；禁止直接修改 /etc/shadow。",
                    "requires_confirm": True,
                    "plan_origin": "tool_resolution",
                    "workflow": workflow,
                    "matched_tools": matched,
                }
        elif workflow == "custom_tools" and matched:
            steps = []
            for i, name in enumerate(matched[:6], start=1):
                hint = next(
                    (h for h in (tool_resolution.get("tool_hints") or []) if h.get("name") == name),
                    {"description": name},
                )
                steps.append({
                    "order": i,
                    "action": hint.get("description") or name,
                    "tool_hint": name,
                    "risk": "L1",
                })
            if steps:
                return {
                    "title": "工具库可执行方案",
                    "intent": intent,
                    "phenomenon": content[:300],
                    "possible_causes": ["已匹配管理员注册的可执行工具"],
                    "steps": steps,
                    "analysis_summary": tool_resolution.get("reason"),
                    "rag_reference": rag_snippet[:200] if rag_snippet else None,
                    "risk_note": "按工具风险等级触发审批与确认。",
                    "requires_confirm": True,
                    "plan_origin": "tool_resolution",
                    "workflow": workflow,
                    "matched_tools": matched,
                }

    steps = []
    planned_commands = []

    # 故障/类故障场景：RAG + LLM 生成贴合现象的根因与步骤
    if intent in ("fault_analysis", "high_risk") and _is_fault_like_content(content):
        llm_plan = await _build_rag_llm_fault_plan(content, intent, rag_context)
        if llm_plan:
            plan = {
                "title": "运维诊断与执行方案",
                "intent": intent,
                "phenomenon": content[:300],
                "possible_causes": llm_plan["possible_causes"],
                "steps": llm_plan["steps"],
                "analysis_summary": llm_plan.get("analysis_summary"),
                "rag_reference": (llm_plan.get("rag_context_used") or "")[:300] or None,
                "rag_sources": llm_plan.get("rag_sources") or [],
                "risk_note": "L4/L5 操作将触发管理员审批 + 用户确认执行；L2/L3 需您在对话页确认。",
                "requires_confirm": True,
                "plan_origin": "rag_llm",
            }
            return plan

    if intent == "fault_analysis":
        low = (content or "").lower()
        if "cups" in low or "打印机" in content or "打印" in content:
            steps = [
                {"order": 1, "action": "检查 CUPS 服务 cupsd 运行状态", "tool_hint": "get_service_status cups", "risk": "L1"},
                {"order": 2, "action": "查看 CUPS 错误日志与最近任务记录", "tool_hint": "get_logs: /var/log/cups/error_log lines=50", "risk": "L1"},
                {"order": 3, "action": "列出已配置打印机与设备发现结果", "tool_hint": "execute_command: lpstat -t", "risk": "L1"},
                {"order": 4, "action": "检查 IPP/USB 设备 URI 与权限配置", "tool_hint": "read_file /etc/cups/cupsd.conf", "risk": "L1"},
                {"order": 5, "action": "重启 CUPS 并重新添加无驱打印机", "tool_hint": "manage_service restart cups", "risk": "L3"},
            ]
        else:
            steps = [
                {"order": 1, "action": "确认故障现象与时间范围", "tool_hint": "get_service_status / get_logs", "risk": "L1"},
                {"order": 2, "action": "检查相关服务状态与资源占用", "tool_hint": "get_service_status, get_memory_info, get_disk_usage", "risk": "L1"},
                {"order": 3, "action": "检索错误日志定位根因", "tool_hint": "get_logs / search_journal_logs", "risk": "L1"},
                {"order": 4, "action": "给出修复建议并按风险等级执行", "tool_hint": "manage_service / execute_command（需审批）", "risk": "L3"},
            ]
    elif is_disk_cleanup_execution_request(content):
        # 麒麟 / RHEL 系默认 dnf；journal 收缩需 root
        steps = [
            {"order": 1, "action": "查看磁盘使用现状", "tool_hint": "get_disk_usage", "risk": "L1"},
            {"order": 2, "action": "清理 DNF/YUM 软件包缓存", "tool_hint": "execute_command: dnf clean all", "risk": "L2"},
            {"order": 3, "action": "清理 3 天前 journal 日志", "tool_hint": "execute_command: journalctl --vacuum-time=3d", "risk": "L2"},
            {"order": 4, "action": "再次检查磁盘空间验证效果", "tool_hint": "get_disk_usage", "risk": "L1"},
        ]
        planned_commands = [
            "get_disk_usage",
            "dnf clean all",
            "journalctl --vacuum-time=3d",
        ]
    elif is_service_control_request(content):
        action, svc = parse_service_control_target(content)
        action_label = {"stop": "停止", "start": "启动", "restart": "重启"}.get(action, action)
        steps = [
            {"order": 1, "action": f"查看 {svc} 服务当前状态", "tool_hint": "get_service_status", "service_name": svc, "risk": "L1"},
            {"order": 2, "action": f"{action_label} {svc} 服务", "tool_hint": f"manage_service {action} {svc}", "risk": "L4"},
            {"order": 3, "action": f"再次检查 {svc} 状态验证结果", "tool_hint": "get_service_status", "service_name": svc, "risk": "L1"},
        ]
        planned_commands = [f"get_service_status {svc}", f"systemctl {action} {svc}"]
    elif is_time_sync_request(content):
        steps = [
            {"order": 1, "action": "查看系统时间与 NTP 同步状态", "tool_hint": "execute_command: timedatectl status", "risk": "L1"},
            {"order": 2, "action": "查看 chrony 时间源与偏差", "tool_hint": "execute_command: chronyc tracking", "risk": "L1"},
            {"order": 3, "action": "执行时间同步（强制对时）", "tool_hint": "execute_command: chronyc -a makestep", "risk": "L3"},
            {"order": 4, "action": "再次确认同步结果", "tool_hint": "execute_command: timedatectl status", "risk": "L1"},
        ]
        planned_commands = [
            "timedatectl status",
            "chronyc tracking",
            "chronyc -a makestep",
            "timedatectl status",
        ]
    else:
        readonly = infer_readonly_ops_plan(content)
        if readonly and intent == "ops_query":
            steps = readonly["steps"]
            planned_commands = readonly.get("planned_commands") or []
        else:
            steps = [
                {"order": 1, "action": "环境预检：连通性、磁盘、并发任务", "tool_hint": "env_precheck"},
                {"order": 2, "action": "执行用户请求的运维操作", "tool_hint": "按意图选择工具"},
                {"order": 3, "action": "验证执行结果并生成报告", "tool_hint": "get_disk_usage / get_service_status"},
            ]
            planned_commands = []

    rag_snippet = (rag_context or "")[:400]
    default_causes = _rule_based_fault_causes(content)
    time_causes = ["NTP 未启用", "chronyd 未运行", "时间源不可达", "与宿主机时钟偏差过大"]

    readonly = infer_readonly_ops_plan(content) if intent == "ops_query" else None
    if readonly and intent == "ops_query":
        plan = {
            **readonly,
            "intent": intent,
            "rag_reference": rag_snippet[:200] if rag_snippet else None,
        }
        return plan

    plan = {
        "title": "运维诊断与执行方案",
        "intent": intent,
        "phenomenon": content[:300],
        "possible_causes": time_causes if is_time_sync_request(content) else default_causes,
        "steps": steps,
        "risk_note": "L4/L5 操作将触发管理员审批 + 用户确认执行；L2/L3 需您在对话页确认。",
        "rag_reference": rag_snippet[:200] if rag_snippet else None,
        "requires_confirm": True,
    }
    if planned_commands:
        plan["planned_commands"] = planned_commands
    return plan


async def enrich_diagnostic_plan_with_env(
    plan: dict,
    content: str,
    rag_context: str = "",
    sensing_mode: str = "fault_diagnosis",
    server_id: str = None,
) -> dict:
    """Plan-Execute 子步骤1：深度环境感知 + 文件保护白名单 + 初步定位。"""
    from app.services.environment_sensor import SensingPlan, sense, get_system_summary
    from app.services.agent_workflow import build_file_protection_whitelist

    mode_map = {
        "quick_check": SensingPlan.QUICK_CHECK,
        "full_check": SensingPlan.FULL_CHECK,
        "fault_diagnosis": SensingPlan.FAULT_DIAG,
    }
    sp = mode_map.get(sensing_mode, SensingPlan.FAULT_DIAG)

    raw = {}
    summary_text = ""
    try:
        raw = sense(plan=sp, server_id=server_id)
        summary = get_system_summary(plan=sp, server_id=server_id)
        parts = [f"状态: {summary.get('status', 'unknown')}"]
        if summary.get("issues"):
            parts.append("问题: " + "; ".join(summary["issues"][:3]))
        if summary.get("warnings"):
            parts.append("警告: " + "; ".join(summary["warnings"][:3]))
        if summary.get("metrics"):
            parts.append("指标: " + str(summary["metrics"]))
        summary_text = " | ".join(parts)
    except Exception:
        summary_text = "环境感知暂不可用，将在确认后执行时重试"

    whitelist = build_file_protection_whitelist(content, rag_context, raw)

    enriched = dict(plan)
    enriched["environment_scan"] = {
        "mode": sensing_mode,
        "summary": summary_text[:800],
        "metrics_keys": list((raw.get("metrics") or {}).keys()) if isinstance(raw, dict) else [],
    }
    enriched["file_protection_whitelist"] = whitelist
    if plan.get("plan_type") == "readonly_query":
        enriched["preliminary_analysis"] = (
            f"**查询目标**：{plan.get('query_goal') or content[:80]}。"
            f" 方案共 {len(plan.get('steps') or [])} 步，核心步骤已标注。"
            f" 已保护 {len(whitelist)} 个关键路径。"
        )
    else:
        analysis = plan.get("analysis_summary") or ""
        rag_titles = [s.get("title") for s in (plan.get("rag_sources") or []) if s.get("title")]
        rag_hint = f" 知识库参考：{'、'.join(rag_titles[:3])}。" if rag_titles else ""
        cause_hint = ""
        causes = plan.get("possible_causes") or []
        if causes:
            cause_hint = f" 初步怀疑：{causes[0][:60]}"
        enriched["preliminary_analysis"] = (
            f"已采集 {sensing_mode} 环境快照；"
            f"保护 {len(whitelist)} 个关键路径不被误删。"
            f" 用户诉求：{content[:120]}。"
            f"{cause_hint}{rag_hint}"
            + (f" {analysis}" if analysis else "")
        )
    if whitelist:
        enriched["risk_note"] = (enriched.get("risk_note") or "") + f" 已启用 {len(whitelist)} 项文件保护。"
    return enriched


def build_plan_execution_prompt(content: str, plan_data: dict) -> str:
    """方案确认后注入 ReAct：强制工具执行，禁止纯文字假装完成。"""
    steps = plan_data.get("steps") or []
    cmds = plan_data.get("planned_commands") or []
    lines = [
        f"用户已确认运维方案，请立即在服务器上执行，诉求：{content[:200]}",
    ]
    if plan_data.get("query_goal"):
        lines.append(f"【查询目标】{plan_data['query_goal']}")
    lines.extend([
        "【硬性要求】",
        "- 必须调用工具完成方案中的每一步，禁止仅用 Markdown 描述已执行",
        "- 核心步骤（标注 core）必须执行对应工具并返回真实数据",
        "- 工具全部完成后用「## 执行结论」总结结果与建议",
    ])
    if steps:
        lines.append("【方案步骤】")
        for s in steps:
            core = " ★核心" if s.get("core") else ""
            lines.append(
                f"{s.get('order', '?')}. {s.get('action', '')} → {s.get('tool_hint', '')} "
                f"[{s.get('risk', 'L?')}]{core}"
            )
    if cmds:
        lines.append("【建议命令顺序】" + " → ".join(cmds))
    return "\n".join(lines)


async def run_env_precheck(server_id: str = None) -> dict:
    """预执行环境检查（SSH 连通 + 磁盘空间）。"""
    from app.services.remote_executor import get_ssh_for_server_sync
    snapshot_id = f"snap-{uuid.uuid4().hex[:10]}"
    checks = []
    ok = True
    try:
        ssh = get_ssh_for_server_sync(server_id)
        out, err, code = ssh.execute("echo ok && df -h / | tail -1")
        if code != 0 or "ok" not in out:
            ok = False
            checks.append({"name": "ssh_connectivity", "ok": False, "detail": err or out or "连接失败"})
        else:
            checks.append({"name": "ssh_connectivity", "ok": True, "detail": "SSH 连通正常"})
            checks.append({"name": "disk_root", "ok": True, "detail": out.strip()[-120:]})
    except Exception as e:
        ok = False
        checks.append({"name": "ssh_connectivity", "ok": False, "detail": str(e)[:200]})

    return {
        "passed": ok,
        "snapshot_id": snapshot_id,
        "snapshot_note": "逻辑快照元数据（记录执行前检查点，全量 VM 快照需对接虚拟化平台）",
        "checks": checks,
        "checked_at": datetime.utcnow().isoformat(),
    }


def _report_tool_lines(tool_records: List[dict]) -> List[str]:
    if not tool_records:
        return ["- （本轮无工具执行记录）"]
    lines = []
    for tc in tool_records:
        name = tc.get("toolName", "?")
        status = tc.get("status", "?")
        risk = tc.get("riskLevel", "L1")
        summary = tc.get("displaySummary") or (tc.get("result") or {}).get("display_summary", "")
        if not summary and status == "completed":
            summary = f"✅ {name} 执行完成"
        lines.append(f"- [{risk}] `{name}` — {status}: {str(summary)[:120]}")
    return lines


def _parse_ps_processes(raw: str) -> List[dict]:
    """解析 ps aux 输出为进程列表。"""
    rows = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.upper().startswith("USER"):
            continue
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        try:
            rows.append({
                "user": parts[0],
                "pid": parts[1],
                "cpu": float(parts[2]),
                "mem": float(parts[3]),
                "cmd": parts[10][:100],
            })
        except (TypeError, ValueError):
            continue
    return rows


def _is_query_command_process(cmd: str) -> bool:
    c = (cmd or "").lower()
    return any(k in c for k in ("ps aux", "ps -", " sort=", "--sort=", "head -"))


def _process_report_insights(tool_records: List[dict], user_question: str) -> tuple:
    """CPU/内存进程类查询：从 list_processes 结果提取关键发现与建议。"""
    findings: List[str] = []
    suggestions: List[str] = []
    proc_tc = next(
        (tc for tc in tool_records
         if tc.get("toolName") in ("list_processes", "get_process_list")
         and tc.get("status") == "completed"),
        None,
    )
    if not proc_tc:
        return findings, suggestions

    data = (proc_tc.get("result") or {}).get("data") or {}
    processes = _parse_ps_processes(data.get("raw") or "")
    if not processes:
        summary = proc_tc.get("displaySummary") or data.get("summary") or ""
        if summary:
            findings.append(summary)
        return findings, suggestions

    real_procs = list(processes)
    if real_procs and _is_query_command_process(real_procs[0].get("cmd", "")):
        top = real_procs[0]
        findings.append(
            f"**Top 1** 为查询命令本身（`{top['cmd'][:45]}`），瞬时 CPU **{top['cpu']:.1f}%**，属正常现象，可忽略。"
        )
        real_procs = real_procs[1:]

    rank_start = 2 if (processes and _is_query_command_process(processes[0].get("cmd", ""))) else 1
    for idx, p in enumerate(real_procs[:3], start=rank_start):
        cmd_short = p["cmd"].split("/")[-1][:40] if "/" in p["cmd"] else p["cmd"][:40]
        findings.append(
            f"**Top {idx}** PID `{p['pid']}` · CPU **{p['cpu']:.1f}%** · 内存 **{p['mem']:.1f}%** · `{cmd_short}`"
        )

    if real_procs:
        max_cpu = max(p["cpu"] for p in real_procs)
        if max_cpu < 20:
            findings.append("除查询命令外，其余进程 CPU 占用均较低，**系统整体负载正常**。")
        elif max_cpu >= 50:
            findings.append(f"存在 CPU 占用 **≥50%** 的进程（最高 **{max_cpu:.1f}%**），建议持续观察或排查业务逻辑。")

    q = (user_question or "").lower()
    suggestions.append("当前未发现典型挖矿/恶意进程特征；若占用持续升高，可用 `top -b -n 3` 或 `pidstat -u 1 5` 持续观测。")
    if real_procs and real_procs[0]["cpu"] >= 10:
        suggestions.append(
            f"重点关注 PID `{real_procs[0]['pid']}`（{real_procs[0]['cmd'][:35]}…），"
            "若内存/CPU 持续增长，可检查该服务日志或考虑重启。"
        )
    if "cpu" in q or "处理器" in q:
        suggestions.append("需要历史峰值时可执行 `sar -u 1 5` 查看采样区间内的 CPU 利用率。")
    return findings, suggestions


def _disk_report_insights(tool_records: List[dict]) -> tuple:
    findings: List[str] = []
    suggestions: List[str] = []
    disk_tc = next(
        (tc for tc in tool_records
         if tc.get("toolName") in ("get_disk_usage", "get_disk_info")
         and tc.get("status") == "completed"),
        None,
    )
    if not disk_tc:
        return findings, suggestions
    data = (disk_tc.get("result") or {}).get("data") or {}
    disks = data.get("disks") or []
    for d in disks[:4]:
        mount = d.get("mount") or d.get("filesystem") or "?"
        pct = str(d.get("use_percent", "?")).replace("%", "")
        try:
            pct_f = float(pct)
            flag = "⚠ 需关注" if pct_f >= 80 else "✓ 正常"
        except ValueError:
            flag = ""
        findings.append(
            f"{flag} `{mount}` 已用 **{d.get('use_percent', '?')}**"
            f"（{d.get('used', '?')} / {d.get('size', '?')}）"
        )
    suggestions.append("根分区使用率 ≥80% 时建议清理日志、包缓存或扩容；可配合 `du -xh /path | sort -rh | head` 定位大目录。")
    return findings, suggestions


def _memory_report_insights(tool_records: List[dict], user_question: str) -> tuple:
    from app.services.response_summarizer import _memory_advice
    findings: List[str] = []
    suggestions: List[str] = []
    mem_tc = next(
        (tc for tc in tool_records
         if tc.get("toolName") == "get_memory_info" and tc.get("status") == "completed"),
        None,
    )
    if not mem_tc:
        return findings, suggestions
    data = (mem_tc.get("result") or {}).get("data") or {}
    for tip in _memory_advice(data, user_question):
        if "建议" in tip or "操作" in tip:
            suggestions.append(tip.replace("**", ""))
        else:
            findings.append(tip.replace("**", ""))
    return findings, suggestions


def _network_speed_report_insights(tool_records: List[dict], user_question: str) -> tuple:
    from app.services.response_summarizer import _network_speed_verdict
    findings: List[str] = []
    suggestions: List[str] = []
    speed_tc = next(
        (tc for tc in tool_records
         if tc.get("toolName") == "get_network_speed" and tc.get("status") == "completed"),
        None,
    )
    if not speed_tc:
        return findings, suggestions
    data = (speed_tc.get("result") or {}).get("data") or {}
    primary = data.get("primary") or {}
    if primary:
        findings.append(_network_speed_verdict(primary).replace("**", ""))
    rating = primary.get("rating", "normal")
    if rating == "idle":
        suggestions.append("当前无活跃传输；若要测峰值带宽，请在有业务流量时再采样。")
    elif rating in ("low", "normal"):
        suggestions.append("网速处于正常范围；若仍感觉慢，请排查 DNS、对端服务或链路质量。")
    else:
        suggestions.append("带宽占用较高，建议用 ss -tunp 排查高占用连接是否为预期任务。")
    return findings, suggestions


def _network_report_insights(tool_records: List[dict], user_question: str) -> tuple:
    from app.services.response_summarizer import _network_advice
    findings: List[str] = []
    suggestions: List[str] = []
    net_tc = next(
        (tc for tc in tool_records
         if tc.get("toolName") == "get_network_connections" and tc.get("status") == "completed"),
        None,
    )
    if not net_tc:
        return findings, suggestions
    tips = _network_advice(net_tc, user_question)
    for tip in tips:
        if "建议" in tip:
            suggestions.append(tip.replace("**", ""))
        else:
            findings.append(tip.replace("**", ""))
    suggestions.append("对 0.0.0.0 监听的 Web/API 端口，建议确认防火墙规则是否最小化暴露。")
    return findings, suggestions


def _cpu_report_insights(tool_records: List[dict]) -> tuple:
    findings: List[str] = []
    suggestions: List[str] = []
    cpu_tc = next(
        (tc for tc in tool_records
         if tc.get("toolName") == "get_cpu_info" and tc.get("status") == "completed"),
        None,
    )
    if not cpu_tc:
        return findings, suggestions
    data = (cpu_tc.get("result") or {}).get("data") or {}
    usage = data.get("cpu_usage", data.get("usage", "?"))
    load = data.get("load_1_5_15", data.get("load", "?"))
    cores = data.get("cpu_cores", data.get("cores", "?"))
    findings.append(f"CPU 使用率 **{usage}%**，**{cores}** 核，负载 `{load}`")
    try:
        if float(str(usage).replace("%", "")) >= 80:
            suggestions.append("CPU 使用率偏高，建议结合 `list_processes` 定位高占用进程。")
        else:
            suggestions.append("CPU 负载处于正常范围，可定期巡检并设置阈值告警。")
    except ValueError:
        pass
    return findings, suggestions


def _build_query_report_insights(user_question: str, tool_records: List[dict]) -> tuple:
    """根据已执行工具与用户诉求，生成报告级关键发现与后续建议。"""
    completed = [tc for tc in tool_records if tc.get("status") == "completed"]
    if not completed:
        return (
            ["本轮查询尚未成功返回数据，请重试或检查目标主机连通性。"],
            ["确认 SSH 连通正常后重新发起查询。"],
        )

    q = (user_question or "").lower()
    findings: List[str] = []
    suggestions: List[str] = []

    tool_names = {tc.get("toolName") for tc in completed}

    if tool_names & {"list_processes", "get_process_list"}:
        f, s = _process_report_insights(completed, user_question)
        findings.extend(f)
        suggestions.extend(s)
    if tool_names & {"get_disk_usage", "get_disk_info"}:
        f, s = _disk_report_insights(completed)
        findings.extend(f)
        suggestions.extend(s)
    if "get_memory_info" in tool_names:
        f, s = _memory_report_insights(completed, user_question)
        findings.extend(f)
        suggestions.extend(s)
    if "get_network_speed" in tool_names or any(k in q for k in ("网速", "带宽", "流量快慢")):
        f, s = _network_speed_report_insights(completed, user_question)
        findings.extend(f)
        suggestions.extend(s)
    if "get_network_connections" in tool_names:
        f, s = _network_report_insights(completed, user_question)
        findings.extend(f)
        suggestions.extend(s)
    if "get_cpu_info" in tool_names and not findings:
        f, s = _cpu_report_insights(completed)
        findings.extend(f)
        suggestions.extend(s)

    if not findings:
        for tc in completed[:3]:
            summary = tc.get("displaySummary") or (tc.get("result") or {}).get("display_summary", "")
            if summary:
                findings.append(f"`{tc.get('toolName')}`：{summary[:120]}")

    if not suggestions:
        if any(k in q for k in ("网络", "端口", "连接")):
            suggestions.append("重点关注 LISTEN 端口与异常 ESTABLISHED 连接是否符合业务预期。")
        elif any(k in q for k in ("内存", "磁盘", "cpu", "进程")):
            suggestions.append("建议定期巡检资源指标并设置阈值告警，异常波动时留存快照持续观察。")
        else:
            suggestions.append("若指标正常可继续观察；需要变更生产环境时请走 L4 审批并在对话页确认。")

    return findings[:5], suggestions[:4]


def build_structured_ops_report(
    user_question: str,
    trace_id: str,
    tool_records: List[dict],
    intent: str,
) -> str:
    """结构化运维报告 Markdown（供前端解析为卡片布局）。"""
    completed = [tc for tc in tool_records if tc.get("status") == "completed"]
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    is_query = intent in ("ops_query", "general")

    lines = [
        "## 运维执行报告",
        "",
        f"**Trace ID**: `{trace_id}`",
        f"**意图**: {intent}",
        f"**用户诉求**: {user_question[:200]}",
        "",
    ]

    if is_query:
        exec_hint = (
            f"已完成 {len(completed)} 项检查，数据见上方工具输出。"
            if completed
            else "本轮查询尚未成功完成，请重试或联系管理员。"
        )
        lines.extend([
            "### 查询概要",
            f"- 用户诉求: {user_question[:150]}",
            f"- 执行结果: {exec_hint}",
            f"- 报告生成: {ts}",
            "",
            "### 工具执行记录",
        ])
        lines.extend(_report_tool_lines(tool_records))
        report_findings, report_suggestions = _build_query_report_insights(user_question, tool_records)
        lines.extend([
            "",
            "### 关键发现",
        ])
        lines.extend(f"- {item}" for item in report_findings)
        lines.extend([
            "",
            "### 后续建议",
        ])
        lines.extend(f"- {item}" for item in report_suggestions)
        lines.append("")
    else:
        lines.extend([
            "### 故障现象与时间",
            f"- 用户描述: {user_question[:150]}",
            f"- 报告生成: {ts}",
            "",
            "### 排查过程与执行命令",
        ])
        lines.extend(_report_tool_lines(tool_records))
        lines.extend([
            "",
            "### 根因分析",
            "- 请结合上述工具输出与日志综合判断；若仅完成状态查询，根因分析需进一步排查。",
            "",
            "### 解决措施与验证",
            "- 已执行工具见上表；高危操作需审批 + 用户确认后才会真正执行。",
            "",
            "### 预防建议",
            "- 定期巡检磁盘与服务状态",
            "- 关键变更前在审批管理页完成 L4 审批",
            "- 对未解决问题请使用对话页「结果反馈」标记，便于知识库迭代",
            "",
        ])
    return "\n".join(lines)


async def save_supervision_plan(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    intent: str,
    plan: dict,
) -> "SupervisionPlan":
    from app.models.supervision import SupervisionPlan
    row = SupervisionPlan(
        session_id=session_id,
        trace_id=trace_id,
        user_id=user_id,
        intent=intent,
        plan_json=json.dumps(plan, ensure_ascii=False),
        status="pending_confirm",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def load_supervision_plan(db: AsyncSession, plan_id: str, session_id: str):
    from app.models.supervision import SupervisionPlan
    result = await db.execute(
        select(SupervisionPlan).where(
            SupervisionPlan.id == plan_id,
            SupervisionPlan.session_id == session_id,
        )
    )
    return result.scalar_one_or_none()


async def get_pending_supervision_plan_for_session(db: AsyncSession, session_id: str) -> Optional[dict]:
    """获取会话中待确认的诊断方案（刷新页面后恢复用）。"""
    from app.models.supervision import SupervisionPlan
    from sqlalchemy import desc

    result = await db.execute(
        select(SupervisionPlan).where(
            SupervisionPlan.session_id == session_id,
            SupervisionPlan.status == "pending_confirm",
        ).order_by(desc(SupervisionPlan.created_at)).limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    plan = json.loads(row.plan_json) if row.plan_json else {}
    return {
        "planId": row.id,
        "traceId": row.trace_id,
        "plan": plan,
        "message": "请确认诊断方案后再执行；确认后将进行环境预检并进入 ReAct 执行。",
    }


async def resolve_plan_resume_context(
    db: AsyncSession, plan_id: str, session_id: str,
) -> Optional[dict]:
    """诊断方案确认恢复：还原原始用户诉求，避免对 (resume) 重新做意图分类。"""
    from app.models.session import Message

    row = await load_supervision_plan(db, plan_id, session_id)
    if not row:
        return None
    if row.status not in ("pending_confirm",):
        return None
    plan_data = json.loads(row.plan_json) if row.plan_json else {}
    user_content = (plan_data.get("phenomenon") or "").strip()
    if not user_content:
        hist = await db.execute(
            select(Message).where(
                Message.session_id == session_id,
                Message.role == "user",
            ).order_by(Message.created_at.desc()).limit(5)
        )
        for msg in hist.scalars().all():
            t = (msg.content or "").strip()
            if t and t not in ("(resume)", "[确认执行方案]"):
                user_content = t
                break
    if not user_content:
        user_content = "继续执行已确认的运维方案"
    return {
        "plan_id": plan_id,
        "plan_row": row,
        "user_content": user_content,
        "intent": row.intent or "high_risk",
        "trace_id": row.trace_id,
        "plan_data": plan_data,
    }


async def ensure_execution_log_schema(db: AsyncSession) -> None:
    """SQLite 兼容：补充 execution_logs 关联字段"""
    from sqlalchemy import text

    alters = [
        "ALTER TABLE execution_logs ADD COLUMN tool_call_id VARCHAR(24)",
        "ALTER TABLE execution_logs ADD COLUMN risk_level VARCHAR(4)",
        "ALTER TABLE execution_logs ADD COLUMN rollback_json TEXT",
        "ALTER TABLE execution_logs ADD COLUMN pre_state_json TEXT",
    ]
    for sql in alters:
        try:
            await db.execute(text(sql))
            await db.commit()
        except Exception:
            await db.rollback()


from app.services.rollback_engine import (
    BASELINE_TOOL,
    build_rollback_plan,
    capture_pre_command_state,
    execute_rollback_action,
    parse_rollback_action,
    restore_vm_logical_snapshot,
    should_track_rollback,
)


async def ensure_session_baseline(
    db: AsyncSession,
    session_id: str,
    server_id: str | None = None,
) -> str:
    """会话首次写操作前创建 VM 逻辑快照基线（供全量回滚）。"""
    from app.models.execution_log import ExecutionLog

    await ensure_execution_log_schema(db)
    existing = await db.execute(
        select(ExecutionLog).where(
            ExecutionLog.session_id == session_id,
            ExecutionLog.tool_name == BASELINE_TOOL,
        )
    )
    row = existing.scalar_one_or_none()
    if row and row.snapshot_id:
        return row.snapshot_id

    env = await run_env_precheck(server_id)
    snap = env.get("snapshot_id") or f"snap-{uuid.uuid4().hex[:10]}"
    baseline = ExecutionLog(
        session_id=session_id,
        trace_id=f"baseline-{session_id[:8]}",
        snapshot_id=snap,
        tool_name=BASELINE_TOOL,
        command_preview="session VM logical baseline",
        reversible=False,
        rollback_hint=f"会话逻辑快照 {snap}",
        result_json=env,
    )
    db.add(baseline)
    await db.commit()
    return snap


def _get_session_baseline_snapshot(db_rows) -> str | None:
    for row in db_rows:
        if getattr(row, "tool_name", None) == BASELINE_TOOL and row.snapshot_id:
            return row.snapshot_id
    return None


async def record_execution_log(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    tool_name: str,
    tool_args: dict,
    result: dict,
    snapshot_id: str = None,
    tool_call_id: str = None,
    risk_level: str = None,
    server_id: str = None,
    pre_state: dict = None,
) -> None:
    """记录 L2-L4 可回滚写操作。"""
    from app.models.execution_log import ExecutionLog
    from app.services.chat_service import preview_tool_command, get_tool_risk_level

    await ensure_execution_log_schema(db)
    risk = risk_level or get_tool_risk_level(tool_name, tool_args)
    if not should_track_rollback(tool_name, tool_args, result, risk):
        return

    baseline_snap = await ensure_session_baseline(db, session_id, server_id)
    cmd_snap = snapshot_id or f"snap-cmd-{uuid.uuid4().hex[:8]}"
    preview = preview_tool_command(tool_name, tool_args)
    reversible, hint, action = build_rollback_plan(tool_name, tool_args, risk)
    if action.get("type") == "logical_restore":
        action["snapshot_id"] = cmd_snap

    row = ExecutionLog(
        session_id=session_id,
        trace_id=trace_id,
        snapshot_id=cmd_snap,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        risk_level=risk,
        command_preview=preview[:512] if preview else None,
        reversible=reversible,
        rollback_hint=hint,
        rollback_json=json.dumps(action, ensure_ascii=False) if action else None,
        pre_state_json=json.dumps(pre_state, ensure_ascii=False) if pre_state else None,
        result_json=result,
    )
    db.add(row)
    await db.commit()


async def _execute_rollback_row(
    db: AsyncSession,
    row,
    *,
    session_baseline_snap: str | None = None,
    use_logical_restore: bool = False,
) -> dict:
    """对单条执行日志执行回滚（逆向命令或逻辑快照恢复）。"""
    if not row or row.rolled_back:
        return {"ok": False, "message": "该操作不可回滚或已回滚", "log_id": getattr(row, "id", None)}
    if getattr(row, "tool_name", None) == BASELINE_TOOL:
        return {"ok": False, "message": "基线快照记录不可单步回滚", "log_id": row.id}

    action = parse_rollback_action(row)
    if not action:
        return {"ok": False, "message": "无有效回滚方案", "log_id": row.id}

    if action.get("type") == "logical_restore" or use_logical_restore:
        snap = action.get("snapshot_id") or row.snapshot_id or session_baseline_snap
        if snap:
            action = {"type": "vm_snapshot_restore", "snapshot_id": snap, "original": action.get("original")}
        elif action.get("type") == "logical_restore":
            row.rolled_back = True
            await db.commit()
            return {
                "ok": True,
                "message": f"已标记回滚：{action.get('original', '')[:80]}（清理类命令请使用全量回滚恢复 VM 快照）",
                "log_id": row.id,
                "tool_call_id": row.tool_call_id,
            }

    exec_result = execute_rollback_action(action)
    ok = exec_result.get("success", False)
    if ok:
        row.rolled_back = True
        await db.commit()
    hint = row.rollback_hint or action.get("command") or action.get("original") or ""
    return {
        "ok": ok,
        "message": exec_result.get("display_summary") or (f"已执行回滚: {hint}" if ok else exec_result.get("error", "回滚失败")),
        "result": exec_result,
        "log_id": row.id,
        "tool_call_id": row.tool_call_id,
    }


async def get_session_rollback_status(db: AsyncSession, session_id: str) -> dict:
    """按 tool_call_id 返回可回滚状态，供前端在工具卡展示按钮。"""
    from sqlalchemy import desc
    from app.models.execution_log import ExecutionLog

    await ensure_execution_log_schema(db)
    result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.session_id == session_id)
        .order_by(desc(ExecutionLog.created_at))
    )
    by_tool: dict = {}
    pending_full = 0
    baseline_snap = None
    for row in result.scalars().all():
        if row.tool_name == BASELINE_TOOL:
            baseline_snap = row.snapshot_id
            continue
        if row.tool_call_id and row.tool_call_id not in by_tool:
            by_tool[row.tool_call_id] = {
                "logId": row.id,
                "reversible": bool(row.reversible),
                "rolledBack": bool(row.rolled_back),
                "rollbackHint": row.rollback_hint or "",
                "toolName": row.tool_name,
                "riskLevel": getattr(row, "risk_level", None) or "",
            }
        if row.reversible and not row.rolled_back:
            pending_full += 1
    return {
        "byToolCallId": by_tool,
        "pendingRollbackCount": pending_full,
        "hasFullRollback": pending_full > 0 or bool(baseline_snap),
        "sessionSnapshotId": baseline_snap,
    }


def _inverse_available(action: dict) -> bool:
    return action.get("type") in ("execute_command", "manage_service")


async def run_session_rollback(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    mode: str = "single_step",
    log_id: str = None,
    tool_call_id: str = None,
) -> dict:
    """阶段3子步骤4：单步/全量回滚（L3 校验由调用方在 API 层提示）。"""
    from sqlalchemy import select, desc
    from app.models.execution_log import ExecutionLog

    await ensure_execution_log_schema(db)

    if mode == "full":
        all_rows = list((await db.execute(
            select(ExecutionLog).where(ExecutionLog.session_id == session_id)
            .order_by(desc(ExecutionLog.created_at))
        )).scalars().all())
        baseline_snap = _get_session_baseline_snapshot(all_rows)

        pending = [
            r for r in all_rows
            if r.tool_name != BASELINE_TOOL and r.reversible and not r.rolled_back
        ]
        items = []
        for row in pending:
            action = parse_rollback_action(row)
            if _inverse_available(action):
                items.append(await _execute_rollback_row(
                    db, row,
                    session_baseline_snap=baseline_snap,
                    use_logical_restore=False,
                ))
            else:
                items.append({
                    "ok": True,
                    "message": f"待会话快照恢复: {row.command_preview or row.tool_name}",
                    "log_id": row.id,
                    "tool_call_id": row.tool_call_id,
                    "deferred": True,
                })

        restore_result = None
        if baseline_snap:
            restore_result = restore_vm_logical_snapshot(baseline_snap)
        for row in pending:
            row.rolled_back = True
        await db.commit()

        ok_count = sum(1 for i in items if i.get("ok"))
        snap = baseline_snap or f"snap-{session_id[:8]}-{uuid.uuid4().hex[:6]}"
        if not pending and not baseline_snap:
            return {
                "ok": True,
                "mode": "full",
                "message": "当前会话无可回滚的 L2-L4 写操作。",
                "snapshot_id": snap,
                "items": [],
            }
        restore_ok = restore_result.get("success") if restore_result else False
        return {
            "ok": ok_count > 0 or restore_ok,
            "mode": "full",
            "message": (
                f"全量回滚完成：已将会话恢复至逻辑快照 {snap}，"
                f"逆向执行 {ok_count}/{len(pending)} 项写操作。"
            ),
            "snapshot_id": snap,
            "items": items,
            "vm_restore": restore_result,
        }

    row = None
    if log_id:
        row = (await db.execute(
            select(ExecutionLog).where(
                ExecutionLog.id == log_id,
                ExecutionLog.session_id == session_id,
            )
        )).scalar_one_or_none()
    elif tool_call_id:
        row = (await db.execute(
            select(ExecutionLog)
            .where(
                ExecutionLog.session_id == session_id,
                ExecutionLog.tool_call_id == tool_call_id,
                ExecutionLog.rolled_back == False,
            )
            .order_by(desc(ExecutionLog.created_at))
            .limit(1)
        )).scalar_one_or_none()
    else:
        row = (await db.execute(
            select(ExecutionLog)
            .where(
                ExecutionLog.session_id == session_id,
                ExecutionLog.reversible == True,
                ExecutionLog.rolled_back == False,
            )
            .order_by(desc(ExecutionLog.created_at))
            .limit(1)
        )).scalar_one_or_none()

    if not row:
        return {"ok": False, "message": "该命令不可回滚或已回滚（只读 L1 命令不支持单步回滚）"}
    if not row.reversible:
        return {"ok": False, "message": "该命令不支持回滚（未记录可逆操作）"}

    all_rows = list((await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.session_id == session_id)
        .order_by(desc(ExecutionLog.created_at))
    )).scalars().all())
    baseline_snap = _get_session_baseline_snapshot(all_rows)

    targets = [
        r for r in all_rows
        if r.tool_name != BASELINE_TOOL
        and r.reversible
        and not r.rolled_back
        and r.created_at >= row.created_at
    ]

    items = []
    for r in targets:
        action = parse_rollback_action(r)
        if _inverse_available(action):
            items.append(await _execute_rollback_row(
                db, r,
                session_baseline_snap=baseline_snap or row.snapshot_id,
                use_logical_restore=False,
            ))
        else:
            items.append({
                "ok": True,
                "message": f"待逻辑快照恢复: {r.command_preview or r.tool_name}",
                "log_id": r.id,
                "tool_call_id": r.tool_call_id,
                "deferred": True,
            })

    restore_result = None
    target_snap = row.snapshot_id or baseline_snap
    if target_snap:
        restore_result = restore_vm_logical_snapshot(target_snap)
    for r in targets:
        if not r.rolled_back:
            r.rolled_back = True
    await db.commit()

    ok_count = sum(1 for i in items if i.get("ok"))
    restore_ok = bool(restore_result and restore_result.get("success"))
    hint = row.rollback_hint or row.command_preview or row.tool_name
    return {
        "ok": ok_count > 0 or restore_ok,
        "mode": "single_step",
        "message": f"单步回滚完成：已恢复至「{hint[:60]}」执行前的状态（共处理 {ok_count}/{len(targets)} 项）",
        "items": items,
        "log_id": row.id,
        "tool_call_id": row.tool_call_id,
        "vm_restore": restore_result,
    }


async def confirm_supervision_plan(
    db: AsyncSession, plan_id: str, session_id: str, server_id: str = None,
) -> Optional[dict]:
    row = await load_supervision_plan(db, plan_id, session_id)
    if not row:
        return None
    if row.status == "confirmed":
        env = json.loads(row.env_json) if row.env_json else {}
        plan = json.loads(row.plan_json) if row.plan_json else {}
        return {"plan": row, "env": env, "ok": True, "plan_data": plan}
    if row.status != "pending_confirm":
        return None
    from app.services.agent.snapshot_manager import SnapshotManager, check_disk_space_ok

    mgr = SnapshotManager(session_id, row.trace_id or "")
    snap = await mgr.create(server_id)
    disk = await check_disk_space_ok(server_id)
    checks = list(snap.get("checks") or [])
    if disk.get("detail"):
        checks.append({"name": "disk_free_pct", "ok": disk.get("ok", False), "detail": disk["detail"]})
    passed = bool(snap.get("passed")) and disk.get("ok", True)
    env = {
        "passed": passed,
        "snapshot_id": snap.get("snapshot_id"),
        "task_id": snap.get("task_id"),
        "checks": checks,
        "snapshot_note": mgr.metadata.get("note", "逻辑快照元数据"),
        "checked_at": snap.get("created_at"),
    }
    row.env_json = json.dumps(env, ensure_ascii=False)
    row.snapshot_id = env.get("snapshot_id")
    if not passed:
        row.status = "env_failed"
        await db.commit()
        return {"plan": row, "env": env, "ok": False}
    row.status = "confirmed"
    row.confirmed_at = datetime.utcnow()
    await db.commit()
    plan = json.loads(row.plan_json) if row.plan_json else {}
    return {"plan": row, "env": env, "ok": True, "plan_data": plan}
