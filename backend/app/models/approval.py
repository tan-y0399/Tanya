import uuid
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Text
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(24), primary_key=True, default=gen_id)
    trace_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(24), nullable=True)
    tool_name = Column(String(128), nullable=False)
    tool_params_json = Column(Text, nullable=True)
    risk_level = Column(String(4), nullable=False)
    detail = Column(String(500), default="")
    requested_by = Column(String(64), nullable=False)
    status = Column(String(16), default="pending")
    approver = Column(String(64), nullable=True)
    comment = Column(String(500), nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True, default=None)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(seconds=120))
