"""
LangGraph Agent 模块 - 核心架构实现

基于 6 层安全架构的智能运维 Agent:
  ① 意图风险过滤层 - 注入检测 + 意图分类 + 风险初判
  ② 对话管理引擎 - 上下文拼接 + 状态更新
  ③ 推理决策层 - LLM推理 + 任务规划 + 思维链生成
  ④ 安全校验层 - 指令过滤 + 高危识别 + 权限校验
  ⑤ 工具调用执行层 - 远程执行 + 审批流程
  ⑥ 响应组装层 - 结果 + 推理链 + 状态卡片 + 风险色标
"""
from .state import AgentState, RiskLevel, AgentStage, ToolCall, ReasoningStep
from .graph import create_agent_graph, create_initial_state
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
from .service import (
    get_agent_graph,
    process_with_langgraph,
    langgraph_chat_handler,
)

__all__ = [
    # State
    'AgentState', 'RiskLevel', 'AgentStage', 'ToolCall', 'ReasoningStep',
    # Graph
    'create_agent_graph', 'create_initial_state',
    # Nodes
    'intent_risk_filter_node',
    'parallel_intent_rag_node',
    'fusion_node',
    'dialog_manager_node',
    'reasoning_node',
    'safety_check_node',
    'confirmation_node',
    'tool_execution_node',
    'response_assembly_node',
    'fallback_node',
    # Service
    'get_agent_graph',
    'process_with_langgraph',
    'langgraph_chat_handler',
]
