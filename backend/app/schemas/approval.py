from pydantic import BaseModel


class ApprovalRequest(BaseModel):
    action: str
    reason: str


class ApprovalResponse(BaseModel):
    approved: bool
    message: str
