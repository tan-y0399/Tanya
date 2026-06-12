"""
对话结果总结 — 在工具执行完成后，基于工具输出生成面向用户的最终结论。
"""
from __future__ import annotations

import json
import re
from typing import Any, AsyncGenerator, Dict, List

TOOLS_MARKER = "\n\n<!--KYLIN_TOOLS-->\n\n"
REPORT_MARKER = "\n\n<!--KYLIN_REPORT-->\n\n"
CONCLUSION_HEADER = "## 执行结论\n\n"


def _tool_record_summary(tc: dict) -> str:
    if tc.get("displaySummary"):
        return str(tc["displaySummary"])
    result = tc.get("result") or {}
    if result.get("display_summary"):
        return str(result["display_summary"])
    data = result.get("data") or {}
    if data.get("summary"):
        return str(data["summary"])
    if not result.get("success"):
        return result.get("error", "执行失败")
    return f"{tc.get('toolName', '工具')} 已完成"


def collect_tool_context(tool_call_records: List[dict]) -> str:
    """收集工具执行结果供 LLM 总结（含结构化摘要与关键字段）。"""
    from app.services.tool_output_formatter import format_for_llm

    lines = []
    for tc in tool_call_records:
        status = tc.get("status", "")
        name = tc.get("toolName", "unknown")
        step = tc.get("planStepOrder")
        step_hint = f"（方案步骤 {step}）" if step else ""
        if status == "completed":
            summary = _tool_record_summary(tc)
            result = tc.get("result") or {}
            detail = format_for_llm(name, result) if result else summary
            lines.append(f"- [{name}]{step_hint} {summary}")
            if detail and detail != summary:
                lines.append(f"  数据详情: {detail[:1200]}")
        elif status == "blocked":
            lines.append(f"- [{name}]{step_hint} 已阻止: {tc.get('result', {}).get('error', '')}")
        elif status == "rejected":
            err = (tc.get("result") or {}).get("error", "管理员已拒绝")
            lines.append(f"- [{name}]{step_hint} 已拒绝: {err}")
        elif status == "pending_approval":
            lines.append(f"- [{name}]{step_hint} 待管理员审批")
        else:
            lines.append(f"- [{name}]{step_hint} 状态: {status}")
    return "\n".join(lines) if lines else "（无工具结果）"


SUMMARY_SYSTEM_PROMPT = """你是 KylinOps 麒麟智能运维助手，负责把工具执行结果整理成**专业、易懂**的中文运维结论。

写作要求：
- 面向运维人员与系统管理员，语言精炼、结构清晰，避免堆砌原始日志
- 必须基于工具返回的真实数据进行分析，不得编造未出现的端口、服务或数值
- 不要重复「我来查看」「正在执行」等过程性表述
- 使用 Markdown，以「## 执行结论」开头"""


def _build_summary_user_prompt(
    user_question: str,
    tool_call_records: List[dict],
    plan_data: dict | None = None,
) -> str:
    tool_ctx = collect_tool_context(tool_call_records)
    plan_block = ""
    if plan_data and (plan_data.get("steps") or plan_data.get("phenomenon")):
        phenomenon = plan_data.get("phenomenon") or user_question[:80]
        steps_txt = "\n".join(
            f"  {s.get('order')}. {s.get('action', '')}"
            for s in sorted(plan_data.get("steps") or [], key=lambda x: x.get("order", 0))
        )
        plan_block = f"""
已执行运维方案：
- 诉求：{phenomenon}
- 步骤：
{steps_txt}
"""

    return f"""用户原始问题：
{user_question}
{plan_block}
已执行工具及结果：
{tool_ctx}
{"【网速专项】用户关心实时网速快慢。必须基于 get_network_speed 的采样速率（KB/s、Mbps）给出明确评价：正常/偏低/偏高/空闲，禁止只复述累计字节数。" if is_network_speed_query(user_question) else ""}

请写出给用户的**最终执行结论**（Markdown），结构如下：

## 执行结论

**总览**
（单独一段，1～2 句话，直接回答用户问题并给出整体判断：正常 / 需关注 / 异常）

**关键发现**
- 第一条发现（端口、服务、资源占用等，基于真实数据）
- 第二条发现
- 第三条发现（共 3～5 条，每条独立一行，以 `- ` 开头）

**结论与建议**
1. 第一条建议（明确结论或可执行动作）
2. 第二条建议
3. 第三条建议（共 2～4 条，每条独立一行，以 `1.` `2.` 编号）

格式要求：
- 「总览」「关键发现」「结论与建议」必须使用 **粗体标题** 且各占独立段落
- 列表项必须换行，禁止挤在同一段落里
- 全文 250～550 字；不要输出 JSON；不要大段复述原始命令输出
- 必须以「## 执行结论」开头"""


def _is_generic_lightweight_conclusion(body: str) -> bool:
    """前端补全的模板结论，需由 LLM 替换。"""
    markers = (
        "已根据您的诉求",
        "已完成远程检查，结果如下",
        "以上数据来自目标主机实时查询",
        "如需进一步排查，请说明具体现象",
    )
    if not any(m in body for m in markers):
        return False
    if re.search(r"\bPID\s*\d+", body, re.I):
        return False
    if re.search(r"\d+\.?\d*\s*%", body):
        return False
    return True


