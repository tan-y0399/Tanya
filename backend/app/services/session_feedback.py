"""会话级 Agent 对话反馈（与 trace 结果反馈区分）"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback, gen_id

SESSION_FEEDBACK_SOURCE = "session_chat"

_OUTCOME_STAR_LABEL = {
    "solved": "非常满意 ★★★★★",
    "partial": "一般满意 ★★★",
    "unsolved": "不满意 ★",
}

_CATEGORY_LABEL = {
    "wrong_answer": "回答不准确",
    "not_solved": "未解决问题",
    "tool_error": "工具执行异常",
    "ui_issue": "界面体验",
    "other": "其他",
}


def build_session_feedback_title(session_title: str = "", category: str = "") -> str:
    brief = (session_title or "智能对话").strip()[:200]
    return brief


def build_session_feedback_content(
    *,
    session_id: str,
    trace_id: str | None,
    category: str,
    body: str,
    outcome: str | None = None,
    star_rating: int | None = None,
    star_label: str | None = None,
    image_urls: list[str] | None = None,
) -> str:
    lines = [
        "来源：对话页 · 会话反馈",
        f"会话 ID：{session_id}",
    ]
    if trace_id:
        lines.append(f"最近 Trace：{trace_id}")
    if category:
        lines.append(f"问题类型：{_CATEGORY_LABEL.get(category, category)}")
    if star_rating and star_label:
        lines.append(f"满意度：{star_label}（{star_rating} 星）")
    elif outcome:
        lines.append(f"满意度：{_OUTCOME_STAR_LABEL.get(outcome, outcome)}")
    lines.extend(["", "详细说明：", (body or "").strip() or "（无）"])
    if image_urls:
        lines.extend(["", "附图："])
        for i, url in enumerate(image_urls, 1):
            lines.append(f"- 图{i}：{url}")
    return "\n".join(lines)


def _dump_attachments(urls: list[str]) -> str:
    items = [{"url": u, "name": u.rsplit("/", 1)[-1]} for u in (urls or []) if u]
    return json.dumps(items, ensure_ascii=False) if items else ""


def _parse_attachments(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


async def get_session_feedback(
    db: AsyncSession, user_id: str, session_id: str
) -> Feedback | None:
    result = await db.execute(
        select(Feedback).where(
            Feedback.user_id == user_id,
            Feedback.session_id == session_id,
            Feedback.source == SESSION_FEEDBACK_SOURCE,
        ).order_by(Feedback.updated_at.desc())
    )
    return result.scalars().first()


async def upsert_session_feedback(
    db: AsyncSession,
    *,
    user_id: str,
    username: str,
    session_id: str,
    category: str,
    content: str,
    trace_id: str | None = None,
    outcome: str | None = None,
    session_title: str = "",
    star_rating: int | None = None,
    star_label: str | None = None,
    image_urls: list[str] | None = None,
) -> Feedback:
    body = (content or "").strip()
    if not body:
        raise ValueError("反馈内容不能为空")

    row = await get_session_feedback(db, user_id, session_id)
    session_title_brief = build_session_feedback_title(session_title, category)
    full_content = build_session_feedback_content(
        session_id=session_id,
        trace_id=trace_id,
        category=category,
        body=body,
        outcome=outcome,
        star_rating=star_rating,
        star_label=star_label,
        image_urls=image_urls,
    )
    att_json = _dump_attachments(image_urls or [])

    if row:
        row.title = session_title_brief
        row.session_title = session_title_brief
        row.category = category
        row.content = full_content
        row.trace_id = trace_id or row.trace_id
        row.outcome = outcome or row.outcome
        row.attachments_json = att_json
        row.status = "pending"
        await db.commit()
        await db.refresh(row)
        return row

    fb = Feedback(
        id=gen_id(),
        user_id=user_id,
        username=username or user_id,
        title=session_title_brief,
        session_title=session_title_brief,
        category=category,
        content=full_content,
        source=SESSION_FEEDBACK_SOURCE,
        session_id=session_id,
        trace_id=trace_id,
        outcome=outcome,
        attachments_json=att_json,
        status="pending",
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return fb
