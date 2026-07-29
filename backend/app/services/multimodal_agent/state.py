"""多模态 Agent 链路状态定义。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class MultimodalAgentState(TypedDict, total=False):
    user_input: str
    user_id: str
    user_role: str
    session_id: str
    trace_id: str
    server_id: Optional[str]
    attachments: List[Dict[str, Any]]
    saved_attachments: List[Dict[str, Any]]
    vision_results: List[Dict[str, Any]]
    rag_result: Dict[str, Any]
    route: Dict[str, Any]
    plan: Optional[Dict[str, Any]]
    final_response: str
    state_cards: List[Dict[str, str]]
    blocked: bool
    block_reason: Optional[str]
