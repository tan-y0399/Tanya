"""运维仪表盘 API —— 从远程麒麟VM获取真实系统数据"""
import os
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
_executor = ThreadPoolExecutor(max_workers=8)

# 单次 SSH 调用的超时秒数（Windows→VM NAT 场景下握手偏慢，过短会导致服务状态误判）
SSH_CALL_TIMEOUT = 8
# 仪表盘 overview 整批 SSH 采集上限（避免页面长时间无响应）
DASHBOARD_SSH_TOTAL_TIMEOUT = 15

# 内存缓存（仪表盘数据过期时间）
_CACHE_TTL = 10  # 秒（实时趋势）
HISTORY_WINDOW_MINUTES = 20
HISTORY_SAMPLE_INTERVAL_SEC = 10
HISTORY_MAX_POINTS = (HISTORY_WINDOW_MINUTES * 60) // HISTORY_SAMPLE_INTERVAL_SEC

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_HISTORY_DIR = os.path.join(_BACKEND_ROOT, "data")
_HISTORY_FILE = os.path.join(_HISTORY_DIR, "dashboard_history.json")

_history_cache = {}
_metrics_cache: dict = {}
_services_cache: dict = {}
_history_loaded = False


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


def _uptime_seconds_to_chinese(total_sec: int) -> str:
    if total_sec <= 0:
        return "N/A"
    d = total_sec // 86400
    rem = total_sec % 86400
    h = rem // 3600
    rem %= 3600
    m = rem // 60
    s = rem % 60
    parts: list[str] = []
    if d:
        parts.append(f"{d}天")
    if h:
        parts.append(f"{h}小时")
    if m:
        parts.append(f"{m}分钟")
    if s or not parts:
        parts.append(f"{s}秒")
    return " ".join(parts)


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
    _ensure_history_loaded()
    key = server_id or "default"
    if key not in _history_cache:
        _history_cache[key] = {
            "cpu": [], "memory": [], "disk": [], "updated_at": None
        }
    return _history_cache[key]


def _ensure_history_loaded() -> None:
    global _history_loaded
    if _history_loaded:
        return
    _history_loaded = True
    if not os.path.isfile(_HISTORY_FILE):
        return
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for key, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                _history_cache[key] = {
                    "cpu": entry.get("cpu") or [],
                    "memory": entry.get("memory") or [],
                    "disk": entry.get("disk") or [],
                    "updated_at": entry.get("updated_at"),
                }
                _trim_history(_history_cache[key])
    except Exception as e:
        logger.warning("Failed to load dashboard history: %s", e)


def _persist_history_cache() -> None:
    try:
        os.makedirs(_HISTORY_DIR, exist_ok=True)
        payload = {}
        for key, entry in _history_cache.items():
            payload[key] = {
                "cpu": entry.get("cpu", []),
                "memory": entry.get("memory", []),
                "disk": entry.get("disk", []),
                "updated_at": entry.get("updated_at").isoformat()
                if isinstance(entry.get("updated_at"), datetime)
                else entry.get("updated_at"),
            }
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("Failed to persist dashboard history: %s", e)


def _trim_history(cache: dict) -> None:
    cutoff = datetime.now().timestamp() - HISTORY_WINDOW_MINUTES * 60
    for key in ("cpu", "memory", "disk"):
        series = cache.get(key) or []
        trimmed = []
        for point in series:
            ts = point.get("ts")
            if ts is None:
                continue
            if float(ts) >= cutoff:
                trimmed.append(point)
        if len(trimmed) > HISTORY_MAX_POINTS:
            trimmed = trimmed[-HISTORY_MAX_POINTS:]
        cache[key] = trimmed


def _history_is_empty(cache: dict) -> bool:
    return not any(cache.get(k) for k in ("cpu", "memory", "disk"))


def _extract_metric_values(current_metrics: dict) -> dict[str, float]:
    values: dict[str, float] = {}
    for key in ("cpu", "memory", "disk"):
        raw = current_metrics.get(key, {})
        data = raw.get("data", {}) if isinstance(raw, dict) and raw.get("success") else (raw or {})
        if not data:
            continue
        if key == "cpu":
            values[key] = float(data.get("cpu_usage", 0))
        elif key == "memory":
            total = int(float(data.get("mem_total_mb", 1)))
            used = int(float(data.get("mem_used_mb", 0)))
            values[key] = round(used / total * 100, 1) if total > 0 else 0
        else:
            disks = data.get("disks", [])
            root = disks[0] if disks else {}
            values[key] = float(str(root.get("use_percent", "0%")).replace("%", ""))
    return values


def _append_history_point(cache: dict, key: str, ts: datetime, value: float) -> None:
    time_label = ts.strftime("%H:%M:%S")
    series = cache.setdefault(key, [])
    if series:
        last_ts = series[-1].get("ts")
        if last_ts is not None and ts.timestamp() - float(last_ts) < 5:
            series[-1] = {"ts": ts.timestamp(), "time": time_label, "value": value}
            return
    series.append({"ts": ts.timestamp(), "time": time_label, "value": value})


