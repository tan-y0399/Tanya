from datetime import datetime

from app.core.database import SessionLocal
from app.services.deepseek import DeepSeekAgent
from app.services.repository import Repository


class ChatService:
    def __init__(self) -> None:
        self.agent = DeepSeekAgent()

    def chat(self, session_id: str, message: str) -> tuple[str, list[dict[str, str]]]:
        reply = self.agent.chat(message)
        plans = self.agent.plan(message)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db = SessionLocal()
        try:
            repo = Repository(db)
            repo.upsert_session(session_id, '麒麟智能运维会话', now)
            repo.add_message(session_id, 'user', message, now)
            repo.add_message(session_id, 'agent', reply, now)
            repo.add_audit('trace-demo-0001', 'chat', 'chat completed', now)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return reply, plans
