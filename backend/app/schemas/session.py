from pydantic import BaseModel


class SessionItem(BaseModel):
    sessionId: str
    title: str
    updatedAt: str


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    createdAt: str


class SessionCreateRequest(BaseModel):
    title: str


class SessionListResponse(BaseModel):
    items: list[SessionItem]


class MessageListResponse(BaseModel):
    items: list[MessageItem]
