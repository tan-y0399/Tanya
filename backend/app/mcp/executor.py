from __future__ import annotations

from typing import Any, Dict

from app.mcp.audit import record_mcp_event
from app.mcp.registry import call_tool
from app.services import approval_service


async def execute_approved_tool(db, approval_id: str) -> Dict[str, Any]:
    approval = await approval_service.get_by_id(db, approval_id)
    if approval is None:
        return {"success": False, "error": "Approval not found"}
    if approval.status != "approved":
        return {"success": False, "error": f"Approval is not approved: {approval.status}"}

    tool_params: Dict[str, Any] = {}
    if approval.tool_params_json:
        import json

        try:
            tool_params = json.loads(approval.tool_params_json)
        except Exception:
            tool_params = {}

    result = call_tool(approval.tool_name, tool_params)
    record_mcp_event("approved_tool_executed", {"approvalId": approval_id, "toolName": approval.tool_name, "result": result})
    return {
        "success": True,
        "data": {
            "approvalId": approval_id,
            "toolName": approval.tool_name,
            "result": result,
        },
    }
