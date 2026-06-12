"""
任务路由器 —— 意图 → Handler 分发中心。

每个 Handler 是独立的异步生成器，产出标准 SSE 事件流。
统一接口: async def handle(db, session_id, content, user_id, messages, **ctx) -> AsyncGenerator
"""

import json
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.intent_classifier import IntentType, classify as classify_intent, get_intent_metadata
from app.services.tool_definitions import (
    TOOLS, SYSTEM_PROMPT, KNOWLEDGE_SYSTEM_PROMPT, OUT_OF_SCOPE_PROMPT,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# SSE 事件辅助
# ═══════════════════════════════════════════
def _sse(event: str, data: Any) -> dict:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False, default=str)}


def _generate_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


# ═══════════════════════════════════════════
# Handler 基类
# ═══════════════════════════════════════════
class BaseHandler:
    intent_type: IntentType = IntentType.GENERAL_QA

    async def handle(
        self, db, session_id, content, user_id, messages,
        trace_id="", assistant_msg_id="", intent_result=None, rag_context="", **ctx,
    ) -> AsyncGenerator[dict, None]:
        raise NotImplementedError

    async def _stream_llm(self, messages_chat: List[Dict], use_tools: bool = False):
        """调用 LLM 流式接口；知识/闲聊路径必须 use_tools=False。"""
        from app.services.chat_service import call_deepseek
        current_tool_calls = []
        current_content = ""

        async for chunk in call_deepseek(messages_chat, stream=True, use_tools=use_tools):
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {})

            if "content" in delta and delta["content"]:
                current_content += delta["content"]
                yield _sse("token", {"token": delta["content"]})

            if "tool_calls" in delta:
                for tc_delta in delta["tool_calls"]:
                    idx = tc_delta.get("index", 0)
                    while len(current_tool_calls) <= idx:
                        current_tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                    tc = current_tool_calls[idx]
                    if "id" in tc_delta:
                        tc["id"] = tc_delta["id"]
                    if "function" in tc_delta:
                        fn = tc_delta["function"]
                        if "name" in fn:
                            tc["function"]["name"] = fn["name"]
                        if "arguments" in fn:
                            tc["function"]["arguments"] += fn["arguments"]

        yield {"__stream_done__": True, "content": current_content, "tool_calls": current_tool_calls}

    async def _execute_tool_safe(self, tool_name: str, tool_args: dict) -> dict:
        from app.services.chat_service import execute_tool
        try:
            return execute_tool(tool_name, tool_args)
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _save_audit(
        self,
        db,
        trace_id,
        session_id,
        user_id,
        content,
        full_response,
        tool_records,
        intent_result=None,
        telemetry=None,
    ):
        try:
            from app.services.audit_service import upsert_chat_audit_record
            intent = (intent_result or {}).get("intent") or self.intent_type.value
            conf = float((intent_result or {}).get("confidence", 0) or 0)
            await upsert_chat_audit_record(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                question=content,
                answer=full_response or "",
                tool_call_records=tool_records or [],
                telemetry=telemetry,
                intent=intent,
                intent_confidence=conf or None,
                flow_status="completed",
            )
        except Exception:
            pass


