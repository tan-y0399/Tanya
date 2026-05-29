from datetime import datetime

from fastapi import APIRouter

from app.core.database import SessionLocal
from app.models.session import Message, Session
from app.schemas.session import (
    MessageItem,
    MessageListResponse,
    SessionCreateRequest,
    SessionItem,
    SessionListResponse,
)

router = APIRouter(prefix='/api', tags=['session'])


@router.get('/sessions', response_model=SessionListResponse)
def list_sessions() -> SessionListResponse:
    db = SessionLocal()
    try:
        rows = db.query(Session).order_by(Session.id.desc()).all()
        return SessionListResponse(
            items=[
                SessionItem(sessionId=row.session_id, title=row.title, updatedAt=row.updated_at)
                for row in rows
            ]
        )
    finally:
        db.close()


@router.post('/sessions', response_model=SessionItem)
def create_session(payload: SessionCreateRequest) -> SessionItem:
    db = SessionLocal()
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        session_id = f'session-{int(datetime.now().timestamp())}'
        record = Session(session_id=session_id, title=payload.title, updated_at=now)
        db.add(record)
        db.commit()
        return SessionItem(sessionId=session_id, title=payload.title, updatedAt=now)
    finally:
        db.close()


@router.get('/sessions/{session_id}/messages', response_model=MessageListResponse)
def list_messages(session_id: str) -> MessageListResponse:
    db = SessionLocal()
    try:
        rows = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id.asc()).all()
        return MessageListResponse(
            items=[
                MessageItem(id=str(row.id), role=row.role, content=row.content, createdAt=row.created_at)
                for row in rows
            ]
        )
    finally:
        db.close()
