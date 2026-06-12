import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Server(Base):
    """麒麟服务器配置，支持多机集群管理"""
    __tablename__ = "servers"

    id = Column(String(24), primary_key=True, default=gen_id)
    name = Column(String(64), nullable=False)
    host = Column(String(128), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(64), default="ty")
    key_path = Column(String(256), default="~/.ssh/id_rsa")
    description = Column(String(256), default="")
    tags = Column(String(256), default="")  # 逗号分隔标签，如 "web,db,prod"
    is_default = Column(Boolean, default=False)
    status = Column(String(16), default="unknown")  # online / offline / unknown
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
