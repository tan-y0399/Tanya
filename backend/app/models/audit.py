import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id = Column(String(24), primary_key=True, default=gen_id)
    trace_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(24), nullable=True)
    user_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    summary = Column(String(500), default="")
    risk_level = Column(String(4), nullable=True)
    detail_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