# ═══════════════════════════════════════════
# 1. GENERAL_QA — 通用对话（无工具，不检索）
# ═══════════════════════════════════════════
class GeneralChatHandler(BaseHandler):
    intent_type = IntentType.GENERAL_QA

    async def handle(self, db, session_id, content, user_id, messages, trace_id="",
                     assistant_msg_id="", intent_result=None, rag_context="", **ctx):
        from app.services.chat_service import save_message

        intent_result = intent_result or {}
        from app.services.ops_scope import (
            is_service_control_request,
            is_disk_cleanup_execution_request,
            react_execution_redirect_message,
            response_claims_fake_execution,
        )
        redirect = react_execution_redirect_message(content)
        if redirect and (is_service_control_request(content) or is_disk_cleanup_execution_request(content)):
            yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id})
            yield _sse("token", {"token": redirect, "phase": "answer"})
            await save_message(db, session_id, "assistant", redirect, trace_id=trace_id)
            yield _sse("message_done", {
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "redirect_react",
            })
            return

        if intent_result.get("out_of_scope"):
            from app.services.ops_scope import build_out_of_scope_refusal
            yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id})
            refusal = build_out_of_scope_refusal()
            yield _sse("token", {"token": refusal, "phase": "answer"})
            await save_message(db, session_id, "assistant", refusal, trace_id=trace_id)
            yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id, "status": "out_of_scope"})
            return

        from app.services.agent_intent_context import build_intent_system_addon
        system_msg = {"role": "system", "content": SYSTEM_PROMPT + build_intent_system_addon(
            intent_result or {"intent": self.intent_type.value}, content)}
        chat_messages = [system_msg] + [
            {"role": m["role"], "content": m["content"]}
            for m in messages if m["role"] in ("user", "assistant")
        ]

        yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id})

        full_response = ""
        async for event in self._stream_llm(chat_messages, use_tools=False):
            if isinstance(event, dict) and event.get("__stream_done__"):
                full_response = event.get("content", "") or ""
                break
            yield event

        if response_claims_fake_execution(full_response):
            full_response = (
                "⚠️ **说明**：上述清理操作尚未在服务器上执行（当前为普通问答模式，未调用 SSH 工具）。\n\n"
                + react_execution_redirect_message(content)
                + "\n\n请重新发送您的清理需求，系统将自动转入运维执行链路，"
                "并按 L2/L3 确认或 L4 审批后才会真正运行命令。"
            )

        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        await self._save_audit(db, trace_id, session_id, user_id, content, full_response, [], intent_result=intent_result, telemetry=ctx.get("telemetry"))

        yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id,
                                     "status": "completed", "usage": {"outputTokens": len(full_response)}})


# ═══════════════════════════════════════════
# 2. KNOWLEDGE_QA — 知识库问答（RAG + LLM）
# ═══════════════════════════════════════════
class KnowledgeQAHandler(BaseHandler):
    intent_type = IntentType.KNOWLEDGE_QA

    async def handle(self, db, session_id, content, user_id, messages, trace_id="",
                     assistant_msg_id="", intent_result=None, rag_context="", **ctx):
        from app.services.chat_service import save_message
        from app.services.ops_scope import (
            is_disk_cleanup_execution_request,
            is_service_control_request,
            react_execution_redirect_message,
            response_claims_fake_execution,
        )

        redirect = react_execution_redirect_message(content)
        if redirect and (is_service_control_request(content) or is_disk_cleanup_execution_request(content)):
            yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id})
            yield _sse("token", {"token": redirect, "phase": "answer"})
            await save_message(db, session_id, "assistant", redirect, trace_id=trace_id)
            yield _sse("message_done", {
                "messageId": assistant_msg_id, "traceId": trace_id, "status": "redirect_react",
            })
            return

        # 构建 RAG 上下文
        if not rag_context:
            try:
                from app.services.knowledge_rag import knowledge_rag
                from app.models.knowledge import KnowledgeArticle
                if not knowledge_rag._initialized:
                    result = await db.execute(select(KnowledgeArticle))
                    articles = [{"id": a.id, "title": a.title, "content": a.content,
                                 "category": a.category, "tags": a.tags} for a in result.scalars().all()]
                    knowledge_rag.build_index(articles)
                rag_context = knowledge_rag.generate_context(content, top_k=3)
                if rag_context:
                    sources = [s["title"] for s in knowledge_rag.search(content, top_k=3)]
                    yield _sse("rag_context", {"sources": sources})
            except Exception as e:
                logger.warning(f"RAG failed: {e}")

        from app.services.agent_intent_context import build_intent_system_addon
        system_prompt = KNOWLEDGE_SYSTEM_PROMPT + build_intent_system_addon(
            intent_result or {"intent": self.intent_type.value}, content)
        rag_sources = []
        if rag_context:
            try:
                from app.services.knowledge_rag import knowledge_rag
                rag_sources = [s.get("title", "") for s in knowledge_rag.search(content, top_k=3)]
            except Exception:
                pass
            system_prompt += "\n\n## 知识库参考\n" + rag_context
            system_prompt += (
                "\n\n**回答要求**：必须在文末列出「参考来源」并标注知识库条目；"
                "不得编造知识库中不存在的具体命令参数或版本号；无依据处请明确说明为通用实践。"
            )
        else:
            system_prompt += (
                "\n\n（知识库暂无匹配条目，请基于麒麟 V11 / Linux 运维通用最佳实践作答，"
                "仍须分步骤说明，勿调用工具；勿声称已执行任何命令。）"
            )
        chat_messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]}
            for m in messages if m["role"] in ("user", "assistant")
        ]

        yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id})
        yield _sse("response_phase", {"phase": "answer", "message": "正在组织运维知识回答…"})

        full_response = ""
        async for event in self._stream_llm(chat_messages, use_tools=False):
            if isinstance(event, dict) and event.get("__stream_done__"):
                full_response = event.get("content", "") or ""
                if event.get("tool_calls"):
                    logger.warning("knowledge_qa received tool_calls, ignored")
                break
            yield event

        if response_claims_fake_execution(full_response):
            full_response = (
                "⚠️ **说明**：清理/删除类命令尚未在服务器上执行（知识问答模式不会调用 SSH）。\n\n"
                + react_execution_redirect_message(content)
                + "\n\n请重新发送执行类请求，系统将逐条调用 `execute_command`，"
                "L2/L3 需您在对话页确认，L4 需管理员审批通过后再执行。"
            )

        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        await self._save_audit(db, trace_id, session_id, user_id, content, full_response, [], intent_result=intent_result, telemetry=ctx.get("telemetry"))

        yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id,
                                     "status": "completed", "mode": "knowledge"})


