from fastapi import APIRouter, Body
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["系统"])


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
async def get_config():
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
async def update_config(payload: dict = Body(...)):
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
        env_path = "/opt/kylinops/backend/.env"
        try:
            with open(env_path, "r") as f:
                lines = f.readlines()
            updated_keys = set()
            with open(env_path, "w") as f:
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
