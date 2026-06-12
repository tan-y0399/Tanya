"""
LangGraph 图定义 — 人类监督分阶段工作流（8 阶段优化）

拓扑:
  intent_risk_filter → parallel_intent_rag → security_recheck → fusion → route_dispatch
       ↘ fallback

  route_dispatch → handler_a (链路A) | chain_b_tool_safety (链路B) | diagnostic_plan (链路C)
  diagnostic_plan → env_precheck | END(待确认方案)
  env_precheck → dialog_manager | fallback

  dialog_manager → reasoning ⇄ safety_check → atomic_step_validate → confirmation/tool_execution
  response_assembly → fact_check → kb_ingest → END
  rollback → END
  fallback → END
"""
from typing import Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.services.human_supervision import validate_user_input
from .state import AgentState, AgentStage
from .nodes import (
    intent_risk_filter_node,
    parallel_intent_rag_node,
    fusion_node,
    dialog_manager_node,
    reasoning_node,
    safety_check_node,
    confirmation_node,
    tool_execution_node,
    response_assembly_node,
    fallback_node,
)
from .nodes_supervision import (
    security_recheck_node,
    route_dispatch_node,
    chain_b_tool_safety_node,
    diagnostic_plan_node,
    env_precheck_node,
    atomic_step_validate_node,
    fact_check_node,
    kb_ingest_node,
    rollback_node,
)

MAX_RETRIES = 2


def should_continue_after_filter(state: AgentState) -> Literal["parallel", "fallback"]:
    if state.get("blocked") or state.get("is_injection"):
        return "fallback"
    return "parallel"


def should_continue_after_recheck(state: AgentState) -> Literal["fusion", "fallback"]:
    if state.get("blocked") or not state.get("recheck_passed", True):
        return "fallback"
    return "fusion"


def should_continue_after_route(
    state: AgentState,
) -> Literal["handler_a", "react_b_light", "react_c_plan"]:
    path = state.get("route_path") or "react_c_plan"
    if path == "handler_a":
        return "handler_a"
    if path == "react_b_light":
        return "react_b_light"
    return "react_c_plan"


def should_continue_after_diagnostic_plan(
    state: AgentState,
) -> Literal["env_precheck", "await_plan"]:
    if state.get("blocked"):
        return "await_plan"
    if state.get("plan_confirmed") or state.get("confirm_plan_id"):
        return "env_precheck"
    if state.get("awaiting_user_action"):
        return "await_plan"
    return "env_precheck"


def should_continue_after_env(state: AgentState) -> Literal["dialog_manager", "fallback"]:
    if state.get("blocked") or state.get("final_status") == "env_failed":
        return "fallback"
    return "dialog_manager"


def should_continue_after_reasoning(
    state: AgentState,
) -> Literal["reasoning", "safety_check", "response_assembly", "fallback"]:
    has_error = bool(state.get("error"))
    retries = state.get("retry_count", 0)
    if has_error and retries < MAX_RETRIES:
        return "reasoning"
    if state.get("current_stage") == AgentStage.FALLBACK:
        return "fallback"
    if has_error:
        return "response_assembly"
    if state.get("tool_calls"):
        return "safety_check"
    return "response_assembly"


def should_continue_after_safety(
    state: AgentState,
) -> Literal["fallback", "confirmation", "tool_execution"]:
    if state.get("blocked"):
        return "fallback"
    if state.get("require_approval") or state.get("require_confirm"):
        return "confirmation"
    return "tool_execution"


def should_continue_after_execution(
    state: AgentState,
) -> Literal["tool_execution", "reasoning", "response_assembly"]:
    has_error = bool(state.get("error"))
    retries = state.get("retry_count", 0)
    if has_error and retries < MAX_RETRIES:
        return "tool_execution"
    if has_error:
        return "response_assembly"
    if state.get("require_approval") or state.get("require_confirm"):
        return "response_assembly"
    if state.get("round_count", 0) >= state.get("max_rounds", 5):
        return "response_assembly"
    return "reasoning"


def should_fact_check_or_end(state: AgentState) -> Literal["fact_check", "kb_ingest"]:
    if state.get("route_path") == "handler_a" and state.get("intent") == "knowledge_qa":
        return "fact_check"
    if state.get("ops_report"):
        return "kb_ingest"
    return "kb_ingest"


