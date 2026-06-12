"""初始化服务器数据 - 添加默认服务器"""
import asyncio
from app.core.database import async_session, engine, Base
from app.models.server import Server


async def init_servers():
    """初始化服务器配置"""
    async with async_session() as session:
        # 检查是否已存在
        from sqlalchemy import select
        result = await session.execute(select(Server).where(Server.host == "192.168.163.15"))
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"服务器 192.168.163.15 已存在，ID: {existing.id}")
            return existing
        
        # 创建新服务器
        server = Server(
            name="麒麟服务器1",
            host="192.168.163.15",
            port=22,
            username="ty",
            key_path="~/.ssh/id_rsa",
            description="麒麟操作系统 - 主要运维服务器",
            tags="麒麟,生产环境,运维",
            is_default=True,
            status="online"
        )
        session.add(server)
        await session.commit()
        await session.refresh(server)
        
        print(f"✅ 已添加服务器: {server.name} ({server.host})")
        print(f"   ID: {server.id}")
        print(f"   是否默认: {server.is_default}")
        return server


if __name__ == "__main__":
    asyncio.run(init_servers())
