"""多模态消息与知识资产模型。"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Float

from app.core.database import Base
from app.models.json_type import JSONType


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id = Column(String(24), primary_key=True, default=gen_id)
    session_id = Column(String(24), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(String(24), ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True)
    role = Column(String(16), default="user")
    kind = Column(String(16), default="image")
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), default="")
    storage_path = Column(String(500), nullable=False)
    public_url = Column(String(500), default="")
    size_bytes = Column(Integer, default=0)
    meta_json = Column(JSONType, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeAsset(Base):
    __tablename__ = "knowledge_assets"

    id = Column(String(24), primary_key=True, default=gen_id)
    article_id = Column(String(24), ForeignKey("knowledge_articles.id", ondelete="SET NULL"), nullable=True, index=True)
    kind = Column(String(16), default="image")
    title = Column(String(200), default="")
    description = Column(Text, default="")
    filename = Column(String(255), default="")
    source_url = Column(String(500), default="")
    storage_path = Column(String(500), default="")
    public_url = Column(String(500), default="")
    tags = Column(String(300), default="")
    score_hint = Column(Float, default=0.0)
    meta_json = Column(JSONType, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
