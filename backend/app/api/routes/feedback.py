"""反馈系统 API"""
import json

from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.feedback import Feedback

router = APIRouter(prefix="/feedback", tags=["反馈"])

_SOURCE_LABEL = {
    "manual": "手动反馈",
    "session_chat": "会话反馈",
    "agent_chat": "会话评价",
}

_TYPE_LABEL = {
    "wrong_answer": "回答不准确",
    "not_solved": "未解决问题",
    "tool_error": "工具执行异常",
    "ui_issue": "界面体验",
    "other": "其他",
    "general": "一般反馈",
    "solved": "已解决",
    "partial": "部分解决",
    "unsolved": "未解决",
}


def _resolve_display_title(f: Feedback) -> str:
    st = getattr(f, "session_title", None)
    if st and str(st).strip():
        return str(st).strip()[:200]
    title = f.title or ""
    if title.startswith("[会话反馈·") and "] " in title:
        return title.split("] ", 1)[1]
    if title.startswith("[Agent对话]"):
        return "智能对话"
    return title


def _resolve_type_label(f: Feedback) -> str:
    source = getattr(f, "source", None) or "manual"
    cat = getattr(f, "category", None)
    if cat and cat in _TYPE_LABEL:
        return _TYPE_LABEL[cat]
    if source == "agent_chat":
        outcome = getattr(f, "outcome", None)
        return _TYPE_LABEL.get(outcome or "", "会话评价")
    if source == "session_chat":
        return _TYPE_LABEL.get(cat or "", "会话反馈")
    return "一般反馈"


def _resolve_source_label(source: str | None) -> str:
    return _SOURCE_LABEL.get(source or "manual", "手动反馈")


def _parse_attachments_field(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _serialize(f: Feedback) -> dict:
    display_title = _resolve_display_title(f)
    return {
        "id": f.id,
        "userId": f.user_id,
        "username": f.username,
        "title": display_title,
        "sessionTitle": display_title,
        "content": f.content,
        "source": getattr(f, "source", None) or "manual",
        "sourceLabel": _resolve_source_label(getattr(f, "source", None)),
        "typeLabel": _resolve_type_label(f),
        "category": getattr(f, "category", None),
        "traceId": getattr(f, "trace_id", None),
        "sessionId": getattr(f, "session_id", None),
        "outcome": getattr(f, "outcome", None),
        "status": f.status,
        "adminReply": f.admin_reply,
        "attachments": _parse_attachments_field(getattr(f, "attachments_json", None)),
        "createdAt": f.created_at.isoformat() if f.created_at else "",
        "updatedAt": f.updated_at.isoformat() if f.updated_at else "",
    }


@router.get("/list")
async def list_feedback(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.feedback_sync import ensure_feedback_schema, backfill_missing_agent_feedbacks

    await ensure_feedback_schema(db)
    try:
        await backfill_missing_agent_feedbacks(
            db, user_id=None if user.get("role") == "admin" else user["id"]
        )
    except Exception:
        pass

    is_admin = user.get("role") == "admin"
    if is_admin:
        result = await db.execute(select(Feedback).order_by(Feedback.created_at.desc()))
    else:
        result = await db.execute(
            select(Feedback).where(Feedback.user_id == user["id"]).order_by(Feedback.created_at.desc())
        )
    items = result.scalars().all()
    return {"code": 0, "data": {"items": [_serialize(f) for f in items]}}


@router.get("/session/{session_id}")
async def get_feedback_by_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户在指定会话下的反馈（每会话独立一条 session_chat 记录）"""
    from app.services.feedback_sync import ensure_feedback_schema
    from app.services.session_feedback import get_session_feedback

    await ensure_feedback_schema(db)
    sid = (session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="sessionId 无效")

    fb = await get_session_feedback(db, user["id"], sid)
    return {"code": 0, "data": {"item": _serialize(fb) if fb else None}}


@router.post("/session")
async def create_session_feedback(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对话页提交会话级反馈，写入反馈模块供管理员审核"""
    from app.services.feedback_sync import ensure_feedback_schema
    from app.services.session_feedback import upsert_session_feedback

    await ensure_feedback_schema(db)
    session_id = (payload.get("sessionId") or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId 不能为空")

    category = (payload.get("category") or "other").strip()
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="请填写反馈内容")

    images = payload.get("images") or payload.get("imageUrls") or []
    if isinstance(images, str):
        images = [images]
    image_urls = [str(u).strip() for u in images if str(u).strip()][:6]

    star_rating = payload.get("starRating")
    try:
        star_rating = int(star_rating) if star_rating is not None else None
    except (TypeError, ValueError):
        star_rating = None
    if star_rating is not None and not (1 <= star_rating <= 5):
        star_rating = None

    try:
        fb = await upsert_session_feedback(
            db,
            user_id=user["id"],
            username=user.get("username", ""),
            session_id=session_id,
            category=category,
            content=content,
            trace_id=(payload.get("traceId") or "").strip() or None,
            outcome=(payload.get("outcome") or "").strip() or None,
            session_title=(payload.get("sessionTitle") or "").strip(),
            star_rating=star_rating,
            star_label=(payload.get("starLabel") or "").strip() or None,
            image_urls=image_urls,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"code": 0, "data": _serialize(fb), "message": "反馈已提交，管理员将尽快处理"}


@router.post("/upload-image")
async def upload_feedback_image(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """上传反馈附图（会话反馈弹窗）"""
    from app.services.feedback_upload import save_feedback_image

    try:
        item = await save_feedback_image(file, user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": item, "message": "上传成功"}


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

    images = payload.get("images") or payload.get("imageUrls") or []
    if isinstance(images, str):
        images = [images]
    image_urls = [str(u).strip() for u in images if str(u).strip()][:6]
    att_json = ""
    if image_urls:
        att_json = json.dumps(
            [{"url": u, "name": u.rsplit("/", 1)[-1]} for u in image_urls],
            ensure_ascii=False,
        )

    fb = Feedback(
        user_id=user["id"],
        username=user.get("username", ""),
        title=title,
        session_title=title,
        content=content,
        category=(payload.get("category") or "general").strip() or "general",
        status="pending",
        source=(payload.get("source") or "manual"),
        session_id=(payload.get("sessionId") or "").strip() or None,
        trace_id=(payload.get("traceId") or "").strip() or None,
        attachments_json=att_json,
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