def _has_valid_conclusion(text: str) -> bool:
    """是否已有可展示的最终结论（含建议/判断，非空壳）。"""
    if "## 执行结论" not in text:
        return False
    # 多段结论时取最后一段（LLM 流式追加在后）
    body = text.split("## 执行结论")[-1].strip()
    if len(body) < 35:
        return False
    if _is_generic_lightweight_conclusion(body):
        return False
    # 仅有标题或重复过程说明视为无效
    noise = ("我将", "正在查看", "稍等", "让我")
    if any(body.startswith(n) for n in noise) and len(body) < 80:
        return False
    return True


def _user_requests_write_action(user_question: str) -> bool:
    from app.services.ops_scope import (
        is_service_control_request,
        is_disk_cleanup_execution_request,
        is_time_sync_execution_request,
    )
    return (
        is_service_control_request(user_question or "")
        or is_disk_cleanup_execution_request(user_question or "")
        or is_time_sync_execution_request(user_question or "")
    )


def _command_text_from_tool(tc: dict) -> str:
    params = tc.get("params") or {}
    if tc.get("toolName") in ("execute_command", "run_command"):
        return str(params.get("command") or params.get("cmd") or "")
    return ""


def _is_time_sync_tool(tc: dict) -> bool:
    cmd = _command_text_from_tool(tc).lower()
    if any(k in cmd for k in ("timedatectl", "chronyc", "chronyd", " ntp", "ntpdate")):
        return True
    if tc.get("toolName") == "get_service_status":
        svc = str((tc.get("params") or {}).get("service_name") or "").lower()
        return "chrony" in svc
    return False


def _time_sync_action_satisfied(user_question: str, tool_call_records: List[dict]) -> bool:
    from app.services.ops_scope import is_time_sync_execution_request
    if not is_time_sync_execution_request(user_question):
        return True
    write_done = False
    read_done = False
    for tc in tool_call_records:
        status = tc.get("status", "")
        if status not in ("completed", "pending_confirm", "pending_approval"):
            continue
        if not _is_time_sync_tool(tc):
            continue
        read_done = True
        cmd = _command_text_from_tool(tc).lower()
        if any(k in cmd for k in ("makestep", "set-ntp", "set-time", "ntpdate")):
            write_done = True
    return read_done and write_done


def _tools_irrelevant_to_request(user_question: str, tool_call_records: List[dict]) -> bool:
    """已完成工具与用户诉求明显无关时，禁止 LLM 幻觉作答。"""
    from app.services.ops_scope import is_time_sync_execution_request
    if not is_time_sync_execution_request(user_question):
        return False
    completed = [tc for tc in tool_call_records if tc.get("status") == "completed"]
    if not completed:
        return False
    if any(_is_time_sync_tool(tc) for tc in completed):
        return False
    return True


def _write_action_satisfied(user_question: str, tool_call_records: List[dict]) -> bool:
    """关闭/启停/清理/时间同步类诉求是否已有对应工具成功执行（含待审批）。"""
    if not _user_requests_write_action(user_question):
        return True
    from app.services.ops_scope import is_time_sync_execution_request
    if is_time_sync_execution_request(user_question):
        return _time_sync_action_satisfied(user_question, tool_call_records)
    for tc in tool_call_records:
        name = tc.get("toolName", "")
        status = tc.get("status", "")
        if name == "manage_service" and status in ("completed", "pending_approval"):
            return True
        if name in ("execute_command", "run_command") and status in ("completed", "pending_approval"):
            return True
    return False


def needs_final_summary(full_response: str, tool_call_records: List[dict]) -> bool:
    """有已完成工具且尚无有效结论时，必须生成总结（不因循环内非致命异常而跳过）。"""
    completed = [tc for tc in tool_call_records if tc.get("status") == "completed"]
    if not completed:
        return False
    if _has_valid_conclusion(full_response):
        return False
    return True


def split_agent_content(content: str) -> tuple:
    """拆分为 (intro, has_marker, conclusion)。"""
    if TOOLS_MARKER not in content:
        return content.strip(), False, ""
    intro, conclusion = content.split(TOOLS_MARKER, 1)
    return intro.strip(), True, conclusion.strip()