# ═══════════════════════════════════════════
# 3. OPS_QUERY — 运维查询（只读工具 + 编排器）
# ═══════════════════════════════════════════
class OpsQueryHandler(BaseHandler):
    intent_type = IntentType.OPS_QUERY

    async def handle(self, db, session_id, content, user_id, messages, trace_id="",
                     assistant_msg_id="", intent_result=None, rag_context="", **ctx):
        from app.services.chat_service import save_message, execute_tool, _check_tool_safety, get_tool_risk_level
        from app.services.task_orchestrator import TaskOrchestrator, TaskStage

        orchestrator = TaskOrchestrator(session_id=session_id, trace_id=trace_id, user_id=user_id)
        orchestrator.transition(TaskStage.PERCEIVING)
        yield _sse("task_progress", orchestrator.get_progress_event())

        chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
            {"role": m["role"], "content": m["content"]}
            for m in messages if m["role"] in ("user", "assistant")
        ]

        yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id})

        full_response = ""
        tool_call_records = []
        max_rounds = settings.max_conversation_rounds
        round_count = 0

        while round_count < max_rounds:
            round_count += 1
            current_content = ""
            tool_calls = []
            async for event in self._stream_llm(chat_messages):
                if isinstance(event, dict) and event.get("__stream_done__"):
                    current_content = event.get("content", "") or ""
                    tool_calls = event.get("tool_calls", [])
                    break
                yield event

            if not current_content and not tool_calls:
                # LLM 没有产生回答也没有工具调用
                break
            if isinstance(current_content, str):
                full_response = current_content

            if not tool_calls:
                break

            chat_messages.append({"role": "assistant", "content": current_content or None,
                                  "tool_calls": tool_calls})

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_call_id = tc.get("id", _generate_id())
                try:
                    tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                except json.JSONDecodeError:
                    tool_args = {}

                risk = get_tool_risk_level(tool_name, tool_args)
                safety = _check_tool_safety(tool_name, tool_args)

                if safety["blocked"]:
                    yield _sse("blocked", {
                        "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                        "riskLevel": safety["risk_level"], "message": safety["block_message"],
                        "status": "blocked",
                    })
                    tool_call_records.append({
                        "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                        "riskLevel": safety["risk_level"], "status": "blocked",
                        "result": {"success": False, "error": safety["block_message"]},
                    })
                    continue

                yield _sse("tool_call", {
                    "id": tool_call_id, "toolName": tool_name,
                    "params": tool_args, "riskLevel": risk, "status": "executing",
                })
                result = execute_tool(tool_name, tool_args)
                yield _sse("tool_result", {
                    "toolName": tool_name, "status": "completed", "result": result,
                })
                tool_call_records.append({
                    "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                    "riskLevel": risk, "status": "completed", "result": result,
                })
                chat_messages.append({
                    "role": "tool", "tool_call_id": tool_call_id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

                if orchestrator:
                    step = orchestrator.add_step(tool_name, tool_name, tool_args)
                    step.status = "completed" if result.get("success", False) else "failed"
                    step.result = result
                    if orchestrator.current_stage != TaskStage.EXECUTING:
                        orchestrator.transition(TaskStage.EXECUTING)
                    yield _sse("task_progress", orchestrator.get_progress_event())

        if orchestrator:
            orchestrator.transition(TaskStage.SUMMARIZING)
            orchestrator.complete()
            yield _sse("task_progress", orchestrator.get_progress_event())

        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        if tool_call_records:
            await save_message(db, session_id, "tool_call", "", tool_calls=tool_call_records, trace_id=trace_id)
        await self._save_audit(db, trace_id, session_id, user_id, content, full_response, tool_call_records, intent_result=intent_result, telemetry=ctx.get("telemetry"))

        yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id,
                                     "status": "completed"})


