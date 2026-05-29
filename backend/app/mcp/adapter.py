from __future__ import annotations

import json
from typing import Any, Dict

from app.core.command_security import get_risk_level_info
from app.mcp.audit import persist_mcp_event, record_mcp_event
from app.mcp.authz import can_access_prompt, can_access_resource, can_access_tool
from app.mcp.prompts import get_prompt, list_prompts
from app.mcp.registry import call_tool, get_tool_definition, list_tools
from app.mcp.resources import RESOURCE_DEFINITIONS, read_resource
from app.mcp.security import validate_tool_call
from app.services import approval_service


def _wrap_success(data: Dict[str, Any], *, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = {"success": True, "data": data}
    if metadata:
        payload["metadata"] = metadata
    return payload


def _wrap_error(error: str, *, error_code: str = "MCP_ERROR", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = {"success": False, "error": error, "errorCode": error_code}
    if metadata:
        payload["metadata"] = metadata
    return payload


async def handle_mcp_request(method: str, params: Dict[str, Any] | None = None, db=None) -> Dict[str, Any]:
    params = params or {}
    record_mcp_event("request", {"method": method, "params": params})

    role = str(params.get("role", "admin"))

    if method == "tools/list":
        tools = [t for t in list_tools() if can_access_tool(role, t["name"])]
        result = _wrap_success({"tools": tools}, metadata={"count": len(tools), "role": role})
        if db is not None:
            await persist_mcp_event(
                db,
                trace_id=params.get("traceId", ""),
                session_id=params.get("sessionId"),
                user_id=str(params.get("user", "mcp")),
                event_type="tools_list",
                summary="MCP tools listed",
                detail_json={"method": method, "count": len(tools), "role": role},
            )
        return result

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        user = params.get("user", "mcp")
        session_id = params.get("sessionId", "")
        decision = validate_tool_call(name, arguments)
        if not decision.get("allowed", False):
            analysis = decision.get("analysis")
            record_mcp_event("blocked", {"name": name, "reason": decision.get("reason"), "analysis": analysis})
            return _wrap_error(decision.get("reason", "blocked"), error_code="MCP_TOOL_BLOCKED", metadata={"analysis": analysis, "tool": name})

        analysis = decision.get("analysis") or {}
        if analysis.get("require_approval"):
            approval = await approval_service.create_approval(
                db,
                trace_id="",
                session_id=session_id,
                tool_name=name,
                tool_params_json=json.dumps(arguments, ensure_ascii=False),
                risk_level=analysis.get("risk_level", "L3"),
                detail=f"MCP tool call: {name}",
                requested_by=str(user),
            )
            risk_info = get_risk_level_info(analysis.get("risk_level", "L3"))
            record_mcp_event("approval_required", {"name": name, "approval_id": approval.id, "analysis": analysis})
            return _wrap_success(
                {
                    "approvalRequired": True,
                    "approvalId": approval.id,
                    "riskLevel": analysis.get("risk_level", "L3"),
                    "riskInfo": risk_info,
                },
                metadata={"analysis": analysis, "tool": name, "approvalId": approval.id},
            )

        result = call_tool(name, arguments)
        record_mcp_event("tool_result", {"name": name, "result": result})
        if result.get("success", False):
            return _wrap_success(result, metadata={"tool": name})
        return _wrap_error(result.get("error", "tool execution failed"), metadata={"tool": name, "toolResult": result})

    if method == "resources/list":
        resources = [r for r in RESOURCE_DEFINITIONS if can_access_resource(role, r["uri"])]
        result = _wrap_success({"resources": resources}, metadata={"count": len(resources), "role": role})
        if db is not None:
            await persist_mcp_event(
                db,
                trace_id=params.get("traceId", ""),
                session_id=params.get("sessionId"),
                user_id=str(params.get("user", "mcp")),
                event_type="resources_list",
                summary="MCP resources listed",
                detail_json={"method": method, "count": len(result["data"])},
            )
        return result

    if method == "resources/read":
        uri = params.get("uri", "")
        result = await read_resource(uri, db=db)
        record_mcp_event("resource_result", {"uri": uri, "result": result})
        return result

    if method == "prompts/list":
        prompts = [p for p in list_prompts() if can_access_prompt(role, p["name"])]
        result = _wrap_success({"prompts": prompts}, metadata={"count": len(prompts), "role": role})
        if db is not None:
            await persist_mcp_event(
                db,
                trace_id=params.get("traceId", ""),
                session_id=params.get("sessionId"),
                user_id=str(params.get("user", "mcp")),
                event_type="prompts_list",
                summary="MCP prompts listed",
                detail_json={"method": method, "count": len(result["data"])},
            )
        return result

    if method == "prompts/get":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = get_prompt(name, arguments)
        record_mcp_event("prompt_result", {"name": name, "result": result})
        if db is not None:
            await persist_mcp_event(
                db,
                trace_id=params.get("traceId", ""),
                session_id=params.get("sessionId"),
                user_id=str(params.get("user", "mcp")),
                event_type="prompt_get",
                summary=f"Prompt fetched: {name}",
                detail_json={"method": method, "name": name},
            )
        return result

    return _wrap_error(f"Unknown method: {method}", error_code="MCP_METHOD_NOT_FOUND")
