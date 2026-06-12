"""
规范化的 Agent SSE 流式事件 — 统一 phase / token 载荷，便于前端分阶段展示。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional


# 响应阶段（与前端展示一一对应）
PHASE_INTENT = "intent"       # 意图已识别
PHASE_PLAN = "plan"           # 规划/说明将要做什么
PHASE_EXECUTE = "execute"     # 工具执行中
PHASE_ANSWER = "answer"       # 正文流式输出
PHASE_SUMMARY = "summary"     # 最终结论生成


def sse(event: str, data: Any) -> dict:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False, default=str)}


def intent_resolved(intent_result: dict, response_mode: str) -> dict:
    meta = intent_result.get("metadata") or {}
    return sse("intent_resolved", {
        "intent": intent_result.get("intent"),
        "label": meta.get("label", intent_result.get("intent")),
        "confidence": intent_result.get("confidence", 0),
        "method": intent_result.get("method", "keyword"),
        "responseMode": response_mode,
        "entities": intent_result.get("entities") or {},
        "matchedKeywords": (intent_result.get("matched_keywords") or [])[:8],
    })


def response_phase(phase: str, message: str = "", detail: str = "") -> dict:
    return sse("response_phase", {
        "phase": phase,
        "message": message,
        "detail": detail or message,
    })


def stream_token(token: str, phase: str = PHASE_ANSWER) -> dict:
    """带阶段的 token 事件（phase 可选，旧客户端仅读 token 字段仍兼容）。"""
    return sse("token", {"token": token, "phase": phase})
