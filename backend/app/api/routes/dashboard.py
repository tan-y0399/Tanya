"""运维仪表盘 API —— 从远程麒麟VM获取真实系统数据"""
import re
import logging
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.audit import AuditRecord
from app.models.approval import Approval
from app.services.remote_executor import (
    get_system_info,
    get_cpu_info,
    get_memory_info,
    get_disk_info
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])

# 内存缓存（Redis不可用时回退）
_history_cache = {}

# Redis 客户端
_redis = None

def _get_redis():
    global _redis
    if _redis is None:
        try:
            import redis as redis_lib
            _redis = redis_lib.from_url(
                "redis://:kylinops_redis@127.0.0.1:6379/0",
                decode_responses=True, socket_connect_timeout=2, socket_timeout=2
            )
        except Exception:
            _redis = False
    return _redis if _redis else None


def _uptime_to_chinese(raw_uptime: str) -> str:
    """将 uptime -p 的英文输出转为中文"""
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


def _get_server_cache(server_id: str):
    """获取缓存，优先 Redis"""
    r = _get_redis()
    cache_key = f"dashboard:cache:{server_id or 'default'}"
    if r:
        try:
            data = r.get(cache_key)
            if data:
                return json.loads(data)
        except Exception:
            pass
    if server_id not in _history_cache:
        _history_cache[server_id] = {
            "cpu": [], "memory": [], "disk": [], "updated_at": None
        }
    return _history_cache[server_id]


def _save_server_cache(server_id: str, cache_data: dict):
    r = _get_redis()
    if r:
        try:
            cache_key = f"dashboard:cache:{server_id or 'default'}"
            r.setex(cache_key, 300, json.dumps(cache_data, default=str))
        except Exception:
            pass


def _update_history_cache(server_id: str, current_metrics: dict):
    cache = _get_server_cache(server_id)
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
        if len(cache[key]) <= 24:
            current_val = cache[key][-1]["value"] if cache[key] else 0
            filled = []
            for i in range(23, -1, -1):
                t = now - timedelta(hours=i)
                filled.append({"time": t.strftime("%H:%M"), "value": current_val})
            cache[key] = filled + cache[key]

    for key in ["cpu", "memory", "disk"]:
        if len(cache[key]) > 48:
            cache[key] = cache[key][-48:]

    cache["updated_at"] = now
    _save_server_cache(server_id, cache)


def _fetch_vm_metrics(server_id: str = None):
    """从远程VM获取实时指标"""
    metrics = {"cpu": {}, "memory": {}, "disk": {}, "network": {}, "system": {}}

    try:
        sys_info = get_system_info(server_id)
        metrics["system"] = sys_info

        cpu_info = get_cpu_info(server_id)
        metrics["cpu"] = cpu_info

        mem_info = get_memory_info(server_id)
        metrics["memory"] = mem_info

        disk_info = get_disk_info(server_id)
        metrics["disk"] = disk_info

    except Exception as e:
        logger.warning(f"Failed to fetch VM metrics: {e}")

    return metrics


def _check_services(server_id: str = None):
    """检查关键服务状态"""
    from app.services.remote_executor import run_command

    services = [
        {"name": "PostgreSQL", "port": 5432, "cmd": "systemctl is-active postgresql"},
        {"name": "Nginx", "port": 80, "cmd": "systemctl is-active nginx"},
        {"name": "KylinOps Backend", "port": 8000, "cmd": "systemctl is-active kylinops"},
        {"name": "Redis", "port": 6379, "cmd": "systemctl is-active redis"},
    ]

    result = []
    for svc in services:
        try:
            output, _, _ = run_command(svc["cmd"], server_id)
            status = "running" if output.strip() == "active" else "stopped"
            uptime = "N/A"
            if status == "running":
                try:
                    since, _, _ = run_command(
                        f"systemctl show {svc['name'].lower().replace(' ', '')} -p ActiveEnterTimestamp 2>/dev/null | cut -d= -f2",
                        server_id
                    )
                    uptime = _service_uptime_to_chinese(since.strip())
                except Exception:
                    pass
            result.append({
                "name": svc["name"], "port": svc["port"],
                "status": status, "uptime": uptime,
            })
        except Exception:
            result.append({
                "name": svc["name"], "port": svc["port"],
                "status": "unknown", "uptime": "N/A",
            })

    return result


@router.get("/overview")
async def dashboard_overview(server_id: str = None, db: AsyncSession = Depends(get_db)):
    total_audit_q = select(func.count()).select_from(AuditRecord)
    total_audit = (await db.execute(total_audit_q)).scalar() or 0
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_q = select(func.count()).select_from(AuditRecord).where(AuditRecord.timestamp >= today_start)
    today_audit = (await db.execute(today_q)).scalar() or 0
    pending_q = select(func.count()).select_from(Approval).where(Approval.status == "pending")
    pending_approvals = (await db.execute(pending_q)).scalar() or 0

    vm_metrics = _fetch_vm_metrics(server_id)
    _update_history_cache(server_id, vm_metrics)
    services = _check_services(server_id)
    cache = _get_server_cache(server_id)

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

    # 内存使用率计算
    mem_total = int(float(mem.get("mem_total_mb", 0)))
    mem_used = int(float(mem.get("mem_used_mb", 0)))
    mem_pct = round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0

    # 磁盘使用率（取根分区）
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
    cache = _get_server_cache(server_id)
    data = cache.get(metric, [])
    return {"code": 0, "data": {"metric": metric, "history": data}}
