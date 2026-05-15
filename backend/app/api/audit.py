from fastapi import APIRouter

from app.core.database import SessionLocal
from app.models.audit import AuditLog
from app.schemas.audit import AuditItem, AuditListResponse

router = APIRouter(prefix='/api', tags=['audit'])


@router.get('/audits', response_model=AuditListResponse)
def list_audits() -> AuditListResponse:
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).order_by(AuditLog.id.desc()).all()
        return AuditListResponse(
            items=[
                AuditItem(traceId=row.trace_id, event=row.event, detail=row.detail, createdAt=row.created_at)
                for row in rows
            ]
        )
    finally:
        db.close()
