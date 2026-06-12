from typing import Optional
from pydantic import BaseModel


class ApprovalItem(BaseModel):
    id: str
    traceId: str
    sessionId: Optional[str] = None
    toolName: str
    toolParams: Optional[dict] = None
    riskLevel: str
    detail: str
    requestedBy: str
    requestedAt: str
    expiresAt: Optional[str] = None
    status: Optional[str] = None
    result: Optional[str] = None


class ApproveRequest(BaseModel):
    comment: str = ""


class RejectRequest(BaseModel):
    reason: str = ""


class UpdateApprovalRequest(BaseModel):
    detail: Optional[str] = None
    comment: Optional[str] = None
    riskLevel: Optional[str] = None
