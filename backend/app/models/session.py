import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(24), primary_key=True, default=gen_id)
    user_id = Column(String(24), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), default="新会话")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(24), primary_key=True, default=gen_id)
    session_id = Column(String(24), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, default="")
    tool_calls_json = Column(Text, nullable=True)
    trace_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