def create_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("intent_risk_filter", intent_risk_filter_node)
    graph.add_node("parallel_intent_rag", parallel_intent_rag_node)
    graph.add_node("security_recheck", security_recheck_node)
    graph.add_node("fusion", fusion_node)
    graph.add_node("route_dispatch", route_dispatch_node)
    graph.add_node("chain_b_entry", chain_b_tool_safety_node)
    graph.add_node("diagnostic_plan", diagnostic_plan_node)
    graph.add_node("env_precheck", env_precheck_node)
    graph.add_node("atomic_step_validate", atomic_step_validate_node)
    graph.add_node("rollback", rollback_node)
    graph.add_node("dialog_manager", dialog_manager_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("confirmation", confirmation_node)
    graph.add_node("tool_execution", tool_execution_node)
    graph.add_node("response_assembly", response_assembly_node)
    graph.add_node("fact_check", fact_check_node)
    graph.add_node("kb_ingest", kb_ingest_node)
    graph.add_node("fallback", fallback_node)

    graph.set_entry_point("intent_risk_filter")

    graph.add_conditional_edges(
        "intent_risk_filter", should_continue_after_filter,
        {"parallel": "parallel_intent_rag", "fallback": "fallback"},
    )
    graph.add_edge("parallel_intent_rag", "security_recheck")
    graph.add_conditional_edges(
        "security_recheck", should_continue_after_recheck,
        {"fusion": "fusion", "fallback": "fallback"},
    )
    graph.add_edge("fusion", "route_dispatch")
    graph.add_conditional_edges(
        "route_dispatch", should_continue_after_route,
        {
            "handler_a": "dialog_manager",
            "react_b_light": "chain_b_entry",
            "react_c_plan": "diagnostic_plan",
        },
    )
    graph.add_edge("chain_b_entry", "dialog_manager")
    graph.add_conditional_edges(
        "diagnostic_plan", should_continue_after_diagnostic_plan,
        {"env_precheck": "env_precheck", "await_plan": END},
    )
    graph.add_conditional_edges(
        "env_precheck", should_continue_after_env,
        {"dialog_manager": "atomic_step_validate", "fallback": "fallback"},
    )
    graph.add_edge("atomic_step_validate", "dialog_manager")
    graph.add_edge("dialog_manager", "reasoning")

    graph.add_conditional_edges(
        "reasoning", should_continue_after_reasoning,
        {
            "reasoning": "reasoning",
            "safety_check": "safety_check",
            "response_assembly": "response_assembly",
            "fallback": "fallback",
        },
    )
    graph.add_conditional_edges(
        "safety_check", should_continue_after_safety,
        {"fallback": "fallback", "confirmation": "confirmation", "tool_execution": "tool_execution"},
    )
    graph.add_edge("confirmation", "response_assembly")
    graph.add_conditional_edges(
        "tool_execution", should_continue_after_execution,
        {"tool_execution": "tool_execution", "reasoning": "reasoning", "response_assembly": "response_assembly"},
    )

    graph.add_conditional_edges(
        "response_assembly", should_fact_check_or_end,
        {"fact_check": "fact_check", "kb_ingest": "kb_ingest"},
    )
    graph.add_edge("fact_check", "kb_ingest")
    graph.add_edge("kb_ingest", END)
    graph.add_edge("fallback", END)

    return graph.compile(checkpointer=MemorySaver())


def create_initial_state(
    user_input: str,
    user_id: str,
    session_id: str,
    trace_id: str = None,
    dialog_history: list = None,
    user_role: str = "user",
    confirm_plan_id: str = None,
    server_id: str = None,
    client_ip: str = None,
) -> AgentState:
    if not trace_id:
        from app.core.trace import generate_trace_id
        trace_id = generate_trace_id()

    pre = validate_user_input(user_input)
    sanitized = pre.get("sanitized", user_input) if pre.get("valid") else user_input

    return {
        "user_input": user_input,
        "sanitized_input": sanitized,
        "user_id": user_id,
        "user_role": user_role,
        "session_id": session_id,
        "trace_id": trace_id,
        "confirm_plan_id": confirm_plan_id,
        "server_id": server_id,
        "client_ip": client_ip,

        "intent": None,
        "intent_confidence": 0.0,
        "is_injection": False,
        "injection_severity": None,
        "blocked": False,
        "block_reason": None,

        "intent_result": None,
        "rag_context": None,
        "rag_sources": None,

        "fused_prompt": None,

        "dialog_history": dialog_history or [],
        "session_memory": None,

        "messages": [],
        "round_count": 0,
        "max_rounds": settings.react_max_rounds,

        "reasoning_steps": [],
        "tool_calls": [],
        "reasoning_output": None,
        "streaming_tokens": [],

        "safety_decision": None,
        "require_approval": False,
        "require_confirm": False,
        "approval_id": None,

        "execution_results": [],

        "diagnostic_stage": None,
        "diagnostic_findings": [],
        "root_cause": None,

        "security_gate_details": None,
        "recheck_passed": False,
        "route_path": None,
        "workflow_link": None,
        "diagnostic_plan": None,
        "plan_id": None,
        "plan_confirmed": bool(confirm_plan_id),
        "env_precheck": None,
        "snapshot_id": None,
        "checkpoint_id": None,
        "file_protection_whitelist": None,
        "current_plan_step": 0,
        "fact_check_passed": None,
        "fact_check_notes": None,
        "execution_command_log": [],
        "ops_report": None,
        "final_status": "processing",
        "awaiting_user_action": False,
        "kb_article_id": None,

        "final_response": None,
        "risk_color": "blue",
        "state_cards": [],
        "reasoning_chain_visible": True,

        "current_stage": AgentStage.INIT,
        "error": None,
        "retry_count": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
