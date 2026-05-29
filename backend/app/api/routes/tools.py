"""工具管理 API"""
import json
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.tool_config import ToolConfig

router = APIRouter(prefix="/tools", tags=["工具管理"])


def _require_admin(user: dict):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")


def _serialize_tool(t: ToolConfig) -> dict:
    try:
        cfg = json.loads(t.config_json) if t.config_json else {}
    except (json.JSONDecodeError, TypeError):
        cfg = {}
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "riskLevel": t.risk_level,
        "enabled": bool(t.enabled),
        "config": cfg,
        "createdAt": t.created_at.isoformat() if t.created_at else "",
        "updatedAt": t.updated_at.isoformat() if t.updated_at else "",
    }


@router.get("/list")
async def list_tools(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ToolConfig).order_by(ToolConfig.category, ToolConfig.name))
    tools = result.scalars().all()
    return {"code": 0, "data": {"items": [_serialize_tool(t) for t in tools]}}


@router.post("/add")
async def add_tool(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="工具名称不能为空")

    existing = (await db.execute(select(ToolConfig).where(ToolConfig.name == name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="工具名称已存在")

    cfg = payload.get("config", {})
    tool = ToolConfig(
        name=name,
        description=payload.get("description", ""),
        category=payload.get("category", ""),
        risk_level=payload.get("riskLevel", 1),
        enabled=1 if payload.get("enabled", True) else 0,
        config_json=json.dumps(cfg, ensure_ascii=False) if isinstance(cfg, dict) else str(cfg),
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return {"code": 0, "data": _serialize_tool(tool), "message": "工具添加成功"}


@router.put("/{tool_id}")
async def update_tool(
    tool_id: str,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    tool = (await db.execute(select(ToolConfig).where(ToolConfig.id == tool_id))).scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    if "name" in payload:
        tool.name = payload["name"]
    if "description" in payload:
        tool.description = payload["description"]
    if "category" in payload:
        tool.category = payload["category"]
    if "riskLevel" in payload:
        tool.risk_level = payload["riskLevel"]
    if "enabled" in payload:
        tool.enabled = 1 if payload["enabled"] else 0
    if "config" in payload:
        cfg = payload["config"]
        tool.config_json = json.dumps(cfg, ensure_ascii=False) if isinstance(cfg, dict) else str(cfg)

    await db.commit()
    await db.refresh(tool)
    return {"code": 0, "data": _serialize_tool(tool), "message": "工具更新成功"}


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    tool = (await db.execute(select(ToolConfig).where(ToolConfig.id == tool_id))).scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    await db.delete(tool)
    await db.commit()
    return {"code": 0, "message": "工具已删除"}


@router.post("/{tool_id}/toggle")
async def toggle_tool(
    tool_id: str,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用工具 — user 角色可操作"""
    tool = (await db.execute(select(ToolConfig).where(ToolConfig.id == tool_id))).scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    enabled = payload.get("enabled", True)
    tool.enabled = 1 if enabled else 0
    await db.commit()
    await db.refresh(tool)
    return {"code": 0, "data": _serialize_tool(tool), "message": "工具已{}".format("启用" if enabled else "禁用")}
