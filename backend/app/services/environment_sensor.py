"""
环境感知层 — 统一的系统状态抽象，自适应感知计划，关联分析

提供:
  1. 自适应感知计划 (不同任务类型 → 不同采集策略)
  2. 统一结果格式 (标准化 data/success/timestamp/credibility)
  3. 关联分析 (进程↔端口, 进程↔文件, 服务↔端口)
  4. 结果缓存 (避免重复SSH调用，时间戳一致性)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from enum import Enum

from app.core.config import settings
from app.services.context_credibility import CredibilityTracker, CredibilityLevel

logger = logging.getLogger(__name__)


class SensingPlan(Enum):
    QUICK_CHECK = "quick_check"        # 快速巡检: CPU/内存/磁盘
    FULL_CHECK = "full_check"          # 全量感知: 所有指标
    FAULT_DIAG = "fault_diagnosis"     # 故障诊断: +进程/日志/连接
    NETWORK_DIAG = "network_diag"      # 网络诊断: +端口/连接/防火墙
    SECURITY_AUDIT = "security_audit"  # 安全审计: +用户/权限/日志


SENSING_PLANS = {
    SensingPlan.QUICK_CHECK: [
        "get_cpu_info", "get_memory_info", "get_disk_info",
    ],
    SensingPlan.FULL_CHECK: [
        "get_system_info", "get_cpu_info", "get_memory_info",
        "get_disk_info", "get_network_connections",
        "get_process_list", "get_service_status",
    ],
    SensingPlan.FAULT_DIAG: [
        "get_system_info", "get_cpu_info", "get_memory_info",
        "get_disk_info", "get_process_list", "get_logs",
        "get_network_connections",
    ],
    SensingPlan.NETWORK_DIAG: [
        "get_network_connections", "get_network_info",
        "get_service_status",
    ],
    SensingPlan.SECURITY_AUDIT: [
        "get_users", "get_groups", "get_logs",
        "get_network_connections", "get_process_list",
    ],
}


# 标准化结果
def _normalize(data: dict, success: bool = True, error: str = "") -> dict:
    return {
        "success": success,
        "data": data if success else {},
        "error": error,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "remote_executor",
        "credibility": CredibilityLevel.TRUSTED.value,
    }


# 感知结果缓存
_sense_cache: Dict[str, dict] = {}
_CACHE_TTL = 30  # 秒


def _cache_key(server_id: str = None) -> str:
    return server_id or "default"


def _cached(key: str) -> Optional[dict]:
    entry = _sense_cache.get(key)
    if entry and (datetime.utcnow() - entry["_ts"]).seconds < _CACHE_TTL:
        return entry
    return None


def _set_cache(key: str, data: dict):
    data["_ts"] = datetime.utcnow()
    _sense_cache[key] = data


# ═══════════════════════════════════════════
# 感知执行
# ═══════════════════════════════════════════
def sense(plan: SensingPlan = SensingPlan.QUICK_CHECK,
          server_id: str = None,
          extra_tools: List[str] = None) -> dict:
    """执行感知计划，返回统一格式的感知结果"""
    from app.services.remote_executor import execute_tool

    tools = list(SENSING_PLANS.get(plan, SENSING_PLANS[SensingPlan.QUICK_CHECK]))
    if extra_tools:
        tools.extend(extra_tools)

    result = {
        "plan": plan.value,
        "server_id": server_id or "default",
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": {},
        "credibility": CredibilityTracker(),
    }

    for tool_name in tools:
        try:
            raw = execute_tool(tool_name, server_id=server_id) if server_id else execute_tool(tool_name)
            result["metrics"][tool_name] = raw if raw else _normalize({}, False, "无响应")
            result["credibility"].tag_source("system_tool", tool_name)
        except Exception as e:
            result["metrics"][tool_name] = _normalize({}, False, str(e))

    return result


def sense_cached(plan: SensingPlan = SensingPlan.QUICK_CHECK,
                 server_id: str = None,
                 force: bool = False) -> dict:
    """带缓存的感知"""
    key = _cache_key(server_id)
    if not force:
        cached = _cached(key)
        if cached and plan.value in cached.get("_plans", {}):
            return cached["_plans"][plan.value]

    result = sense(plan, server_id)
    entry = _cached(key) or {}
    entry.setdefault("_plans", {})[plan.value] = result
    _set_cache(key, entry)
    return result


# ═══════════════════════════════════════════
# 关联分析
# ═══════════════════════════════════════════
def correlate_process_port(process_result: dict, network_result: dict) -> List[dict]:
    """关联进程与监听端口"""
    correlations = []
    proc_data = process_result.get("data", {}) if process_result.get("success") else {}
    net_data = network_result.get("data", {}) if network_result.get("success") else {}

    # 从进程列表和网络连接中提取端口
    proc_raw = proc_data.get("raw", "") if isinstance(proc_data, dict) else ""
    net_raw = net_data.get("raw", "") if isinstance(net_data, dict) else ""

    import re
    # 从网络输出提取端口→进程映射
    port_pattern = re.compile(r':(\d+)\s+.*?(?:users:\(\("([^"]+)"')
    net_ports = {}
    for line in net_raw.split("\n") if net_raw else []:
        m = port_pattern.search(line)
        if m:
            net_ports[int(m.group(1))] = m.group(2)

    # 从进程输出提取 PID→名称
    pid_pattern = re.compile(r'(\d+)\s+(\S+)')
    for line in proc_raw.split("\n") if proc_raw else []:
        parts = line.split()
        if len(parts) >= 11:
            pid = parts[1]
            name = parts[10].split("/")[-1]
            correlations.append({"pid": pid, "process": name, "command": " ".join(parts[10:])})

    return correlations


def correlate_process_file(process_result: dict, file_list: dict = None) -> List[dict]:
    """关联进程与打开的文件"""
    # 简化实现：从进程结果中提取进程信息
    correlations = []
    proc_data = process_result.get("data", {}) if process_result.get("success") else {}
    proc_raw = proc_data.get("raw", "") if isinstance(proc_data, dict) else ""

    for line in (proc_raw or "").split("\n"):
        parts = line.split()
        if len(parts) >= 11:
            correlations.append({
                "pid": parts[1],
                "cpu": parts[2],
                "mem": parts[3],
                "process": parts[10].split("/")[-1],
            })

    return correlations[:20]


def get_system_summary(plan: SensingPlan = SensingPlan.QUICK_CHECK,
                       server_id: str = None) -> dict:
    """获取系统状态摘要（人可读）"""
    result = sense_cached(plan, server_id)
    summary = {"status": "healthy", "issues": [], "warnings": [], "metrics": {}}

    for tool_name, raw in result.get("metrics", {}).items():
        if not raw.get("success"):
            continue
        data = raw.get("data", {})

        if tool_name == "get_cpu_info":
            cpu_usage = float(data.get("cpu_usage", 0))
            summary["metrics"]["cpu"] = cpu_usage
            if cpu_usage > 90:
                summary["issues"].append(f"CPU使用率 {cpu_usage}%")
                summary["status"] = "critical"
            elif cpu_usage > 70:
                summary["warnings"].append(f"CPU使用率偏高 {cpu_usage}%")
                if summary["status"] == "healthy":
                    summary["status"] = "warning"

        elif tool_name == "get_memory_info":
            total = int(float(data.get("mem_total_mb", 1)))
            used = int(float(data.get("mem_used_mb", 0)))
            pct = round(used / total * 100, 1) if total > 0 else 0
            summary["metrics"]["memory"] = pct
            if pct > 90:
                summary["issues"].append(f"内存使用率 {pct}%")
                summary["status"] = "critical"
            elif pct > 80:
                summary["warnings"].append(f"内存使用率偏高 {pct}%")
                if summary["status"] == "healthy":
                    summary["status"] = "warning"

        elif tool_name == "get_disk_info":
            disks = data.get("disks", [])
            for d in disks[:1]:
                pct = float(str(d.get("use_percent", "0%")).replace("%", ""))
                summary["metrics"]["disk"] = pct
                if pct > 90:
                    summary["issues"].append(f"磁盘使用率 {pct}% ({d.get('mount', '?')})")
                    summary["status"] = "critical"
                elif pct > 80:
                    summary["warnings"].append(f"磁盘使用率偏高 {pct}%")
                    if summary["status"] == "healthy":
                        summary["status"] = "warning"

    return summary
