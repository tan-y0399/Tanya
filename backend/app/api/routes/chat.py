import json
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["对话"])


@router.get("/sessions")
async def list_sessions(page: int = 1, size: int = 20,
                       user: dict = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    data = await chat_service.get_sessions(db, user["id"], page, size)
    return {"code": 0, "data": data}


@router.post("/sessions")
async def new_session(req: dict = Body(...),
                      user: dict = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db)):
    title = req.get("title", "新会话")
    data = await chat_service.create_session(db, user["id"], title)
    return {"code": 0, "data": data}


@router.delete("/sessions/{session_id}")
async def remove_session(session_id: str,
                         user: dict = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    await chat_service.delete_session(db, session_id)
    return {"code": 0, "message": "删除成功"}


@router.delete("/sessions/{session_id}/messages")
async def clear_session_messages(session_id: str,
                                  user: dict = Depends(get_current_user),
                                  db: AsyncSession = Depends(get_db)):
    await chat_service.clear_session_messages(db, session_id)
    return {"code": 0, "message": "清空成功"}


@router.delete("/messages/{message_id}")
async def remove_message(message_id: str,
                          user: dict = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    await chat_service.delete_message(db, message_id)
    return {"code": 0, "message": "删除成功"}


@router.get("/sessions/{session_id}/messages")
async def list_messages(session_id: str, page: int = 1, size: int = 50,
                        user: dict = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    data = await chat_service.get_messages(db, session_id, page, size)
    return {"code": 0, "data": data}


@router.post("/send")
async def send_message(req: dict = Body(...),
                       user: dict = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    session_id = req.get("sessionId", "")
    content = req.get("content", "")
    pending_approval_id = req.get("pendingApprovalId", "")
    pending_execution_id = req.get("pendingExecutionId", "")

    async def event_stream():
        try:
            if pending_approval_id or pending_execution_id:
                async for event in chat_service.resume_after_approval(
                    db, session_id, user["id"],
                    approval_id=pending_approval_id or None,
                    pending_execution_id=pending_execution_id or None,
                ):
                    yield f"event: {event['event']}\ndata: {event['data']}\n\n"
            else:
                async for event in chat_service.process_message(db, session_id, content, user["id"]):
                    yield f"event: {event['event']}\ndata: {event['data']}\n\n"
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("SSE stream fatal error")
            err_data = json.dumps({
                "messageId": "err-{}".format(__import__('uuid').uuid4().hex[:8]),
                "traceId": "",
                "status": "error",
                "error": str(e)[:200],
            })
            yield "event: message_done\ndata: {}\n\n".format(err_data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

