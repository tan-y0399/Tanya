from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import event
from .config import settings

# 根据数据库类型构建引擎参数
_engine_kwargs = {
    "echo": False,
}

if "sqlite" in settings.database_url:
    _engine_kwargs["connect_args"] = {"timeout": 10}
elif "postgresql" in settings.database_url:
    _engine_kwargs["connect_args"] = {"ssl": False}

# 仅 PostgreSQL 支持连接池参数（多用户局域网访问需更大池）
if "postgresql" in settings.database_url:
    from sqlalchemy.pool import AsyncAdaptedQueuePool
    _engine_kwargs["poolclass"] = AsyncAdaptedQueuePool
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
    _engine_kwargs["pool_timeout"] = 10
    _engine_kwargs["pool_recycle"] = 1800

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


# SQLite 优化：仅在 SQLite 时启用 WAL 模式 + 外键约束
if "sqlite" in settings.database_url:
    @event.listens_for(engine.sync_engine, "connect")
    def _setup_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    await engine.dispose()
