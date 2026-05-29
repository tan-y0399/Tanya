"""
LangGraph 图定义 - 完整的 Agent 工作流（对标6层架构图）

拓扑结构:
  intent_risk_filter ──(安全)──> parallel_intent_rag ──> fusion ──> dialog_manager
                    ──(拦截)──> fallback

  dialog_manager ──> reasoning ──(有tool_calls)──> safety_check
                               ──(无tool_calls)──> response_assembly
                               ──(异常,可重试)──> reasoning (重试循环)
                               ──(异常,重试耗尽)──> fallback

  safety_check ──(阻断)──> fallback
              ──(需确认/审批)──> confirmation ──> response_assembly (暂停等用户)
              ──(安全)──> tool_execution

  tool_execution ──(需审批/确认)──> response_assembly (暂停等待)
                ──(执行异常,可重试)──> tool_execution (重试)
                ──(已执行,继续)──> reasoning (ReAct循环)
                ──(全部完成)──> response_assembly

  confirmation ──> response_assembly ──> END
  fallback ──> END
"""
from typing import Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

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

MAX_RETRIES = 2


# ═══════════════════════════════════════════
# 条件路由函数
# ═══════════════════════════════════════════

def should_continue_after_filter(state: AgentState) -> Literal["parallel", "fallback"]:
    """意图风险过滤后决定走向"""
    if state.get("blocked") or state.get("is_injection"):
        return "fallback"
    return "parallel"


def should_continue_after_reasoning(
    state: AgentState,
) -> Literal["reasoning", "safety_check", "response_assembly", "fallback"]:
    """
    推理完成后决定走向:
    - 异常 + 有重试次数 → 重试 reasoning
    - 异常 + 重试耗尽 → response_assembly (展示错误)
    - 明确降级标记 → fallback
    - 有 tool_calls → safety_check
    - 无 tool_calls → response_assembly
    """
    has_error = bool(state.get("error"))
    retries = state.get("retry_count", 0)

    # 有错误且可重试 → 重试
    if has_error and retries < MAX_RETRIES:
        return "reasoning"

    # 明确降级标记 → 直接降级
    if state.get("current_stage") == AgentStage.FALLBACK:
        return "fallback"

    # 错误但重试耗尽 → 进入响应组装展示错误
    if has_error:
        return "response_assembly"

    # 有工具调用 → 安全校验
    tool_calls = state.get("tool_calls", [])
    if tool_calls and len(tool_calls) > 0:
        return "safety_check"

    # 无工具调用 → 响应组装
    return "response_assembly"


def should_continue_after_safety(
    state: AgentState,
) -> Literal["fallback", "confirmation", "tool_execution"]:
    """
    安全校验后决定走向:
    - 全部被阻止 → fallback
    - 有需审批/确认 → confirmation (④.5 确认请求节点)
    - 安全通过 → tool_execution
    """
    if state.get("blocked"):
        return "fallback"

    if state.get("require_approval") or state.get("require_confirm"):
        return "confirmation"

    return "tool_execution"


def should_continue_after_execution(
    state: AgentState,
) -> Literal["tool_execution", "reasoning", "response_assembly"]:
    """
    工具执行完成后决定走向:
    - 执行异常 + 可重试 → tool_execution (重试)
    - 执行异常 + 重试耗尽 → response_assembly (报告错误)
    - 需审批/确认 → response_assembly (暂停等待用户)
    - 还有轮次 → reasoning (继续 ReAct)
    - 达到最大轮次 → response_assembly
    """
    # 执行异常且可重试 → 重试
    has_error = bool(state.get("error"))
    retries = state.get("retry_count", 0)
    if has_error and retries < MAX_RETRIES:
        return "tool_execution"

    # 执行异常但重试耗尽 → 结束（报告错误）
    if has_error:
        return "response_assembly"

    # 需要用户操作 → 暂停
    if state.get("require_approval") or state.get("require_confirm"):
        return "response_assembly"

    # 轮次限制检查
    round_count = state.get("round_count", 0)
    max_rounds = state.get("max_rounds", 5)

    if round_count >= max_rounds:
        return "response_assembly"

    # 继续 ReAct 循环
    return "reasoning"


# ═══════════════════════════════════════════
# 图构建
# ═══════════════════════════════════════════

def create_agent_graph():
    """创建完整的 Agent 工作流图"""
    graph = StateGraph(AgentState)

    # 添加所有节点
    graph.add_node("intent_risk_filter", intent_risk_filter_node)
    graph.add_node("parallel_intent_rag", parallel_intent_rag_node)
    graph.add_node("fusion", fusion_node)
    graph.add_node("dialog_manager", dialog_manager_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("confirmation", confirmation_node)
    graph.add_node("tool_execution", tool_execution_node)
    graph.add_node("response_assembly", response_assembly_node)
    graph.add_node("fallback", fallback_node)

    # 入口
    graph.set_entry_point("intent_risk_filter")

    # ① → 并行 或 降级
    graph.add_conditional_edges(
        "intent_risk_filter", should_continue_after_filter,
        {"parallel": "parallel_intent_rag", "fallback": "fallback"},
    )

    # ②→③→④→⑤ 线性链
    graph.add_edge("parallel_intent_rag", "fusion")
    graph.add_edge("fusion", "dialog_manager")
    graph.add_edge("dialog_manager", "reasoning")

    # ⑤ 推理 → 重试 / 安全校验 / 响应 / 降级
    graph.add_conditional_edges(
        "reasoning", should_continue_after_reasoning,
        {
            "reasoning": "reasoning",
            "safety_check": "safety_check",
            "response_assembly": "response_assembly",
            "fallback": "fallback",
        },
    )

    # ④ 安全校验 → 降级 / 确认 / 执行
    graph.add_conditional_edges(
        "safety_check", should_continue_after_safety,
        {
            "fallback": "fallback",
            "confirmation": "confirmation",
            "tool_execution": "tool_execution",
        },
    )

    # ④.5 确认 → 响应组装 (构造确认请求,暂停等用户)
    graph.add_edge("confirmation", "response_assembly")

    # ⑤ 工具执行 → 重试 / 推理(ReAct) / 响应
    graph.add_conditional_edges(
        "tool_execution", should_continue_after_execution,
        {
            "tool_execution": "tool_execution",
            "reasoning": "reasoning",
            "response_assembly": "response_assembly",
        },
    )

    # ⑥ 响应组装 → END
    graph.add_edge("response_assembly", END)
    graph.add_edge("fallback", END)

    # 编译（带记忆检查点）
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)

    return app


def create_initial_state(
    user_input: str,
    user_id: str,
    session_id: str,
    trace_id: str = None,
    dialog_history: list = None,
) -> AgentState:
    """创建初始状态"""
    if not trace_id:
        from app.core.trace import generate_trace_id
        trace_id = generate_trace_id()

    return {
        "user_input": user_input,
        "user_id": user_id,
        "session_id": session_id,
        "trace_id": trace_id,

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
        "max_rounds": 5,

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

        "final_response": None,
        "risk_color": "blue",
        "state_cards": [],
        "reasoning_chain_visible": True,

        "current_stage": AgentStage.INIT,
        "error": None,
        "retry_count": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
