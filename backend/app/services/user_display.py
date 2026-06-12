"""用户 ID / 用户名解析为展示名。"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

ROLE_LABELS = {
    "admin": "管理员",
    "auditor": "审计员",
    "deployer": "部署员",
    "user": "普通用户",
}

RISK_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}


def role_label(role: Optional[str]) -> str:
    return ROLE_LABELS.get((role or "user").strip(), "普通用户")


def user_display_from_row(user: Optional[User], fallback_id: str = "") -> dict:
    if user:
        username = user.username
        role = user.role or "user"
        return {
            "userId": user.id,
            "username": username,
            "userRole": role,
            "userRoleLabel": role_label(role),
            "userDisplayName": username,
        }
    fid = (fallback_id or "").strip()
    return {
        "userId": fid,
        "username": fid or "未知用户",
        "userRole": "user",
        "userRoleLabel": "普通用户",
        "userDisplayName": fid or "未知用户",
    }


async def load_users_map(db: AsyncSession, refs: Iterable[str]) -> Dict[str, User]:
    ids = {r.strip() for r in refs if r and r.strip()}
    if not ids:
        return {}
    by_id: Dict[str, User] = {}
    by_name: Dict[str, User] = {}

    result = await db.execute(select(User).where(User.id.in_(list(ids))))
    for u in result.scalars().all():
        by_id[u.id] = u

    remaining = ids - set(by_id.keys())
    if remaining:
        result2 = await db.execute(select(User).where(User.username.in_(list(remaining))))
        for u in result2.scalars().all():
            by_name[u.username] = u

    out: Dict[str, User] = {}
    for ref in ids:
        if ref in by_id:
            out[ref] = by_id[ref]
        elif ref in by_name:
            out[ref] = by_name[ref]
    return out


async def resolve_user_display(db: AsyncSession, ref: Optional[str]) -> dict:
    if not ref or not str(ref).strip():
        return user_display_from_row(None, "")
    ref = str(ref).strip()
    users = await load_users_map(db, [ref])
    return user_display_from_row(users.get(ref), ref)


def max_risk_level(levels: Iterable[Optional[str]]) -> str:
    best = "L1"
    for lv in levels:
        if not lv:
            continue
        if RISK_ORDER.get(lv, 0) > RISK_ORDER.get(best, 0):
            best = lv
    return best
