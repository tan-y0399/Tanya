from sqlalchemy.orm import Session as DbSession

from app.models.audit import AuditLog
from app.models.message import Message
from app.models.session import Session


class Repository:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def upsert_session(self, session_id: str, title: str, updated_at: str) -> None:
        record = self.db.query(Session).filter(Session.session_id == session_id).first()
        if record is None:
            record = Session(session_id=session_id, title=title, updated_at=updated_at)
            self.db.add(record)
        else:
            record.title = title
            record.updated_at = updated_at

    def add_message(self, session_id: str, role: str, content: str, created_at: str) -> None:
        self.db.add(Message(session_id=session_id, role=role, content=content, created_at=created_at))

    def add_audit(self, trace_id: str, event: str, detail: str, created_at: str) -> None:
        self.db.add(AuditLog(trace_id=trace_id, event=event, detail=detail, created_at=created_at))
