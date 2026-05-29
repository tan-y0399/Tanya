from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.mcp.adapter import handle_mcp_request
from app.mcp.executor import execute_approved_tool
from app.mcp.prompts import list_prompts
from app.mcp.registry import list_tools
from app.mcp.resources import RESOURCE_DEFINITIONS

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP"])


@router.get("/tools")
async def mcp_tools(role: str = "admin"):
    from app.mcp.authz import can_access_tool

    tools = [t for t in list_tools() if can_access_tool(role, t["name"])]
    return {"success": True, "data": {"tools": tools}, "metadata": {"count": len(tools), "role": role}}


@router.get("/resources")
async def mcp_resources(role: str = "admin"):
    from app.mcp.authz import can_access_resource

    resources = [r for r in RESOURCE_DEFINITIONS if can_access_resource(role, r["uri"])]
    return {"success": True, "data": {"resources": resources}, "metadata": {"count": len(resources), "role": role}}


@router.get("/prompts")
async def mcp_prompts(role: str = "admin"):
    from app.mcp.authz import can_access_prompt

    prompts = [p for p in list_prompts() if can_access_prompt(role, p["name"])]
    return {"success": True, "data": {"prompts": prompts}, "metadata": {"count": len(prompts), "role": role}}


@router.post("/call")
async def mcp_call(payload: dict, db: AsyncSession = Depends(get_db)):
    method = payload.get("method", "")
    params = payload.get("params", {})
    return await handle_mcp_request(method, params, db=db)


@router.get("/manifest")
async def mcp_manifest():
    return {
        "success": True,
        "data": {
            "name": "kylinops-mcp",
            "version": "1.3.0",
            "capabilities": ["tools", "resources", "prompts", "approvals", "execution", "audit-persistence"],
            "transport": "http-json",
        },
    }


@router.post("/execute-approved")
async def mcp_execute_approved(payload: dict, db: AsyncSession = Depends(get_db)):
    approval_id = payload.get("approvalId", "")
    if not approval_id:
        return {"success": False, "error": "approvalId is required"}
    result = await execute_approved_tool(db, approval_id)
    return result
