"""运维仪表盘 API —— 从远程麒麟VM获取真实系统数据"""
import re
import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.audit import AuditRecord
from app.models.approval import Approval

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])

# 线程池用于并行执行 SSH 调用（避免阻塞事件循环）
_executor = ThreadPoolExecutor(max_workers=4)

# 单次 SSH 调用的超时秒数（SSH 层有重试，单个调用可设短些）
SSH_CALL_TIMEOUT = 3

# 内存缓存（仪表盘数据过期时间）
_CACHE_TTL = 10  # 秒（实时趋势）
_history_cache = {}
_metrics_cache: dict = {}
_services_cache: dict = {}


def _parse_kv(text: str) -> dict:
    """解析 ===KEY===\\nVALUE 格式的文本。"""
    result = {}
    current_key = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("===") and line.endswith("==="):
            current_key = line.strip("=")
            result[current_key] = ""
        elif current_key:
            result[current_key] = result.get(current_key, "") + ("\n" if result.get(current_key) else "") + line
    for k in result:
        if isinstance(result[k], str):
            result[k] = result[k].strip()
    return result


def _uptime_to_chinese(raw_uptime: str) -> str:
    if not raw_uptime:
        return "N/A"
    raw = raw_uptime.strip()
    raw = re.sub(r'^up\s+', '', raw)
    raw = re.sub(r'(\d+)\s*days?', r'\1天', raw)
    raw = re.sub(r'(\d+)\s*hours?', r'\1小时', raw)
    raw = re.sub(r'(\d+)\s*minutes?', r'\1分钟', raw)
    raw = re.sub(r'(\d+)\s*seconds?', r'\1秒', raw)
    raw = raw.replace(',', '').strip()
    raw = re.sub(r'(\d+)\s*weeks?', r'\1周', raw)
    return raw if raw else "N/A"


def _service_uptime_to_chinese(raw_since: str) -> str:
    if not raw_since or raw_since == "N/A":
        return "N/A"
    try:
        parts = raw_since.strip().split()
        if len(parts) >= 3:
            return f"{parts[1]} {parts[2][:5]}"
    except Exception:
        pass
    return raw_since[:16]


def _get_history_cache(server_id: str):
    key = server_id or "default"
    if key not in _history_cache:
        _history_cache[key] = {
            "cpu": [], "memory": [], "disk": [], "updated_at": None
        }
    return _history_cache[key]


def _update_history(server_id: str, current_metrics: dict):
    cache = _get_history_cache(server_id)
    now = datetime.utcnow()
    time_label = now.strftime("%H:%M")

    for key in ["cpu", "memory", "disk"]:
        raw = current_metrics.get(key, {})
        data = raw.get("data", {}) if isinstance(raw, dict) and raw.get("success") else (raw or {})
        if data:
            if key == "cpu":
                val = float(data.get("cpu_usage", 0))
            elif key == "memory":
                total = int(float(data.get("mem_total_mb", 1)))
                used = int(float(data.get("mem_used_mb", 0)))
                val = round(used / total * 100, 1) if total > 0 else 0
            else:  # disk
                disks = data.get("disks", [])
                root = disks[0] if disks else {}
                val = float(str(root.get("use_percent", "0%")).replace("%", ""))
            cache[key].append({"time": time_label, "value": val})

    for key in ["cpu", "memory", "disk"]:
        if len(cache[key]) > 120:
            cache[key] = cache[key][-120:]

    cache["updated_at"] = now


def _call_ssh_with_timeout(func, *args, **kwargs):
    """在线程池中执行单个SSH调用，带超时保护"""
    server_id = kwargs.pop("server_id", None)
    try:
        future = _executor.submit(func, *args, server_id=server_id, **kwargs)
        return future.result(timeout=SSH_CALL_TIMEOUT)
    except FutureTimeout:
        logger.warning(f"SSH call {func.__name__} timed out after {SSH_CALL_TIMEOUT}s")
        return {"success": False, "error": f"操作超时（>{SSH_CALL_TIMEOUT}秒）"}
    except Exception as e:
        logger.warning(f"SSH call {func.__name__} failed: {e}")
        return {"success": False, "error": str(e)}


