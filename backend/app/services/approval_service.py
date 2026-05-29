"""
审批管理 — 过期清理、防重复、规则细化、临时授权

增强功能:
  - 自动过期清理 (expires_at 超时 → timeout)
  - 防重复审批 (相同 session+trace 去重)
  - 审批规则细化 (按风险级别区分处理)
  - 审批统计 (按用户/工具/状态)
"""

import json
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import desc
from app.models.approval import Approval
from app.core.config import settings


async def create_approval(db: AsyncSession, **kwargs) -> Optional[Approval]:
    # 防重复: 检查同一个 session+trace+tool 是否已有 pending 审批
    existing = await db.execute(
        select(Approval).where(
            Approval.session_id == kwargs.get("session_id", ""),
            Approval.trace_id == kwargs.get("trace_id", ""),
            Approval.tool_name == kwargs.get("tool_name", ""),
            Approval.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        return None

    approval = Approval(**kwargs)
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def get_pending(db: AsyncSession) -> dict:
    now = datetime.utcnow()
    # 自动过期
    expire_result = await db.execute(
        select(Approval).where(Approval.status == "pending", Approval.expires_at < now))
    expired = expire_result.scalars().all()
    if expired:
        for a in expired:
            a.status = "timeout"
            a.resolved_at = now
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
    return {"items": [_format_approval(r) for r in rows], "total": total, "page": page, "size": size}


async def get_by_id(db: AsyncSession, approval_id: str) -> Optional[Approval]:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    return result.scalar_one_or_none()


async def approve(db: AsyncSession, approval_id: str, approver: str, comment: str = "") -> Optional[Approval]:
    result = await db.execute(
        select(Approval).where(Approval.id == approval_id, Approval.status == "pending"))
    approval = result.scalar_one_or_none()
    if not approval:
        return None
    # 检查过期
    if approval.expires_at and approval.expires_at < datetime.utcnow():
        approval.status = "timeout"
        approval.resolved_at = datetime.utcnow()
        await db.commit()
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
    if approval.expires_at and approval.expires_at < datetime.utcnow():
        approval.status = "timeout"
        approval.resolved_at = datetime.utcnow()
        await db.commit()
        return None
    approval.status = "rejected"
    approval.approver = approver
    approval.comment = reason
    approval.resolved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(approval)
    return approval


async def get_stats(db: AsyncSession) -> dict:
    now = datetime.utcnow()
    total_q = select(func.count()).select_from(Approval)
    pending_q = select(func.count()).select_from(Approval).where(Approval.status == "pending",
                                                                   Approval.expires_at > now)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_q = select(func.count()).select_from(Approval).where(Approval.requested_at >= today)

    total = (await db.execute(total_q)).scalar() or 0
    pending = (await db.execute(pending_q)).scalar() or 0
    today_count = (await db.execute(today_q)).scalar() or 0

    return {
        "total": total,
        "pending": pending,
        "today": today_count,
        "approved": (await db.execute(
            select(func.count()).select_from(Approval).where(Approval.status == "approved"))).scalar() or 0,
        "rejected": (await db.execute(
            select(func.count()).select_from(Approval).where(Approval.status == "rejected"))).scalar() or 0,
        "timeout": (await db.execute(
            select(func.count()).select_from(Approval).where(Approval.status == "timeout"))).scalar() or 0,
    }


def _format_approval(a: Approval) -> dict:
    tool_params = None
    if a.tool_params_json:
        try:
            tool_params = json.loads(a.tool_params_json)
        except Exception:
            pass
    # 计算剩余时间
    remaining = None
    if a.expires_at and a.status == "pending":
        remaining = int((a.expires_at - datetime.utcnow()).total_seconds())
        if remaining < 0:
            remaining = 0
    return {
        "id": a.id, "traceId": a.trace_id, "sessionId": a.session_id,
        "toolName": a.tool_name, "toolParams": tool_params,
        "riskLevel": a.risk_level, "detail": a.detail,
        "requestedBy": a.requested_by,
        "requestedAt": a.requested_at.isoformat() if a.requested_at else "",
        "expiresAt": a.expires_at.isoformat() if a.expires_at else None,
        "remainingSeconds": remaining,
        "status": a.status,
        "approver": a.approver,
        "comment": a.comment,
    }