def _seed_history(server_id: str, current_metrics: dict) -> None:
    """无历史数据时，用当前指标回填近 20 分钟时间轴，避免图表空白。"""
    cache = _get_history_cache(server_id)
    if not _history_is_empty(cache):
        return
    values = _extract_metric_values(current_metrics)
    if not values:
        return
    now = datetime.now()
    for i in range(HISTORY_MAX_POINTS - 1, -1, -1):
        ts = now - timedelta(seconds=i * HISTORY_SAMPLE_INTERVAL_SEC)
        for key, val in values.items():
            _append_history_point(cache, key, ts, val)
    _trim_history(cache)
    cache["updated_at"] = now
    _persist_history_cache()
    logger.info("Seeded dashboard history for %s (%d points)", server_id or "default", HISTORY_MAX_POINTS)


def _update_history(server_id: str, current_metrics: dict):
    cache = _get_history_cache(server_id)
    now = datetime.now()
    values = _extract_metric_values(current_metrics)
    if not values:
        return
    for key, val in values.items():
        _append_history_point(cache, key, now, val)

    _trim_history(cache)
    cache["updated_at"] = now
    _persist_history_cache()


def _history_for_response(server_id: str) -> dict:
    cache = _get_history_cache(server_id)
    _trim_history(cache)
    return {
        "cpu": list(cache.get("cpu") or []),
        "memory": list(cache.get("memory") or []),
        "disk": list(cache.get("disk") or []),
    }


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
    """从远程 VM 采集指标。

    注意：同一 SSHClient/paramiko 连接不可多线程并发 exec，
    因此改为顺序采集，避免仪表盘服务状态被并发写坏。
    """
    from app.services.remote_executor import get_system_info, get_cpu_info, get_memory_info, get_disk_info

    metrics = {}
    for name, func in (
        ("cpu", get_cpu_info),
        ("memory", get_memory_info),
        ("disk", get_disk_info),
        ("system", get_system_info),
    ):
        try:
            metrics[name] = func(server_id)
        except Exception as e:
            logger.warning(f"Metric {name} SSH call failed: {e}")
            metrics[name] = {"success": False, "error": str(e)}
    return metrics


def _check_kylinops_backend_local() -> dict:
    """KylinOps 后端跑在平台本机，不能依赖 SSH 到 Agent VM 查 systemctl。"""
    import subprocess
    import urllib.request

    status = "unknown"
    uptime = "N/A"
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", "kylinops"],
            capture_output=True, text=True, timeout=3,
        )
        raw = (proc.stdout or proc.stderr or "").strip()
        if raw == "active":
            status = "running"
        elif raw in ("inactive", "failed", "dead"):
            status = "stopped"
    except Exception as exc:
        logger.debug("local kylinops systemctl check failed: %s", exc)

    if status != "running":
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/system/health", timeout=2) as resp:
                if resp.status == 200:
                    status = "running"
        except Exception:
            pass

    if status == "running":
        try:
            show = subprocess.run(
                ["systemctl", "show", "kylinops", "-p", "ActiveEnterTimestamp"],
                capture_output=True, text=True, timeout=3,
            )
            since_raw = (show.stdout or "").split("=", 1)[-1].strip()
            if since_raw:
                uptime = _service_uptime_to_chinese(since_raw)
        except Exception:
            uptime = "运行中"

    return {"name": "KylinOps Backend", "port": 8000, "status": status, "uptime": uptime}


