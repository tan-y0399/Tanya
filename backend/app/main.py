import os
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select, func, text
from app.models.knowledge import KnowledgeArticle

from app.core.config import settings
from app.core.database import init_db, async_session, close_db
from app.core.security import hash_password
from app.models.user import User
from app.models.server import Server
from app.api.routes import auth, chat, audit, approval, system, dashboard, knowledge, alerts, servers, users, tools, feedback, trace_outcome
from app.models.supervision import SupervisionPlan, TraceOutcome
from app.models.execution_log import ExecutionLog
from app.models.multimodal import MessageAttachment, KnowledgeAsset
from app.api.routes.knowledge import seed_knowledge
# from app.mcp.server import router as mcp_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

# 初始化标记文件路径（基于项目根目录，兼容 SQLite / PostgreSQL）
_INIT_FLAG_PATH = os.path.join(os.path.dirname(__file__), "..", ".initialized")

app = FastAPI(title=settings.app_name, version=settings.version)


class NoCacheIndexMiddleware(BaseHTTPMiddleware):
    """避免浏览器长期缓存 index.html，导致前端 JS 包未更新。"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path or ""
        if path.startswith("/api/"):
            return response
        ct = (response.headers.get("content-type") or "").lower()
        if path in ("", "/") or path.endswith("/index.html") or "text/html" in ct:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(NoCacheIndexMiddleware)


def _is_first_startup() -> bool:
    """通过标记文件判断是否首次启动（比查数据库更可靠）"""
    return not os.path.exists(_INIT_FLAG_PATH)


def _mark_initialized():
    """写入初始化完成标记"""
    with open(_INIT_FLAG_PATH, "w") as f:
        f.write("ok")


@app.on_event("startup")
async def startup():
    logger.info(f"Starting KylinOps... DB: {settings.database_url}")
    await init_db()

    async with async_session() as db:
        try:
            from app.services.feedback_sync import ensure_feedback_schema
            await ensure_feedback_schema(db)
        except Exception as e:
            logger.warning("feedback schema migrate: %s", e)
        try:
            from app.services.knowledge_engagement import ensure_knowledge_schema
            await ensure_knowledge_schema(db)
        except Exception as e:
            logger.warning("knowledge schema migrate: %s", e)
        # ✅ 安全的首次启动检测：使用标记文件，不会误判
        if _is_first_startup():
            logger.info("🎉 First startup detected — initializing database...")

            try:
                # 清空所有数据（仅真正首次启动时）
                from sqlalchemy import delete as sa_delete
                from app.models.session import Session, Message
                from app.models.audit import AuditRecord
                from app.models.approval import Approval
                from app.models.pending_execution import PendingExecution
                from app.models.feedback import Feedback

                tables_to_clear = [
                    PendingExecution, Message, Session,
                    AuditRecord, Approval, Feedback,
                    User, KnowledgeArticle, Server,
                ]
                for table in tables_to_clear:
                    await db.execute(sa_delete(table))
                await db.commit()
                logger.info("All tables cleared for fresh start")

                # 创建默认用户
                db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin"))
                db.add(User(username="ty", password_hash=hash_password("ty666"), role="user"))
                await db.commit()
                logger.info("Seed users created: admin, ty")

            except Exception as e:
                logger.error(f"Failed to initialize: {e}")
                raise

            # 写入标记文件（必须在所有初始化成功后）
            _mark_initialized()
            logger.info("Initialization complete ✓")

        # 每次启动都执行：确保知识库和服务器数据完整
        await seed_knowledge(db)

        knowledge_count = (await db.execute(
            select(func.count()).select_from(KnowledgeArticle)
        )).scalar() or 0

        result = await db.execute(select(Server))
        servers = result.scalars().all()

        from app.services.server_user_policy import is_restricted_ssh_user, default_ops_ssh_user
        from app.services.ssh_client import SSH_POOL

        ops_user = default_ops_ssh_user()
        legacy_users = {"root", "administrator", "test"}
        migrated = False
        for s in servers:
            uname = (s.username or "").strip().lower()
            if is_restricted_ssh_user(s.username) or (uname in legacy_users and uname != ops_user.lower()):
                s.username = ops_user
                migrated = True
        if migrated:
            await db.commit()
            SSH_POOL.close_all()
            logger.info("Migrated SSH users to %s", ops_user)
            result = await db.execute(select(Server))
            servers = result.scalars().all()

        if not servers:
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
            logger.info("Default server seeded")
        
        logger.info(f"✓ System ready — Knowledge: {knowledge_count} articles, Servers: {len(servers)}")


@app.on_event("shutdown")
async def shutdown():
    from app.services.ssh_client import SSH_POOL
    SSH_POOL.close_all()
    await close_db()
    logger.info("KylinOps shut down")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",  # 允许所有 HTTP/HTTPS 来源（局域网 + 本地 + 远程）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(approval.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(servers.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(trace_outcome.router, prefix="/api/v1")
# app.include_router(mcp_router)

from app.services.feedback_upload import feedback_upload_dir as _feedback_upload_dir
from app.services.image_store import chat_upload_dir as _chat_upload_dir
from app.services.multimodal_assets import generated_asset_dir as _generated_asset_dir

_fb_upload_path = _feedback_upload_dir()
if _fb_upload_path.is_dir():
    app.mount(
        "/api/v1/feedback/files",
        StaticFiles(directory=str(_fb_upload_path)),
        name="feedback_files",
    )

_chat_upload_path = _chat_upload_dir()
if _chat_upload_path.is_dir():
    app.mount(
        "/api/v1/chat/files",
        StaticFiles(directory=str(_chat_upload_path)),
        name="chat_files",
    )

_generated_asset_path = _generated_asset_dir()
if _generated_asset_path.is_dir():
    app.mount(
        "/api/v1/chat/generated",
        StaticFiles(directory=str(_generated_asset_path)),
        name="chat_generated_assets",
    )

if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.dev_mode,
    )
