from pydantic import BaseModel


class AuditItem(BaseModel):
    traceId: str
    event: str
    detail: str
    createdAt: str


class AuditListResponse(BaseModel):
    items: list[AuditItem]
