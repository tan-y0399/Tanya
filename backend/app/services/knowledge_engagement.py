"""知识库互动：点赞/收藏 schema 迁移与业务逻辑"""
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge import KnowledgeArticle
from app.models.knowledge_engagement import KnowledgeEngagement


async def ensure_knowledge_schema(db: AsyncSession) -> None:
    alters = [
        "ALTER TABLE knowledge_articles ADD COLUMN like_count INTEGER DEFAULT 0",
        "ALTER TABLE knowledge_articles ADD COLUMN favorite_count INTEGER DEFAULT 0",
    ]
    for sql in alters:
        try:
            await db.execute(text(sql))
            await db.commit()
        except Exception:
            await db.rollback()

    try:
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS knowledge_engagements (
                id VARCHAR(24) PRIMARY KEY,
                article_id VARCHAR(24) NOT NULL,
                user_key VARCHAR(64) NOT NULL,
                liked BOOLEAN DEFAULT FALSE,
                favorited BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, user_key)
            )
        """))
        await db.commit()
    except Exception:
        await db.rollback()


def _article_payload(article: KnowledgeArticle, engagement: Optional[KnowledgeEngagement] = None) -> dict:
    data = {
        "likeCount": article.like_count or 0,
        "favoriteCount": article.favorite_count or 0,
        "liked": bool(engagement.liked) if engagement else False,
        "favorited": bool(engagement.favorited) if engagement else False,
    }
    return data


async def _get_engagement(db: AsyncSession, article_id: str, user_key: str) -> Optional[KnowledgeEngagement]:
    result = await db.execute(
        select(KnowledgeEngagement).where(
            KnowledgeEngagement.article_id == article_id,
            KnowledgeEngagement.user_key == user_key,
        )
    )
    return result.scalar_one_or_none()


async def get_user_engagements(db: AsyncSession, user_key: str, article_ids: list[str] | None = None) -> dict:
    q = select(KnowledgeEngagement).where(KnowledgeEngagement.user_key == user_key)
    if article_ids:
        q = q.where(KnowledgeEngagement.article_id.in_(article_ids))
    rows = (await db.execute(q)).scalars().all()
    return {
        r.article_id: {"liked": bool(r.liked), "favorited": bool(r.favorited)}
        for r in rows
    }


async def toggle_like(db: AsyncSession, article_id: str, user_key: str) -> dict:
    article = (await db.execute(
        select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
    )).scalar_one_or_none()
    if not article:
        return {}

    engagement = await _get_engagement(db, article_id, user_key)
    if not engagement:
        engagement = KnowledgeEngagement(article_id=article_id, user_key=user_key)
        db.add(engagement)

    if engagement.liked:
        engagement.liked = False
        article.like_count = max(0, (article.like_count or 0) - 1)
    else:
        engagement.liked = True
        article.like_count = (article.like_count or 0) + 1

    await db.commit()
    await db.refresh(article)
    return _article_payload(article, engagement)


async def toggle_favorite(db: AsyncSession, article_id: str, user_key: str) -> dict:
    article = (await db.execute(
        select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
    )).scalar_one_or_none()
    if not article:
        return {}

    engagement = await _get_engagement(db, article_id, user_key)
    if not engagement:
        engagement = KnowledgeEngagement(article_id=article_id, user_key=user_key)
        db.add(engagement)

    if engagement.favorited:
        engagement.favorited = False
        article.favorite_count = max(0, (article.favorite_count or 0) - 1)
    else:
        engagement.favorited = True
        article.favorite_count = (article.favorite_count or 0) + 1

    await db.commit()
    await db.refresh(article)
    return _article_payload(article, engagement)
