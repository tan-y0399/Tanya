"""
审批管理 — 过期清理、防重复、规则细化、临时授权
"""

import json
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import desc
from app.models.approval import Approval
from app.services.user_display import load_users_map, resolve_user_display


async def create_approval(db: AsyncSession, **kwargs) -> Optional[Approval]:
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
    items = [await _format_approval(db, r) for r in rows]
    return {"items": items, "total": len(items)}


async def get_history(db: AsyncSession, page: int = 1, size: int = 20) -> dict:
    q = select(Approval).where(Approval.status != "pending").order_by(desc(Approval.requested_at))
    total_result = await db.execute(
        select(func.count()).select_from(Approval).where(Approval.status != "pending"))
    total = total_result.scalar() or 0
    rows_result = await db.execute(q.offset((page - 1) * size).limit(size))
    rows = rows_result.scalars().all()
    items = [await _format_approval(db, r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


async def get_by_id(db: AsyncSession, approval_id: str) -> Optional[Approval]:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    return result.scalar_one_or_none()


async def delete_approval(db: AsyncSession, approval_id: str) -> bool:
    approval = await get_by_id(db, approval_id)
    if not approval:
        return False
    from app.models.pending_execution import PendingExecution
    pe_result = await db.execute(
        select(PendingExecution).where(PendingExecution.approval_id == approval_id)
    )
    for pe in pe_result.scalars().all():
        await db.delete(pe)
    await db.delete(approval)
    await db.commit()
    return True


async def update_approval(
    db: AsyncSession,
    approval_id: str,
    *,
    detail: Optional[str] = None,
    comment: Optional[str] = None,
    risk_level: Optional[str] = None,
) -> Optional[Approval]:
    approval = await get_by_id(db, approval_id)
    if not approval:
        return None
    if detail is not None:
        approval.detail = detail[:500]
    if comment is not None:
        approval.comment = comment[:500]
    if risk_level is not None:
        approval.risk_level = risk_level[:4]
    await db.commit()
    await db.refresh(approval)
    return approval


async def approve(db: AsyncSession, approval_id: str, approver: str, comment: str = "") -> Optional[Approval]:
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
    expire_result = await db.execute(
        select(Approval).where(Approval.status == "pending", Approval.expires_at < now))
    expired = expire_result.scalars().all()
    if expired:
        for a in expired:
            a.status = "timeout"
            a.resolved_at = now
        await db.commit()

    total_q = select(func.count()).select_from(Approval)
    pending_q = select(func.count()).select_from(Approval).where(Approval.status == "pending")
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


async def _resolve_event_summary(db: AsyncSession, a: Approval, tool_params: Optional[dict] = None) -> str:
    """从审计/会话消息解析用户原始诉求，用于审批列表展示。"""
    from app.models.audit import AuditRecord
    from app.models.session import Message

    skip = frozenset({"(resume)", "[确认执行方案]"})

    if a.trace_id:
        audit_row = await db.execute(
            select(AuditRecord.detail_json, AuditRecord.summary).where(
                AuditRecord.trace_id == a.trace_id,
            ).limit(1)
        )
        row = audit_row.first()
        if row:
            raw_detail, summary = row
            detail = raw_detail if isinstance(raw_detail, dict) else {}
            if not detail and raw_detail:
                try:
                    detail = json.loads(raw_detail)
                except Exception:
                    detail = {}
            question = (detail.get("question") or "").strip()
            if question and question not in skip:
                return question[:200]
            if summary:
                text = summary.split("|", 1)[-1].strip() if "|" in summary else summary.strip()
                if text:
                    return text[:200]

        msg_row = await db.execute(
            select(Message.content).where(
                Message.trace_id == a.trace_id,
                Message.role == "user",
            ).order_by(Message.created_at).limit(1)
        )
        content = (msg_row.scalar_one_or_none() or "").strip()
        if content and content not in skip:
            return content[:200]

    if a.session_id:
        msg_row = await db.execute(
            select(Message.content).where(
                Message.session_id == a.session_id,
                Message.role == "user",
            ).order_by(Message.created_at.desc()).limit(1)
        )
        content = (msg_row.scalar_one_or_none() or "").strip()
        if content and content not in skip:
            return content[:200]

    preview = _approval_command_preview(a.tool_name, tool_params or {})
    if preview:
        return preview[:200]
    if a.detail and not a.detail.startswith("MCP tool"):
        return a.detail[:200]
    return a.tool_name or "运维操作"


def _resolve_source_type(a: Approval) -> str:
    detail = (a.detail or "").strip().lower()
    if detail.startswith("mcp tool"):
        return "MCP 调用"
    if a.session_id or a.trace_id:
        return "Agent 对话"
    return "系统操作"


async def _format_approval(db: AsyncSession, a: Approval) -> dict:
    tool_params = None
    if a.tool_params_json:
        try:
            tool_params = json.loads(a.tool_params_json)
        except Exception:
            pass
    remaining = None
    if a.expires_at and a.status == "pending":
        remaining = int((a.expires_at - datetime.utcnow()).total_seconds())
        if remaining < 0:
            remaining = 0

    requester = await resolve_user_display(db, a.requested_by)
    approver_info = await resolve_user_display(db, a.approver) if a.approver else None
    event_summary = await _resolve_event_summary(db, a, tool_params)

    return {
        "id": a.id,
        "traceId": a.trace_id,
        "sessionId": a.session_id,
        "toolName": a.tool_name,
        "toolParams": tool_params,
        "riskLevel": a.risk_level,
        "detail": a.detail,
        "eventSummary": event_summary,
        "sourceType": _resolve_source_type(a),
        "requestedBy": requester["userDisplayName"],
        "requestedByUsername": requester["username"],
        "requestedByRole": requester["userRoleLabel"],
        "requestedAt": a.requested_at.isoformat() if a.requested_at else "",
        "expiresAt": a.expires_at.isoformat() if a.expires_at else None,
        "remainingSeconds": remaining,
        "status": a.status,
        "approver": approver_info["userDisplayName"] if approver_info else (a.approver or ""),
        "approverRole": approver_info["userRoleLabel"] if approver_info else "",
        "comment": a.comment,
        "resolvedAt": a.resolved_at.isoformat() if a.resolved_at else "",
        "commandPreview": _approval_command_preview(a.tool_name, tool_params),
    }


def _approval_command_preview(tool_name: str, tool_params: dict) -> str:
    try:
        from app.services.chat_service import preview_tool_command
        return preview_tool_command(tool_name, tool_params or {})
    except Exception:
        return ""
