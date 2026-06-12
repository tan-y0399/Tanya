from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse, ToolCallItem
from app.services.chat_service import ChatService

router = APIRouter(prefix='/api', tags=['chat'])
service = ChatService()


@router.post('/chat', response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    reply, plans = service.chat(payload.sessionId, payload.message)
    return ChatResponse(
        reply=reply,
        traceId='trace-demo-0001',
        toolCalls=[ToolCallItem(**item) for item in plans],
    )