# ═══════════════════════════════════════════
# 4. FAULT_ANALYSIS — 故障分析（多步诊断 + 审批）
# ═══════════════════════════════════════════
class FaultAnalysisHandler(BaseHandler):
    intent_type = IntentType.FAULT_ANALYSIS

    async def handle(self, db, session_id, content, user_id, messages, trace_id="",
                     assistant_msg_id="", intent_result=None, rag_context="", **ctx):
        from app.services.chat_service import save_message, execute_tool, _check_tool_safety, get_tool_risk_level
        from app.services.task_orchestrator import TaskOrchestrator, TaskStage

        orchestrator = TaskOrchestrator(session_id=session_id, trace_id=trace_id, user_id=user_id)
        orchestrator.transition(TaskStage.PERCEIVING)
        yield _sse("task_progress", orchestrator.get_progress_event())

        # 搜索故障案例
        fault_rag = ""
        try:
            from app.services.knowledge_rag import knowledge_rag
            from app.models.knowledge import KnowledgeArticle
            if not knowledge_rag._initialized:
                result = await db.execute(select(KnowledgeArticle))
                articles = [{"id": a.id, "title": a.title, "content": a.content,
                             "category": a.category, "tags": a.tags} for a in result.scalars().all()]
                knowledge_rag.build_index(articles)
            fault_rag = knowledge_rag.generate_context(content, top_k=2)
            if fault_rag:
                yield _sse("rag_context", {"sources": [s["title"] for s in knowledge_rag.search(content, top_k=2)]})
        except Exception as e:
            logger.warning(f"Fault RAG failed: {e}")

        system_prompt = SYSTEM_PROMPT + (
            "\n\n你正在进行故障分析。请按流程：1.感知系统状态 2.诊断根因 3.给出修复建议"
        )
        if fault_rag:
            system_prompt += f"\n\n相关历史案例：\n{fault_rag}"

        chat_messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]}
            for m in messages if m["role"] in ("user", "assistant")
        ]

        yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id})

        orchestrator.transition(TaskStage.ANALYZING)
        yield _sse("task_progress", orchestrator.get_progress_event())

        full_response = ""
        tool_call_records = []
        max_rounds = settings.max_conversation_rounds
        round_count = 0

        while round_count < max_rounds:
            round_count += 1
            current_content = ""
            tool_calls = []
            async for event in self._stream_llm(chat_messages):
                if isinstance(event, dict) and event.get("__stream_done__"):
                    current_content = event.get("content", "") or ""
                    tool_calls = event.get("tool_calls", [])
                    break
                yield event

            if not current_content and not tool_calls:
                # LLM 没有产生回答也没有工具调用
                break
            if isinstance(current_content, str):
                full_response = current_content

            if not tool_calls:
                break

            chat_messages.append({"role": "assistant", "content": current_content or None,
                                  "tool_calls": tool_calls})

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_call_id = tc.get("id", _generate_id())
                try:
                    tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                except json.JSONDecodeError:
                    tool_args = {}

                risk = get_tool_risk_level(tool_name, tool_args)
                safety = _check_tool_safety(tool_name, tool_args)

                if safety["blocked"]:
                    yield _sse("blocked", {
                        "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                        "riskLevel": safety["risk_level"], "message": safety["block_message"],
                        "status": "blocked",
                    })
                    tool_call_records.append({
                        "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                        "riskLevel": safety["risk_level"], "status": "blocked",
                        "result": {"success": False, "error": safety["block_message"]},
                    })
                    continue

                # 需要审批或确认
                if safety["require_approval"] or safety["require_confirm"]:
                    from app.services.chat_service import _build_risk_description, _save_pending_execution
                    from app.models.approval import Approval
                    risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
                    now = datetime.utcnow()
                    expires_at = now + timedelta(seconds=settings.approval_timeout)

                    approval = Approval(
                        trace_id=trace_id, session_id=session_id,
                        tool_name=tool_name,
                        tool_params_json=json.dumps(tool_args, ensure_ascii=False),
                        risk_level=safety["risk_level"], detail=risk_desc,
                        requested_by=user_id, expires_at=expires_at,
                    )
                    db.add(approval)
                    await db.commit()
                    await db.refresh(approval)

                    pe = await _save_pending_execution(
                        db, session_id, trace_id, user_id,
                        tool_name, tool_args, safety["risk_level"],
                        messages_snapshot=chat_messages,
                        need_approval=safety["require_approval"],
                        approval_id=approval.id,
                    )

                    event_name = "need_approval" if safety["require_approval"] else "need_confirm"
                    yield _sse(event_name, {
                        "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                        "riskLevel": safety["risk_level"],
                        "approvalId": approval.id if safety["require_approval"] else None,
                        "pendingExecutionId": pe.id if safety["require_confirm"] else None,
                        "message": risk_desc,
                        "status": "pending_approval" if safety["require_approval"] else "pending_confirm",
                        "expiresAt": expires_at.isoformat() if safety["require_approval"] else None,
                    })
                    await save_message(db, session_id, "tool_call", "", tool_calls=[{
                        "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                        "riskLevel": safety["risk_level"],
                        "status": "pending_approval" if safety["require_approval"] else "pending_confirm",
                    }], trace_id=trace_id)
                    yield _sse("message_done", {
                        "messageId": assistant_msg_id, "traceId": trace_id,
                        "status": "awaiting_user_action",
                    })
                    return

                yield _sse("tool_call", {
                    "id": tool_call_id, "toolName": tool_name,
                    "params": tool_args, "riskLevel": risk, "status": "executing",
                })
                exec_result = execute_tool(tool_name, tool_args)
                yield _sse("tool_result", {
                    "toolName": tool_name, "status": "completed", "result": exec_result,
                })
                tool_call_records.append({
                    "id": tool_call_id, "toolName": tool_name, "params": tool_args,
                    "riskLevel": risk, "status": "completed", "result": exec_result,
                })
                chat_messages.append({
                    "role": "tool", "tool_call_id": tool_call_id,
                    "content": json.dumps(exec_result, ensure_ascii=False),
                })

                step = orchestrator.add_step(tool_name, tool_name, tool_args)
                step.status = "completed" if exec_result.get("success", False) else "failed"
                step.result = exec_result
                yield _sse("task_progress", orchestrator.get_progress_event())

        if orchestrator:
            orchestrator.transition(TaskStage.SUMMARIZING)
            orchestrator.complete()
            yield _sse("task_progress", orchestrator.get_progress_event())

        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        if tool_call_records:
            await save_message(db, session_id, "tool_call", "", tool_calls=tool_call_records, trace_id=trace_id)
        await self._save_audit(db, trace_id, session_id, user_id, content, full_response, tool_call_records, intent_result=intent_result, telemetry=ctx.get("telemetry"))

        yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id,
                                     "status": "completed"})