def _memory_advice(data: dict, user_question: str) -> List[str]:
    """根据内存数据生成清理/优化建议。"""
    tips: List[str] = []
    try:
        total = float(data.get("mem_total_mb") or 0)
        used = float(data.get("mem_used_mb") or 0)
        avail = float(data.get("mem_available_mb") or 0)
        swap_used = float(data.get("swap_used_mb") or 0)
        swap_total = float(data.get("swap_total_mb") or 0)
    except (TypeError, ValueError):
        return tips

    if total <= 0:
        return tips

    pct = round(used / total * 100, 1)
    tips.append(f"物理内存已用约 **{pct}%**（{int(used)}/{int(total)} MB），可用约 {int(avail)} MB。")

    if pct >= 85:
        tips.append("**状态：偏高** — 建议用 `list_processes` 排查占用高的进程，或清理缓存/重启非关键服务。")
    elif pct >= 70:
        tips.append("**状态：中等偏高** — 可关注缓存与常驻进程，必要时释放 PageCache：`sync; echo 3 > /proc/sys/vm/drop_caches`（需 root，谨慎）。")
    else:
        tips.append("**状态：正常** — 暂无需紧急清理；若仍感觉卡顿，请结合 CPU/磁盘与 Swap 一并排查。")

    if swap_total > 0 and swap_used / swap_total > 0.5:
        tips.append(f"Swap 使用较高（{int(swap_used)}/{int(swap_total)} MB），可能存在内存压力，建议扩容或优化应用内存占用。")

    q = (user_question or "").lower()
    if any(k in q for k in ("清理", "释放", "优化", "建议", "怎么办")):
        tips.append("**建议操作**：① `top`/`list_processes` 找大进程；② 停止无用服务；③ 检查日志与定时任务是否泄漏内存。")

    return tips


def is_network_speed_query(user_question: str) -> bool:
    q = (user_question or "").lower()
    return any(k in q for k in ("网速", "带宽", "流量快慢", "网络速度", "network speed", "throughput", "快慢"))


def _network_speed_from_records(tool_call_records: List[dict]) -> dict | None:
    for tc in tool_call_records:
        if tc.get("toolName") != "get_network_speed" or tc.get("status") != "completed":
            continue
        data = (tc.get("result") or {}).get("data") or {}
        if data.get("primary"):
            return data
    return None


def enrich_tool_records_for_summary(user_question: str, tool_call_records: List[dict]) -> List[dict]:
    """网速类诉求若仅有累计流量数据，自动补一次实时采样。"""
    if not is_network_speed_query(user_question):
        return tool_call_records
    if _network_speed_from_records(tool_call_records):
        return tool_call_records
    try:
        from app.services.remote_executor import get_network_speed
        from app.services.tool_output_formatter import enrich_tool_result

        result = enrich_tool_result("get_network_speed", get_network_speed(interval=1.0))
        if not result.get("success"):
            return tool_call_records
        return list(tool_call_records) + [{
            "id": "auto-network-speed",
            "toolName": "get_network_speed",
            "params": {"interval": 1.0},
            "riskLevel": "L1",
            "status": "completed",
            "result": result,
            "displaySummary": result.get("display_summary", ""),
        }]
    except Exception:
        return tool_call_records


def _network_speed_verdict(primary: dict) -> str:
    rating = primary.get("rating", "normal")
    rx_kbps = primary.get("rx_kbps", 0)
    tx_kbps = primary.get("tx_kbps", 0)
    iface = primary.get("iface", "?")
    if rating == "idle":
        return (
            f"网卡 **{iface}** 在采样 {primary.get('interval_sec', 1)} 秒内几乎无数据传输"
            f"（下行 {rx_kbps} KB/s、上行 {tx_kbps} KB/s），当前处于**空闲状态**——"
            "不能简单说「快」或「慢」，而是**此刻没有活跃的网络传输**。"
        )
    if rating == "low":
        return (
            f"网卡 **{iface}** 当前网速**偏低但正常**（下行 {rx_kbps} KB/s、上行 {tx_kbps} KB/s），"
            "适合轻量管理流量或间歇性访问，**不属于异常**。"
        )
    if rating == "normal":
        return (
            f"网卡 **{iface}** 当前网速**正常**（下行 {rx_kbps} KB/s / {primary.get('rx_mbps', '?')} Mbps，"
            f"上行 {tx_kbps} KB/s / {primary.get('tx_mbps', '?')} Mbps），"
            "可满足一般业务与管理访问，**无需特别担心**。"
        )
    if rating == "high":
        return (
            f"网卡 **{iface}** 当前网速**较高**（下行 {rx_kbps} KB/s、上行 {tx_kbps} KB/s），"
            "可能正在传输大文件或存在较多并发连接，**需关注是否预期内的高负载**。"
        )
    return (
        f"网卡 **{iface}** 当前网速**非常高**（下行 {rx_kbps} KB/s、上行 {tx_kbps} KB/s），"
        "已接近或达到千兆带宽上限，**建议确认是否有大流量任务或异常下载**。"
    )


def is_process_cpu_query(user_question: str) -> bool:
    q = (user_question or "").lower()
    return any(k in q for k in ("进程", "process", "cpu", "占用")) and any(
        k in q for k in ("最高", "top", "占用", "排序", "哪些", "哪个", "列出", "list")
    )


def _processes_from_records(tool_call_records: List[dict]) -> Optional[dict]:
    from app.services.tool_output_formatter import _parse_ps_aux

    for tc in reversed(tool_call_records):
        if tc.get("toolName") not in ("list_processes", "get_process_list") or tc.get("status") != "completed":
            continue
        data = (tc.get("result") or {}).get("data") or {}
        procs = data.get("processes") or _parse_ps_aux(data.get("raw") or "")
        if procs:
            return {"processes": procs, "sort_by": data.get("sort_by", "cpu")}
    return None


