"""反馈系统 API"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.feedback import Feedback

router = APIRouter(prefix="/feedback", tags=["反馈"])


def _serialize(f: Feedback) -> dict:
    return {
        "id": f.id,
        "userId": f.user_id,
        "username": f.username,
        "title": f.title,
        "content": f.content,
        "status": f.status,
        "adminReply": f.admin_reply,
        "createdAt": f.created_at.isoformat() if f.created_at else "",
        "updatedAt": f.updated_at.isoformat() if f.updated_at else "",
    }


@router.get("/list")
async def list_feedback(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = user.get("role") == "admin"
    if is_admin:
        result = await db.execute(select(Feedback).order_by(Feedback.created_at.desc()))
    else:
        result = await db.execute(
            select(Feedback).where(Feedback.user_id == user["id"]).order_by(Feedback.created_at.desc())
        )
    items = result.scalars().all()
    return {"code": 0, "data": {"items": [_serialize(f) for f in items]}}


@router.post("/create")
async def create_feedback(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")

    fb = Feedback(
        user_id=user["id"],
        username=user.get("username", ""),
        title=title,
        content=content,
        status="pending",
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return {"code": 0, "data": _serialize(fb), "message": "反馈提交成功"}


@router.post("/{feedback_id}/reply")
async def reply_feedback(
    feedback_id: str,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可回复")

    fb = (await db.execute(select(Feedback).where(Feedback.id == feedback_id))).scalar_one_or_none()
    if not fb:
        raise HTTPException(status_code=404, detail="反馈不存在")

    reply_content = (payload.get("reply") or "").strip()
    fb.admin_reply = reply_content
    fb.status = "replied"
    await db.commit()
    await db.refresh(fb)
    return {"code": 0, "data": _serialize(fb), "message": "回复成功"}


@router.put("/{feedback_id}/status")
async def update_status(
    feedback_id: str,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    fb = (await db.execute(select(Feedback).where(Feedback.id == feedback_id))).scalar_one_or_none()
    if not fb:
        raise HTTPException(status_code=404, detail="反馈不存在")

    new_status = payload.get("status", "pending")
    if new_status not in ("pending", "replied", "closed"):
        raise HTTPException(status_code=400, detail="无效状态")
    fb.status = new_status
    await db.commit()
    await db.refresh(fb)
    return {"code": 0, "data": _serialize(fb), "message": "状态更新成功"}
