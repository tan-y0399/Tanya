"""可回滚命令执行日志"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean
from app.core.database import Base
from app.models.json_type import JSONType


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(String(24), primary_key=True, default=gen_id)
    session_id = Column(String(24), nullable=False, index=True)
    trace_id = Column(String(64), nullable=False, index=True)
    snapshot_id = Column(String(32), nullable=True)
    tool_call_id = Column(String(24), nullable=True, index=True)
    tool_name = Column(String(128), nullable=False)
    risk_level = Column(String(4), nullable=True)
    command_preview = Column(String(512), nullable=True)
    reversible = Column(Boolean, default=False)
    rollback_hint = Column(Text, nullable=True)
    rollback_json = Column(Text, nullable=True)
    pre_state_json = Column(Text, nullable=True)
    result_json = Column(JSONType, nullable=True)
    rolled_back = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