def build_process_list_conclusion(user_question: str, tool_call_records: List[dict]) -> str:
    """基于 list_processes 结果生成结构化 CPU/进程结论。"""
    pack = _processes_from_records(tool_call_records)
    if not pack:
        return build_rule_based_conclusion(user_question, tool_call_records)

    procs = pack["processes"]
    sort_by = (pack.get("sort_by") or "cpu").lower()
    metric = "CPU" if sort_by != "mem" else "内存"
    top = procs[0]
    lines = [CONCLUSION_HEADER, "**总览**"]
    val = top["cpu_pct"] if sort_by != "mem" else top["mem_pct"]
    lines.append(
        f"当前系统中{metric}占用最高的进程为 **PID {top['pid']}**（用户 {top.get('user', '?')}），"
        f"{metric}使用率 **{val}%**，整体资源占用{'偏高' if val >= 50 else '处于正常范围'}。"
    )
    lines.append("")
    lines.append("**关键发现**")
    for i, p in enumerate(procs[:5], 1):
        cpu_v, mem_v = p.get("cpu_pct", 0), p.get("mem_pct", 0)
        cmd = (p.get("cmd") or "?")[:100]
        lines.append(
            f"- 第{i}位：PID **{p['pid']}**（{p.get('user', '?')}）"
            f" CPU **{cpu_v}%** / 内存 **{mem_v}%** — `{cmd}`"
        )
    lines.append("")
    lines.append("**结论与建议**")
    if val >= 80:
        lines.append(f"1. **{metric}占用偏高** — 建议确认 `{top.get('cmd', '')[:60]}` 是否为预期业务进程。")
        lines.append("2. 可使用 `list_processes` 持续观察，必要时重启或优化对应服务。")
    elif val >= 30:
        lines.append("1. **当前占用中等** — 暂无需紧急处理，建议结合业务高峰时段再观察。")
        lines.append("2. 若系统卡顿，可同时检查内存与磁盘 IO。")
    else:
        lines.append("1. **当前 CPU/进程占用正常**，无需干预。")
        lines.append("2. 若后续出现卡顿，可再次查询进程列表对比变化。")
    return "\n".join(lines)


def build_network_speed_conclusion(user_question: str, tool_call_records: List[dict]) -> str:
    """基于 get_network_speed 采样结果生成结构化网速结论。"""
    speed_data = _network_speed_from_records(tool_call_records)
    if not speed_data:
        return build_rule_based_conclusion(user_question, tool_call_records)

    primary = speed_data.get("primary") or {}
    interfaces = speed_data.get("interfaces") or []
    lines = [CONCLUSION_HEADER, "**总览**", _network_speed_verdict(primary), ""]

    lines.append("**关键发现**")
    for item in interfaces[:4]:
        lines.append(
            f"- 网卡 `{item.get('iface')}`：下行 **{item.get('rx_kbps')} KB/s**（{item.get('rx_mbps')} Mbps），"
            f"上行 **{item.get('tx_kbps')} KB/s**（{item.get('tx_mbps')} Mbps）→ {item.get('rating_label')}"
        )
    lines.append(
        f"- 采样方式：间隔 **{speed_data.get('interval_sec', 1)} 秒** 读取 `/proc/net/dev` 差值计算实时速率"
    )

    lines.append("")
    lines.append("**结论与建议**")
    rating = primary.get("rating", "normal")
    if rating == "idle":
        lines.append("1. **当前评价：空闲** — 此刻没有明显网络传输，不代表网卡故障。")
        lines.append("2. 若您关心「最大能跑多快」，需在有大文件下载/业务压测时再测一次。")
        lines.append("3. 可执行 `ping 网关` 或访问业务端口，确认连通性正常。")
    elif rating in ("low", "normal"):
        lines.append("1. **当前评价：正常** — 实时网速处于健康范围，可支撑日常运维与业务访问。")
        lines.append("2. 若主观感觉慢，可能是 DNS、对端服务或 Wi-Fi/交换机问题，而非本机网卡瓶颈。")
        lines.append("3. 持续监控可用 `get_network_speed` 定期采样，对比高峰与低谷。")
    else:
        lines.append("1. **当前评价：偏高/很高** — 带宽占用明显，请确认是否有备份、同步或大文件传输任务。")
        lines.append("2. 若非预期流量，可用 `ss -tunp` 排查高占用连接与对应进程。")
        lines.append("3. 长期高负载建议设置流量告警，避免影响关键业务。")

    return "\n".join(lines)


def _network_advice(tc: dict, user_question: str) -> List[str]:
    """网络连接查询的规则化解读。"""
    data = (tc.get("result") or {}).get("data") or {}
    raw = (data.get("raw") or "").strip()
    if not raw and not data.get("notable"):
        return []
    from app.services.tool_output_formatter import _parse_network_connections
    parsed = data if data.get("notable") else _parse_network_connections(raw)
    tips = [
        f"系统当前有 **{parsed.get('tcp_listen_count', 0)}** 个 TCP 监听端口、"
        f"**{parsed.get('udp_listen_count', 0)}** 个 UDP 端口。"
    ]
    notable = parsed.get("notable") or []
    if notable:
        tips.append("**主要监听**：" + "；".join(notable[:4]))
    q = user_question or ""
    if any(k in q for k in ("网络", "连接", "端口", "监听")):
        tips.append(
            "**建议**：核对 LISTEN 端口是否符合业务预期；数据库/缓存若仅绑定 127.0.0.1 通常更安全。"
        )
    return tips


