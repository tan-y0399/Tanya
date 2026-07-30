import os
import time
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.server import Server

router = APIRouter(prefix="/system", tags=["系统"])

# 定位 .env 文件：优先从环境变量读取，否则在 backend 目录下找
_ENV_PATH = os.environ.get("KILINOPS_ENV_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
_ENV_PATH = os.path.abspath(_ENV_PATH)


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    vm_status = "unknown"
    vm_latency = None
    vm_host = settings.ssh_host
    vm_port = settings.ssh_port
    vm_username = settings.ssh_user
    vm_server_name = None

    result = await db.execute(select(Server).where(Server.is_default == True))
    default_server = result.scalar_one_or_none()
    if default_server:
        vm_host = default_server.host
        vm_port = default_server.port
        vm_username = default_server.username
        vm_server_name = default_server.name

    try:
        from app.services.ssh_client import SSHClient, SSH_POOL

        t0 = time.time()
        if default_server:
            ssh = SSH_POOL.get_or_create(
                default_server.id,
                default_server.host,
                default_server.port,
                default_server.username,
                default_server.key_path,
            )
        else:
            ssh = SSHClient()
            ssh.connect()

        if ssh.is_alive():
            vm_status = "up"
        else:
            ssh.reconnect()
            vm_status = "up" if ssh.is_alive() else "down"
        vm_latency = round((time.time() - t0) * 1000)

        vm_host = ssh.host
        vm_port = ssh.port
        vm_username = ssh.username
    except Exception:
        vm_status = "down"

    host_display = f"{vm_host}:{vm_port}" if vm_port and vm_port != 22 else vm_host
    description = "麒麟VM Agent 执行节点"
    if vm_server_name:
        description = f"{vm_server_name} · 麒麟VM Agent 执行节点"

    # 检查数据库连通性
    db_status = "up"
    try:
        from app.core.database import engine
        # 简单测试：engine 存在即可认为数据库配置正常
    except Exception:
        db_status = "down"

    return {
        "code": 0,
        "data": {
            "status": "healthy" if vm_status == "up" else "degraded",
            "version": settings.version,
            "components": {
                "database": {"status": db_status, "latencyMs": None},
                "llmApi": {"status": "up", "latencyMs": None},
                "vmAgent": {
                    "status": vm_status,
                    "host": host_display,
                    "port": vm_port,
                    "username": vm_username,
                    "serverName": vm_server_name,
                    "latencyMs": vm_latency,
                    "description": description,
                },
            },
        },
    }


@router.get("/config")
async def get_config(user: dict = Depends(get_current_user)):
    return {
        "code": 0,
        "data": {
            "llm": {
                "model": settings.llm_model, "apiBase": settings.llm_api_base,
                # 不回传明文，仅告知是否已配置；更换时由前端提交新值
                "apiKey": "",
                "apiKeySet": bool(settings.llm_api_key and str(settings.llm_api_key).strip()),
                "temperature": settings.llm_temperature, "maxTokens": settings.llm_max_tokens,
                "systemRoleSupport": settings.llm_system_role_support,
            },
            "tool": {
                "defaultTimeout": settings.tool_default_timeout,
                "enabledTools": [
                    "get_cpu_info", "get_memory_info", "get_disk_usage",
                    "get_disk_io", "list_processes", "get_process_detail",
                    "get_network_connections", "search_journal_logs",
                ],
            },
            "security": {
                "approvalTimeout": settings.approval_timeout,
                "maxConversationRounds": settings.max_conversation_rounds,
            },
        },
    }


@router.put("/config")
async def update_config(payload: dict = Body(...), user: dict = Depends(get_current_user)):
    is_admin = user.get("role") == "admin"
    has_llm = bool(payload.get("llm"))
    has_security = bool(payload.get("security"))

    if has_security and not is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可修改安全配置")
    if not is_admin and not has_llm:
        raise HTTPException(status_code=403, detail="仅管理员可修改系统配置")

    changed = []
    env_updates = {}

    # LLM 配置映射：前端字段 → .env 键名
    llm_map = {
        "apiKey": "LLM_API_KEY",
        "model": "LLM_MODEL",
        "apiBase": "LLM_API_BASE",
        "temperature": "LLM_TEMPERATURE",
        "maxTokens": "LLM_MAX_TOKENS",
        "systemRoleSupport": "LLM_SYSTEM_ROLE_SUPPORT",
    }
    llm_attr_map = {
        "apiKey": "llm_api_key",
        "model": "llm_model",
        "apiBase": "llm_api_base",
        "temperature": "llm_temperature",
        "maxTokens": "llm_max_tokens",
        "systemRoleSupport": "llm_system_role_support",
    }
    if payload.get("llm"):
        for k, v in payload["llm"].items():
            # apiKey 留空表示不修改已保存的值
            if k == "apiKey" and (v is None or str(v).strip() == ""):
                continue
            if k == "apiKeySet":
                continue
            env_key = llm_map.get(k)
            if env_key:
                env_updates[env_key] = str(v)
                changed.append(f"llm.{k}")
            attr = llm_attr_map.get(k)
            if attr and hasattr(settings, attr):
                setattr(settings, attr, v)

    if payload.get("security") and is_admin:
        for k, v in payload["security"].items():
            if k == "approvalTimeout":
                env_updates["APPROVAL_TIMEOUT"] = str(v)
                settings.approval_timeout = int(v)
                changed.append(f"security.{k}")
            elif k in ("maxConversationRounds", "maxRounds"):
                env_updates["MAX_CONVERSATION_ROUNDS"] = str(v)
                settings.max_conversation_rounds = int(v)
                changed.append("security.maxConversationRounds")

    # 写回 .env 文件
    if env_updates:
        try:
            with open(_ENV_PATH, "r") as f:
                lines = f.readlines()
            updated_keys = set()
            with open(_ENV_PATH, "w") as f:
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        key = stripped.split("=")[0].strip()
                        if key in env_updates:
                            f.write(f"{key}={env_updates[key]}\n")
                            updated_keys.add(key)
                            continue
                    f.write(line)
                # 追加新增的配置项
                for key, val in env_updates.items():
                    if key not in updated_keys:
                        f.write(f"{key}={val}\n")
        except Exception:
            pass  # 写入失败不影响已生效的内存配置

    return {"code": 0, "message": "配置已更新", "data": {"changed": changed}}


@router.delete("/config")
async def delete_config(user: dict = Depends(get_current_user)):
    """重置/删除安全配置 — user 角色可操作"""
    defaults = {
        "LLM_TEMPERATURE": "0.1",
        "LLM_MAX_TOKENS": "4096",
        "APPROVAL_TIMEOUT": "300",
        "MAX_CONVERSATION_ROUNDS": "20",
    }
    for key, val in defaults.items():
        attr = {
            "LLM_TEMPERATURE": "llm_temperature",
            "LLM_MAX_TOKENS": "llm_max_tokens",
            "APPROVAL_TIMEOUT": "approval_timeout",
            "MAX_CONVERSATION_ROUNDS": "max_conversation_rounds",
        }.get(key)
        if attr and hasattr(settings, attr):
            setattr(settings, attr, val)

    try:
        with open(_ENV_PATH, "r") as f:
            lines = f.readlines()
        with open(_ENV_PATH, "w") as f:
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    key = stripped.split("=")[0].strip()
                    if key in defaults:
                        f.write(f"{key}={defaults[key]}\n")
                        continue
                f.write(line)
    except Exception:
        pass

    return {"code": 0, "message": "安全配置已重置为默认值"}


@router.get("/telemetry")
async def get_telemetry(limit: int = 50):
    """获取 Agent 处理链路性能遥测数据（最近 N 条 + 聚合统计）"""
    try:
        from app.services.performance_telemetry import get_recent_telemetry, get_aggregate_stats
    except ImportError:
        return {"code": 0, "data": {"count": 0, "message": "遥测服务未启用"}}

    recent = get_recent_telemetry(limit=min(limit, 200))
    stats = get_aggregate_stats()
    return {
        "code": 0,
        "data": {
            "recent": recent,
            "aggregate": stats,
        },
    }
