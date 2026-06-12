"""
LangGraph Agent 服务层 — SSE 事件与分阶段人类监督流程对齐
"""
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from app.core.config import settings
from app.core.trace import generate_trace_id
from .graph import create_agent_graph, create_initial_state
from .state import AgentState, AgentStage

logger = logging.getLogger(__name__)

_agent_graph = None


def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph


def _sse(event: str, data: dict) -> Dict[str, Any]:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


async def process_with_langgraph(
    user_input: str,
    user_id: str,
    session_id: str,
    trace_id: Optional[str] = None,
    dialog_history: Optional[list] = None,
    user_role: str = "user",
    confirm_plan_id: Optional[str] = None,
    server_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    db=None,
) -> AsyncGenerator[Dict[str, Any], None]:
    if not trace_id:
        trace_id = generate_trace_id()

    logger.info("[LangGraph] trace=%s session=%s", trace_id, session_id)

    try:
        initial_state = create_initial_state(
            user_input=user_input,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            dialog_history=dialog_history or [],
            user_role=user_role,
            confirm_plan_id=confirm_plan_id,
            server_id=server_id,
            client_ip=client_ip,
        )

        config = {"configurable": {"thread_id": session_id}}
        app = get_agent_graph()

        yield _sse("message_start", {"messageId": trace_id, "traceId": trace_id})

        current_state = None
        seen_stages = set()

        async for event in app.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                current_state = {**(current_state or {}), **node_output}
                stage = node_output.get("current_stage", "")

                stage_key = f"{node_name}_{stage}"
                if stage_key not in seen_stages:
                    seen_stages.add(stage_key)
                    yield _sse("exploring_step", {
                        "id": stage_key,
                        "label": node_name,
                        "detail": str(stage),
                        "status": "done",
                    })
                    yield _sse("stage_update", {
                        "stage": node_name,
                        "state": _extract_state_for_frontend(node_output),
                    })

                if node_name == "intent_risk_filter":
                    details = node_output.get("security_gate_details") or {}
                    if details:
                        yield _sse("security_gate", {
                            "layers": details,
                            "passed": not node_output.get("blocked"),
                        })
                    if node_output.get("intent"):
                        yield _sse("intent", {
                            "intent": node_output.get("intent"),
                            "confidence": node_output.get("intent_confidence", 0),
                        })

                if node_output.get("is_injection") or node_output.get("blocked"):
                    if node_name in ("intent_risk_filter", "security_recheck", "fallback"):
                        yield _sse("prompt_injection_detected", {
                            "message": node_output.get("block_reason", "安全策略拦截"),
                            "severity": node_output.get("injection_severity", "high"),
                            "blocked": True,
                            "riskLevel": "L5" if node_output.get("final_status") == "permission_denied" else "high",
                        })

                if node_name == "parallel_intent_rag" and node_output.get("rag_sources"):
                    yield _sse("rag_context", {
                        "sources": [
                            s.get("title", s.get("id", ""))
                            for s in (node_output.get("rag_sources") or [])[:5]
                        ],
                    })

                if node_name == "security_recheck":
                    yield _sse("security_recheck", {
                        "passed": node_output.get("recheck_passed", True),
                        "reason": node_output.get("block_reason"),
                    })

                if node_name == "route_dispatch":
                    yield _sse("route_dispatch", {
                        "path": node_output.get("route_path"),
                        "link": node_output.get("workflow_link"),
                        "linkLabel": node_output.get("link_label"),
                        "linkDescription": node_output.get("link_description"),
                        "reason": node_output.get("route_reason"),
                        "intent": node_output.get("intent"),
                    })

                if node_name == "diagnostic_plan" and node_output.get("diagnostic_plan"):
                    yield _sse("diagnostic_plan", {
                        "plan": node_output.get("diagnostic_plan"),
                        "planId": node_output.get("plan_id"),
                        "awaitingConfirm": node_output.get("awaiting_user_action", False),
                    })

                if node_name == "env_precheck" and node_output.get("env_precheck"):
                    yield _sse("env_precheck", node_output.get("env_precheck"))

                if node_name == "reasoning":
                    rnd = node_output.get("round_count", 0)
                    yield _sse("react_round", {"round": rnd, "maxRounds": node_output.get("max_rounds", 5)})
                    steps = node_output.get("reasoning_steps", [])
                    if steps:
                        yield _sse("reasoning_step", {"steps": steps[-3:]})

                if node_name == "safety_check":
                    safety = node_output.get("safety_decision", {})
                    if safety:
                        yield _sse("safety_decision", safety)

                if node_name == "tool_execution":
                    for tc in node_output.get("tool_calls", []):
                        status = tc.get("status", "pending")
                        base = {
                            "id": tc.get("id", ""),
                            "toolName": tc["tool_name"],
                            "params": tc.get("tool_args", {}),
                            "riskLevel": tc.get("risk_level", "L1"),
                        }
                        if status == "blocked":
                            yield _sse("blocked", {**base, "message": tc.get("error", ""), "status": "blocked"})
                        elif status == "pending_approval":
                            yield _sse("need_approval", {
                                **base,
                                "message": f"需要审批: {tc['tool_name']}",
                                "status": "pending_approval",
                            })
                        elif status == "pending_confirm":
                            yield _sse("need_confirm", {
                                **base,
                                "message": f"确认执行: {tc['tool_name']}",
                                "status": "pending_confirm",
                            })
                        elif status in ("executed", "completed", "approved"):
                            yield _sse("tool_call", {**base, "status": "executing"})
                            if tc.get("result"):
                                yield _sse("tool_result", {
                                    "toolName": tc["tool_name"],
                                    "status": "completed" if tc["result"].get("success") else "failed",
                                    "result": tc["result"],
                                })

                if node_name == "fact_check":
                    yield _sse("fact_check", {
                        "passed": node_output.get("fact_check_passed"),
                        "notes": node_output.get("fact_check_notes"),
                    })

                if node_name == "response_assembly" and node_output.get("ops_report"):
                    yield _sse("ops_report", {"report": node_output.get("ops_report")})

                if node_name == "kb_ingest" and node_output.get("kb_article_id"):
                    yield _sse("kb_ingest", {"articleId": node_output.get("kb_article_id")})

        if current_state:
            final_response = current_state.get("final_response", "")
            streaming_tokens = current_state.get("streaming_tokens", [])

            if streaming_tokens:
                for token in streaming_tokens:
                    yield _sse("token", {"token": token})
            elif final_response:
                import asyncio
                for i in range(0, len(final_response), 2):
                    yield _sse("token", {"token": final_response[i:i + 2]})
                    await asyncio.sleep(0.012)

            if current_state.get("reasoning_chain_visible"):
                steps = current_state.get("reasoning_steps", [])
                if steps:
                    yield _sse("reasoning_chain", {"steps": steps})

            cards = current_state.get("state_cards", [])
            if cards:
                yield _sse("state_cards", {
                    "cards": cards,
                    "riskColor": current_state.get("risk_color", "blue"),
                })

        status = "completed"
        if current_state:
            if current_state.get("awaiting_user_action") and not current_state.get("plan_confirmed"):
                status = "awaiting_plan_confirm"
            elif current_state.get("require_approval"):
                status = "awaiting_approval"
            elif current_state.get("require_confirm"):
                status = "awaiting_confirm"
            elif current_state.get("blocked") or current_state.get("error"):
                status = "failed"
            elif current_state.get("final_status"):
                status = current_state.get("final_status")

        yield _sse("message_done", {
            "messageId": trace_id,
            "traceId": trace_id,
            "status": status,
            "final_response": (current_state or {}).get("final_response", ""),
            "intent": (current_state or {}).get("intent"),
        })

    except Exception as e:
        logger.error("[LangGraph] failed: %s", e, exc_info=True)
        yield _sse("error", {"message": str(e)[:300]})
        yield _sse("message_done", {
            "messageId": trace_id,
            "traceId": trace_id,
            "status": "error",
        })


def _extract_state_for_frontend(state: AgentState) -> Dict[str, Any]:
    return {
        "current_stage": state.get("current_stage"),
        "intent": state.get("intent"),
        "intent_confidence": state.get("intent_confidence"),
        "is_injection": state.get("is_injection"),
        "has_rag": bool(state.get("rag_context")),
        "risk_color": state.get("risk_color", "blue"),
        "round_count": state.get("round_count", 0),
        "tool_calls_count": len(state.get("tool_calls", [])),
        "require_approval": state.get("require_approval", False),
        "require_confirm": state.get("require_confirm", False),
        "route_path": state.get("route_path"),
    }


async def langgraph_chat_handler(db, session_id: str, content: str, user_id: str, user_role: str = "user"):
    """兼容旧调用：委托 chat_orchestrator。"""
    from app.services.chat_orchestrator import process_chat_message
    async for event in process_chat_message(
        db, session_id, content, user_id, user_role=user_role, use_langgraph=True,
    ):
        yield event
