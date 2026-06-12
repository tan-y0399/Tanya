"""
工具输出格式化 — 将原始 SSH/命令结果转为结构化数据与自然语言摘要，
供前端展示与 LLM 二次总结使用。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def parse_systemctl_status(raw: str, service_name: str = "") -> Dict[str, Any]:
    """解析 systemctl status 输出为结构化字段。"""
    if not raw or "not found" in raw.lower() or "could not be found" in raw.lower():
        label = service_name or "服务"
        return {
            "active": False,
            "state": "not-found",
            "substate": "",
            "summary": f"{label} 未找到或未安装",
            "loaded": "",
            "main_pid": None,
            "since": "",
            "memory": "",
        }

    active_m = re.search(r"Active:\s*(\S+)\s*\((\w+)\)", raw)
    state = active_m.group(1) if active_m else "unknown"
    substate = active_m.group(2) if active_m else ""
    is_running = state.lower() == "active" and substate.lower() == "running"

    loaded_m = re.search(r"Loaded:\s*([^;]+);\s*(\w+)", raw)
    loaded = loaded_m.group(2) if loaded_m else ""

    pid_m = re.search(r"Main PID:\s*(\d+)", raw)
    main_pid = int(pid_m.group(1)) if pid_m else None

    since_m = re.search(r"since\s+([^;]+);", raw)
    since = since_m.group(1).strip() if since_m else ""

    mem_m = re.search(r"Memory:\s*([^\n]+)", raw)
    memory = mem_m.group(1).strip() if mem_m else ""

    name = service_name or "服务"
    if is_running:
        summary = f"🟢 {name} 运行正常（{state}/{substate}）"
        if since:
            summary += f"，自 {since} 起"
    elif state.lower() in ("inactive", "dead"):
        summary = f"🔴 {name} 未运行（{state}）"
    elif state.lower() == "failed":
        summary = f"🔴 {name} 启动失败（{state}）"
    else:
        summary = f"🟡 {name} 状态：{state}（{substate}）"

    return {
        "active": is_running,
        "state": state,
        "substate": substate,
        "loaded": loaded,
        "main_pid": main_pid,
        "since": since,
        "memory": memory,
        "summary": summary,
    }


def _summarize_disk(data: dict) -> str:
    disks = data.get("disks") or []
    if not disks:
        return "未获取到磁盘信息"
    parts = []
    for d in disks[:5]:
        pct = d.get("use_percent", "?")
        mount = d.get("mount", d.get("filesystem", ""))
        icon = "🔴" if str(pct).replace("%", "").isdigit() and int(str(pct).replace("%", "")) > 80 else "🟢"
        parts.append(f"{icon} {mount} 已用 {pct}")
    return "；".join(parts)


def _summarize_cpu(data: dict) -> str:
    usage = data.get("cpu_usage", data.get("usage", "?"))
    cores = data.get("cpu_cores", data.get("cores", "?"))
    load = data.get("load_1_5_15", data.get("load", ""))
    return f"CPU {usage}%（{cores} 核），负载 {load}"


def _parse_network_connections(raw: str) -> Dict[str, Any]:
    """解析 ss -tuln 输出，提取监听端口与统计。"""
    listen_ports: List[Dict[str, str]] = []
    tcp_listen = udp_listen = 0
    for line in (raw or "").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0].lower()
        state = parts[1] if len(parts) > 1 else ""
        if proto == "tcp" and state == "LISTEN":
            tcp_listen += 1
            local = parts[4] if len(parts) > 4 else ""
            listen_ports.append({"proto": "tcp", "local": local, "state": "LISTEN"})
        elif proto == "udp" and state in ("UNCONN", "LISTEN"):
            udp_listen += 1
            local = parts[4] if len(parts) > 4 else ""
            listen_ports.append({"proto": "udp", "local": local, "state": state})

    notable = []
    port_hints = {
        "22": "SSH 远程管理",
        "80": "HTTP Web 服务",
        "443": "HTTPS",
        "5432": "PostgreSQL 数据库",
        "6379": "Redis 缓存",
        "8000": "应用/API 服务",
        "5000": "开发/Web 服务",
        "323": "Chrony/NTP",
    }
    for p in listen_ports[:12]:
        local = p.get("local", "")
        port = local.rsplit(":", 1)[-1] if ":" in local else ""
        hint = port_hints.get(port, "")
        bind = "本机" if local.startswith("127.0.0.1") or local.startswith("[::1]") else "全网"
        label = f"{p['proto'].upper()} {local}"
        if hint:
            label += f"（{hint}）"
        label += f"，{bind}监听"
        notable.append(label)

    summary = f"共 {tcp_listen} 个 TCP 监听、{udp_listen} 个 UDP 端口"
    if notable:
        summary += "；" + "；".join(notable[:5])
        if len(notable) > 5:
            summary += f" 等共 {len(listen_ports)} 项"
    return {
        "tcp_listen_count": tcp_listen,
        "udp_listen_count": udp_listen,
        "listen_ports": listen_ports[:20],
        "notable": notable,
        "summary": summary,
    }


def _summarize_memory(data: dict) -> str:
    used = data.get("mem_used_mb", data.get("used_mb", "?"))
    total = data.get("mem_total_mb", data.get("total_mb", "?"))
    pct = data.get("usage_pct", data.get("mem_usage_pct", "?"))
    free = data.get("mem_free_mb", data.get("available_mb"))
    swap_used = data.get("swap_used_mb")
    swap_total = data.get("swap_total_mb")
    summary = f"内存已用 {used}/{total} MB（{pct}%）"
    if free not in (None, "?"):
        summary += f"，可用 {free} MB"
    if swap_total not in (None, "?", 0, "0"):
        summary += f"；Swap {swap_used or '?'}/{swap_total} MB"
    return summary


def _summarize_network(data: dict) -> str:
    raw = (data.get("raw") or "").strip()
    if not raw:
        return "未获取到网络连接信息"
    parsed = _parse_network_connections(raw)
    data.update(parsed)
    return parsed.get("summary", "网络连接状态已查询")


def _summarize_network_speed(data: dict) -> str:
    if data.get("summary"):
        return str(data["summary"])
    primary = data.get("primary") or {}
    if not primary:
        return "网速采样完成"
    emoji = {"idle": "⚪", "low": "🟢", "normal": "🟢", "high": "🟡", "very_high": "🟠"}.get(primary.get("rating"), "🟢")
    return (
        f"{emoji} {primary.get('iface', '?')}："
        f"下行 {primary.get('rx_kbps', '?')} KB/s，上行 {primary.get('tx_kbps', '?')} KB/s；"
        f"{primary.get('rating_label', '已采样')}"
    )


def _parse_chronyc_tracking(raw: str) -> dict:
    """解析 chronyc tracking 输出。"""
    info: dict = {}
    for line in (raw or "").splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        info[key.strip()] = val.strip()
    summary_parts = []
    if info.get("System time"):
        summary_parts.append(f"系统时间：{info['System time']}")
    if info.get("Last offset"):
        summary_parts.append(f"偏差 {info['Last offset']}")
    if info.get("Leap status"):
        summary_parts.append(f"闰秒 {info['Leap status']}")
    summary = "；".join(summary_parts) if summary_parts else "chrony 跟踪状态已查询"
    return {"parsed": info, "summary": summary}


def _parse_timedatectl_status(raw: str) -> dict:
    """解析 timedatectl status 输出。"""
    text = raw or ""
    sync = "NTP synchronized: yes" in text or "System clock synchronized: yes" in text
    ntp = "NTP service: active" in text or "NTP enabled: yes" in text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    local = next((ln for ln in lines if ln.startswith("Local time:")), "")
    summary = f"{'🟢' if sync else '🟡'} "
    if local:
        summary += local.replace("Local time:", "本地时间").strip()
    else:
        summary += "时间状态已查询"
    summary += f"；NTP {'已同步' if sync else '未同步'}"
    if ntp:
        summary += "，NTP 服务运行中"
    return {"synced": sync, "ntp_active": ntp, "summary": summary}


def _parse_ps_aux(raw: str) -> List[dict]:
    """解析 ps aux 输出为进程列表。"""
    rows: List[dict] = []
    lines = (raw or "").strip().splitlines()
    for line in lines[1:] if lines else []:
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        try:
            rows.append({
                "user": parts[0],
                "pid": int(parts[1]),
                "cpu_pct": float(parts[2]),
                "mem_pct": float(parts[3]),
                "cmd": parts[10][:200],
            })
        except (ValueError, IndexError):
            continue
    return rows


def _summarize_process_list(data: dict) -> str:
    procs = data.get("processes") or _parse_ps_aux(data.get("raw") or "")
    if not procs:
        return "未获取到进程列表"
    top = procs[0]
    sort_by = (data.get("sort_by") or "cpu").lower()
    metric = "CPU" if sort_by != "mem" else "内存"
    val = top["cpu_pct"] if sort_by != "mem" else top["mem_pct"]
    cmd = top.get("cmd") or "?"
    return (
        f"占用{metric}最高：PID **{top['pid']}**（{top.get('user', '?')}）"
        f" {metric} **{val}%**，命令 `{cmd[:80]}`"
    )


def build_display_summary(tool_name: str, result: dict) -> str:
    """生成面向用户的单行/多行摘要。"""
    if not result.get("success"):
        return f"❌ {result.get('error', '执行失败')}"

    data = result.get("data") or {}
    if isinstance(data, str):
        return data[:500]

    if data.get("summary"):
        return str(data["summary"])

    if tool_name in ("get_service_status", "manage_service"):
        svc = data.get("service", "")
        if tool_name == "manage_service":
            action = data.get("action", "")
            return f"✅ 已对 {svc} 执行 {action}：{data.get('result', '')[:120]}"
        parsed = data if "active" in data else parse_systemctl_status(data.get("status", ""), svc)
        return parsed.get("summary", f"{svc} 状态已查询")

    if tool_name in ("get_disk_usage", "get_disk_info"):
        return _summarize_disk(data)

    if tool_name == "get_cpu_info":
        return _summarize_cpu(data)

    if tool_name == "get_memory_info":
        return _summarize_memory(data)

    if tool_name == "get_network_connections":
        return _summarize_network(data)

    if tool_name == "get_network_speed":
        return _summarize_network_speed(data)

    if tool_name in ("execute_command", "run_command"):
        stdout = (data.get("stdout") or data.get("raw") or "")
        stderr = (data.get("stderr") or "")[:200]
        code = data.get("exit_code", data.get("exitCode", 0))
        if "Reference ID" in stdout or ("System time" in stdout and "Leap status" in stdout):
            parsed = _parse_chronyc_tracking(stdout)
            data["parsed"] = parsed.get("parsed")
            data["summary"] = parsed.get("summary")
            return parsed.get("summary", "chrony 状态已查询")
        if "Local time:" in stdout and ("NTP" in stdout or "System clock" in stdout):
            parsed = _parse_timedatectl_status(stdout)
            data["parsed"] = parsed
            data["summary"] = parsed.get("summary")
            return parsed.get("summary", "时间状态已查询")
        if code not in (0, None):
            hint = stderr.strip() or stdout.strip().split("\n")[0] if stdout else ""
            return f"❌ 命令失败（退出码 {code}）" + (f"：{hint[:120]}" if hint else "")
        if data.get("diagnostic_negative"):
            return f"🟡 {data.get('summary') or '检查完成：条件不满足（未安装或未找到）'}"
        if data.get("summary"):
            return str(data["summary"])
        if stdout:
            first = stdout.strip().split("\n")[0]
            return f"✅ 命令已执行：{first}"
        return "✅ 命令已执行成功"

    if tool_name == "get_logs":
        raw = (data.get("raw") or data.get("logs") or "")[:150]
        return f"已获取日志：{raw}..." if len(raw) >= 150 else f"已获取日志：{raw}"

    if tool_name in ("list_processes", "get_process_list"):
        return _summarize_process_list(data)

    return f"✅ {tool_name} 执行完成"


def format_for_llm(tool_name: str, result: dict) -> str:
    """压缩工具结果供 LLM 阅读，避免超长原始 JSON。"""
    summary = build_display_summary(tool_name, result)
    if not result.get("success"):
        return summary

    data = result.get("data") or {}
    compact: Dict[str, Any] = {"summary": summary}

    if tool_name == "get_service_status":
        for k in ("service", "active", "state", "substate", "main_pid", "since", "memory", "loaded"):
            if k in data:
                compact[k] = data[k]
    elif tool_name in ("get_disk_usage", "get_disk_info") and data.get("disks"):
        compact["disks"] = [
            {kk: d.get(kk) for kk in ("mount", "filesystem", "size", "used", "available", "use_percent")}
            for d in (data.get("disks") or [])[:8]
        ]
    elif tool_name == "get_cpu_info":
        compact.update({k: data[k] for k in data if k in ("cpu_usage", "cpu_cores", "load_1_5_15")})
    elif tool_name == "get_memory_info":
        compact.update({k: data[k] for k in data if k.startswith("mem_") or k.endswith("_mb") or "usage" in k})
    elif tool_name == "get_network_connections":
        raw = data.get("raw") or ""
        parsed = _parse_network_connections(raw) if raw else {}
        compact.update({
            k: parsed.get(k)
            for k in ("tcp_listen_count", "udp_listen_count", "notable", "summary")
            if parsed.get(k) is not None
        })
        if parsed.get("listen_ports"):
            compact["listen_ports"] = parsed["listen_ports"][:15]
    elif tool_name == "get_network_speed":
        primary = data.get("primary") or {}
        compact.update({
            k: primary.get(k)
            for k in ("iface", "rx_kbps", "tx_kbps", "rx_mbps", "tx_mbps", "rating", "rating_label")
            if primary.get(k) is not None
        })
        if data.get("interfaces"):
            compact["interfaces"] = data["interfaces"][:5]
    elif tool_name in ("list_processes", "get_process_list"):
        procs = data.get("processes") or _parse_ps_aux(data.get("raw") or "")
        compact["processes"] = procs[:10]
        compact["sort_by"] = data.get("sort_by", "cpu")
    elif tool_name in ("execute_command", "run_command"):
        stdout = data.get("stdout") or data.get("raw") or ""
        if "Reference ID" in stdout or ("System time" in stdout and "Leap status" in stdout):
            parsed = _parse_chronyc_tracking(stdout)
            compact["parsed"] = parsed.get("parsed")
            compact["summary"] = parsed.get("summary")
        elif "Local time:" in stdout and ("NTP" in stdout or "System clock" in stdout):
            parsed = _parse_timedatectl_status(stdout)
            compact["parsed"] = {k: parsed[k] for k in ("synced", "ntp_active", "summary") if k in parsed}
            compact["summary"] = parsed.get("summary")
        else:
            compact["stdout_preview"] = stdout[:800] if len(stdout) > 800 else stdout
            compact["exit_code"] = data.get("exit_code", 0)
    else:
        # 其他工具保留精简字段，去掉超大 raw
        for k, v in data.items():
            if k in ("raw", "status", "stdout") and isinstance(v, str) and len(v) > 500:
                compact[f"{k}_preview"] = v[:500] + "…"
            elif isinstance(v, (str, int, float, bool)) or v is None:
                compact[k] = v
            elif isinstance(v, list) and len(v) <= 10:
                compact[k] = v

    compact["hint"] = "请用简洁中文向用户解释上述结果，不要复述 JSON。"
    return json.dumps(compact, ensure_ascii=False)


def enrich_tool_result(tool_name: str, result: dict) -> dict:
    """为工具结果附加 display_summary，并结构化常见工具数据。"""
    if not isinstance(result, dict):
        return result

    out = dict(result)
    data = out.get("data")
    if not out.get("success") or not isinstance(data, dict):
        out["display_summary"] = build_display_summary(tool_name, out)
        return out

    # get_service_status：解析 systemctl 原文（兼容旧版仅含 status 字段的返回）
    if tool_name == "get_service_status":
        if "status" in data and isinstance(data["status"], str) and "active" not in data:
            parsed = parse_systemctl_status(data["status"], data.get("service", ""))
            data = {**data, **parsed, "raw_status": data["status"]}
            del data["status"]
            out["data"] = data

    if tool_name == "manage_service" and "result" in data and isinstance(data["result"], str):
        svc = data.get("service", "")
        if "Active:" in data["result"]:
            parsed = parse_systemctl_status(data["result"], svc)
            data["service_state"] = parsed
            data["summary"] = parsed.get("summary", f"{svc} {data.get('action')} 完成")
        out["data"] = data

    if tool_name == "get_memory_info":
        try:
            total = float(data.get("mem_total_mb") or 0)
            used = float(data.get("mem_used_mb") or 0)
            if total > 0:
                pct = round(used / total * 100, 1)
                data["mem_usage_pct"] = pct
                data["usage_pct"] = pct
                out["data"] = data
        except (TypeError, ValueError):
            pass

    if tool_name in ("list_processes", "get_process_list") and data.get("raw"):
        data = dict(data)
        data["processes"] = _parse_ps_aux(data.get("raw") or "")
        out["data"] = data

    if tool_name == "get_network_connections" and data.get("raw"):
        parsed = _parse_network_connections(data["raw"])
        data = {**data, **parsed}
        out["data"] = data

    out["display_summary"] = build_display_summary(tool_name, out)
    return out
