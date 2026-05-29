"""任务编排持久化模型"""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer
from app.core.database import Base


def gen_id():
    import uuid
    return uuid.uuid4().hex[:24]


class TaskState(Base):
    __tablename__ = "task_states"

    id = Column(String(24), primary_key=True, default=gen_id)
    session_id = Column(String(24), nullable=False, index=True)
    trace_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    state = Column(String(32), nullable=False, default="init")
    steps_json = Column(Text, nullable=True)
    progress = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
