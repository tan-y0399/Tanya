from fastapi import FastAPI

from app.api.approval import router as approval_router
from app.api.audit import router as audit_router
from app.api.chat import router as chat_router
from app.api.session import router as session_router
from app.core.database import Base, engine
from app.models.audit import AuditLog
from app.models.message import Message
from app.models.session import Session

app = FastAPI(title='麒麟智能运维 Agent API', version='0.1.0')
app.include_router(chat_router)
app.include_router(session_router)
app.include_router(approval_router)
app.include_router(audit_router)


@app.on_event('startup')
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/api/info')
def app_info() -> dict[str, str]:
    return {
        'name': '麒麟智能运维 Agent API',
        'version': '0.1.0',
        'message': 'backend skeleton is ready',
    }