def _check_services_parallel(server_id: str = None):
    """检查远程基础设施服务状态（在线程池 worker 内同步执行，避免二次 submit 死锁）。"""
    from app.services.ssh_client import get_ssh_for_server_sync

    remote_services = [
        {"name": "PostgreSQL", "port": 5432, "unit": "postgresql"},
        {"name": "Nginx", "port": 80, "unit": "nginx"},
        {"name": "Redis", "port": 6379, "unit": "redis"},
    ]

    status_cmd = "; ".join(
        f"echo '==={svc['unit']}==='; systemctl is-active {svc['unit']} 2>/dev/null || echo unknown"
        for svc in remote_services
    )
    status_map = {}
    try:
        ssh = get_ssh_for_server_sync(server_id)
        out, _err, _code = ssh.execute(status_cmd)
        status_map = _parse_kv(out or "")
        logger.info(
            "service status probe server_id=%s parsed=%s raw=%r",
            server_id,
            {k: status_map.get(k) for k in ("postgresql", "nginx", "redis")},
            (out or "")[:200],
        )
    except Exception as e:
        logger.warning("service status SSH probe failed: %s", e)

    running_units = [svc["unit"] for svc in remote_services if status_map.get(svc["unit"], "").strip() == "active"]
    uptime_map = {}
    if running_units:
        uptime_cmd = "; ".join(
            f"echo '==={u}==='; systemctl show {u} -p ActiveEnterTimestamp 2>/dev/null | cut -d= -f2"
            for u in running_units
        )
        try:
            ssh = get_ssh_for_server_sync(server_id)
            out, _err, _code = ssh.execute(uptime_cmd)
            uptime_map = _parse_kv(out or "")
        except Exception as e:
            logger.debug("service uptime probe failed: %s", e)

    results = []
    for svc in remote_services:
        raw_status = status_map.get(svc["unit"], "").strip()
        status = "running" if raw_status == "active" else ("stopped" if raw_status else "unknown")
        uptime = "N/A"
        if status == "running":
            since_raw = uptime_map.get(svc["unit"], "")
            uptime = _service_uptime_to_chinese(since_raw) if since_raw else "N/A"
        results.append({"name": svc["name"], "port": svc["port"], "status": status, "uptime": uptime})

    results.append(_check_kylinops_backend_local())
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

        # 指标与服务状态共用同一 SSH 连接，必须串行，避免 paramiko 并发 exec 损坏结果
        def _collect_all():
            m = _fetch_vm_metrics_parallel(server_id)
            s = _check_services_parallel(server_id)
            return m, s

        try:
            vm_metrics, services = await asyncio.wait_for(
                loop.run_in_executor(_executor, _collect_all),
                timeout=DASHBOARD_SSH_TOTAL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            vm_metrics, services = {}, []
            logger.warning("Dashboard SSH collect timed out")

        # SSH 全部失败时，回退到旧缓存数据（但不要用旧的 unknown 覆盖已采到的服务状态）
        has_metrics = any(
            isinstance(vm_metrics.get(k, {}), dict) and vm_metrics.get(k, {}).get("success")
            for k in ["cpu", "memory", "disk"]
        )
        if not has_metrics and cache_entry:
            vm_metrics = cache_entry.get("metrics", vm_metrics)
            if not services:
                services = cache_entry.get("services", services)
            fresh_data = False
        else:
            # 缓存新结果
            _metrics_cache[cache_key] = {"metrics": vm_metrics, "services": services, "_ts": now_ts}
            fresh_data = True

    if fresh_data:
        cache = _get_history_cache(server_id)
        if _history_is_empty(cache):
            _seed_history(server_id, vm_metrics)
        _update_history(server_id, vm_metrics)
    else:
        cache = _get_history_cache(server_id)
        has_metrics = any(
            isinstance(vm_metrics.get(k, {}), dict) and vm_metrics.get(k, {}).get("success")
            for k in ["cpu", "memory", "disk"]
        )
        if has_metrics and _history_is_empty(cache):
            _seed_history(server_id, vm_metrics)

    history = _history_for_response(server_id)

    def _extract(raw):
        if isinstance(raw, dict) and raw.get("success"):
            return raw.get("data", {})
        return raw or {}

    cpu = _extract(vm_metrics.get("cpu", {}))
    mem = _extract(vm_metrics.get("memory", {}))
    disk = _extract(vm_metrics.get("disk", {}))
    sys_info = _extract(vm_metrics.get("system", {}))

    uptime_seconds = 0
    uptime_sec_raw = str(sys_info.get("uptime_sec", "") or "").strip()
    if uptime_sec_raw:
        try:
            uptime_seconds = int(float(uptime_sec_raw))
        except (TypeError, ValueError):
            uptime_seconds = 0

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
                "systemUptime": _uptime_seconds_to_chinese(uptime_seconds)
                if uptime_seconds
                else _uptime_to_chinese(sys_info.get("uptime", "")),
                "systemUptimeSeconds": uptime_seconds,
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
                    "history": history.get("cpu", []),
                },
                "memory": {
                    "current": mem_pct,
                    "total_mb": mem_total,
                    "used_mb": mem_used,
                    "available_mb": int(float(mem.get("mem_available_mb", 0))),
                    "history": history.get("memory", []),
                },
                "disk": {
                    "current": disk_pct,
                    "size": root_disk.get("size", "N/A"),
                    "used": root_disk.get("used", "N/A"),
                    "available": root_disk.get("available", "N/A"),
                    "history": history.get("disk", []),
                },
                "network": vm_metrics.get("network", {}),
            },
            "anomalies": [],
            "services": services,
        },
    }


@router.get("/history")
async def metric_history(server_id: str = None, metric: str = "cpu", minutes: int = HISTORY_WINDOW_MINUTES):
    history = _history_for_response(server_id)
    data = history.get(metric, [])
    return {
        "code": 0,
        "data": {
            "metric": metric,
            "windowMinutes": minutes,
            "history": data,
        },
    }
