import json
from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, cast, String
from app.models.audit import AuditRecord
from app.models.user import User
from app.services.user_display import (
    load_users_map,
    max_risk_level,
    user_display_from_row,
)


def _group_key_expr(event_type: Optional[str] = None):
    if event_type == "workflow":
        return AuditRecord.trace_id
    return func.coalesce(AuditRecord.session_id, AuditRecord.trace_id)


def _parse_detail(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _extract_intent(detail: dict) -> str:
    intent = detail.get("intent") or ""
    if intent:
        return intent
    telemetry = detail.get("telemetry") or {}
    for step in telemetry.get("steps") or []:
        if step.get("intent"):
            return step["intent"]
    return ""


def infer_intent_from_question(question: str) -> tuple[str, float]:
    q = (question or "").strip()
    if not q or q in ("(resume)", "[确认执行方案]"):
        return "", 0.0
    try:
        from app.services.intent_classifier import classify_sync
        result = classify_sync(q)
        return result.get("intent", ""), float(result.get("confidence", 0))
    except Exception:
        return "", 0.0


async def _load_supervision_intent(
    db: AsyncSession, trace_id: str, session_id: str, plan_id: Optional[str] = None,
) -> str:
    from app.models.supervision import SupervisionPlan
    try:
        if plan_id:
            result = await db.execute(
                select(SupervisionPlan.intent).where(SupervisionPlan.id == plan_id).limit(1)
            )
            intent = result.scalar_one_or_none()
            if intent:
                return intent
        if trace_id:
            result = await db.execute(
                select(SupervisionPlan.intent)
                .where(SupervisionPlan.trace_id == trace_id)
                .order_by(desc(SupervisionPlan.created_at))
                .limit(1)
            )
            intent = result.scalar_one_or_none()
            if intent:
                return intent
        if session_id:
            result = await db.execute(
                select(SupervisionPlan.intent)
                .where(SupervisionPlan.session_id == session_id)
                .order_by(desc(SupervisionPlan.created_at))
                .limit(1)
            )
            return result.scalar_one_or_none() or ""
    except Exception:
        pass
    return ""


async def compute_trace_duration_ms(
    db: AsyncSession, trace_id: str, session_id: Optional[str] = None,
) -> Optional[float]:
    from app.models.session import Message
    try:
        q = select(func.min(Message.created_at), func.max(Message.created_at)).where(
            Message.trace_id == trace_id,
        )
        if session_id:
            q = q.where(Message.session_id == session_id)
        result = await db.execute(q)
        row = result.one_or_none()
        if not row or not row[0] or not row[1]:
            return None
        delta_ms = (row[1] - row[0]).total_seconds() * 1000
        return round(max(delta_ms, 0), 1)
    except Exception:
        return None


async def enrich_audit_detail_meta(
    db: AsyncSession,
    detail: dict,
    *,
    trace_id: str,
    session_id: Optional[str] = None,
) -> dict:
    """补全 intent / total_ms，供回放与详情展示。"""
    enriched = dict(detail or {})
    question = (enriched.get("question") or "").strip()

    intent = _extract_intent(enriched)
    if not intent:
        intent = await _load_supervision_intent(
            db, trace_id, session_id or "", enriched.get("plan_id"),
        )
    if not intent and question:
        intent, conf = infer_intent_from_question(question)
        if conf and not enriched.get("intent_confidence"):
            enriched["intent_confidence"] = conf
    if intent:
        enriched["intent"] = intent

    telemetry = dict(enriched.get("telemetry") or {})
    if telemetry.get("total_ms") is None:
        duration = await compute_trace_duration_ms(db, trace_id, session_id)
        if duration is not None and duration > 0:
            telemetry["total_ms"] = duration
    if telemetry.get("total_ms") is None:
        step_sum = sum(float(s.get("duration_ms") or 0) for s in (telemetry.get("steps") or []))
        if step_sum > 0:
            telemetry["total_ms"] = round(step_sum, 1)
    if telemetry.get("total_ms") is not None:
        enriched["telemetry"] = telemetry

    return enriched


def _tool_records_to_audit_tools(tool_call_records: list) -> list:
    return [
        {
            "name": tc.get("toolName") or tc.get("name"),
            "status": tc.get("status"),
            "risk": tc.get("riskLevel") or tc.get("risk"),
        }
        for tc in (tool_call_records or [])
        if tc.get("toolName") or tc.get("name")
    ]


def _max_risk_from_tools(tool_call_records: list) -> str:
    risks = [tc.get("riskLevel") or tc.get("risk") or "L1" for tc in (tool_call_records or [])]
    return max_risk_level(risks) if risks else "L1"


async def upsert_chat_audit_record(
    db: AsyncSession,
    *,
    trace_id: str,
    session_id: str,
    user_id: str,
    question: str,
    answer: str = "",
    tool_call_records: Optional[list] = None,
    telemetry=None,
    event_type: str = "chat",
    flow_status: str = "completed",
    plan_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    intent: Optional[str] = None,
    intent_confidence: Optional[float] = None,
    sync_workflow: bool = True,
    workflow_link: Optional[str] = None,
) -> None:
    """写入或更新对话审计（同一 trace 续跑时合并工具与结论）。"""
    import logging
    logger = logging.getLogger(__name__)
    try:
        tools_payload = _tool_records_to_audit_tools(tool_call_records or [])
        tools_used = list({t["name"] for t in tools_payload if t.get("name")})
        max_risk = _max_risk_from_tools(tool_call_records or [])

        telemetry_data = None
        if telemetry is not None:
            if hasattr(telemetry, "to_audit_json"):
                telemetry_data = json.loads(telemetry.to_audit_json())
            elif isinstance(telemetry, dict):
                telemetry_data = telemetry
            elif isinstance(telemetry, str):
                try:
                    telemetry_data = json.loads(telemetry)
                except Exception:
                    telemetry_data = None

        q = (question or "").strip()
        summary = q[:100] if q else "Agent 对话"
        if tools_used:
            summary = "调用 {} | {}".format(",".join(tools_used), (q or summary)[:60])

        detail = {
            "question": q[:500],
            "answer": (answer or "")[:3000],
            "tools": tools_payload,
            "flow_status": flow_status,
            "telemetry": telemetry_data,
        }
        if plan_id:
            detail["plan_id"] = plan_id
        if intent:
            detail["intent"] = intent
        if intent_confidence is not None:
            detail["intent_confidence"] = intent_confidence

        result = await db.execute(select(AuditRecord).where(AuditRecord.trace_id == trace_id))
        existing = result.scalars().first()
        if existing:
            old_detail = _parse_detail(existing.detail_json)
            merged_tools = {t.get("name"): t for t in old_detail.get("tools") or []}
            for t in tools_payload:
                if t.get("name"):
                    merged_tools[t["name"]] = t
            detail["tools"] = list(merged_tools.values())
            if not detail["question"]:
                detail["question"] = old_detail.get("question", "")
            if not detail.get("intent") and old_detail.get("intent"):
                detail["intent"] = old_detail["intent"]
            if detail.get("intent_confidence") is None and old_detail.get("intent_confidence") is not None:
                detail["intent_confidence"] = old_detail["intent_confidence"]
            if telemetry_data is None and old_detail.get("telemetry"):
                detail["telemetry"] = old_detail["telemetry"]
            elif telemetry_data is not None and old_detail.get("telemetry"):
                old_telemetry = old_detail["telemetry"]
                merged_telemetry = dict(old_telemetry)
                merged_telemetry.update({k: v for k, v in telemetry_data.items() if v is not None})
                if merged_telemetry.get("total_ms") is None:
                    merged_telemetry["total_ms"] = old_telemetry.get("total_ms")
                detail["telemetry"] = merged_telemetry
            old_answer = old_detail.get("answer", "")
            if not detail["answer"]:
                detail["answer"] = old_answer
            elif old_answer and detail["answer"] not in old_answer:
                detail["answer"] = (old_answer + "\n---\n" + detail["answer"])[:3000]
            existing.detail_json = json.dumps(detail, ensure_ascii=False)
            existing.summary = summary
            existing.risk_level = max_risk_level([existing.risk_level, max_risk])
            existing.event_type = event_type
            existing.session_id = session_id or existing.session_id
            if timestamp is not None:
                existing.timestamp = timestamp
        else:
            db.add(AuditRecord(
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                event_type=event_type,
                summary=summary,
                risk_level=max_risk,
                detail_json=json.dumps(detail, ensure_ascii=False),
                timestamp=timestamp or datetime.utcnow(),
            ))
        await db.commit()
        if sync_workflow:
            from app.services.workflow_audit import finalize_workflow_audit
            workflow = {"link": workflow_link} if workflow_link else None
            intent_result = None
            if intent or intent_confidence is not None:
                intent_result = {
                    "intent": intent or "",
                    "confidence": intent_confidence if intent_confidence is not None else 0,
                }
            await finalize_workflow_audit(
                db,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                question=question,
                flow_status=flow_status,
                telemetry=telemetry,
                workflow=workflow,
                intent_result=intent_result,
                tool_call_records=tool_call_records,
                related_event_types=["chat"],
            )
    except Exception as exc:
        logger.warning("upsert_chat_audit_record failed trace=%s: %s", trace_id, exc)
        try:
            await db.rollback()
        except Exception:
            pass


def _record_group_key(record: AuditRecord) -> str:
    return record.session_id or record.trace_id


def _infer_workflow_link(detail: dict, intent: str) -> str:
    link = detail.get("link")
    if link in ("link_a", "link_b", "link_c"):
        return link
    if intent in ("general_qa", "knowledge_qa"):
        return "link_a"
    if intent in ("fault_analysis", "high_risk"):
        return "link_c"
    return "link_b"


async def _user_ids_for_username(db: AsyncSession, username: str) -> List[str]:
    kw = f"%{username.strip()}%"
    result = await db.execute(select(User.id).where(User.username.ilike(kw)))
    return [row[0] for row in result.all()]


def _build_conditions(
    event_type: Optional[str],
    risk_level: Optional[str],
    trace_id: Optional[str],
    keyword: Optional[str],
    start_time: Optional[str],
    end_time: Optional[str],
    user_ids: Optional[List[str]] = None,
):
    conditions = []
    if user_ids is not None:
        if not user_ids:
            return None
        conditions.append(AuditRecord.user_id.in_(user_ids))
    if event_type:
        conditions.append(AuditRecord.event_type == event_type)
    if risk_level:
        conditions.append(AuditRecord.risk_level == risk_level)
    if trace_id:
        conditions.append(AuditRecord.trace_id.ilike(f"%{trace_id}%"))
    if keyword:
        kw = f"%{keyword.strip()}%"
        conditions.append(or_(
            AuditRecord.summary.ilike(kw),
            AuditRecord.trace_id.ilike(kw),
            cast(AuditRecord.detail_json, String).ilike(kw),
        ))
    if start_time:
        conditions.append(AuditRecord.timestamp >= start_time)
    if end_time:
        conditions.append(AuditRecord.timestamp <= end_time)
    return conditions


async def _fetch_group_records(
    db: AsyncSession, group_key: str, event_type: Optional[str] = None,
) -> List[AuditRecord]:
    result = await db.execute(
        select(AuditRecord)
        .where(_group_key_expr(event_type) == group_key)
        .order_by(AuditRecord.timestamp)
    )
    return list(result.scalars().all())


def _summarize_group(rows: List[AuditRecord], users_map: dict) -> dict:
    if not rows:
        return {}
    first = rows[0]
    latest = rows[-1]
    first_detail = _parse_detail(first.detail_json)
    latest_detail = _parse_detail(latest.detail_json)
    latest_telemetry = latest_detail.get("telemetry") or {}

    intent = _extract_intent(latest_detail)
    if not intent:
        q = (first_detail.get("question") or "").strip()
        if q and q not in ("(resume)", "[确认执行方案]"):
            intent, _ = infer_intent_from_question(q)

    total_ms = latest_telemetry.get("total_ms")
    if total_ms is None and first.timestamp and latest.timestamp:
        total_ms = round((latest.timestamp - first.timestamp).total_seconds() * 1000, 1)

    tool_count = 0
    for r in rows:
        tool_count += len((_parse_detail(r.detail_json).get("tools") or []))

    summary = (first_detail.get("question") or first.summary or latest.summary or "").strip()
    if len(rows) > 1 and summary:
        summary = summary[:120]

    user = users_map.get(latest.user_id)
    user_info = user_display_from_row(user, latest.user_id)
    group_key = _record_group_key(latest)

    item = {
        "id": group_key,
        "traceId": latest.trace_id,
        "sessionId": latest.session_id,
        **user_info,
        "eventType": latest.event_type,
        "summary": summary,
        "riskLevel": max_risk_level(r.risk_level for r in rows),
        "timestamp": latest.timestamp.isoformat() if latest.timestamp else "",
        "startedAt": first.timestamp.isoformat() if first.timestamp else "",
        "toolCount": tool_count,
        "totalMs": total_ms,
        "intent": intent,
        "turnCount": len(rows),
        "traceIds": [r.trace_id for r in rows],
    }

    workflow_row = next((r for r in reversed(rows) if r.event_type == "workflow"), None)
    if workflow_row is None and latest.event_type == "workflow":
        workflow_row = latest
    if workflow_row:
        wd = _parse_detail(workflow_row.detail_json)
        item["workflowLink"] = _infer_workflow_link(wd, intent)
        item["flowStatus"] = wd.get("flow_status") or ""
        item["workflowStages"] = wd.get("stages") or []
        item["workflowQuestion"] = (wd.get("question") or summary or "").strip()

    return item


async def _count_groups(db: AsyncSession, conditions: list, event_type: Optional[str] = None) -> int:
    groups_q = select(_group_key_expr(event_type).label("gk")).select_from(AuditRecord)
    if conditions:
        groups_q = groups_q.where(*conditions)
    groups_q = groups_q.group_by(_group_key_expr(event_type))
    sub = groups_q.subquery()
    result = await db.execute(select(func.count()).select_from(sub))
    return result.scalar() or 0


async def _list_group_keys(
    db: AsyncSession, conditions: list, page: int, size: int,
    event_type: Optional[str] = None,
) -> List[tuple]:
    groups_q = (
        select(
            _group_key_expr(event_type).label("gk"),
            func.max(AuditRecord.timestamp).label("latest_ts"),
        )
        .select_from(AuditRecord)
    )
    if conditions:
        groups_q = groups_q.where(*conditions)
    groups_q = groups_q.group_by(_group_key_expr(event_type)).order_by(desc("latest_ts"))
    result = await db.execute(groups_q.offset((page - 1) * size).limit(size))
    return result.all()


async def get_audit_stats(db: AsyncSession) -> dict:
    total = await _count_groups(db, [])

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today = await _count_groups(db, [AuditRecord.timestamp >= today_start])

    l3_plus = await _count_groups(db, [AuditRecord.risk_level.in_(["L3", "L4", "L5"])])

    blocked = await _count_groups(db, [
        or_(AuditRecord.event_type == "blocked_injection", AuditRecord.risk_level == "L5")
    ])

    by_event_type = {}
    for et in ("chat", "chat_resume", "blocked_injection", "workflow"):
        by_event_type[et] = await _count_groups(
            db, [AuditRecord.event_type == et], event_type=et,
        )

    return {
        "total": total,
        "today": today,
        "l3Plus": l3_plus,
        "blocked": blocked,
        "byEventType": by_event_type,
    }


async def get_audit_records(
    db: AsyncSession, page: int = 1, size: int = 20,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    event_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    trace_id: Optional[str] = None,
    keyword: Optional[str] = None,
) -> dict:
    user_ids = None
    if username:
        user_ids = await _user_ids_for_username(db, username)
    elif user_id:
        matched = await _user_ids_for_username(db, user_id)
        user_ids = matched if matched else [user_id]

    conditions = _build_conditions(
        event_type, risk_level, trace_id, keyword, start_time, end_time, user_ids,
    )
    if conditions is None:
        return {"items": [], "total": 0, "page": page, "size": size}

    total = await _count_groups(db, conditions, event_type)
    group_rows = await _list_group_keys(db, conditions, page, size, event_type)

    all_user_refs = set()
    group_records: List[tuple] = []
    for gk, _ in group_rows:
        rows = await _fetch_group_records(db, gk, event_type)
        group_records.append((gk, rows))
        for r in rows:
            all_user_refs.add(r.user_id)

    users_map = await load_users_map(db, all_user_refs)

    items = []
    for _, rows in group_records:
        item = _summarize_group(rows, users_map)
        if item:
            items.append(item)

    return {"items": items, "total": total, "page": page, "size": size}


def _build_turn_event(record: AuditRecord, seq: int) -> dict:
    detail = _parse_detail(record.detail_json)
    return {
        "sequence": seq,
        "traceId": record.trace_id,
        "timestamp": record.timestamp.isoformat() if record.timestamp else "",
        "eventType": record.event_type,
        "summary": record.summary,
        "riskLevel": record.risk_level,
        "question": detail.get("question", ""),
        "answer": detail.get("answer", ""),
        "tools": detail.get("tools") or [],
        "telemetry": detail.get("telemetry") or {},
        "intent": _extract_intent(detail),
        "data": detail,
    }


async def get_audit_detail(db: AsyncSession, ref_id: str) -> Optional[dict]:
    """按会话 ID 或 TraceId 获取详情（会话内多轮合并）。"""
    rows = await _fetch_group_records(db, ref_id)
    if not rows:
        result = await db.execute(
            select(AuditRecord).where(AuditRecord.trace_id == ref_id).order_by(AuditRecord.timestamp)
        )
        rows = list(result.scalars().all())
    if not rows:
        return None

    users_map = await load_users_map(db, {r.user_id for r in rows})
    latest = rows[-1]
    user_info = user_display_from_row(users_map.get(latest.user_id), latest.user_id)
    turns = [_build_turn_event(r, i + 1) for i, r in enumerate(rows)]
    latest_turn = turns[-1]

    enriched_detail = await enrich_audit_detail_meta(
        db,
        _parse_detail(latest.detail_json),
        trace_id=latest.trace_id,
        session_id=latest.session_id,
    )
    enriched_telemetry = enriched_detail.get("telemetry") or {}
    enriched_intent = _extract_intent(enriched_detail)
    total_ms = enriched_telemetry.get("total_ms")
    if total_ms is None and len(rows) > 1 and rows[0].timestamp and latest.timestamp:
        total_ms = round((latest.timestamp - rows[0].timestamp).total_seconds() * 1000, 1)
        if total_ms > 0:
            enriched_telemetry = {**enriched_telemetry, "total_ms": total_ms}

    return {
        "id": _record_group_key(latest),
        "traceId": latest.trace_id,
        "sessionId": latest.session_id,
        **user_info,
        "eventType": latest.event_type,
        "summary": turns[0].get("question") or latest.summary,
        "riskLevel": max_risk_level(r.risk_level for r in rows),
        "timestamp": latest.timestamp.isoformat() if latest.timestamp else "",
        "startedAt": rows[0].timestamp.isoformat() if rows[0].timestamp else "",
        "question": enriched_detail.get("question") or latest_turn.get("question", ""),
        "answer": enriched_detail.get("answer") or latest_turn.get("answer", ""),
        "tools": enriched_detail.get("tools") or latest_turn.get("tools") or [],
        "telemetry": enriched_telemetry,
        "intent": enriched_intent,
        "totalMs": enriched_telemetry.get("total_ms"),
        "turnCount": len(turns),
        "turns": turns,
        "traceIds": [r.trace_id for r in rows],
        "events": turns,
    }


async def create_audit_record(db: AsyncSession, **kwargs) -> AuditRecord:
    detail = kwargs.pop("detail", None)
    record = AuditRecord(**kwargs)
    if detail:
        record.detail_json = json.dumps(detail, ensure_ascii=False)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record
