"""安全流程审计 — 将聊天链路安全防护阶段写入 event_type=workflow。"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditRecord
from app.services.audit_service import _max_risk_from_tools, max_risk_level

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

STAGE_ORDER = (
    "prompt_injection",
    "intent_parsing",
    "context_recheck",
    "route_dispatch",
    "risk_filter",
    "permission_check",
    "execution",
)

STAGE_LABELS = {
    "prompt_injection": "注入检测",
    "intent_parsing": "意图识别",
    "context_recheck": "二次复核",
    "route_dispatch": "路由分发",
    "risk_filter": "风险过滤",
    "permission_check": "权限校验",
    "execution": "执行阶段",
}

TELEMETRY_STEP_STAGE = {
    "1_安全预检": "prompt_injection",
    "2_意图分类+RAG检索(并行)": "intent_parsing",
    "3_注入二次复核": "context_recheck",
    "5_路由分发": "route_dispatch",
    "plan_confirm_resume": "route_dispatch",
}

TELEMETRY_STATUS_MAP = {
    "ok": "passed",
    "error": "failed",
    "warn": "warning",
    "running": "running",
}

_STATUS_PRIORITY = {
    "blocked": 5,
    "failed": 4,
    "pending": 3,
    "warning": 2,
    "passed": 1,
    "running": 0,
}


def _stage_index(stage: str) -> int:
    try:
        return STAGE_ORDER.index(stage)
    except ValueError:
        return len(STAGE_ORDER)


class WorkflowAuditCollector:
    """单次 trace 的安全流程收集器（内存态，出口单次 persist）。"""

    def __init__(
        self,
        trace_id: str,
        session_id: str,
        user_id: str,
        question: str,
    ):
        self.trace_id = trace_id
        self.session_id = session_id
        self.user_id = user_id
        self.question = (question or "").strip()
        self.flow_status = "routing"
        self.link: Optional[str] = None
        self.intent: Optional[str] = None
        self.intent_confidence: Optional[float] = None
        self._stages: Dict[str, dict] = {}
        self._telemetry: Optional[dict] = None
        self._tools: List[dict] = []
        self.approval_id: Optional[str] = None
        self.related_event_types: List[str] = []

    def mark(
        self,
        stage: str,
        status: str,
        *,
        detail: str = "",
        duration_ms: Optional[float] = None,
        risk_level: Optional[str] = None,
        **meta: Any,
    ) -> None:
        if stage not in STAGE_ORDER:
            return
        entry = {
            "stage": stage,
            "status": status,
            "detail": (detail or "")[:300],
        }
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        if risk_level:
            entry["risk_level"] = risk_level
        if meta:
            entry["meta"] = meta
        prev = self._stages.get(stage)
        if prev is None or _STATUS_PRIORITY.get(status, 0) >= _STATUS_PRIORITY.get(prev.get("status", ""), 0):
            self._stages[stage] = entry
        self.flow_status = _flow_status_from_stage(stage, status, self.flow_status)

    def set_route(self, link: str, intent: str, confidence: float) -> None:
        self.link = link
        self.intent = intent
        try:
            self.intent_confidence = float(confidence)
        except (TypeError, ValueError):
            self.intent_confidence = None

    def set_flow_status(self, status: str) -> None:
        self.flow_status = status

    def attach_telemetry(self, telemetry: Any) -> None:
        if telemetry is None:
            return
        if hasattr(telemetry, "to_audit_json"):
            try:
                self._telemetry = json.loads(telemetry.to_audit_json())
            except Exception:
                self._telemetry = None
        elif isinstance(telemetry, dict):
            self._telemetry = telemetry

    def attach_tools(self, tool_call_records: Optional[List[dict]]) -> None:
        if not tool_call_records:
            self._tools = []
            return
        self._tools = [
            {
                "name": tc.get("toolName") or tc.get("name") or "",
                "risk": tc.get("riskLevel") or tc.get("risk") or "L1",
                "status": tc.get("status") or "completed",
            }
            for tc in tool_call_records
            if tc.get("toolName") or tc.get("name")
        ]

    def _merge_telemetry_stages(self) -> List[dict]:
        if not self._telemetry:
            return []
        merged: List[dict] = []
        for step in self._telemetry.get("steps") or []:
            step_name = step.get("step") or ""
            stage = TELEMETRY_STEP_STAGE.get(step_name)
            if not stage or stage in self._stages:
                continue
            status = TELEMETRY_STATUS_MAP.get(step.get("status", "ok"), "passed")
            if status == "failed" and step.get("blocked"):
                status = "blocked"
            detail_parts = []
            if step.get("intent"):
                detail_parts.append(f"intent={step['intent']}")
            if step.get("link"):
                detail_parts.append(f"link={step['link']}")
            if step.get("guard_pass") is not None:
                detail_parts.append("guard_pass" if step["guard_pass"] else "guard_fail")
            if step.get("reason"):
                detail_parts.append(str(step["reason"]))
            merged.append({
                "stage": stage,
                "status": status,
                "detail": " · ".join(detail_parts)[:300],
                "duration_ms": step.get("duration_ms"),
            })
        return merged

    def _infer_tool_stages(self) -> None:
        if not self._tools:
            return
        blocked = any(t.get("status") == "blocked" for t in self._tools)
        pending_approval = any(t.get("status") == "pending_approval" for t in self._tools)
        pending_confirm = any(t.get("status") == "pending_confirm" for t in self._tools)
        completed = any(t.get("status") == "completed" for t in self._tools)
        max_risk = _max_risk_from_tools(
            [{"riskLevel": t.get("risk"), "risk": t.get("risk")} for t in self._tools],
        )
        if "risk_filter" not in self._stages:
            self.mark(
                "risk_filter",
                "blocked" if blocked else "passed",
                detail=f"工具 {len(self._tools)} 个，最高 {max_risk}",
                risk_level=max_risk,
            )
        if pending_approval and "permission_check" not in self._stages:
            self.mark("permission_check", "pending", detail="等待 L4 审批")
        elif "permission_check" not in self._stages and (completed or pending_confirm):
            self.mark("permission_check", "passed", detail="权限与确认检查通过")
        if completed and "execution" not in self._stages:
            names = ", ".join(t["name"] for t in self._tools if t.get("status") == "completed")[:120]
            self.mark("execution", "passed", detail=names or "工具执行完成")

    def build_stages(self) -> List[dict]:
        for item in self._merge_telemetry_stages():
            self._stages[item["stage"]] = item
        self._infer_tool_stages()
        return [self._stages[s] for s in STAGE_ORDER if s in self._stages]

    def build_detail(self) -> dict:
        stages = self.build_stages()
        final_stage = stages[-1]["stage"] if stages else "prompt_injection"
        detail: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "question": self.question[:500],
            "flow_status": self.flow_status,
            "final_stage": final_stage,
            "stages": stages,
            "related_event_types": list(self.related_event_types),
        }
        if self.link:
            detail["link"] = self.link
        if self.intent:
            detail["intent"] = self.intent
        if self.intent_confidence is not None:
            detail["intent_confidence"] = self.intent_confidence
        if self._telemetry:
            detail["telemetry"] = self._telemetry
        if self._tools:
            detail["tools"] = self._tools
        if self.approval_id:
            detail["approval_id"] = self.approval_id
        return detail

    def resolve_risk_level(self) -> str:
        risks = [s.get("risk_level") for s in self.build_stages() if s.get("risk_level")]
        if self._tools:
            risks.append(_max_risk_from_tools(
                [{"riskLevel": t.get("risk"), "risk": t.get("risk")} for t in self._tools],
            ))
        if self.flow_status == "blocked":
            risks.append("L5")
        return max_risk_level(risks) if risks else "L1"

    def build_summary(self) -> str:
        stages = self.build_stages()
        final_stage = stages[-1]["stage"] if stages else "init"
        label = STAGE_LABELS.get(final_stage, final_stage)
        q = self.question[:50] if self.question else "安全流程"
        return f"{label}: {self.flow_status} | {q}"

    async def persist(self, db: AsyncSession) -> None:
        try:
            detail = self.build_detail()
            summary = self.build_summary()
            risk_level = self.resolve_risk_level()
            result = await db.execute(
                select(AuditRecord).where(
                    AuditRecord.trace_id == self.trace_id,
                    AuditRecord.event_type == "workflow",
                ),
            )
            existing = result.scalars().first()
            if existing:
                old = {}
                if existing.detail_json:
                    try:
                        raw = existing.detail_json
                        old = json.loads(raw) if isinstance(raw, str) else (raw or {})
                    except Exception:
                        old = {}
                merged_stages = {s["stage"]: s for s in old.get("stages") or []}
                for s in detail.get("stages") or []:
                    merged_stages[s["stage"]] = s
                detail["stages"] = [merged_stages[k] for k in STAGE_ORDER if k in merged_stages]
                detail["final_stage"] = detail["stages"][-1]["stage"] if detail["stages"] else detail.get("final_stage")
                related = set(old.get("related_event_types") or [])
                related.update(detail.get("related_event_types") or [])
                detail["related_event_types"] = list(related)
                existing.summary = summary
                existing.risk_level = max_risk_level([existing.risk_level, risk_level])
                existing.detail_json = json.dumps(detail, ensure_ascii=False)
                existing.session_id = self.session_id or existing.session_id
                existing.timestamp = datetime.utcnow()
            else:
                db.add(AuditRecord(
                    trace_id=self.trace_id,
                    session_id=self.session_id,
                    user_id=self.user_id,
                    event_type="workflow",
                    summary=summary,
                    risk_level=risk_level,
                    detail_json=json.dumps(detail, ensure_ascii=False),
                    timestamp=datetime.utcnow(),
                ))
            await db.commit()
        except Exception as exc:
            logger.warning("workflow audit persist failed trace=%s: %s", self.trace_id, exc)
            try:
                await db.rollback()
            except Exception:
                pass


def _flow_status_from_stage(stage: str, status: str, current: str) -> str:
    if status == "blocked":
        return "blocked"
    if status == "pending":
        return "pending_approval"
    if status == "failed":
        return "failed"
    if stage == "execution" and status == "passed":
        return "completed"
    return current


async def finalize_workflow_audit(
    db: AsyncSession,
    *,
    trace_id: str,
    session_id: str,
    user_id: str,
    question: str,
    flow_status: str,
    telemetry: Any = None,
    workflow: Optional[dict] = None,
    intent_result: Optional[dict] = None,
    tool_call_records: Optional[List[dict]] = None,
    extra_marks: Optional[List[dict]] = None,
    related_event_types: Optional[List[str]] = None,
    approval_id: Optional[str] = None,
) -> None:
    """从当前请求上下文构建 collector 并落库（供 chat / 拦截出口调用）。"""
    collector = WorkflowAuditCollector(trace_id, session_id, user_id, question)
    collector.set_flow_status(flow_status)
    if workflow:
        collector.set_route(
            workflow.get("link", ""),
            (intent_result or {}).get("intent", ""),
            float((intent_result or {}).get("confidence", 0) or 0),
        )
    elif intent_result:
        collector.intent = intent_result.get("intent")
        try:
            collector.intent_confidence = float(intent_result.get("confidence", 0))
        except (TypeError, ValueError):
            pass
    collector.attach_telemetry(telemetry)
    collector.attach_tools(tool_call_records)
    if approval_id:
        collector.approval_id = approval_id
    if related_event_types:
        collector.related_event_types = list(related_event_types)
    for item in extra_marks or []:
        collector.mark(
            item.get("stage", ""),
            item.get("status", "passed"),
            detail=item.get("detail", ""),
            duration_ms=item.get("duration_ms"),
            risk_level=item.get("risk_level"),
            **(item.get("meta") or {}),
        )
    await collector.persist(db)
