import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class PendingExecution(Base):
    """待审批或待确认的工具调用，审批通过后继续执行"""
    __tablename__ = "pending_executions"

    id = Column(String(24), primary_key=True, default=gen_id)
    session_id = Column(String(24), nullable=False, index=True)
    trace_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    approval_id = Column(String(24), nullable=True, index=True)

    tool_name = Column(String(128), nullable=False)
    tool_params_json = Column(Text, nullable=True)
    risk_level = Column(String(4), nullable=False)

    messages_snapshot_json = Column(Text, nullable=True)

    need_confirm = Column(Boolean, default=False)
    need_approval = Column(Boolean, default=False)

    status = Column(String(16), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
