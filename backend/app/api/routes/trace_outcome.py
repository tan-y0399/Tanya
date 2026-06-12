"""对话轮次结果反馈 API（阶段5）"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.supervision import TraceOutcome
from app.services.human_supervision import validate_user_input

router = APIRouter(prefix="/chat", tags=["对话反馈"])


@router.get("/sessions/{session_id}/trace-outcome")
async def get_trace_outcome(
    session_id: str,
    traceId: str = "",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前用户在某会话某 trace 是否已提交反馈"""
    trace_id = (traceId or "").strip()
    if not trace_id:
        raise HTTPException(status_code=400, detail="缺少 traceId")
    result = await db.execute(
        select(TraceOutcome).where(
            TraceOutcome.session_id == session_id,
            TraceOutcome.trace_id == trace_id,
            TraceOutcome.user_id == user["id"],
        ).order_by(desc(TraceOutcome.created_at))
    )
    row = result.scalars().first()
    if not row:
        return {"code": 0, "data": {"submitted": False}}
    return {
        "code": 0,
        "data": {
            "submitted": True,
            "outcome": row.outcome,
            "comment": row.comment or "",
            "needsExpert": row.needs_expert,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        },
    }


@router.post("/trace-outcome")
async def submit_trace_outcome(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trace_id = (payload.get("traceId") or "").strip()
    session_id = (payload.get("sessionId") or "").strip()
    outcome = (payload.get("outcome") or "").strip()
    comment = (payload.get("comment") or "").strip()

    if not trace_id or not session_id:
        raise HTTPException(status_code=400, detail="缺少 traceId 或 sessionId")
    if outcome not in ("solved", "partial", "unsolved"):
        raise HTTPException(status_code=400, detail="outcome 须为 solved / partial / unsolved")
    if comment:
        v = validate_user_input(comment)
        if not v["valid"]:
            raise HTTPException(status_code=400, detail=v["message"])

    row = TraceOutcome(
        trace_id=trace_id,
        session_id=session_id,
        user_id=user["id"],
        outcome=outcome,
        comment=comment[:2000],
        needs_expert=(outcome == "unsolved"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    feedback_id = None
    try:
        from app.services.feedback_sync import sync_trace_outcome_to_feedback
        fb = await sync_trace_outcome_to_feedback(
            db,
            user_id=user["id"],
            username=user.get("username", ""),
            session_id=session_id,
            trace_id=trace_id,
            outcome=outcome,
            comment=comment,
        )
        if fb:
            feedback_id = fb.id
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("sync trace outcome to feedback failed: %s", e)

    return {
        "code": 0,
        "message": "感谢反馈，未解决问题将标记待专家优化" if outcome == "unsolved" else "反馈已记录",
        "data": {
            "id": row.id,
            "outcome": row.outcome,
            "needsExpert": row.needs_expert,
            "feedbackId": feedback_id,
        },
    }


@router.get("/trace-outcome/stats")
async def trace_outcome_stats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看统计")
    result = await db.execute(select(TraceOutcome))
    rows = result.scalars().all()
    total = len(rows)
    solved = sum(1 for r in rows if r.outcome == "solved")
    unsolved = sum(1 for r in rows if r.outcome == "unsolved")
    return {
        "code": 0,
        "data": {
            "total": total,
            "solved": solved,
            "unsolved": unsolved,
            "solveRate": round(solved / total * 100, 1) if total else 0,
        },
    }
