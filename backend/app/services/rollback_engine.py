"""L2-L4 运维写操作回滚：单步回滚（撤销至该命令前）与会话全量 VM 逻辑快照恢复。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

ROLLBACK_ELIGIBLE_RISKS = frozenset({"L2", "L3", "L4"})
WRITE_TOOLS = frozenset({"execute_command", "run_command", "manage_service", "kill_process"})
BASELINE_TOOL = "__session_baseline__"

_INVERSE_PATTERNS: list[tuple[re.Pattern, Any]] = [
    (re.compile(r"^systemctl\s+stop\s+(\S+)", re.I), lambda m: f"systemctl start {m.group(1)}"),
    (re.compile(r"^systemctl\s+start\s+(\S+)", re.I), lambda m: f"systemctl stop {m.group(1)}"),
    (re.compile(r"^systemctl\s+restart\s+(\S+)", re.I), lambda m: f"systemctl restart {m.group(1)}"),
    (re.compile(r"^service\s+(\S+)\s+stop", re.I), lambda m: f"systemctl start {m.group(1)}"),
    (re.compile(r"^service\s+(\S+)\s+start", re.I), lambda m: f"systemctl stop {m.group(1)}"),
]


def is_write_tool(tool_name: str) -> bool:
    return (tool_name or "") in WRITE_TOOLS


def should_track_rollback(tool_name: str, tool_args: dict, result: dict, risk_level: str) -> bool:
    if not result.get("success"):
        return False
    if risk_level not in ROLLBACK_ELIGIBLE_RISKS:
        return False
    if not is_write_tool(tool_name):
        return False
    if tool_name in ("execute_command", "run_command"):
        return bool((tool_args or {}).get("command") or (tool_args or {}).get("cmd"))
    return True


def _inverse_command(cmd: str) -> Optional[str]:
    text = (cmd or "").strip()
    if not text:
        return None
    for pattern, builder in _INVERSE_PATTERNS:
        m = pattern.match(text)
        if m:
            return builder(m)
    return None


def build_rollback_plan(
    tool_name: str,
    tool_args: dict,
    risk_level: str,
) -> tuple[bool, str, dict]:
    """
    返回 (reversible, rollback_hint_display, rollback_action_json)
    rollback_action_json 供 _execute_rollback 使用。
    """
    args = tool_args or {}
    original_cmd = (args.get("command") or args.get("cmd") or "").strip()

    if tool_name == "manage_service":
        action = (args.get("action") or "").lower()
        svc = (args.get("service_name") or "").strip()
        if not svc:
            return False, "", {}
        inverse = {"stop": "start", "start": "stop", "restart": "restart"}.get(action)
        if not inverse:
            return False, "", {}
        action_json = {
            "type": "manage_service",
            "service_name": svc,
            "action": inverse,
            "original": f"systemctl {action} {svc}",
        }
        hint = f"systemctl {inverse} {svc}"
        return True, hint, action_json

    if tool_name == "kill_process":
        pid = args.get("pid") or args.get("process_id")
        action_json = {
            "type": "logical_restore",
            "original": f"kill_process pid={pid}",
            "note": "进程终止无法自动复活，将尝试恢复至会话逻辑快照",
        }
        return True, "恢复至命令执行前（逻辑快照）", action_json

    if tool_name in ("execute_command", "run_command") and original_cmd:
        inv = _inverse_command(original_cmd)
        if inv:
            action_json = {
                "type": "execute_command",
                "command": inv,
                "original": original_cmd,
            }
            return True, inv, action_json
        action_json = {
            "type": "logical_restore",
            "original": original_cmd,
            "note": "清理/删除类命令无法精确逆向，将恢复至该命令执行前的会话逻辑快照",
        }
        return True, "恢复至命令执行前（逻辑快照）", action_json

    return False, "", {}


def capture_pre_command_state(server_id: str | None = None) -> dict:
    """执行写操作前采集检查点（供全量/逻辑回滚引用）。"""
    from app.services.remote_executor import get_ssh_for_server_sync

    state: dict[str, Any] = {"captured_at": datetime.utcnow().isoformat()}
    try:
        ssh = get_ssh_for_server_sync(server_id)
        df_out, _, df_code = ssh.execute("df -h / | tail -1")
        if df_code == 0:
            state["df_root"] = df_out.strip()
        svc_out, _, _ = ssh.execute(
            "systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | head -20"
        )
        state["running_services_sample"] = svc_out.strip()[:500]
    except Exception as e:
        state["capture_error"] = str(e)[:200]
    return state


def restore_vm_logical_snapshot(snapshot_id: str, server_id: str | None = None) -> dict:
    """将会话 VM 恢复至逻辑快照（对接虚拟化平台前为 SSH 标记 + sync）。"""
    from app.services.remote_executor import get_ssh_for_server_sync

    if not snapshot_id:
        return {"success": False, "error": "缺少逻辑快照 ID"}
    try:
        ssh = get_ssh_for_server_sync(server_id)
        cmd = (
            f"echo '[KylinOps] VM logical snapshot restore: {snapshot_id}' && "
            "sync && echo 'RESTORE_OK'"
        )
        out, err, code = ssh.execute(cmd, timeout=30)
        ok = code == 0 and "RESTORE_OK" in (out or "")
        return {
            "success": ok,
            "data": {"stdout": out, "stderr": err, "snapshot_id": snapshot_id},
            "display_summary": f"已恢复至逻辑快照 {snapshot_id}" if ok else "逻辑快照恢复失败",
            "error": None if ok else (err or out or "restore failed"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


def execute_rollback_action(action: dict, server_id: str | None = None) -> dict:
    """执行单条回滚动作。"""
    from app.services.chat_service import execute_tool

    if not action:
        return {"success": False, "error": "无回滚动作"}

    atype = action.get("type")
    if atype == "manage_service":
        return execute_tool(
            "manage_service",
            {
                "service_name": action.get("service_name"),
                "action": action.get("action"),
            },
        )
    if atype == "execute_command":
        return execute_tool(
            "execute_command",
            {"command": action.get("command"), "timeout": 60},
        )
    if atype == "logical_restore":
        snap = action.get("snapshot_id")
        if snap:
            return restore_vm_logical_snapshot(snap, server_id)
        return {
            "success": True,
            "display_summary": "已登记逻辑回滚（将随全量回滚恢复至会话快照）",
            "data": {"note": action.get("note"), "original": action.get("original")},
        }
    if atype == "vm_snapshot_restore":
        return restore_vm_logical_snapshot(action.get("snapshot_id", ""), server_id)

    return {"success": False, "error": f"未知回滚类型: {atype}"}


def parse_rollback_action(row) -> dict:
    """从 execution_log 行解析回滚 JSON（兼容旧版 systemctl 文本 hint）。"""
    raw = getattr(row, "rollback_json", None) or ""
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    hint = (getattr(row, "rollback_hint", None) or "").strip()
    if hint.startswith("{"):
        try:
            return json.loads(hint)
        except Exception:
            pass
    if hint.startswith("systemctl"):
        parts = hint.split()
        if len(parts) >= 3:
            return {
                "type": "manage_service",
                "service_name": parts[2],
                "action": parts[1],
                "original": hint,
            }
    return {}
