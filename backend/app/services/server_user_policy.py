"""SSH 运维用户策略：禁止 root 直连，默认使用普通用户。"""
from typing import Optional

from app.core.config import settings

RESTRICTED_SSH_USERS = frozenset({"root", "administrator"})


def is_restricted_ssh_user(username: Optional[str]) -> bool:
    return (username or "").strip().lower() in RESTRICTED_SSH_USERS


def default_ops_ssh_user() -> str:
    candidate = (settings.ssh_user or "").strip() or "ty"
    if is_restricted_ssh_user(candidate):
        return "ty"
    return candidate


def normalize_ssh_user(username: Optional[str]) -> str:
    """空值时使用默认运维用户。"""
    u = (username or "").strip()
    return u or default_ops_ssh_user()


def assert_allowed_ssh_user(username: Optional[str]) -> str:
    """校验并返回合法 SSH 用户名，禁止 root 等特权账户。"""
    u = normalize_ssh_user(username)
    if is_restricted_ssh_user(u):
        raise ValueError(
            f"禁止使用 {u!r} 作为 SSH 运维用户，请配置普通用户（如 {default_ops_ssh_user()}）"
        )
    return u
