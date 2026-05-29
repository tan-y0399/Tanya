"""上下文可信度管理 —— 信息来源信任级别标记"""

from enum import Enum
from typing import Dict, List, Optional


class CredibilityLevel(Enum):
    TRUSTED = "trusted"       # 系统工具返回、已审核知识库
    NEUTRAL = "neutral"       # 用户输入、对话历史
    UNCERTAIN = "uncertain"   # LLM 推理、未验证数据
    UNTRUSTED = "untrusted"   # 外部 URL、用户提供的代码


CREDIBILITY_LABELS = {
    CredibilityLevel.TRUSTED.value: "可信",
    CredibilityLevel.NEUTRAL.value: "中性",
    CredibilityLevel.UNCERTAIN.value: "不确定",
    CredibilityLevel.UNTRUSTED.value: "不可信",
}

SOURCE_TYPE_MAP = {
    "system_tool": CredibilityLevel.TRUSTED,
    "knowledge_base": CredibilityLevel.TRUSTED,
    "verified_knowledge": CredibilityLevel.TRUSTED,
    "user_input": CredibilityLevel.NEUTRAL,
    "chat_history": CredibilityLevel.NEUTRAL,
    "conversation": CredibilityLevel.NEUTRAL,
    "llm_generated": CredibilityLevel.UNCERTAIN,
    "llm_inference": CredibilityLevel.UNCERTAIN,
    "external_url": CredibilityLevel.UNTRUSTED,
    "user_code": CredibilityLevel.UNTRUSTED,
}


class CredibilityTracker:
    def __init__(self):
        self._annotations: List[dict] = []

    def tag_source(self, source_type: str, source_name: str = "") -> dict:
        level = SOURCE_TYPE_MAP.get(source_type, CredibilityLevel.NEUTRAL)
        annotation = {
            "sourceType": source_type,
            "sourceName": source_name,
            "credibility": level.value,
            "credibilityLabel": CREDIBILITY_LABELS.get(level.value, "未知"),
        }
        self._annotations.append(annotation)
        return annotation

    def annotate_message(self, content: str, sources: List[dict]) -> str:
        if not sources:
            return content

        trusted = [s for s in sources if s.get("credibility") == CredibilityLevel.TRUSTED.value]
        uncertain = [s for s in sources if s.get("credibility") in (CredibilityLevel.UNCERTAIN.value, CredibilityLevel.UNTRUSTED.value)]

        annotations = []
        if uncertain:
            names = [s.get("sourceName", "") for s in uncertain if s.get("sourceName")]
            if names:
                annotations.append(f"[注意：以下信息来自不确定性来源：{', '.join(names)}，请谨慎参考]")

        if annotations:
            return content + "\n\n" + "\n".join(annotations)
        return content

    def get_credibility_summary(self) -> dict:
        levels = {}
        for a in self._annotations:
            lv = a["credibility"]
            levels[lv] = levels.get(lv, 0) + 1

        trusted_count = levels.get(CredibilityLevel.TRUSTED.value, 0)
        untrusted_count = levels.get(CredibilityLevel.UNTRUSTED.value, 0) + levels.get(CredibilityLevel.UNCERTAIN.value, 0)

        return {
            "total_sources": len(self._annotations),
            "trusted": trusted_count,
            "untrusted_or_uncertain": untrusted_count,
            "overall": "high" if trusted_count >= untrusted_count else "low",
            "details": levels,
        }

    def clear(self):
        self._annotations.clear()