# ═══════════════════════════════════════════
# 5. HIGH_RISK — 高风险操作（风险提醒 + 走 ReAct）
# ═══════════════════════════════════════════
class HighRiskHandler(BaseHandler):
    intent_type = IntentType.HIGH_RISK

    async def handle(self, db, session_id, content, user_id, messages, trace_id="",
                     assistant_msg_id="", intent_result=None, rag_context="", **ctx):
        from app.services.chat_service import save_message

        yield _sse("risk_notice", {
            "message": "您的请求涉及高风险操作，相关指令将需要审批后方可执行。",
            "intent": "high_risk",
        })

        system_prompt = SYSTEM_PROMPT + (
            "\n\n注意：用户请求涉及高风险操作。请先评估风险，说明操作影响，再建议具体命令。所有写操作需审批。"
        )
        chat_messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]}
            for m in messages if m["role"] in ("user", "assistant")
        ]

        yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id})

        full_response = ""
        result = None
        gen = self._stream_llm(chat_messages)
        try:
            while True:
                event = await gen.__anext__()
                yield event
        except StopAsyncIteration as e:
            result = e.value

        if result:
            full_response = result[0] or ""

        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        await self._save_audit(db, trace_id, session_id, user_id, content, full_response, [], intent_result=intent_result, telemetry=ctx.get("telemetry"))

        yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id,
                                     "status": "completed", "usage": {"outputTokens": len(full_response)}})


