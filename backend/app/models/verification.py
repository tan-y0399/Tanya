import uuid
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Integer
from app.core.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class SmsCode(Base):
    """短信验证码，含有效期和尝试限制"""
    __tablename__ = "sms_codes"

    id = Column(String(24), primary_key=True, default=gen_id)
    phone = Column(String(20), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    attempts = Column(Integer, default=0)        # 已尝试次数
    max_attempts = Column(Integer, default=3)     # 最多尝试3次
    used = Column(Integer, default=0)             # 0=未使用, 1=已使用
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=5))


class WechatLoginState(Base):
    """微信扫码登录状态"""
    __tablename__ = "wechat_login_states"

    id = Column(String(24), primary_key=True, default=gen_id)
    ticket = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(16), default="pending")  # pending / scanned / confirmed / expired
    openid = Column(String(64), nullable=True)
    nickname = Column(String(64), nullable=True)
    user_id = Column(String(24), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=3))


class EmailCode(Base):
    """邮箱验证码"""
    __tablename__ = "email_codes"

    id = Column(String(24), primary_key=True, default=gen_id)
    email = Column(String(128), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    purpose = Column(String(16), default="register")  # register / login
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=5))
