"""
按识别意图为 Agent 注入差异化系统提示，提升「对症下药」与回答质量。
"""
from __future__ import annotations

from typing import Dict

from app.services.intent_classifier import IntentType, get_intent_metadata


INTENT_SYSTEM_ADDONS: Dict[str, str] = {
    IntentType.GENERAL_QA.value: """
## 当前意图：普通问答
- 直接回答，不要调用任何工具。
- 若用户只是打招呼或问概念，用 1～3 段简洁中文说明即可。
""",
    IntentType.KNOWLEDGE_QA.value: """
## 当前意图：运维知识问答（禁止调用工具）
- 用户要学习**方法/步骤/配置**，不是要查看本机当前数值。
- 必须用分章节 Markdown（标题、步骤、代码块、注意事项），参考图2「操作指南」风格。
- 禁止出现「我来检查…」并调用 get_* 类工具。
""",
    IntentType.OPS_QUERY.value: """
## 当前意图：运维查询（只读）
- 必须调用与问题直接相关的工具获取真实数据，禁止编造指标。
- 过程说明保持 1 句；工具返回后翻译为自然语言，禁止输出原始 JSON。
- 完成查询后写「## 执行结论」，明确正常/异常及关键数值。
""",
    IntentType.FAULT_ANALYSIS.value: """
## 当前意图：故障分析
- 按「现象确认 → 关联检查（服务/日志/资源）→ 根因推断 → 处理建议」推进。
- 至少调用 2 个相关工具（如服务状态 + 日志/资源）再下结论。
- 结论须包含：可能原因（按概率排序）、已核实事实、建议操作步骤。
""",
    IntentType.HIGH_RISK.value: """
## 当前意图：高风险操作
- 关闭/启动/重启服务：必须调用 `manage_service`（或等价工具），禁止仅用 `get_service_status` 代替执行。
- 磁盘/垃圾清理：必须逐条调用 `execute_command`，禁止一次性在文字中谎称「已清理/已执行」。
- 写操作会触发 L2 确认、L3 确认+审计、L4 管理员审批；批准后用户须在对话页点击「执行」才会真正运行。
- 未调用工具或未获批准前，禁止写「已成功关闭/已清理/已执行」；可说明「已提交审批」或「待您确认执行」。
""",
}


def build_intent_system_addon(intent_result: dict, user_question: str) -> str:
    """根据意图分类结果生成追加系统提示。"""
    intent = intent_result.get("intent", IntentType.GENERAL_QA.value)
    meta = intent_result.get("metadata") or get_intent_metadata(intent)
    label = meta.get("label", intent)
    conf = intent_result.get("confidence", 0)
    method = intent_result.get("method", "keyword")
    entities = intent_result.get("entities") or {}

    base = INTENT_SYSTEM_ADDONS.get(intent, INTENT_SYSTEM_ADDONS[IntentType.GENERAL_QA.value])
    entity_hint = ""
    if entities:
        parts = []
        for k, v in entities.items():
            if v:
                parts.append(f"{k}={','.join(str(x) for x in v[:3])}")
        if parts:
            entity_hint = f"\n- 已从用户问题提取实体：{'; '.join(parts)}"

    reason = intent_result.get("llm_reason", "")
    reason_line = f"\n- 分类依据：{reason}" if reason else ""

    return (
        f"\n\n---\n【意图路由】{label}（{intent}，置信度 {conf:.0%}，{method}）"
        f"{entity_hint}{reason_line}\n{base.strip()}\n"
        f"【用户问题】{user_question[:500]}\n---\n"
    )


def get_response_mode(intent: str) -> str:
    """前端流式展示用的响应模式。"""
    mapping = {
        IntentType.GENERAL_QA.value: "chat",
        IntentType.KNOWLEDGE_QA.value: "knowledge",
        IntentType.OPS_QUERY.value: "ops",
        IntentType.FAULT_ANALYSIS.value: "diagnosis",
        IntentType.HIGH_RISK.value: "risk",
        IntentType.PROMPT_INJECTION.value: "blocked",
    }
    return mapping.get(intent, "chat")
