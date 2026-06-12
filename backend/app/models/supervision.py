"""人类监督：诊断方案确认、对话结果反馈"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean
from app.core.database import Base
from app.models.json_type import JSONType


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class SupervisionPlan(Base):
    """待用户确认的诊断/执行方案"""
    __tablename__ = "supervision_plans"

    id = Column(String(24), primary_key=True, default=gen_id)
    session_id = Column(String(24), nullable=False, index=True)
    trace_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    intent = Column(String(32), nullable=False)
    plan_json = Column(JSONType, nullable=True)
    env_json = Column(JSONType, nullable=True)
    snapshot_id = Column(String(32), nullable=True)
    status = Column(String(24), default="pending_confirm")  # pending_confirm / confirmed / cancelled / env_failed
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)


class TraceOutcome(Base):
    """阶段5：单轮对话结果反馈"""
    __tablename__ = "trace_outcomes"

    id = Column(String(24), primary_key=True, default=gen_id)
    trace_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(24), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    outcome = Column(String(16), nullable=False)  # solved / partial / unsolved
    comment = Column(Text, default="")
    needs_expert = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
