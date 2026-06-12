"""将 Agent 对话结果反馈同步到反馈模块（feedbacks 表）"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback

logger = logging.getLogger(__name__)

_OUTCOME_TITLE = {
    "solved": "已解决",
    "partial": "部分解决",
    "unsolved": "未解决",
}

_OUTCOME_LABEL = {
    "solved": "已解决",
    "partial": "部分解决",
    "unsolved": "未解决",
}


async def _resolve_session_title(db: AsyncSession, session_id: str) -> str:
    from app.models.session import Session
    if not session_id:
        return "智能对话"
    row = await db.execute(select(Session).where(Session.id == session_id))
    session = row.scalar_one_or_none()
    if session and session.title and session.title.strip() not in ("", "新会话"):
        return session.title.strip()[:200]
    return "智能对话"


async def ensure_feedback_schema(db: AsyncSession) -> None:
    """SQLite 兼容：为已有库补充 agent 反馈关联字段"""
    from sqlalchemy import text

    alters = [
        "ALTER TABLE feedbacks ADD COLUMN source VARCHAR(24) DEFAULT 'manual'",
        "ALTER TABLE feedbacks ADD COLUMN trace_id VARCHAR(64)",
        "ALTER TABLE feedbacks ADD COLUMN session_id VARCHAR(24)",
        "ALTER TABLE feedbacks ADD COLUMN outcome VARCHAR(16)",
        "ALTER TABLE feedbacks ADD COLUMN attachments_json TEXT",
        "ALTER TABLE feedbacks ADD COLUMN category VARCHAR(64)",
        "ALTER TABLE feedbacks ADD COLUMN session_title VARCHAR(200)",
    ]
    for sql in alters:
        try:
            await db.execute(text(sql))
            await db.commit()
        except Exception:
            await db.rollback()


async def sync_trace_outcome_to_feedback(
    db: AsyncSession,
    *,
    user_id: str,
    username: str,
    session_id: str,
    trace_id: str,
    outcome: str,
    comment: str = "",
) -> Feedback | None:
    """
    Agent 对话页提交 trace-outcome 时，同步写入反馈模块，供「反馈」菜单展示与管理员回复。
    同一 trace_id 仅同步一条，避免重复。
    """
    if not trace_id or not session_id:
        return None

    existing = await db.execute(
        select(Feedback).where(
            Feedback.trace_id == trace_id,
            Feedback.user_id == user_id,
        )
    )
    row = existing.scalar_one_or_none()
    session_title = await _resolve_session_title(db, session_id)
    if row:
        row.title = session_title
        row.session_title = session_title
        row.content = _build_content(session_id, trace_id, outcome, comment)
        row.outcome = outcome
        row.category = outcome
        row.source = "agent_chat"
        if outcome == "unsolved":
            row.status = "pending"
        await db.commit()
        await db.refresh(row)
        return row

    fb = Feedback(
        user_id=user_id,
        username=username or user_id,
        title=session_title,
        session_title=session_title,
        content=_build_content(session_id, trace_id, outcome, comment),
        source="agent_chat",
        trace_id=trace_id,
        session_id=session_id,
        outcome=outcome,
        category=outcome,
        status="pending",
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    logger.info("Synced trace outcome to feedback: trace=%s feedback=%s", trace_id, fb.id)
    return fb


def _build_content(session_id: str, trace_id: str, outcome: str, comment: str) -> str:
    outcome_label = _OUTCOME_LABEL.get(outcome, outcome)
    lines = [
        "来源：智能对话 · 会话评价",
        f"会话 ID：{session_id}",
        f"Trace ID：{trace_id}",
        f"评价结果：{outcome_label}",
    ]
    if comment and comment.strip():
        lines.extend(["", "用户说明：", comment.strip()])
    else:
        lines.append("")
        lines.append("（用户未填写补充说明）")
    return "\n".join(lines)


async def backfill_missing_agent_feedbacks(db: AsyncSession, user_id: str | None = None) -> int:
    """将历史 TraceOutcome 补录到 feedbacks（尚未关联的）"""
    from app.models.supervision import TraceOutcome
    from app.models.user import User

    q = select(TraceOutcome).order_by(TraceOutcome.created_at.desc()).limit(100)
    if user_id:
        q = q.where(TraceOutcome.user_id == user_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    count = 0
    for to in rows:
        dup = await db.execute(
            select(Feedback).where(Feedback.trace_id == to.trace_id)
        )
        if dup.scalar_one_or_none():
            continue
        uname = to.user_id
        ur = await db.execute(select(User).where(User.id == to.user_id))
        u = ur.scalar_one_or_none()
        if u:
            uname = u.username
        await sync_trace_outcome_to_feedback(
            db,
            user_id=to.user_id,
            username=uname,
            session_id=to.session_id,
            trace_id=to.trace_id,
            outcome=to.outcome,
            comment=to.comment or "",
        )
        count += 1
    return count
