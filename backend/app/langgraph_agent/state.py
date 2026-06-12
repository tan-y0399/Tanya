"""
Agent 状态定义 - LangGraph State
"""
from typing import List, Dict, Optional, Any
from enum import Enum

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict


class RiskLevel(str, Enum):
    L1 = "L1"  # 安全，直接执行
    L2 = "L2"  # 低风险，需要确认
    L3 = "L3"  # 中风险，需要审批
    L4 = "L4"  # 高风险，严格审批
    L5 = "L5"  # 极高风险，直接拒绝


class AgentStage(str, Enum):
    INIT = "init"
    INTENT_FILTER = "intent_filter"
    SECURITY_RECHECK = "security_recheck"
    PARALLEL_PROCESS = "parallel_process"
    FUSION = "fusion"
    ROUTE_DISPATCH = "route_dispatch"
    DIAGNOSTIC_PLAN = "diagnostic_plan"
    ENV_PRECHECK = "env_precheck"
    DIALOG_MANAGE = "dialog_manage"
    REASONING = "reasoning"
    SAFETY_CHECK = "safety_check"
    CONFIRMATION = "confirmation"
    TOOL_EXECUTION = "tool_execution"
    FACT_CHECK = "fact_check"
    RESPONSE_ASSEMBLY = "response_assembly"
    KB_INGEST = "kb_ingest"
    ROLLBACK = "rollback"
    FALLBACK = "fallback"
    COMPLETED = "completed"


class ToolCall(TypedDict):
    id: str
    tool_name: str
    tool_args: Dict[str, Any]
    risk_level: str
    status: str  # pending, approved, rejected, executed, blocked
    result: Optional[Dict]
    error: Optional[str]


class ReasoningStep(TypedDict):
    step: int
    thought: str
    action: Optional[str]
    observation: Optional[str]


class AgentState(TypedDict):
    # 输入
    user_input: str
    user_id: str
    user_role: str
    session_id: str
    trace_id: str
    confirm_plan_id: Optional[str]
    server_id: Optional[str]
    client_ip: Optional[str]
    sanitized_input: Optional[str]

    # 意图风险过滤
    intent: Optional[str]
    intent_confidence: float
    is_injection: bool
    injection_severity: Optional[str]
    blocked: bool
    block_reason: Optional[str]

    # 并行执行结果
    intent_result: Optional[Dict]
    rag_context: Optional[str]
    rag_sources: Optional[List[Dict]]

    # 融合层
    fused_prompt: Optional[str]

    # 对话管理
    dialog_history: List[Dict]
    session_memory: Optional[Dict]

    # === ReAct 循环核心字段 ===
    # 完整的消息列表（发送给 LLM 的上下文）
    messages: List[Dict[str, Any]]
    # 当前 ReAct 轮次
    round_count: int
    # 最大 ReAct 轮次
    max_rounds: int

    # 推理决策
    reasoning_steps: List[ReasoningStep]
    tool_calls: List[ToolCall]
    reasoning_output: Optional[str]
    streaming_tokens: List[str]  # LLM 流式 token 缓存

    # 安全校验
    safety_decision: Optional[Dict]
    require_approval: bool
    require_confirm: bool
    approval_id: Optional[str]

    # 工具执行
    execution_results: List[Dict]

    # 故障诊断追踪（Phase 4: 多轮根因引导）
    diagnostic_stage: Optional[str]   # info_gathering / hypothesis / verification / root_cause / remediation
    diagnostic_findings: List[Dict]   # 诊断发现列表
    root_cause: Optional[Dict]        # 根因分析结果

    # 响应组装
    final_response: Optional[str]
    risk_color: str
    state_cards: List[Dict]
    reasoning_chain_visible: bool

    # 人类监督扩展（分阶段流程）
    security_gate_details: Optional[Dict]
    recheck_passed: bool
    route_path: Optional[str]
    workflow_link: Optional[str]
    diagnostic_plan: Optional[Dict]
    plan_id: Optional[str]
    plan_confirmed: bool
    env_precheck: Optional[Dict]
    snapshot_id: Optional[str]
    checkpoint_id: Optional[str]
    file_protection_whitelist: Optional[List[str]]
    current_plan_step: int
    fact_check_passed: Optional[bool]
    fact_check_notes: Optional[str]
    execution_command_log: List[Dict]
    ops_report: Optional[str]
    final_status: str
    awaiting_user_action: bool
    kb_article_id: Optional[str]

    # 元数据
    current_stage: AgentStage
    error: Optional[str]
    retry_count: int
    created_at: str