def _step_record_for_order(tool_call_records: List[dict], order: int) -> dict | None:
    for tc in tool_call_records:
        if tc.get("planStepOrder") == order:
            return tc
    return None


def _expected_tools_for_question(user_question: str) -> List[str]:
    """从用户诉求推断应执行的关键工具。"""
    q = (user_question or "").lower()
    if any(k in q for k in ("进程", "process")) and any(k in q for k in ("cpu", "占用", "最高", "top")):
        return ["list_processes"]
    if any(k in q for k in ("内存", "memory", "swap")):
        return ["get_memory_info"]
    if any(k in q for k in ("磁盘", "disk", "空间", "分区")):
        return ["get_disk_usage"]
    if "cpu" in q and "进程" not in q:
        return ["get_cpu_info"]
    if any(k in q for k in ("网速", "带宽", "流量", "网卡", "吞吐")):
        return ["get_network_speed"]
    if any(k in q for k in ("网络", "端口", "连接", "监听")):
        return ["get_network_connections"]
    return []


def _resolve_plan_step_status(step: dict, tool_call_records: List[dict], all_steps: List[dict]) -> str:
    from app.services.human_supervision import _is_virtual_plan_step
    from app.services.chat_service import _parse_plan_step_to_tool

    order = step.get("order", 0)
    rec = _step_record_for_order(tool_call_records, order)
    if rec:
        st = rec.get("status") or "pending"
        if st == "skipped":
            return "skipped"
        return st
    hint = (step.get("tool_hint") or "").strip()
    if hint in ("env_precheck", "按意图选择工具"):
        return "skipped"
    if _is_virtual_plan_step(step):
        actionable = [s for s in all_steps if _parse_plan_step_to_tool(s)]
        terminal = {"completed", "failed", "blocked", "rejected", "skipped"}
        if actionable and all(
            (_step_record_for_order(tool_call_records, s.get("order", 0)) or {}).get("status") in terminal
            for s in actionable
        ):
            return "completed"
        return "pending"
    return "pending"


def _actionable_plan_steps(plan_data: dict | None) -> List[dict]:
    from app.services.chat_service import _parse_plan_step_to_tool

    steps = (plan_data or {}).get("steps") or []
    return [s for s in steps if _parse_plan_step_to_tool(s)]


def is_plan_execution_complete(plan_data: dict | None, tool_call_records: List[dict]) -> bool:
    """方案每个可执行步骤均有终态记录时视为执行完毕。"""
    actionable = _actionable_plan_steps(plan_data)
    if not actionable:
        return False
    terminal = {"completed", "failed", "blocked", "rejected", "timeout", "skipped"}
    for step in actionable:
        rec = _step_record_for_order(tool_call_records, step.get("order", 0))
        if not rec or rec.get("status") not in terminal:
            return False
    return True


def build_plan_step_progress_brief(
    user_question: str,
    tool_call_records: List[dict],
    plan_data: dict | None = None,
) -> dict:
    """方案执行中的轻量进度（非最终结论）。"""
    from app.services.chat_service import preview_tool_command

    steps = (plan_data or {}).get("steps") or []
    actionable = _actionable_plan_steps(plan_data)
    total = len(actionable) if actionable else len(steps)
    terminal = {"completed", "failed", "blocked", "rejected", "skipped"}
    done_orders = set()
    for tc in tool_call_records:
        order = tc.get("planStepOrder")
        if order is not None and tc.get("status") in terminal:
            done_orders.add(int(order))

    completed_actionable = sum(
        1 for s in actionable
        if (_step_record_for_order(tool_call_records, s.get("order", 0)) or {}).get("status") == "completed"
    )
    processed_actionable = sum(
        1 for s in actionable
        if (_step_record_for_order(tool_call_records, s.get("order", 0)) or {}).get("status") in terminal
    )
    failed_actionable = sum(
        1 for s in actionable
        if (_step_record_for_order(tool_call_records, s.get("order", 0)) or {}).get("status") == "failed"
    )

    pending = [
        tc for tc in tool_call_records
        if tc.get("status") in ("pending_confirm", "pending_approval")
    ]
    current = pending[0] if pending else None
    phenomenon = (plan_data or {}).get("phenomenon") or (user_question or "")[:80]

    brief_parts = [f"方案进度 {processed_actionable}/{total}"]
    if failed_actionable:
        brief_parts.append(f"{failed_actionable} 步未成功")
    if current:
        step = current.get("planStepOrder")
        action = current.get("planStepAction") or preview_tool_command(
            current.get("toolName", ""), current.get("params") or {},
        )
        if current.get("status") == "pending_approval":
            brief_parts.append(f"步骤 {step}「{action}」待管理员审批")
        else:
            brief_parts.append(f"步骤 {step}「{action}」待您确认执行")

    return {
        "phenomenon": phenomenon,
        "totalSteps": total,
        "completedSteps": processed_actionable,
        "successfulSteps": completed_actionable,
        "failedSteps": failed_actionable,
        "currentStepOrder": current.get("planStepOrder") if current else None,
        "currentStepAction": current.get("planStepAction") if current else None,
        "currentStatus": current.get("status") if current else (
            "completed" if total and completed_actionable >= total else "executing"
        ),
        "brief": "，".join(brief_parts),
        "steps": [
            {
                "order": s.get("order"),
                "action": s.get("action", ""),
                "status": _resolve_plan_step_status(s, tool_call_records, steps),
                "core": bool(s.get("core")),
            }
            for s in sorted(steps, key=lambda x: x.get("order", 0))
        ],
    }


