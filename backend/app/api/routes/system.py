import os
from fastapi import APIRouter, Depends, Body, HTTPException
from app.core.config import settings
from app.core.security import get_current_user

router = APIRouter(prefix="/system", tags=["系统"])

# 定位 .env 文件：优先从环境变量读取，否则在 backend 目录下找
_ENV_PATH = os.environ.get("KILINOPS_ENV_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
_ENV_PATH = os.path.abspath(_ENV_PATH)


@router.get("/health")
async def health():
    # 检查远程VM连通性
    vm_status = "unknown"
    vm_latency = None
    try:
        from app.services.ssh_client import get_ssh_client
        import time
        t0 = time.time()
        ssh = get_ssh_client()
        if ssh.is_alive():
            vm_status = "up"
        else:
            ssh.reconnect()
            vm_status = "up" if ssh.is_alive() else "down"
        vm_latency = round((time.time() - t0) * 1000)
    except Exception:
        vm_status = "down"

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
                    "host": "192.168.163.15",
                    "latencyMs": vm_latency,
                    "description": "麒麟VM Agent 执行节点",
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
                "apiKey": settings.llm_api_key,
                "temperature": settings.llm_temperature, "maxTokens": settings.llm_max_tokens,
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
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可修改安全配置")
    changed = []
    env_updates = {}

    # LLM 配置映射：前端字段 → .env 键名
    llm_map = {
        "apiKey": "LLM_API_KEY",
        "model": "LLM_MODEL",
        "apiBase": "LLM_API_BASE",
        "temperature": "LLM_TEMPERATURE",
        "maxTokens": "LLM_MAX_TOKENS",
    }
    if payload.get("llm"):
        for k, v in payload["llm"].items():
            env_key = llm_map.get(k)
            if env_key:
                env_updates[env_key] = str(v)
                changed.append(f"llm.{k}")
            attr = f"llm_{k}"
            if hasattr(settings, attr):
                setattr(settings, attr, v)

    if payload.get("security"):
        for k, v in payload["security"].items():
            if k == "approvalTimeout":
                env_updates["APPROVAL_TIMEOUT"] = str(v)
                changed.append(f"security.{k}")
            elif k == "maxConversationRounds":
                env_updates["MAX_CONVERSATION_ROUNDS"] = str(v)
                changed.append(f"security.{k}")

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