# ═══════════════════════════════════════════
# 6. PROMPT_INJECTION — 注入拦截
# ═══════════════════════════════════════════
class InjectionBlockHandler(BaseHandler):
    intent_type = IntentType.PROMPT_INJECTION

    async def handle(self, db, session_id, content, user_id, messages, trace_id="",
                     assistant_msg_id="", intent_result=None, rag_context="", **ctx):
        from app.services.chat_service import save_message

        severity = intent_result.get("injection_severity", "high") if intent_result else "high"
        block_msg = "检测到潜在的提示词注入行为，该请求已被安全系统拦截。"

        yield _sse("prompt_injection_detected", {
            "message": block_msg, "severity": severity,
            "blocked": severity in ("critical", "high"),
        })

        await save_message(db, session_id, "assistant", f"⚠ {block_msg}", trace_id=trace_id)
        await self._save_audit(db, trace_id, session_id, user_id, content, "", [], intent_result=intent_result, telemetry=ctx.get("telemetry"))

        yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id,
                                     "status": "blocked_injection"})


# ═══════════════════════════════════════════
# Handler 注册表
# ═══════════════════════════════════════════
HANDLER_REGISTRY: Dict[IntentType, type] = {
    IntentType.GENERAL_QA: GeneralChatHandler,
    IntentType.KNOWLEDGE_QA: KnowledgeQAHandler,
    IntentType.OPS_QUERY: OpsQueryHandler,
    IntentType.FAULT_ANALYSIS: FaultAnalysisHandler,
    IntentType.HIGH_RISK: HighRiskHandler,
    IntentType.PROMPT_INJECTION: InjectionBlockHandler,
}


async def dispatch(
    db: AsyncSession,
    session_id: str,
    content: str,
    user_id: str,
    messages: List[Dict],
    intent_result: dict = None,
    **ctx,
) -> AsyncGenerator[dict, None]:
    """
    统一路由入口：根据意图分发到对应 Handler。
    Yields: SSE 事件 dict {"event": str, "data": str}
    """
    trace_id = ctx.pop("trace_id", _generate_id())
    assistant_msg_id = ctx.pop("assistant_msg_id", _generate_id())

    if intent_result is None:
        intent_result = await classify_intent(content)

    intent_str = intent_result.get("intent", IntentType.GENERAL_QA.value)
    try:
        intent_type = IntentType(intent_str)
    except ValueError:
        intent_type = IntentType.GENERAL_QA

    logger.info(f"[Router] intent={intent_type.value} confidence={intent_result.get('confidence', 0):.2f} "
                f"method={intent_result.get('method', 'unknown')}")

    if intent_result.get("is_injection"):
        intent_type = IntentType.PROMPT_INJECTION

    handler_cls = HANDLER_REGISTRY.get(intent_type, GeneralChatHandler)
    handler = handler_cls()

    async for event in handler.handle(
        db=db, session_id=session_id, content=content, user_id=user_id,
        messages=messages, trace_id=trace_id, assistant_msg_id=assistant_msg_id,
        intent_result=intent_result, **ctx,
    ):
        yield event