def build_plan_final_conclusion(
    user_question: str,
    tool_call_records: List[dict],
    plan_data: dict | None = None,
) -> str:
    """方案全部步骤执行完毕后的规范化总结。"""
    from app.services.chat_service import preview_tool_command

    steps = (plan_data or {}).get("steps") or []
    actionable = _actionable_plan_steps(plan_data)
    phenomenon = (plan_data or {}).get("phenomenon") or (user_question or "")[:80]
    lines = [CONCLUSION_HEADER]
    lines.append(f"针对您的诉求「{phenomenon}」，运维诊断方案已执行完毕。\n")
    lines.append("**方案执行摘要**")

    ok_count = fail_count = 0
    for step in sorted(steps, key=lambda s: s.get("order", 0)):
        order = step.get("order", 0)
        action = step.get("action", "")
        rec = _step_record_for_order(tool_call_records, order)
        if not rec:
            lines.append(f"- 步骤 {order} · {action} → 未执行")
            continue
        status = rec.get("status", "")
        cmd = preview_tool_command(rec.get("toolName", ""), rec.get("params") or {})
        if status == "completed":
            ok_count += 1
            lines.append(f"- 步骤 {order} · {action}（`{cmd}`）→ {_tool_record_summary(rec)}")
        elif status in ("failed", "blocked"):
            fail_count += 1
            err = (rec.get("result") or {}).get("error", "执行未成功")
            lines.append(f"- 步骤 {order} · {action}（`{cmd}`）→ ⚠ {err}")
        elif status == "rejected":
            lines.append(f"- 步骤 {order} · {action} → 已跳过/取消")
        else:
            lines.append(f"- 步骤 {order} · {action} → 状态：{status}")

    lines.append(f"\n**统计**：共 {len(actionable) or len(steps)} 个可执行步骤，成功 {ok_count} 步" + (
        f"，未成功 {fail_count} 步" if fail_count else ""
    ) + "。")

    lines.append("\n**结论与建议**")
    expected = _expected_tools_for_question(user_question or phenomenon)
    executed = {
        tc.get("toolName") for tc in tool_call_records if tc.get("status") == "completed"
    }
    missing = [t for t in expected if t not in executed]
    if missing:
        tool_label = {"list_processes": "进程列表", "get_memory_info": "内存信息",
                      "get_disk_usage": "磁盘使用", "get_cpu_info": "CPU 状态"}.get(missing[0], missing[0])
        lines.append(
            f"- ⚠ 本次未完成核心操作（{tool_label}），未能完整回答「{phenomenon[:40]}」。"
            " 请点击「继续执行方案」或重新发起查询。"
        )
    q = (user_question or phenomenon or "").lower()
    if any(k in q for k in ("清理", "垃圾", "磁盘", "空间")):
        disk_tc = next(
            (tc for tc in tool_call_records
             if tc.get("toolName") == "get_disk_usage" and tc.get("status") == "completed"),
            None,
        )
        if disk_tc:
            lines.append("- 已按方案完成磁盘检查与清理操作；请对比步骤 1 与最后一步的磁盘使用率变化评估效果。")
        else:
            lines.append("- 已按方案执行清理相关操作，建议稍后再次检查磁盘使用率确认释放效果。")
        if fail_count:
            lines.append("- 部分步骤未成功，可根据上方失败原因手动处理，或新建对话重新执行方案。")
        else:
            lines.append("- 若空间仍紧张，可继续排查大文件目录或应用日志增长。")
    else:
        if fail_count:
            lines.append("- 方案已走完，部分步骤未成功，请根据摘要中的失败原因处理。")
        else:
            lines.append("- 方案步骤均已执行，系统状态请结合上方各步工具输出综合判断。")

    return "\n".join(lines)


