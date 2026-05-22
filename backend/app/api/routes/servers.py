"""服务器管理 API —— 多机集群运维"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.server import Server
from app.services.ssh_client import SSHClient, SSH_POOL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/servers", tags=["服务器管理"])


def _format_server(s: Server) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "host": s.host,
        "port": s.port,
        "username": s.username,
        "keyPath": s.key_path,
        "description": s.description or "",
        "tags": (s.tags or "").split(",") if s.tags else [],
        "isDefault": s.is_default,
        "status": s.status or "unknown",
        "lastChecked": s.last_checked.isoformat() if s.last_checked else None,
        "createdAt": s.created_at.isoformat() if s.created_at else "",
        "updatedAt": s.updated_at.isoformat() if s.updated_at else "",
    }


@router.get("/list")
async def list_servers(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取所有服务器"""
    result = await db.execute(select(Server).order_by(Server.created_at))
    servers = result.scalars().all()
    return {"code": 0, "data": {"items": [_format_server(s) for s in servers]}}


@router.post("/add")
async def add_server(req: dict = Body(...),
                     user: dict = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    """添加服务器"""
    name = req.get("name", "").strip()
    host = req.get("host", "").strip()
    if not name or not host:
        raise HTTPException(status_code=400, detail="名称和主机地址不能为空")

    # 检查是否已存在相同 host 的服务器
    existing = await db.execute(select(Server).where(Server.host == host))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"主机 {host} 已存在")

    # 如果设为默认，先取消其他默认
    is_default = req.get("isDefault", False)
    if is_default:
        defaults = await db.execute(select(Server).where(Server.is_default == True))
        for s in defaults.scalars().all():
            s.is_default = False

    server = Server(
        name=name,
        host=host,
        port=req.get("port", 22),
        username=req.get("username", "root"),
        key_path=req.get("keyPath", "~/.ssh/id_rsa"),
        description=req.get("description", ""),
        tags=",".join(req.get("tags", [])) if req.get("tags") else "",
        is_default=is_default,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    # 添加后尝试测试连接
    try:
        ssh = SSH_POOL.get_or_create(server.id, server.host, server.port, server.username, server.key_path)
        out, err, code = ssh.execute("hostname")
        server.status = "online" if code == 0 else "offline"
    except Exception as e:
        logger.warning(f"Server {name} connection test failed: {e}")
        server.status = "offline"
    server.last_checked = datetime.utcnow()
    await db.commit()

    return {"code": 0, "data": _format_server(server), "message": "服务器添加成功"}


@router.put("/{server_id}")
async def update_server(server_id: str, req: dict = Body(...),
                        user: dict = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """编辑服务器"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")

    if "name" in req:
        server.name = req["name"].strip()
    if "host" in req:
        server.host = req["host"].strip()
    if "port" in req:
        server.port = req["port"]
    if "username" in req:
        server.username = req["username"]
    if "keyPath" in req:
        server.key_path = req["keyPath"]
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

    # 刷新连接池
    SSH_POOL.remove(server_id)
    try:
        SSH_POOL.get_or_create(server.id, server.host, server.port, server.username, server.key_path)
        server.status = "online"
    except Exception:
        server.status = "offline"
    server.last_checked = datetime.utcnow()
    await db.commit()

    return {"code": 0, "data": _format_server(server), "message": "服务器更新成功"}


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
