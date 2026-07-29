import json
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
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


@router.get("/sessions/{session_id}/awaiting-run")
async def list_awaiting_run(session_id: str,
                            user: dict = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db)):
    """L2 待确认 / L4 已批准待执行的挂起操作（刷新页面后恢复）"""
    data = await chat_service.get_awaiting_run(db, session_id)
    return {"code": 0, "data": data}


@router.get("/sessions/{session_id}/pending-plan")
async def get_pending_plan(session_id: str,
                           user: dict = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    """待确认的诊断方案（刷新页面后恢复）"""
    data = await chat_service.get_pending_diagnostic_plan(db, session_id)
    return {"code": 0, "data": data}


@router.post("/sessions/{session_id}/cancel-run")
async def cancel_awaiting_run(session_id: str, req: dict = Body(...),
                              user: dict = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    """用户跳过/取消已批准但未执行的操作"""
    ok = await chat_service.cancel_awaiting_run(
        db, session_id,
        approval_id=req.get("approvalId") or None,
        pending_execution_id=req.get("pendingExecutionId") or None,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="未找到可取消的待执行操作")
    return {"code": 0, "message": "已取消执行"}


@router.get("/sessions/{session_id}/rollback-status")
async def rollback_status(session_id: str,
                          user: dict = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    """查询会话内各工具调用的可回滚状态。"""
    from app.services.human_supervision import get_session_rollback_status

    data = await get_session_rollback_status(db, session_id)
    return {"code": 0, "data": data}


@router.post("/sessions/{session_id}/rollback")
async def rollback_session(session_id: str, req: dict = Body(...),
                           user: dict = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    """阶段3子步骤4：单步/全量回滚（L3 级操作，需用户明确发起）。"""
    from app.services.human_supervision import run_session_rollback

    mode = req.get("mode", "single_step")
    if mode not in ("single_step", "full"):
        raise HTTPException(status_code=400, detail="mode 须为 single_step 或 full")
    result = await run_session_rollback(
        db, session_id, user["id"],
        mode=mode,
        log_id=(req.get("logId") or "").strip() or None,
        tool_call_id=(req.get("toolCallId") or "").strip() or None,
    )
    if not result.get("ok") and mode == "single_step":
        raise HTTPException(status_code=400, detail=result.get("message", "回滚失败"))
    return {"code": 0, "data": result}


@router.get("/checkpoints/{checkpoint_id}")
async def get_checkpoint(checkpoint_id: str,
                         user: dict = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    """查询断点续传检查点。"""
    from app.services.agent.checkpoint_manager import CheckpointManager
    data = await CheckpointManager.load(db, checkpoint_id)
    if not data or data.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="检查点不存在")
    return {"code": 0, "data": data}


@router.post("/tts")
async def text_to_speech(req: dict = Body(...),
                         user: dict = Depends(get_current_user)):
    """Generate speech audio for an assistant answer."""
    from app.services.multimodal_assets import synthesize_tts

    text = (req.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    data = await synthesize_tts(
        text,
        voice=(req.get("voice") or getattr(settings, "tts_voice", "Cherry")),
        speed=float(req.get("speed") or 1.0),
    )
    return {"code": 0, "data": data}


@router.post("/sessions/{session_id}/checkpoints")
async def save_checkpoint(session_id: str, req: dict = Body(...),
                          user: dict = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    """保存执行断点（网络中断/流程挂起时）。"""
    from app.services.agent.checkpoint_manager import CheckpointManager
    payload = req.get("payload") or req
    trace_id = req.get("traceId") or payload.get("trace_id") or ""
    ckpt_id = await CheckpointManager.save(
        db, session_id, trace_id, user["id"], payload,
        status=req.get("status", "interrupted"),
    )
    return {"code": 0, "data": {"checkpointId": ckpt_id}}


@router.post("/checkpoints/{checkpoint_id}/resume")
async def resume_checkpoint(checkpoint_id: str,
                            user: dict = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db)):
    """恢复断点续传状态。"""
    from app.services.agent.checkpoint_manager import CheckpointManager
    data = await CheckpointManager.resume(db, checkpoint_id)
    if not data or data.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="检查点不存在或无权访问")
    return {"code": 0, "data": data}


@router.post("/sessions/{session_id}/continue-plan")
async def continue_plan_execution(
    session_id: str,
    req: dict = Body(default={}),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """方案执行卡壳时续跑下一步（SSE）。"""
    server_id = req.get("serverId", "") if req else ""

    async def event_stream():
        try:
            async for event in chat_service.stream_continue_plan_execution(
                db, session_id, user["id"], server_id=server_id or None,
            ):
                yield f"event: {event['event']}\ndata: {event['data']}\n\n"
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("continue-plan failed")
            yield f"event: error\ndata: {json.dumps({'message': str(e)[:200]})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/approval-rejected")
async def session_approval_rejected(
    session_id: str,
    req: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员拒绝/超时后，补全工具卡状态与 Agent 执行结论。"""
    approval_id = (req.get("approvalId") or "").strip()
    if not approval_id:
        raise HTTPException(status_code=400, detail="缺少 approvalId")

    async def event_stream():
        try:
            async for event in chat_service.stream_approval_rejection_finalize(
                db, session_id, approval_id,
            ):
                yield f"event: {event['event']}\ndata: {event['data']}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)[:200]})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/send")
async def send_message(req: dict = Body(...),
                       user: dict = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    from app.services.human_supervision import validate_user_input

    session_id = req.get("sessionId", "")
    content = req.get("content", "") or ""
    thinking_mode = (req.get("thinkingMode") or "fast").strip().lower()
    attachments = req.get("attachments") or []
    deep_intent_choice = (req.get("deepIntentChoice") or "").strip()
    pending_approval_id = req.get("pendingApprovalId", "")
    pending_execution_id = req.get("pendingExecutionId", "")
    confirm_plan_id = req.get("confirmPlanId", "")
    server_id = req.get("serverId", "")

    if attachments and not content.strip():
        content = "请分析我上传的图片"

    if not pending_approval_id and not pending_execution_id and not confirm_plan_id:
        pre = validate_user_input(content)
        if not pre["valid"]:
            raise HTTPException(status_code=400, detail=pre["message"])
        content = pre["sanitized"]

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
                if (
                    getattr(settings, "enable_multimodal_agent", True)
                    and thinking_mode == "deep"
                    and not confirm_plan_id
                ):
                    from app.services.multimodal_agent.service import process_multimodal_message
                    async for event in process_multimodal_message(
                        db, session_id, content, user["id"],
                        user_role=user.get("role", "user"),
                        server_id=server_id or None,
                        attachments=attachments,
                        intent_choice=deep_intent_choice or None,
                    ):
                        yield f"event: {event['event']}\ndata: {event['data']}\n\n"
                    return

                if getattr(settings, "use_langgraph_orchestrator", False):
                    from app.services.chat_orchestrator import process_chat_message
                    stream_fn = process_chat_message
                else:
                    stream_fn = chat_service.process_message

                async for event in stream_fn(
                    db, session_id, content, user["id"],
                    user_role=user.get("role", "user"),
                    confirm_plan_id=confirm_plan_id or None,
                    server_id=server_id or None,
                ):
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
