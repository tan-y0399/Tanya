"""用户管理 API — 仅管理员可操作"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user, hash_password
from app.models.user import User

router = APIRouter(prefix="/users", tags=["用户管理"])


def _require_admin(user: dict):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")


def _serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
    }


@router.get("/list")
async def list_users(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    result = await db.execute(select(User).order_by(User.username))
    users = result.scalars().all()
    return {"code": 0, "data": {"items": [_serialize_user(u) for u in users]}}


@router.post("/create")
async def create_user(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    role = payload.get("role") or "user"

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    existing = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    new_user = User(username=username, password_hash=hash_password(password), role=role)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"code": 0, "data": _serialize_user(new_user), "message": "用户创建成功"}


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    if u.username == "admin":
        raise HTTPException(status_code=400, detail="不能修改超级管理员")

    if "role" in payload:
        u.role = payload["role"]
    if "password" in payload and payload["password"]:
        u.password_hash = hash_password(payload["password"])

    await db.commit()
    await db.refresh(u)
    return {"code": 0, "data": _serialize_user(u), "message": "用户更新成功"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    if u.username == "admin":
        raise HTTPException(status_code=400, detail="不能删除超级管理员")

    await db.delete(u)
    await db.commit()
    return {"code": 0, "message": "用户已删除"}


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    new_password = payload.get("password") or "123456"
    u.password_hash = hash_password(new_password)
    await db.commit()
    return {"code": 0, "message": "密码已重置"}
