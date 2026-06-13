"""自定义工具注册表 — 从 tool_configs 加载并供 Agent 调用"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_config import ToolConfig
from app.services.tool_file_validator import _load_python_run

logger = logging.getLogger(__name__)

_BUILTIN_NAMES = {
    "get_system_info", "get_disk_usage", "get_cpu_info", "get_memory_info",
    "list_processes", "get_process_detail", "kill_process", "get_service_status",
    "manage_service", "get_file_list", "read_file", "get_logs", "get_users",
    "get_groups", "execute_command", "search_journal_logs", "summarize_task",
    "get_network_connections", "get_network_speed", "get_network_interfaces",
}


class CustomToolRegistry:
    """会话级自定义工具缓存。"""

    def __init__(self) -> None:
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    @property
    def tools(self) -> Dict[str, Dict[str, Any]]:
        return self._tools

    @property
    def openai_schemas(self) -> List[Dict[str, Any]]:
        return [t["schema"] for t in self._tools.values() if t.get("schema")]

    async def load(self, db: AsyncSession) -> None:
        if self._loaded:
            return
        self._tools.clear()
        try:
            rows = (
                await db.execute(
                    select(ToolConfig).where(ToolConfig.enabled == 1).order_by(ToolConfig.name)
                )
            ).scalars().all()
            for row in rows:
                if row.name in _BUILTIN_NAMES:
                    continue
                entry = _build_tool_entry(row)
                if entry:
                    self._tools[row.name] = entry
        except Exception as exc:
            logger.warning("custom tool registry load failed: %s", exc)
        self._loaded = True

    def get_risk_level(self, name: str) -> str:
        entry = self._tools.get(name)
        if not entry:
            return "L2"
        level = int(entry.get("risk_level") or 1)
        return f"L{max(1, min(5, level))}"

    def execute(self, name: str, args: dict) -> Optional[dict]:
        entry = self._tools.get(name)
        if not entry or not entry.get("run_fn"):
            return None
        try:
            result = entry["run_fn"](**(args or {}))
            if not isinstance(result, dict):
                return {"success": False, "error": "自定义工具必须返回 dict"}
            return result
        except Exception as exc:
            return {"success": False, "error": f"自定义工具执行异常: {exc}"}


def _build_tool_entry(row: ToolConfig) -> Optional[Dict[str, Any]]:
    try:
        cfg = json.loads(row.config_json or "{}")
    except (json.JSONDecodeError, TypeError):
        cfg = {}

    source = cfg.get("sourceContent") or cfg.get("source") or ""
    run_fn = None
    if source:
        _, run_fn, errors = _load_python_run(str(source))
        if errors or not run_fn:
            logger.warning("skip custom tool %s: %s", row.name, errors[:1] if errors else "no run()")
            return None

    schema = _tool_to_openai_schema(row.name, row.description or "", cfg)
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description or "",
        "category": row.category or "",
        "risk_level": row.risk_level or 1,
        "config": cfg,
        "schema": schema,
        "run_fn": run_fn,
    }


def _tool_to_openai_schema(name: str, description: str, cfg: dict) -> dict:
    properties: Dict[str, Any] = {}
    required: List[str] = []

    params = cfg.get("parameters") if isinstance(cfg.get("parameters"), dict) else {}
    for key, meta in params.items():
        if not isinstance(meta, dict):
            properties[key] = {"type": "string", "description": str(meta)}
            continue
        prop: Dict[str, Any] = {
            "type": meta.get("type") or "string",
            "description": meta.get("description") or key,
        }
        if "enum" in meta:
            prop["enum"] = meta["enum"]
        if meta.get("default") is not None:
            prop["default"] = meta["default"]
        properties[key] = prop
        if meta.get("required"):
            required.append(key)

    trial_args = cfg.get("trialArgs") or cfg.get("trial_args") or {}
    if isinstance(trial_args, dict):
        for key, default in trial_args.items():
            if key not in properties:
                properties[key] = {
                    "type": "boolean" if isinstance(default, bool) else "string",
                    "description": key,
                }

    if not properties:
        properties["kwargs"] = {"type": "string", "description": "JSON 格式参数字符串（可选）"}

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (description or name)[:500],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


async def load_custom_tool_registry(db: AsyncSession) -> CustomToolRegistry:
    registry = CustomToolRegistry()
    await registry.load(db)
    return registry
