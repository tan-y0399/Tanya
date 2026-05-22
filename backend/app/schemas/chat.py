from typing import Optional
from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    title: str = "新会话"


class SendMessageRequest(BaseModel):
    sessionId: str
    content: str


class SessionItem(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messageCount: int


class ToolCallInfo(BaseModel):
    id: str
    toolName: str
    params: dict
    riskLevel: Optional[str] = None


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    toolCalls: Optional[list] = None
    traceId: Optional[str] = None
    createdAt: str
