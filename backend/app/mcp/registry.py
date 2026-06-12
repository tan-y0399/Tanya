from __future__ import annotations

from typing import Any, Callable, Dict, List

from app.services import remote_executor


ToolHandler = Callable[..., Dict[str, Any]]


def _json_schema_from_parameters(parameters: Dict[str, Any]) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for name, spec in parameters.items():
        if isinstance(spec, dict):
            schema = {k: v for k, v in spec.items() if k != "required"}
            if "type" not in schema:
                schema["type"] = "string"
            properties[name] = schema
            if spec.get("required", False):
                required.append(name)
        else:
            properties[name] = {"type": "string"}

    result: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        result["required"] = required
    return result


TOOL_MAP: Dict[str, ToolHandler] = {
    "get_system_info": remote_executor.get_system_info,
    "get_cpu_info": remote_executor.get_cpu_info,
    "get_memory_info": remote_executor.get_memory_info,
    "get_disk_info": remote_executor.get_disk_info,
    "get_network_info": remote_executor.get_network_info,
    "get_network_connections": remote_executor.get_network_connections,
    "get_network_interfaces": remote_executor.get_network_interfaces,
    "get_network_speed": remote_executor.get_network_speed,
    "get_process_list": remote_executor.get_process_list,
    "list_processes": remote_executor.get_process_list,
    "get_process_detail": remote_executor.get_process_detail,
    "kill_process": remote_executor.kill_process,
    "get_service_status": remote_executor.get_service_status,
    "manage_service": remote_executor.manage_service,
    "get_file_list": remote_executor.get_file_list,
    "read_file": remote_executor.read_file,
    "get_logs": remote_executor.get_logs,
    "get_users": remote_executor.get_users,
    "get_groups": remote_executor.get_groups,
    "run_command": remote_executor.run_command,
}


def list_tools() -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for item in remote_executor.TOOL_DESCRIPTIONS:
        tools.append(
            {
                "name": item["name"],
                "description": item["description"],
                "inputSchema": _json_schema_from_parameters(item.get("parameters", {})),
            }
        )
    return tools


def get_tool_definition(name: str) -> Dict[str, Any] | None:
    from app.services.tool_args import resolve_remote_tool_name

    lookup = resolve_remote_tool_name(name)
    for item in remote_executor.TOOL_DESCRIPTIONS:
        if item["name"] == lookup or item["name"] == name:
            return {
                "name": item["name"],
                "description": item["description"],
                "inputSchema": _json_schema_from_parameters(item.get("parameters", {})),
            }
    return None


def call_tool(name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
    from app.services.tool_args import normalize_tool_args, resolve_remote_tool_name

    internal_name = resolve_remote_tool_name(name)
    handler = TOOL_MAP.get(internal_name) or TOOL_MAP.get(name)
    if handler is None:
        return {"success": False, "error": f"Unknown tool: {name}"}
    arguments = normalize_tool_args(internal_name, arguments or {})
    try:
        return handler(**arguments)
    except TypeError as exc:
        return {"success": False, "error": f"Invalid arguments for tool {name}: {exc}"}
