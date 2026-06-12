"""知识库用户互动（点赞/收藏）"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, UniqueConstraint
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class KnowledgeEngagement(Base):
    __tablename__ = "knowledge_engagements"
    __table_args__ = (
        UniqueConstraint("article_id", "user_key", name="uq_kb_engagement"),
    )

    id = Column(String(24), primary_key=True, default=gen_id)
    article_id = Column(String(24), nullable=False, index=True)
    user_key = Column(String(64), nullable=False, index=True)
    liked = Column(Boolean, default=False)
    favorited = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
