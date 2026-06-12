"""工具参数规范化 — LLM 入参与远程执行器函数签名对齐。"""
from __future__ import annotations

from typing import Any, Dict


def normalize_tool_args(name: str, args: Dict[str, Any] | None) -> Dict[str, Any]:
    """将 Agent 工具名 + 原始参数转为远程 handler 可接受的 kwargs。"""
    a = dict(args or {})

    # list_processes / get_process_list 共用
    if name in ("list_processes", "get_process_list"):
        top_n = a.pop("limit", None) or a.pop("top_n", None) or 10
        try:
            top_n = int(top_n)
        except (TypeError, ValueError):
            top_n = 10
        sort_by = str(a.pop("sort_by", None) or "cpu").lower()
        if sort_by not in ("cpu", "mem"):
            sort_by = "cpu"
        out: Dict[str, Any] = {"top_n": top_n, "sort_by": sort_by}
        if "server_id" in a:
            out["server_id"] = a.pop("server_id")
        return out

    if name == "read_file":
        fp = a.pop("path", None) or a.pop("file_path", None)
        if fp:
            a["file_path"] = fp
        return a

    if name == "get_logs":
        path = a.pop("path", None) or a.pop("file_path", None)
        if path and not a.get("service"):
            if str(path).startswith("/") or ".log" in str(path):
                a["path"] = path
            else:
                a["service"] = path
        return a

    return a


def resolve_remote_tool_name(name: str) -> str:
    """chat 层工具名 → remote_executor 注册名。"""
    mapping = {
        "list_processes": "get_process_list",
        "get_disk_usage": "get_disk_info",
    }
    return mapping.get(name, name)