def build_plan_progress_conclusion(
    user_question: str,
    tool_call_records: List[dict],
    plan_data: dict | None = None,
) -> str:
    """方案执行暂停或进行中时，基于已完成步骤生成进度总结。"""
    from app.services.chat_service import preview_tool_command

    terminal = {"completed", "failed", "blocked", "rejected", "skipped"}
    finished = [tc for tc in tool_call_records if tc.get("status") in terminal]
    completed = [tc for tc in tool_call_records if tc.get("status") == "completed"]
    pending = [
        tc for tc in tool_call_records
        if tc.get("status") in ("pending_confirm", "pending_approval")
    ]
    failed = [tc for tc in tool_call_records if tc.get("status") in ("failed", "blocked")]

    phenomenon = (plan_data or {}).get("phenomenon") or (user_question or "")[:120]
    lines = [CONCLUSION_HEADER]
    if phenomenon:
        lines.append(f"针对您的诉求「{phenomenon}」，当前方案执行进度如下：\n")

    if finished:
        lines.append("**已完成检查**")
        for tc in sorted(finished, key=lambda x: x.get("planStepOrder") or 0):
            cmd = preview_tool_command(tc.get("toolName", ""), tc.get("params") or {})
            step = tc.get("planStepOrder")
            action = tc.get("planStepAction") or ""
            prefix = f"步骤 {step} · {action} — " if step else ""
            status = tc.get("status")
            if status == "completed":
                lines.append(f"- {prefix}`{cmd}` → {_tool_record_summary(tc)}")
            else:
                err = (tc.get("result") or {}).get("error") or _tool_record_summary(tc) or "执行未成功"
                lines.append(f"- {prefix}`{cmd}` → ⚠ {err}")

    if pending:
        lines.append("\n**待您确认**")
        for tc in pending:
            cmd = preview_tool_command(tc.get("toolName", ""), tc.get("params") or {})
            risk = tc.get("riskLevel", "L?")
            step = tc.get("planStepOrder")
            action = tc.get("planStepAction") or cmd
            prefix = f"步骤 {step} · {action} — " if step else ""
            if tc.get("status") == "pending_approval":
                lines.append(f"- {prefix}`{cmd}`（{risk}，待管理员审批）")
            else:
                lines.append(f"- {prefix}`{cmd}`（{risk}，请在下方点击「执行」继续）")

    steps = (plan_data or {}).get("steps") or []
    actionable = _actionable_plan_steps(plan_data)
    total = len(actionable) if actionable else len(steps)
    done_orders = {
        int(tc["planStepOrder"])
        for tc in finished
        if tc.get("planStepOrder") is not None
    }
    fail_count = len(failed)
    if total:
        lines.append(f"\n**方案进度**：已处理 {len(done_orders)}/{total} 步" + (
            f"，其中 {fail_count} 步未成功" if fail_count else ""
        ) + "。")

    lines.append("\n**结论与建议**")
    low = (phenomenon or "").lower()
    svc_missing = [
        tc for tc in failed
        if tc.get("toolName") == "get_service_status"
        and ((tc.get("result") or {}).get("data") or {}).get("state") == "not-found"
    ]
    if svc_missing:
        names = ", ".join(
            dict.fromkeys(
                (tc.get("params") or {}).get("service_name")
                or ((tc.get("result") or {}).get("data") or {}).get("service")
                or "相关服务"
                for tc in svc_missing
            )
        )
        lines.append(
            f"- 目标主机未安装或未注册 systemd 单元：{names}。"
            " 请先安装对应软件包并启用服务后，再添加打印机或继续后续修复步骤。"
        )
    elif fail_count:
        lines.append("- 前几步检查未通过，建议根据上方失败原因逐项处理后再继续方案。")
    elif completed and pending:
        lines.append("- 只读检查已完成，确认待执行步骤后将继续安装/配置类操作。")

    if pending:
        lines.append("- 确认后将自动继续执行后续步骤；全部完成后会更新最终结论。")
    elif fail_count and ("cups" in low or "打印" in phenomenon):
        lines.append("- 建议先在目标主机执行：`dnf install -y cups avahi nss-mdns`，并 `systemctl enable --now cups avahi-daemon`。")

    return "\n".join(lines)


def build_rule_based_conclusion(user_question: str, tool_call_records: List[dict]) -> str:
    """LLM 不可用时的规则总结（保证有结论与建议）。"""
    completed = [tc for tc in tool_call_records if tc.get("status") == "completed"]
    failed = [tc for tc in tool_call_records if tc.get("status") not in ("completed",)]
    lines = [CONCLUSION_HEADER]

    if completed:
        lines.append("根据刚才的检查，结论如下：\n")
        for tc in completed:
            lines.append(f"- {_tool_record_summary(tc)}")
            if tc.get("toolName") == "get_memory_info":
                data = (tc.get("result") or {}).get("data") or {}
                for tip in _memory_advice(data, user_question):
                    lines.append(f"  {tip}")
            if tc.get("toolName") == "get_network_connections":
                for tip in _network_advice(tc, user_question):
                    lines.append(f"  {tip}")
            if tc.get("toolName") == "get_network_speed":
                data = (tc.get("result") or {}).get("data") or {}
                primary = data.get("primary") or {}
                if primary:
                    lines.append(f"  {_network_speed_verdict(primary)}")
    if failed:
        lines.append(f"\n另有 {len(failed)} 项操作未完成或需您确认。")

    if _user_requests_write_action(user_question) and not _write_action_satisfied(user_question, tool_call_records):
        from app.services.ops_scope import is_time_sync_execution_request
        if is_time_sync_execution_request(user_question):
            lines.append(
                "\n**说明**：时间同步属于系统配置写操作，需依次执行 "
                "`timedatectl status` / `chronyc tracking` 检查，再经您确认执行 "
                "`chronyc makestep` 或 `timedatectl set-ntp true`。"
                "当前仅完成了无关检查，**尚未执行时间同步**。"
            )
        else:
            lines.append(
                "\n**说明**：关闭/启停服务属于高危操作，需调用 `manage_service` 并经管理员审批；"
                "批准后请在对话页底部确认框点击「执行」，命令才会在虚拟机运行。"
                "当前仅完成了状态检查，**尚未执行**关闭/启动。"
            )

    if _tools_irrelevant_to_request(user_question, tool_call_records):
        lines.append(
            "\n**提示**：本轮未执行与时间同步相关的命令（如 timedatectl / chronyc）。"
            "请重新确认诊断方案，或让我直接执行时间检查与同步步骤。"
        )

    if user_question and "nginx" in user_question.lower():
        for tc in completed:
            data = (tc.get("result") or {}).get("data") or {}
            if data.get("active") is True:
                lines.append("\n**nginx 服务当前运行正常。**")
                break

    if len(lines) <= 2:
        lines.append("\n请根据上述工具结果进一步说明您的现象，我可继续帮您排查。")

    return "\n".join(lines)