def _fetch_vm_metrics_parallel(server_id: str = None):
    """并行从远程VM获取实时指标（4个SSH调用同时进行）"""
    from app.services.remote_executor import get_system_info, get_cpu_info, get_memory_info, get_disk_info

    tasks = [
        ("cpu", get_cpu_info, server_id),
        ("memory", get_memory_info, server_id),
        ("disk", get_disk_info, server_id),
        ("system", get_system_info, server_id),
    ]

    futures = {}
    for name, func, sid in tasks:
        futures[name] = _executor.submit(func, sid)

    metrics = {}
    for name in futures:
        try:
            metrics[name] = futures[name].result(timeout=SSH_CALL_TIMEOUT)
        except FutureTimeout:
            logger.warning(f"Metric {name} SSH call timed out")
            metrics[name] = {"success": False, "error": "超时"}
        except Exception as e:
            logger.warning(f"Metric {name} SSH call failed: {e}")
            metrics[name] = {"success": False, "error": str(e)}

    return metrics


def _check_services_parallel(server_id: str = None):
    """并行检查多个服务状态（批量查询，减少 SSH 调用次数）"""
    from app.services.remote_executor import run_command

    services = [
        {"name": "PostgreSQL", "port": 5432, "unit": "postgresql"},
        {"name": "Nginx", "port": 80, "unit": "nginx"},
        {"name": "KylinOps Backend", "port": 8000, "unit": "kylinops"},
        {"name": "Redis", "port": 6379, "unit": "redis"},
    ]

    # 批量查询所有服务状态（一次 SSH 调用）
    status_cmd = "; ".join(f"echo '==={svc['unit']}==='; systemctl is-active {svc['unit']} 2>/dev/null || echo 'unknown'" for svc in services)
    status_result = _call_ssh_with_timeout(run_command, status_cmd, server_id=server_id)

    status_map = {}
    if status_result.get("success") and status_result.get("data"):
        raw = status_result["data"].get("stdout", "")
        status_map = _parse_kv(raw)

    # 批量查询运行中服务的 uptime（一次 SSH 调用）
    running_units = [svc["unit"] for svc in services if status_map.get(svc["unit"], "").strip() == "active"]
    uptime_map = {}
    if running_units:
        uptime_cmd = "; ".join(
            f"echo '==={u}==='; systemctl show {u} -p ActiveEnterTimestamp 2>/dev/null | cut -d= -f2"
            for u in running_units
        )
        uptime_result = _call_ssh_with_timeout(run_command, uptime_cmd, server_id=server_id)
        if uptime_result.get("success") and uptime_result.get("data"):
            raw = uptime_result["data"].get("stdout", "")
            uptime_map = _parse_kv(raw)

    results = []
    for svc in services:
        raw_status = status_map.get(svc["unit"], "").strip()
        status = "running" if raw_status == "active" else ("stopped" if raw_status else "unknown")
        uptime = "N/A"
        if status == "running":
            since_raw = uptime_map.get(svc["unit"], "")
            uptime = _service_uptime_to_chinese(since_raw) if since_raw else "N/A"
        results.append({"name": svc["name"], "port": svc["port"], "status": status, "uptime": uptime})

    return results


