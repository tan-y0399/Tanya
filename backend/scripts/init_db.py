from datetime import datetime

from app.core.database import Base, SessionLocal, engine
from app.models.audit import AuditRecord
from app.models.session import Message, Session


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        existing = db.query(Session).filter(Session.id == 'demo-session').first()
        if existing is None:
            db.add(Session(id='demo-session', user_id='demo-user', title='磁盘检查会话', updated_at=now))
            db.add(Session(id='demo-session-2', user_id='demo-user', title='日志分析会话', updated_at=now))
            db.add(Message(session_id='demo-session', role='user', content='帮我查看当前系统磁盘占用情况。', created_at=now))
            db.add(Message(session_id='demo-session', role='agent', content='已识别为只读查询任务，正在调用系统信息工具。', created_at=now))
            db.add(AuditRecord(trace_id='trace-demo-0001', session_id='demo-session',
                user_id='demo-user', event_type='bootstrap',
                summary='初始化演示数据', risk_level='L1'))
        db.commit()
        print('database initialized successfully')
    except Exception as exc:
        db.rollback()
        raise SystemExit('failed to initialize database: {}'.format(exc))
    finally:
        db.close()


if __name__ == '__main__':
    main()
