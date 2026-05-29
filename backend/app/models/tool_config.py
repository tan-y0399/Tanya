"""工具配置模型"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class ToolConfig(Base):
    __tablename__ = "tool_configs"

    id = Column(String(24), primary_key=True, default=gen_id)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(300), default="")
    category = Column(String(64), default="")  # system_monitor / process_management / etc.
    risk_level = Column(Integer, default=1)  # 1-5
    enabled = Column(Integer, default=1)  # 0=disabled, 1=enabled
    config_json = Column(Text, default="{}")  # JSON config for the tool
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
