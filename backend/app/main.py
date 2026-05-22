import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import init_db, async_session
from app.core.security import hash_password
from app.models.user import User
from app.models.verification import SmsCode, WechatLoginState
from app.models.knowledge import KnowledgeArticle
from app.models.pending_execution import PendingExecution
from app.models.server import Server
from app.api.routes import auth, chat, audit, approval, system, dashboard, knowledge, alerts, servers


app = FastAPI(title=settings.app_name, version=settings.version)

# 前端静态文件目录
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    from sqlalchemy import select
    async with async_session() as db:
        # 种子用户
        result = await db.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin"))
            db.add(User(username="auditor", password_hash=hash_password("audit123"), role="auditor"))
            await db.commit()
        # 种子知识库
        from app.api.routes.knowledge import seed_knowledge
        await seed_knowledge(db)

        # 种子默认服务器（从 SSH 配置读取）
        result = await db.execute(select(Server))
        if not result.scalars().first():
            default_server = Server(
                name="默认麒麟服务器",
                host=settings.ssh_host,
                port=settings.ssh_port,
                username=settings.ssh_user,
                key_path=settings.ssh_key_path,
                description="系统默认服务器（来自 .env 配置）",
                is_default=True,
                status="unknown",
            )
            db.add(default_server)
            await db.commit()


app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(approval.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(servers.router, prefix="/api/v1")

# 托管前端 SPA（必须在所有 API 路由之后注册）
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
