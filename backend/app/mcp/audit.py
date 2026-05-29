from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditRecord

AUDIT_LOGS: List[Dict[str, Any]] = []


def record_mcp_event(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    AUDIT_LOGS.append(entry)
    return entry


def list_mcp_events(limit: int = 200) -> List[Dict[str, Any]]:
    return AUDIT_LOGS[-limit:]


async def persist_mcp_event(
    db: AsyncSession,
    *,
    trace_id: str,
    session_id: Optional[str],
    user_id: str,
    event_type: str,
    summary: str = "",
    risk_level: Optional[str] = None,
    detail_json: Optional[Dict[str, Any]] = None,
) -> AuditRecord:
    record = AuditRecord(
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
        event_type=event_type,
        summary=summary,
        risk_level=risk_level,
        detail_json=json.dumps(detail_json, ensure_ascii=False) if detail_json is not None else None,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record
