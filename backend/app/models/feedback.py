"""反馈模型"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(String(24), primary_key=True, default=gen_id)
    user_id = Column(String(24), nullable=False, index=True)
    username = Column(String(64), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    status = Column(String(16), default="pending")  # pending / replied / closed
    admin_reply = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
