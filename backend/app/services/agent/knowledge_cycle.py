"""
知识库自迭代 — 自动报告草稿 + 专家审核队列
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


async def ingest_ops_report(
    db: AsyncSession,
    *,
    title: str,
    content: str,
    trace_id: str,
    outcome: str = "pending_review",
) -> Optional[str]:
    """将运维报告写入知识库草稿，待专家审核后发布。"""
    try:
        from app.models.knowledge import KnowledgeArticle

        article = KnowledgeArticle(
            title=title[:200],
            content=content[:8000],
            category="auto_ops_report",
            tags=f"auto,report,{outcome},trace:{trace_id[:16]}",
            status="draft",
        )
        db.add(article)
        await db.commit()
        await db.refresh(article)

        try:
            from app.services.knowledge_rag import knowledge_rag
            from sqlalchemy import select
            result = await db.execute(select(KnowledgeArticle))
            articles = [
                {"id": a.id, "title": a.title, "content": a.content,
                 "category": a.category, "tags": a.tags}
                for a in result.scalars().all()
            ]
            if articles:
                knowledge_rag.refresh(articles)
        except Exception:
            pass

        return article.id
    except Exception:
        return None


async def publish_after_expert_review(db: AsyncSession, article_id: str) -> bool:
    """专家审核通过后发布文章并刷新索引。"""
    from sqlalchemy import select
    from app.models.knowledge import KnowledgeArticle

    row = (await db.execute(
        select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
    )).scalar_one_or_none()
    if not row:
        return False
    row.status = "published"
    await db.commit()
    return True
