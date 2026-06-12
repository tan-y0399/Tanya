"""
用户反馈闭环 — 解决/未解决 → 待优化标记
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supervision import TraceOutcome


async def submit_feedback(
    db: AsyncSession,
    *,
    session_id: str,
    trace_id: str,
    user_id: str,
    outcome: str,
    comment: str = "",
) -> dict:
    """outcome: solved | partial | unsolved"""
    from app.services.feedback_sync import sync_trace_outcome_to_feedback

    row = TraceOutcome(
        session_id=session_id,
        trace_id=trace_id,
        user_id=user_id,
        outcome=outcome,
        comment=comment or "",
        needs_expert=1 if outcome in ("unsolved", "partial") else 0,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    fb_id = None
    try:
        fb = await sync_trace_outcome_to_feedback(db, row)
        fb_id = fb.get("feedback_id") if isinstance(fb, dict) else None
    except Exception:
        pass

    return {
        "outcome_id": row.id,
        "outcome": outcome,
        "needs_expert": bool(row.needs_expert),
        "feedback_id": fb_id,
        "message": "感谢反馈，未解决问题将推送专家审核" if row.needs_expert else "感谢反馈",
    }


async def get_session_outcome(
    db: AsyncSession, session_id: str, trace_id: str, user_id: str,
) -> Optional[dict]:
    from sqlalchemy import select, desc
    q = select(TraceOutcome).where(
        TraceOutcome.session_id == session_id,
        TraceOutcome.trace_id == trace_id,
        TraceOutcome.user_id == user_id,
    ).order_by(desc(TraceOutcome.created_at)).limit(1)
    row = (await db.execute(q)).scalar_one_or_none()
    if not row:
        return None
    return {
        "outcome": row.outcome,
        "comment": row.comment,
        "needs_expert": bool(row.needs_expert),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
