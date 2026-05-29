"""
LangGraph Agent 服务层 - 集成到现有系统

支持:
  - 对话历史加载
  - ReAct 循环流式推送
  - 审批/确认流程
  - 降级处理
"""
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from app.core.trace import generate_trace_id
from .graph import create_agent_graph, create_initial_state
from .state import AgentState, AgentStage

logger = logging.getLogger(__name__)

# 全局 Agent 图实例
_agent_graph = None


def get_agent_graph():
    """获取或初始化 Agent 图"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph


async def process_with_langgraph(
    user_input: str,
    user_id: str,
    session_id: str,
    trace_id: Optional[str] = None,
    dialog_history: Optional[list] = None,
    db=None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    使用 LangGraph 处理用户消息（流式输出）

    Args:
        user_input: 用户输入
        user_id: 用户ID
        session_id: 会话ID
        trace_id: 追踪ID
        dialog_history: 对话历史列表
        db: 数据库会话（用于创建审批记录）

    Yields:
        SSE 事件数据字典
    """
    if not trace_id:
        trace_id = generate_trace_id()

    logger.info(f"[LangGraph Agent] 开始处理: trace_id={trace_id}, session={session_id}")

    try:
        # 1. 创建初始状态（含对话历史）
        initial_state = create_initial_state(
            user_input=user_input,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            dialog_history=dialog_history or [],
        )

        # 2. 配置检查点
        config = {
            "configurable": {
                "thread_id": session_id,
            }
        }

        # 3. 获取 Agent 图
        app = get_agent_graph()

        # 4. 发送开始事件
        yield {
            "event": "message_start",
            "data": {"message_id": trace_id, "trace_id": trace_id}
        }

        # 5. 流式执行图
        current_state = None
        seen_stages = set()

        async for event in app.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                stage = node_output.get("current_stage", "")

                # 发送阶段更新（去重）
                stage_key = f"{node_name}_{stage}"
                if stage_key not in seen_stages:
                    seen_stages.add(stage_key)
                    yield {
                        "event": "stage_update",
                        "data": {
                            "stage": node_name,
                            "state": _extract_state_for_frontend(node_output),
                        }
                    }

                # 意图识别事件
                if node_name == "intent_risk_filter" and node_output.get("intent"):
                    yield {
                        "event": "intent",
                        "data": {
                            "intent": node_output.get("intent"),
                            "confidence": node_output.get("intent_confidence", 0),
                        }
                    }

                # 注入检测事件
                if node_output.get("is_injection"):
                    yield {
                        "event": "prompt_injection_detected",
                        "data": {
                            "message": node_output.get("block_reason", "检测到注入行为"),
                            "severity": node_output.get("injection_severity", "high"),
                            "blocked": True,
                        }
                    }

                # RAG 检索事件
                if node_name == "parallel_intent_rag" and node_output.get("rag_sources"):
                    yield {
                        "event": "rag_context",
                        "data": {
                            "sources": [s.get("title", "") for s in node_output.get("rag_sources", [])[:3]],
                        }
                    }

                # 推理步骤事件
                if node_name == "reasoning":
                    steps = node_output.get("reasoning_steps", [])
                    if steps:
                        yield {
                            "event": "reasoning_step",
                            "data": {"steps": steps}
                        }

                # 安全校验事件
                if node_name == "safety_check":
                    safety = node_output.get("safety_decision", {})
                    if safety:
                        yield {
                            "event": "safety_decision",
                            "data": safety,
                        }

                # 工具调用和审批事件
                if node_name == "tool_execution":
                    for tc in node_output.get("tool_calls", []):
                        status = tc.get("status", "pending")

                        if status == "blocked":
                            yield {
                                "event": "blocked",
                                "data": {
                                    "id": tc["id"],
                                    "toolName": tc["tool_name"],
                                    "params": tc.get("tool_args", {}),
                                    "riskLevel": tc.get("risk_level", "L3"),
                                    "message": tc.get("error", "被安全策略阻止"),
                                    "status": "blocked",
                                }
                            }
                        elif status == "pending_approval":
                            yield {
                                "event": "need_approval",
                                "data": {
                                    "id": tc["id"],
                                    "toolName": tc["tool_name"],
                                    "params": tc.get("tool_args", {}),
                                    "riskLevel": tc.get("risk_level", "L3"),
                                    "message": f"需要审批: {tc['tool_name']} [{tc.get('risk_level', 'L3')}]",
                                    "status": "pending_approval",
                                }
                            }
                        elif status == "pending_confirm":
                            yield {
                                "event": "need_confirm",
                                "data": {
                                    "id": tc["id"],
                                    "toolName": tc["tool_name"],
                                    "params": tc.get("tool_args", {}),
                                    "riskLevel": tc.get("risk_level", "L2"),
                                    "message": f"确认执行: {tc['tool_name']}",
                                    "status": "pending_confirm",
                                }
                            }
                        elif status in ("executed", "completed"):
                            yield {
                                "event": "tool_call",
                                "data": {
                                    "id": tc["id"],
                                    "toolName": tc["tool_name"],
                                    "params": tc.get("tool_args", {}),
                                    "riskLevel": tc.get("risk_level", "L1"),
                                    "status": "executing",
                                }
                            }
                            if tc.get("result"):
                                yield {
                                    "event": "tool_result",
                                    "data": {
                                        "toolName": tc["tool_name"],
                                        "status": "completed" if tc["result"].get("success") else "failed",
                                        "result": tc["result"],
                                    }
                                }

                current_state = node_output

        # 6. 发送最终结果 - 流式 token 推送
        if current_state:
            final_response = current_state.get("final_response", "")
            streaming_tokens = current_state.get("streaming_tokens", [])

            if streaming_tokens:
                # 真实流式：逐 token 推送（来自 LLM 流式调用）
                for token in streaming_tokens:
                    yield {
                        "event": "token",
                        "data": {"token": token}
                    }
            elif final_response:
                # 降级方案：打字效果模拟（用于审批/确认等非 LLM 场景）
                import asyncio
                chars = final_response
                chunk_size = 2
                for i in range(0, len(chars), chunk_size):
                    chunk = chars[i:i + chunk_size]
                    yield {
                        "event": "token",
                        "data": {"token": chunk}
                    }
                    await asyncio.sleep(0.015)

            # 推理链
            if current_state.get("reasoning_chain_visible"):
                steps = current_state.get("reasoning_steps", [])
                if steps:
                    yield {
                        "event": "reasoning_chain",
                        "data": {"steps": steps}
                    }

            # 状态卡片
            state_cards = current_state.get("state_cards", [])
            if state_cards:
                yield {
                    "event": "state_cards",
                    "data": {
                        "cards": state_cards,
                        "risk_color": current_state.get("risk_color", "blue"),
                    }
                }

        # 7. 完成事件
        status = "completed"
        if current_state:
            if current_state.get("require_approval"):
                status = "awaiting_approval"
            elif current_state.get("require_confirm"):
                status = "awaiting_confirm"
            elif current_state.get("error"):
                status = "error"

        yield {
            "event": "message_done",
            "data": {
                "message_id": trace_id,
                "trace_id": trace_id,
                "status": status,
            }
        }

    except Exception as e:
        logger.error(f"[LangGraph Agent] 处理失败: {e}", exc_info=True)
        yield {
            "event": "error",
            "data": {"message": f"处理失败: {str(e)}"}
        }
        yield {
            "event": "message_done",
            "data": {
                "message_id": trace_id,
                "trace_id": trace_id,
                "status": "error",
            }
        }


def _extract_state_for_frontend(state: AgentState) -> Dict[str, Any]:
    """从完整状态中提取前端展示所需字段"""
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
    }


async def langgraph_chat_handler(
    db,
    session_id: str,
    content: str,
    user_id: str,
):
    """
    兼容现有 chat_service 的 LangGraph 处理器。
    先保存用户消息，加载历史，再调用 LangGraph 流程。
    """
    from app.services.chat_service import save_message, get_messages

    # 保存用户消息
    await save_message(db, session_id, "user", content)

    # 加载对话历史
    history_data = await get_messages(db, session_id)
    dialog_history = history_data.get("items", [])

    # 使用 LangGraph 处理
    async for event in process_with_langgraph(
        content, user_id, session_id,
        dialog_history=dialog_history,
        db=db,
    ):
        yield event
