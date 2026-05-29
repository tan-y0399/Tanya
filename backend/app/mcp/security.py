from __future__ import annotations

from typing import Any, Dict

from app.core.command_security import analyze_command


BLOCKED_TOOL_NAMES = {"run_command"}


def validate_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "run_command":
        command = str(arguments.get("command", "")).strip()
        if not command:
            return {"allowed": False, "reason": "empty command"}
        analysis = analyze_command(command)
        if analysis.get("blocked"):
            return {"allowed": False, "reason": analysis.get("block_message", "blocked"), "analysis": analysis}
        if analysis.get("require_approval"):
            return {"allowed": False, "reason": "approval required", "analysis": analysis}
        return {"allowed": True, "analysis": analysis}

    if name in {"kill_process", "manage_service", "read_file", "get_file_list", "get_logs"}:
        return {"allowed": True}

    return {"allowed": True}
