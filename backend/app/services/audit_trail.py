"""
审计追踪增强 — 完整记录、链路回放、结构化分析

每一条审计记录包含:
  - 用户输入原文
  - 推理过程 (LLM 思考阶段)
  - 环境感知快照 (当时的系统状态)
  - 安全校验细节 (每个检查项的结果)
  - 工具调用参数与返回值
  - 最终响应摘要
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.audit import AuditRecord


class AuditTrail:
    """审计追踪 — 在请求处理过程中收集完整的审计信息"""

    def __init__(self, trace_id: str, session_id: str, user_id: str):
        self.trace_id = trace_id
        self.session_id = session_id
        self.user_id = user_id
        self.started_at = datetime.utcnow()

        # 收集各阶段信息
        self.user_input: str = ""
        self.user_input_sanitized: str = ""
        self.intent_result: dict = {}
        self.security_checks: List[dict] = []
        self.env_snapshot: dict = {}
        self.tool_calls: List[dict] = []
        self.llm_response_summary: str = ""
        self.final_status: str = "unknown"
        self.errors: List[str] = []

    def record_input(self, original: str, sanitized: str = ""):
        self.user_input = original[:500]
        self.user_input_sanitized = sanitized[:500]

    def record_intent(self, intent_result: dict):
        self.intent_result = {
            "intent": intent_result.get("intent"),
            "confidence": intent_result.get("confidence"),
            "method": intent_result.get("method"),
            "entities": intent_result.get("entities", {}),
        }

    def record_security(self, check_name: str, result: dict):
        self.security_checks.append({
            "check": check_name,
            "passed": result.get("pass", result.get("is_injection", True) is False),
            "severity": result.get("severity", "none"),
            "detail": str(result.get("reason", result.get("block_reason", "")))[:200],
        })

    def record_env_snapshot(self, snapshot: dict):
        self.env_snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                k: v.get("data", {}) if isinstance(v, dict) and v.get("success") else str(v)[:100]
                for k, v in (snapshot.get("metrics", {}) or {}).items()
            },
        }

    def record_tool_call(self, tool_name: str, args: dict, result: dict, risk: str, status: str):
        self.tool_calls.append({
            "tool": tool_name,
            "args": {k: str(v)[:100] for k, v in (args or {}).items()},
            "result_summary": str(result.get("data", result.get("error", "")))[:200] if isinstance(result, dict) else str(result)[:200],
            "risk": risk,
            "status": status,
            "at": datetime.utcnow().isoformat(),
        })

    def record_response(self, summary: str, status: str):
        self.llm_response_summary = summary[:300]
        self.final_status = status

    def record_error(self, error: str):
        self.errors.append({"error": error[:300], "at": datetime.utcnow().isoformat()})

    def build_detail(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "duration_seconds": round((datetime.utcnow() - self.started_at).total_seconds(), 2),

            "input": {
                "original": self.user_input,
                "sanitized": self.user_input_sanitized,
            },
            "intent": self.intent_result,
            "security_checks": self.security_checks,
            "environment_snapshot": self.env_snapshot,
            "tool_calls": self.tool_calls,
            "response": {
                "summary": self.llm_response_summary,
                "status": self.final_status,
            },
            "errors": self.errors,
        }

    def get_risk_level(self) -> str:
        if not self.tool_calls:
            return "L1"
        risks = [tc.get("risk", "L1") for tc in self.tool_calls]
        for level in ["L5", "L4", "L3", "L2", "L1"]:
            if level in risks:
                return level
        return "L1"

    async def persist(self, db: AsyncSession):
        detail = self.build_detail()
        record = AuditRecord(
            trace_id=self.trace_id,
            session_id=self.session_id,
            user_id=self.user_id,
            event_type="chat_full",
            summary=self.user_input[:100] or self.llm_response_summary[:100],
            risk_level=self.get_risk_level(),
            detail_json=json.dumps(detail, ensure_ascii=False, default=str),
        )
        db.add(record)
        await db.commit()

    def to_playback(self) -> dict:
        """生成可回放的审计链路"""
        events = [
            {"stage": "input", "data": {"content": self.user_input}, "at": self.started_at.isoformat()},
            {"stage": "intent", "data": self.intent_result},
        ]
        for check in self.security_checks:
            events.append({"stage": "security", "data": check})
        if self.env_snapshot:
            events.append({"stage": "env_snapshot", "data": self.env_snapshot})
        for tc in self.tool_calls:
            events.append({"stage": "tool_call", "data": tc})
        events.append({"stage": "response", "data": {"summary": self.llm_response_summary, "status": self.final_status}})
        for err in self.errors:
            events.append({"stage": "error", "data": err})

        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "total_events": len(events),
            "events": events,
        }


async def get_trace_history(db: AsyncSession, session_id: str, limit: int = 20) -> List[dict]:
    result = await db.execute(
        select(AuditRecord)
        .where(AuditRecord.session_id == session_id)
        .order_by(AuditRecord.timestamp.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    traces = []
    for r in records:
        detail = {}
        if r.detail_json:
            try:
                detail = json.loads(r.detail_json)
            except Exception:
                pass
        traces.append({
            "id": r.id, "traceId": r.trace_id, "eventType": r.event_type,
            "summary": r.summary, "riskLevel": r.risk_level,
            "timestamp": r.timestamp.isoformat() if r.timestamp else "",
            "detail": detail,
        })
    return traces


async def get_trace_playback(db: AsyncSession, trace_id: str) -> Optional[dict]:
    result = await db.execute(
        select(AuditRecord).where(AuditRecord.trace_id == trace_id))
    record = result.scalar_one_or_none()
    if not record:
        return None
    detail = {}
    if record.detail_json:
        try:
            detail = json.loads(record.detail_json)
        except Exception:
            pass
    return {
        "traceId": record.trace_id,
        "sessionId": record.session_id,
        "userId": record.user_id,
        "eventType": record.event_type,
        "summary": record.summary,
        "riskLevel": record.risk_level,
        "timestamp": record.timestamp.isoformat() if record.timestamp else "",
        "detail": detail,
    }
