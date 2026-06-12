from typing import Optional
from pydantic import BaseModel


class AuditRecordItem(BaseModel):
    id: str
    traceId: str
    userId: str
    eventType: str
    summary: str
    riskLevel: Optional[str] = None
    exitCode: Optional[int] = None
    timestamp: str
