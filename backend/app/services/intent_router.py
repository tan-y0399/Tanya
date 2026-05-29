"""
意图识别与任务路由 —— 兼容层

委托给 intent_classifier 做实际分类。
保留原有的 classify() 函数签名和 intent_router 单例，确保 chat_service 兼容。
"""

from app.services.intent_classifier import (
    IntentType,
    classify_sync,
    classify as _classify_async,
    get_intent_metadata,
    FAULT_PATTERNS,
    HIGH_RISK_PATTERNS,
    OPS_PATTERNS,
    KNOWLEDGE_PATTERNS,
    INJECTION_PATTERNS as INJECTION_PRE_CHECK,
)


def classify(user_input: str) -> dict:
    """
    同步分类（兼容旧接口）。
    注意：同步版本不使用 LLM，仅关键词匹配。
    如需 LLM 语义分类，请使用 intent_classifier.classify() (异步)。
    """
    return classify_sync(user_input)


def get_metadata(intent_value: str) -> dict:
    return get_intent_metadata(intent_value)


# 单例（兼容 chat_service 的 intent_router.classify() 调用）
class _IntentRouter:
    classify = staticmethod(classify)
    get_metadata = staticmethod(get_metadata)


intent_router = _IntentRouter()
