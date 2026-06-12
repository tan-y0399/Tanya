"""服务器管理 API —— 多机集群运维"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.server import Server
from app.services.ssh_client import SSHClient, SSH_POOL
from app.services.server_user_policy import assert_allowed_ssh_user, default_ops_ssh_user, is_restricted_ssh_user
from app.services.server_provisioner import auto_provision_server, check_host_reachable, diagnose_host_connectivity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/servers", tags=["服务器管理"])


def _format_server(s: Server) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "host": s.host,
        "port": s.port,
        "username": s.username,
        "authConfigured": bool(s.key_path),
        "description": s.description or "",
        "tags": (s.tags or "").split(",") if s.tags else [],
        "isDefault": s.is_default,
        "status": s.status or "unknown",
        "lastChecked": s.last_checked.isoformat() if s.last_checked else None,
        "createdAt": s.created_at.isoformat() if s.created_at else "",
        "updatedAt": s.updated_at.isoformat() if s.updated_at else "",
    }


def _provision_or_raise(host: str, port: int, username: str, host_password: str) -> dict:
    result = auto_provision_server(host, port, username, host_password)
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": result.get("error") or "自动化配置失败",
                "steps": result.get("steps") or [],
            },
        )
    return result


@router.get("/defaults")
async def server_defaults(user: dict = Depends(get_current_user)):
    """返回推荐的 SSH 运维用户默认值（供前端表单使用）。"""
    return {
        "code": 0,
        "data": {
            "username": default_ops_ssh_user(),
            "restrictedUsers": sorted({"root", "administrator"}),
            "platformKeyPath": settings.ssh_key_path,
        },
    }


@router.get("/list")
async def list_servers(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取所有服务器"""
    result = await db.execute(select(Server).order_by(Server.created_at))
    servers = result.scalars().all()
    return {"code": 0, "data": {"items": [_format_server(s) for s in servers]}}


@router.post("/provision")
async def provision_server(req: dict = Body(...), user: dict = Depends(get_current_user)):
    """预览/执行自动化 SSH 配置（不写入数据库）。"""
    host = req.get("host", "").strip()
    port = int(req.get("port") or 22)
    username = req.get("username") or default_ops_ssh_user()
    host_password = req.get("hostPassword") or ""

    if not host:
        raise HTTPException(status_code=400, detail="主机地址不能为空")
    if not host_password:
        raise HTTPException(status_code=400, detail="请填写主机密码")

    result = auto_provision_server(host, port, username, host_password)
    return {"code": 0 if result.get("success") else 1, "data": result}


@router.post("/check-reachable")
async def check_reachable(req: dict = Body(...), user: dict = Depends(get_current_user)):
    """快速检测主机端口是否可达。"""
    host = req.get("host", "").strip()
    port = int(req.get("port") or 22)
    if not host:
        raise HTTPException(status_code=400, detail="主机地址不能为空")
    diag = diagnose_host_connectivity(host, port)
    return {"code": 0, "data": diag}