async def stream_final_summary(
    user_question: str,
    tool_call_records: List[dict],
    plan_data: dict | None = None,
) -> AsyncGenerator[str, None]:
    """流式生成最终总结文本（含结论标题）。"""
    tool_call_records = enrich_tool_records_for_summary(user_question, tool_call_records)
    if is_process_cpu_query(user_question) and _processes_from_records(tool_call_records):
        yield build_process_list_conclusion(user_question, tool_call_records)
        return
    if is_network_speed_query(user_question) and _network_speed_from_records(tool_call_records):
        yield build_network_speed_conclusion(user_question, tool_call_records)
        return
    if _tools_irrelevant_to_request(user_question, tool_call_records):
        yield build_rule_based_conclusion(user_question, tool_call_records)
        return
    if _user_requests_write_action(user_question) and not _write_action_satisfied(user_question, tool_call_records):
        yield build_rule_based_conclusion(user_question, tool_call_records)
        return

    prompt = _build_summary_user_prompt(user_question, tool_call_records, plan_data)
    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    from app.services.chat_service import call_deepseek

    header_sent = False
    body_len = 0
    try:
        async for chunk in call_deepseek(messages, stream=True, use_tools=False):
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {})
            if "content" not in delta or not delta["content"]:
                continue
            token = delta["content"]
            if not header_sent:
                if "## 执行结论" in token:
                    header_sent = True
                else:
                    yield CONCLUSION_HEADER
                    header_sent = True
            body_len += len(token)
            yield token
    except Exception:
        body_len = 0

    if not header_sent or body_len < 60:
        if plan_data:
            yield build_plan_final_conclusion(user_question, tool_call_records, plan_data)
        elif is_process_cpu_query(user_question) and _processes_from_records(tool_call_records):
            yield build_process_list_conclusion(user_question, tool_call_records)
        else:
            yield build_rule_based_conclusion(user_question, tool_call_records)


def build_approval_rejection_conclusion(
    user_question: str,
    tool_call_records: List[dict],
    rejected_tool: dict,
    reject_reason: str = "",
    approval_status: str = "rejected",
) -> str:
    """管理员拒绝或审批超时后，基于已完成检查生成执行结论。"""
    from app.services.chat_service import preview_tool_command

    is_timeout = approval_status == "timeout"
    lines = [CONCLUSION_HEADER]

    if is_timeout:
        lines.append("本次运维操作因**审批超时**已中止，高危命令**未在虚拟机执行**。")
    else:
        lines.append("本次运维操作因**管理员审批未通过**已中止，目标命令**未在虚拟机执行**。")

    if reject_reason:
        lines.append(f"\n**说明**：{reject_reason}")

    completed = [tc for tc in tool_call_records if tc.get("status") == "completed"]
    if completed:
        lines.append("\n**已完成检查**：")
        for tc in completed:
            lines.append(f"- {_tool_record_summary(tc)}")

    rej_name = rejected_tool.get("toolName", "未知工具")
    preview = preview_tool_command(rej_name, rejected_tool.get("params") or {})
    if preview:
        lines.append(f"\n**未执行的操作**：`{preview}`")
    else:
        lines.append(f"\n**未执行的操作**：`{rej_name}`")

    lines.append("\n**后续建议**：")
    if is_timeout:
        lines.append("- 如需继续，请重新发起并在审批时限内完成管理员确认；")
    else:
        lines.append("- 如需继续，请联系管理员说明业务必要性后重新发起；")
    lines.append("- 或调整方案后告诉我，我可帮您重新制定执行步骤。")

    if user_question and "nginx" in user_question.lower():
        for tc in completed:
            data = (tc.get("result") or {}).get("data") or {}
            if data.get("active") is True:
                lines.append("\n**当前状态**：nginx 服务仍在运行，本次未执行关闭/重启操作。")
                break

    return "\n".join(lines)
