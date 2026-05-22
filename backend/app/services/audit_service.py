import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import desc
from app.models.audit import AuditRecord


async def create_audit_record(db: AsyncSession, **kwargs) -> AuditRecord:
    detail = kwargs.pop("detail", None)
    record = AuditRecord(**kwargs)
    if detail:
        record.detail_json = json.dumps(detail, ensure_ascii=False)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_audit_records(
    db: AsyncSession, page: int = 1, size: int = 20,
    user_id: Optional[str] = None, event_type: Optional[str] = None,
    risk_level: Optional[str] = None, start_time: Optional[str] = None,
    end_time: Optional[str] = None, trace_id: Optional[str] = None,
) -> dict:
    q = select(AuditRecord).order_by(desc(AuditRecord.timestamp))
    conditions = []

    if user_id:
        conditions.append(AuditRecord.user_id == user_id)
    if event_type:
        conditions.append(AuditRecord.event_type == event_type)
    if risk_level:
        conditions.append(AuditRecord.risk_level == risk_level)
    if trace_id:
        conditions.append(AuditRecord.trace_id == trace_id)
    if start_time:
        conditions.append(AuditRecord.timestamp >= start_time)
    if end_time:
        conditions.append(AuditRecord.timestamp <= end_time)

    if conditions:
        q = q.where(*conditions)
        total_result = await db.execute(select(func.count()).select_from(AuditRecord).where(*conditions))
    else:
        total_result = await db.execute(select(func.count()).select_from(AuditRecord))
    total = total_result.scalar() or 0

    rows_result = await db.execute(q.offset((page - 1) * size).limit(size))
    rows = rows_result.scalars().all()

    items = []
    for r in rows:
        items.append({
            "id": r.id, "traceId": r.trace_id, "userId": r.user_id,
            "eventType": r.event_type, "summary": r.summary,
            "riskLevel": r.risk_level,
            "timestamp": r.timestamp.isoformat() if r.timestamp else "",
        })
    return {"items": items, "total": total, "page": page, "size": size}


async def get_audit_detail(db: AsyncSession, trace_id: str) -> Optional[dict]:
    q = select(AuditRecord).where(AuditRecord.trace_id == trace_id).order_by(AuditRecord.timestamp)
    result = await db.execute(q)
    rows = result.scalars().all()
    if not rows:
        return None

    events = []
    for i, r in enumerate(rows):
        detail = None
        if r.detail_json:
            try:
                detail = json.loads(r.detail_json)
            except Exception:
                detail = r.detail_json

        events.append({
            "sequence": i + 1,
            "timestamp": r.timestamp.isoformat() if r.timestamp else "",
            "eventType": r.event_type,
            "data": detail or {},
        })

    return {
        "traceId": trace_id,
        "sessionId": rows[0].session_id if rows else None,
        "events": events,
    }
