from datetime import datetime

from app.core.database import Base, SessionLocal, engine
from app.models.audit import AuditLog
from app.models.message import Message
from app.models.session import Session


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        existing = db.query(Session).filter(Session.session_id == 'demo-session').first()
        if existing is None:
            db.add(Session(session_id='demo-session', title='磁盘检查会话', updated_at=now))
            db.add(Session(session_id='demo-session-2', title='日志分析会话', updated_at=now))
            db.add(Message(session_id='demo-session', role='user', content='帮我查看当前系统磁盘占用情况。', created_at=now))
            db.add(Message(session_id='demo-session', role='agent', content='已识别为只读查询任务，正在调用系统信息工具。', created_at=now))
            db.add(AuditLog(trace_id='trace-demo-0001', event='bootstrap', detail='初始化演示数据', created_at=now))
        db.commit()
        print('database initialized successfully')
    except Exception as exc:
        db.rollback()
        raise SystemExit(f'failed to initialize database: {exc}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
