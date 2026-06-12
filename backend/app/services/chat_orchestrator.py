"""
统一聊天编排入口 — 分阶段人类监督流程

默认使用 LangGraph 图；审批恢复仍走 chat_service.resume_after_approval。
"""
import json
import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.trace import generate_trace_id
from app.services.human_supervision import validate_user_input, save_supervision_plan

logger = logging.getLogger(__name__)


async def _persist_approval_from_tool(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    tool_payload: dict,
    messages_snapshot: list,
) -> Optional[str]:
    """LangGraph 路径：将 need_approval 写入 DB（与 chat_service 一致）。"""
    from datetime import datetime, timedelta
    from app.models.approval import Approval
    from app.services.chat_service import _save_pending_execution, _build_risk_description, get_tool_risk_level

    tool_name = tool_payload.get("toolName", "")
    tool_args = tool_payload.get("params", {})
    risk = tool_payload.get("riskLevel") or get_tool_risk_level(tool_name, tool_args)
    now = datetime.utcnow()
    approval = Approval(
        trace_id=trace_id,
        session_id=session_id,
        tool_name=tool_name,
        tool_params_json=json.dumps(tool_args, ensure_ascii=False),
        risk_level=risk,
        detail=_build_risk_description(tool_name, tool_args, risk),
        requested_by=user_id,
        expires_at=now + timedelta(seconds=settings.approval_timeout),
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    await _save_pending_execution(
        db, session_id, trace_id, user_id,
        tool_name, tool_args, risk,
        messages_snapshot=messages_snapshot or [],
        need_approval=True,
        approval_id=approval.id,
    )
    return approval.id


async def process_chat_message(
    db: AsyncSession,
    session_id: str,
    content: str,
    user_id: str,
    user_role: str = "user",
    confirm_plan_id: str = None,
    server_id: str = None,
    client_ip: str = None,
    use_langgraph: bool = True,
) -> AsyncGenerator[dict, None]:
    """
    统一 SSE 事件流。
    use_langgraph=False 时回退 chat_service.process_message（兼容）。
    """
    if not use_langgraph:
        from app.services import chat_service
        async for ev in chat_service.process_message(
            db, session_id, content, user_id,
            user_role=user_role,
            confirm_plan_id=confirm_plan_id,
            server_id=server_id,
        ):
            yield ev
        return

    from app.services.chat_service import save_message, get_messages
    from app.langgraph_agent.service import process_with_langgraph

    pre = validate_user_input(content)
    def _out(event: str, data: dict):
        return {"event": event, "data": json.dumps(data, ensure_ascii=False)}

    if not pre["valid"]:
        yield _out("error", {"message": pre["message"], "code": pre["code"]})
        yield _out("message_done", {"status": "validation_failed"})
        return

    content = pre["sanitized"]
    trace_id = generate_trace_id()

    if not confirm_plan_id:
        await save_message(db, session_id, "user", content, trace_id=trace_id)

    history_data = await get_messages(db, session_id)
    dialog_history = history_data.get("items", [])

    last_state = None
    assistant_msg_id = None

    async for event in process_with_langgraph(
        user_input=content,
        user_id=user_id,
        session_id=session_id,
        trace_id=trace_id,
        dialog_history=dialog_history,
        user_role=user_role,
        confirm_plan_id=confirm_plan_id,
        server_id=server_id,
        client_ip=client_ip,
    ):
        ev_name = event.get("event")
        data_raw = event.get("data", "{}")
        try:
            data = json.loads(data_raw) if isinstance(data_raw, str) else data_raw
        except Exception:
            data = {}

        if ev_name == "message_start":
            assistant_msg_id = data.get("messageId") or data.get("message_id") or trace_id

        if ev_name == "need_approval" and db:
            aid = await _persist_approval_from_tool(
                db, session_id, trace_id, user_id, data, [],
            )
            if aid:
                data["approvalId"] = aid

        if ev_name == "diagnostic_plan" and db and data.get("plan"):
            sp = await save_supervision_plan(
                db, session_id, trace_id, user_id,
                data.get("plan", {}).get("intent", "fault_analysis"),
                data["plan"],
            )
            data["planId"] = sp.id

        if ev_name == "message_done":
            last_state = data

        yield _out(ev_name, data)

    # 持久化助手消息
    if last_state and assistant_msg_id:
        final_text = last_state.get("final_response", "")
        if not final_text and last_state.get("status") == "awaiting_plan_confirm":
            final_text = "已生成运维诊断方案，请在下方确认后开始执行。"
        if final_text:
            await save_message(db, session_id, "assistant", final_text, trace_id=trace_id)
