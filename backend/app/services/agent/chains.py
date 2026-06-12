"""
三条链路分发 — 链路 A/B/C 统一抽象
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from app.services.agent_workflow import (
    WorkflowLink,
    resolve_workflow_link,
    get_risk_disposition_table,
    LINK_LABELS,
    LINK_DESCRIPTIONS,
)


class ChainId(str, Enum):
    QA = "link_a"
    LIGHTWEIGHT_REACT = "link_b"
    PLAN_EXECUTE = "link_c"


CHAIN_TO_ROUTE = {
    ChainId.QA.value: "handler_a",
    ChainId.LIGHTWEIGHT_REACT.value: "react_b_light",
    ChainId.PLAN_EXECUTE.value: "react_c_plan",
}


def dispatch_chain(content: str, intent_result: dict) -> Dict[str, Any]:
    """统一链路分流，返回链路元数据 + LangGraph route_path。"""
    wf = resolve_workflow_link(content, intent_result)
    link = wf["link"]
    return {
        **wf,
        "chain_id": link,
        "route_path": CHAIN_TO_ROUTE.get(link, "react_c_plan"),
        "skip_diagnostic_plan": link == ChainId.LIGHTWEIGHT_REACT.value,
        "requires_env_enrich": link == ChainId.PLAN_EXECUTE.value,
        "risk_levels": get_risk_disposition_table(),
    }


def chain_label(chain_id: str) -> str:
    return LINK_LABELS.get(chain_id, chain_id)
