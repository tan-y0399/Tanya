import json
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import desc
from app.models.approval import Approval


async def create_approval(db: AsyncSession, **kwargs) -> Approval:
    approval = Approval(**kwargs)
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def get_pending(db: AsyncSession) -> dict:
    now = datetime.utcnow()
    expire_result = await db.execute(
        select(Approval).where(Approval.status == "pending", Approval.expires_at < now))
    expired = expire_result.scalars().all()
    for a in expired:
        a.status = "timeout"
    if expired:
        await db.commit()

    result = await db.execute(
        select(Approval).where(Approval.status == "pending").order_by(desc(Approval.requested_at)))
    rows = result.scalars().all()

    items = [_format_approval(r) for r in rows]
    return {"items": items, "total": len(items)}


async def get_history(db: AsyncSession, page: int = 1, size: int = 20) -> dict:
    q = select(Approval).where(Approval.status != "pending").order_by(desc(Approval.requested_at))
    total_result = await db.execute(
        select(func.count()).select_from(Approval).where(Approval.status != "pending"))
    total = total_result.scalar() or 0

    rows_result = await db.execute(q.offset((page - 1) * size).limit(size))
    rows = rows_result.scalars().all()
    items = [_format_approval(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


async def approve(db: AsyncSession, approval_id: str, approver: str, comment: str = "") -> Optional[Approval]:
    result = await db.execute(
        select(Approval).where(Approval.id == approval_id, Approval.status == "pending"))
    approval = result.scalar_one_or_none()
    if not approval:
        return None
    approval.status = "approved"
    approval.approver = approver
    approval.comment = comment
    approval.resolved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(approval)
    return approval


async def reject(db: AsyncSession, approval_id: str, approver: str, reason: str = "") -> Optional[Approval]:
    result = await db.execute(
        select(Approval).where(Approval.id == approval_id, Approval.status == "pending"))
    approval = result.scalar_one_or_none()
    if not approval:
        return None
    approval.status = "rejected"
    approval.approver = approver
    approval.comment = reason
    approval.resolved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(approval)
    return approval


def _format_approval(a: Approval) -> dict:
    tool_params = None
    if a.tool_params_json:
        try:
            tool_params = json.loads(a.tool_params_json)
        except Exception:
            pass
    return {
        "id": a.id, "traceId": a.trace_id, "sessionId": a.session_id,
        "toolName": a.tool_name, "toolParams": tool_params,
        "riskLevel": a.risk_level, "detail": a.detail,
        "requestedBy": a.requested_by,
        "requestedAt": a.requested_at.isoformat() if a.requested_at else "",
        "expiresAt": a.expires_at.isoformat() if a.expires_at else None,
        "status": a.status,
        "result": a.status.upper() if a.status != "pending" else None,
    }
