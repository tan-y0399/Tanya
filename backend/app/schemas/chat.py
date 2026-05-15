from pydantic import BaseModel


class ChatRequest(BaseModel):
    sessionId: str
    message: str


class ToolCallItem(BaseModel):
    name: str
    status: str
    description: str | None = None


class ChatResponse(BaseModel):
    reply: str
    traceId: str
    toolCalls: list[ToolCallItem]
