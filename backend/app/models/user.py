import uuid
from sqlalchemy import Column, String
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class User(Base):
    __tablename__ = "users"

    id = Column(String(24), primary_key=True, default=gen_id)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(32), default="admin")
