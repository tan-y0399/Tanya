"""知识库模型"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id = Column(String(24), primary_key=True, default=gen_id)
    title = Column(String(200), nullable=False)
    category = Column(String(64), nullable=False, index=True)  # 故障排查/操作指南/安全策略/案例库
    tags = Column(String(300), default="")  # 逗号分隔的标签
    content = Column(Text, default="")
    source = Column(String(64), default="manual")  # manual / agent_generated / imported
    severity = Column(String(16), default="info")  # info / warning / critical
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    favorite_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