@router.post("/add")
async def add_server(req: dict = Body(...),
                     user: dict = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    """添加服务器（含自动化 SSH 配置）"""
    name = req.get("name", "").strip()
    host = req.get("host", "").strip()
    host_password = req.get("hostPassword") or ""
    if not name or not host:
        raise HTTPException(status_code=400, detail="名称和主机地址不能为空")
    if not host_password:
        raise HTTPException(status_code=400, detail="请填写主机密码以完成自动化配置")

    existing = await db.execute(select(Server).where(Server.host == host))
    dup = existing.scalar_one_or_none()
    if dup:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"主机 {host} 已存在，请编辑已有服务器「{dup.name}」",
                "existing": _format_server(dup),
            },
        )

    try:
        username = assert_allowed_ssh_user(req.get("username"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    port = int(req.get("port") or 22)
    provision = _provision_or_raise(host, port, username, host_password)

    is_default = req.get("isDefault", False)
    if is_default:
        defaults = await db.execute(select(Server).where(Server.is_default == True))
        for s in defaults.scalars().all():
            s.is_default = False

    server = Server(
        name=name,
        host=host,
        port=port,
        username=provision.get("username") or username,
        key_path=provision.get("keyPath") or settings.ssh_key_path,
        description=req.get("description", ""),
        tags=",".join(req.get("tags", [])) if req.get("tags") else "",
        is_default=is_default,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    try:
        ssh = SSH_POOL.get_or_create(server.id, server.host, server.port, server.username, server.key_path)
        out, err, code = ssh.execute("hostname")
        server.status = "online" if code == 0 else "offline"
    except Exception as e:
        logger.warning(f"Server {name} connection test failed: {e}")
        server.status = "offline"
    server.last_checked = datetime.utcnow()
    await db.commit()

    return {
        "code": 0,
        "data": _format_server(server),
        "provision": {"steps": provision.get("steps") or []},
        "message": "服务器添加成功，SSH 自动化配置已完成",
    }


@router.put("/{server_id}")
async def update_server(server_id: str, req: dict = Body(...),
                        user: dict = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """编辑服务器（填写密码时重新执行自动化配置）"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")

    provision = None
    host_password = (req.get("hostPassword") or "").strip()
    next_host = req.get("host", server.host).strip() if "host" in req else server.host
    next_port = int(req.get("port") or server.port)
    next_username = req.get("username", server.username) if "username" in req else server.username

    if host_password:
        try:
            next_username = assert_allowed_ssh_user(next_username)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        provision = _provision_or_raise(next_host, next_port, next_username, host_password)
        server.username = provision.get("username") or next_username
        server.key_path = provision.get("keyPath") or settings.ssh_key_path

    if "name" in req:
        server.name = req["name"].strip()
    if "host" in req:
        new_host = req["host"].strip()
        if new_host != server.host:
            conflict = await db.execute(
                select(Server).where(Server.host == new_host, Server.id != server_id)
            )
            dup = conflict.scalar_one_or_none()
            if dup:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"主机 {new_host} 已被「{dup.name}」使用",
                        "existing": _format_server(dup),
                    },
                )
        server.host = new_host
    if "port" in req:
        server.port = req["port"]
    if "username" in req and not host_password:
        try:
            server.username = assert_allowed_ssh_user(req["username"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if "description" in req:
        server.description = req["description"]
    if "tags" in req:
        server.tags = ",".join(req["tags"]) if isinstance(req["tags"], list) else req["tags"]

    if "isDefault" in req and req["isDefault"]:
        defaults = await db.execute(select(Server).where(Server.is_default == True, Server.id != server_id))
        for s in defaults.scalars().all():
            s.is_default = False
        server.is_default = True

    server.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(server)

    SSH_POOL.remove(server_id)
    try:
        SSH_POOL.get_or_create(server.id, server.host, server.port, server.username, server.key_path)
        server.status = "online"
    except Exception:
        server.status = "offline"
    server.last_checked = datetime.utcnow()
    await db.commit()

    resp = {"code": 0, "data": _format_server(server), "message": "服务器更新成功"}
    if provision:
        resp["provision"] = {"steps": provision.get("steps") or []}
        resp["message"] = "服务器更新成功，SSH 自动化配置已完成"
    return resp


@router.delete("/{server_id}")
async def delete_server(server_id: str,
                        user: dict = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """删除服务器"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")

    SSH_POOL.remove(server_id)
    await db.delete(server)
    await db.commit()
    return {"code": 0, "message": "服务器已删除"}


@router.post("/{server_id}/test")
async def test_connection(server_id: str,
                          user: dict = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    """测试服务器连接"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")

    try:
        ssh = SSH_POOL.get_or_create(server.id, server.host, server.port, server.username, server.key_path)
        out, err, code = ssh.execute("echo 'OK' && hostname && uname -r")
        server.status = "online" if code == 0 else "offline"
        server.last_checked = datetime.utcnow()
        await db.commit()
        return {"code": 0, "data": {"success": code == 0, "output": out, "hostname": out.split("\n")[1] if "\n" in out else ""}}
    except Exception as e:
        server.status = "offline"
        server.last_checked = datetime.utcnow()
        await db.commit()
        return {"code": 0, "data": {"success": False, "error": str(e)}}