@router.get("/overview")
async def dashboard_overview(server_id: str = None, db: AsyncSession = Depends(get_db)):
    """仪表盘总览 —— SSH 调用并行执行，最多 5 秒返回"""

    # 数据库查询（异步，不阻塞）
    total_audit_q = select(func.count()).select_from(AuditRecord)
    total_audit = (await db.execute(total_audit_q)).scalar() or 0
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_q = select(func.count()).select_from(AuditRecord).where(AuditRecord.timestamp >= today_start)
    today_audit = (await db.execute(today_q)).scalar() or 0
    pending_q = select(func.count()).select_from(Approval).where(Approval.status == "pending")
    pending_approvals = (await db.execute(pending_q)).scalar() or 0

    # 检查缓存是否有效
    cache_key = server_id or "default"
    cache_entry = _metrics_cache.get(cache_key, {})
    cache_time = cache_entry.get("_ts", 0)
    now_ts = datetime.utcnow().timestamp()

    if now_ts - cache_time < _CACHE_TTL and cache_entry:
        vm_metrics = cache_entry.get("metrics", {})
        services = cache_entry.get("services", [])
        fresh_data = False
    else:
        loop = asyncio.get_event_loop()

        # 并行执行 SSH 指标采集和服务检查
        metrics_future = loop.run_in_executor(_executor, _fetch_vm_metrics_parallel, server_id)
        services_future = loop.run_in_executor(_executor, _check_services_parallel, server_id)

        try:
            vm_metrics = await asyncio.wait_for(metrics_future, timeout=SSH_CALL_TIMEOUT + 2)
        except asyncio.TimeoutError:
            vm_metrics = {}
            logger.warning("Dashboard metrics fetch timed out, will try stale cache")

        try:
            services = await asyncio.wait_for(services_future, timeout=SSH_CALL_TIMEOUT + 4)
        except asyncio.TimeoutError:
            services = []

        # SSH 全部失败时，回退到旧缓存数据
        has_metrics = any(
            isinstance(vm_metrics.get(k, {}), dict) and vm_metrics.get(k, {}).get("success")
            for k in ["cpu", "memory", "disk"]
        )
        if not has_metrics and cache_entry:
            vm_metrics = cache_entry.get("metrics", vm_metrics)
            services = cache_entry.get("services", services)
            fresh_data = False
        else:
            # 缓存新结果
            _metrics_cache[cache_key] = {"metrics": vm_metrics, "services": services, "_ts": now_ts}
            fresh_data = True

    if fresh_data:
        _update_history(server_id, vm_metrics)
    cache = _get_history_cache(server_id)

    def _extract(raw):
        if isinstance(raw, dict) and raw.get("success"):
            return raw.get("data", {})
        return raw or {}

    cpu = _extract(vm_metrics.get("cpu", {}))
    mem = _extract(vm_metrics.get("memory", {}))
    disk = _extract(vm_metrics.get("disk", {}))
    sys_info = _extract(vm_metrics.get("system", {}))

    cpu_usage = float(cpu.get("cpu_usage", 0))
    loads = (cpu.get("load_1_5_15", "0,0,0") or "0,0,0").split(",")

    mem_total = int(float(mem.get("mem_total_mb", 0)))
    mem_used = int(float(mem.get("mem_used_mb", 0)))
    mem_pct = round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0

    disks = disk.get("disks", [])
    root_disk = disks[0] if disks else {}
    disk_pct = float(str(root_disk.get("use_percent", "0%")).replace("%", ""))

    return {
        "code": 0,
        "data": {
            "stats": {
                "totalOperations": total_audit,
                "todayOperations": today_audit,
                "pendingApprovals": pending_approvals,
                "systemUptime": _uptime_to_chinese(sys_info.get("uptime", "")),
                "mcpToolsOnline": sum(1 for s in services if s["status"] == "running"),
                "mcpToolsTotal": len(services),
            },
            "metrics": {
                "cpu": {
                    "current": cpu_usage,
                    "cores": int(cpu.get("cpu_cores", 0)),
                    "load1": float(loads[0] or 0),
                    "load5": float(loads[1] or 0) if len(loads) > 1 else 0,
                    "load15": float(loads[2] or 0) if len(loads) > 2 else 0,
                    "history": cache.get("cpu", []),
                },
                "memory": {
                    "current": mem_pct,
                    "total_mb": mem_total,
                    "used_mb": mem_used,
                    "available_mb": int(float(mem.get("mem_available_mb", 0))),
                    "history": cache.get("memory", []),
                },
                "disk": {
                    "current": disk_pct,
                    "size": root_disk.get("size", "N/A"),
                    "used": root_disk.get("used", "N/A"),
                    "available": root_disk.get("available", "N/A"),
                    "history": cache.get("disk", []),
                },
                "network": vm_metrics.get("network", {}),
            },
            "anomalies": [],
            "services": services,
        },
    }


@router.get("/history")
async def metric_history(server_id: str = None, metric: str = "cpu", hours: int = 24):
    cache = _get_history_cache(server_id)
    data = cache.get(metric, [])
    return {"code": 0, "data": {"metric": metric, "history": data}}
