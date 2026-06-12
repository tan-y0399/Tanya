#!/usr/bin/env python3
"""
从 messages 表回填缺失的 audit_records（诊断方案流等未写审计的历史会话）。

用法:
  cd backend && .venv_linux/bin/python scripts/backfill_audit_from_messages.py --dry-run
  cd backend && .venv_linux/bin/python scripts/backfill_audit_from_messages.py
  cd backend && .venv_linux/bin/python scripts/backfill_audit_from_messages.py --trace trace-20260606T103526-d674d3c4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select, text  # noqa: E402
from app.core.database import async_session, engine  # noqa: E402
from app.models.session import Message, Session  # noqa: E402
from app.models.audit import AuditRecord  # noqa: E402
from app.services.audit_service import (  # noqa: E402
    upsert_chat_audit_record,
    infer_intent_from_question,
    enrich_audit_detail_meta,
    compute_trace_duration_ms,
)


def _infer_flow_status(answer: str, tool_records: list) -> str:
    a = (answer or "").strip()
    if "请在下方确认后开始执行" in a or "已生成运维诊断方案" in a:
        return "awaiting_plan_confirm"
    pending = {r.get("status") for r in (tool_records or [])}
    if "pending_approval" in pending:
        return "awaiting_approval"
    if "pending_confirm" in pending:
        return "awaiting_user_action"
    if "executing" in pending:
        return "executing"
    if any(s in pending for s in ("failed", "blocked", "rejected")):
        return "plan_interrupted"
    return "completed"


async def find_traces_to_backfill(
    db, trace_filter: str | None = None, *, missing_only: bool = True,
) -> list[dict]:
    """返回有 user 消息但无 audit_records 的 trace 列表。"""
    sql = """
        SELECT m.trace_id,
               m.session_id,
               s.user_id,
               MIN(m.created_at) AS first_at,
               MAX(m.created_at) AS last_at,
               COUNT(*) AS msg_count
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE m.trace_id IS NOT NULL
          AND m.trace_id != ''
          AND EXISTS (
              SELECT 1 FROM messages u
              WHERE u.trace_id = m.trace_id AND u.role = 'user'
          )
    """
    if missing_only:
        sql += """
          AND NOT EXISTS (
              SELECT 1 FROM audit_records a WHERE a.trace_id = m.trace_id
          )
        """
    params: dict = {}
    if trace_filter:
        sql += " AND m.trace_id = :trace_id"
        params["trace_id"] = trace_filter
    sql += " GROUP BY m.trace_id, m.session_id, s.user_id ORDER BY last_at DESC"

    result = await db.execute(text(sql), params)
    rows = []
    for row in result.all():
        rows.append({
            "trace_id": row[0],
            "session_id": row[1],
            "user_id": row[2],
            "first_at": row[3],
            "last_at": row[4],
            "msg_count": row[5],
        })
    return rows


async def load_trace_context(db, trace_id: str, session_id: str) -> dict:
    result = await db.execute(
        select(Message)
        .where(Message.trace_id == trace_id, Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    question = ""
    answer = ""
    tool_records: list = []

    for m in messages:
        if m.role == "user" and not question:
            content = (m.content or "").strip()
            if content and content != "[确认执行方案]":
                question = content
        elif m.role == "assistant" and (m.content or "").strip():
            answer = (m.content or "").strip()
        elif m.role == "tool_call" and m.tool_calls_json:
            try:
                recs = json.loads(m.tool_calls_json)
                if isinstance(recs, list):
                    tool_records = recs
            except Exception:
                pass

    if not question:
        for m in messages:
            if m.role == "user" and (m.content or "").strip():
                question = (m.content or "").strip()
                break

    return {
        "question": question,
        "answer": answer,
        "tool_records": tool_records,
        "flow_status": _infer_flow_status(answer, tool_records),
    }


async def backfill_one(db, item: dict, dry_run: bool) -> dict:
    ctx = await load_trace_context(db, item["trace_id"], item["session_id"])
    intent, intent_conf = infer_intent_from_question(ctx["question"])
    duration_ms = await compute_trace_duration_ms(db, item["trace_id"], item["session_id"])
    telemetry = {"total_ms": duration_ms} if duration_ms is not None else None
    if dry_run:
        return {**item, **ctx, "intent": intent, "duration_ms": duration_ms, "action": "would_upsert"}

    await upsert_chat_audit_record(
        db,
        trace_id=item["trace_id"],
        session_id=item["session_id"],
        user_id=item["user_id"],
        question=ctx["question"],
        answer=ctx["answer"],
        tool_call_records=ctx["tool_records"],
        flow_status=ctx["flow_status"],
        timestamp=item.get("last_at"),
        intent=intent or None,
        intent_confidence=intent_conf or None,
        telemetry=telemetry,
    )
    return {**item, **ctx, "intent": intent, "duration_ms": duration_ms, "action": "upserted"}


async def enrich_existing(db, trace_filter: str | None = None) -> int:
    """为已有 audit 记录补全 intent / total_ms 并写回数据库。"""
    from app.models.audit import AuditRecord
    q = select(AuditRecord).order_by(AuditRecord.timestamp.desc())
    if trace_filter:
        q = q.where(AuditRecord.trace_id == trace_filter)
    result = await db.execute(q)
    rows = result.scalars().all()
    updated = 0
    for row in rows:
        detail = row.detail_json if isinstance(row.detail_json, dict) else {}
        if isinstance(row.detail_json, str):
            try:
                detail = json.loads(row.detail_json)
            except Exception:
                detail = {}
        enriched = await enrich_audit_detail_meta(
            db, detail, trace_id=row.trace_id, session_id=row.session_id,
        )
        if enriched != detail:
            row.detail_json = json.dumps(enriched, ensure_ascii=False)
            updated += 1
    if updated:
        await db.commit()
    return updated


async def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing audit_records from messages")
    parser.add_argument("--dry-run", action="store_true", help="Only report, do not write")
    parser.add_argument("--trace", type=str, default=None, help="Only backfill one trace_id")
    parser.add_argument(
        "--fix-timestamps",
        action="store_true",
        help="Re-upsert all user-message traces (fix timestamp on existing audits)",
    )
    parser.add_argument(
        "--enrich-meta",
        action="store_true",
        help="Backfill intent/total_ms on existing audit_records",
    )
    args = parser.parse_args()

    async with async_session() as db:
        if args.enrich_meta:
            count = await enrich_existing(db, args.trace)
            print(f"Enriched audit meta on {count} records")
            await engine.dispose()
            return 0

        missing = await find_traces_to_backfill(
            db, args.trace, missing_only=not args.fix_timestamps,
        )
        label = "Traces to process" if args.fix_timestamps else "Missing audit traces"
        print(f"{label}: {len(missing)}")
        if not missing:
            return 0

        for item in missing:
            out = await backfill_one(db, item, args.dry_run)
            tools = [t.get("toolName") for t in out.get("tool_records") or [] if t.get("toolName")]
            print(
                f"  [{out['action']}] {out['trace_id']} | "
                f"user={out['user_id']} | {out['last_at']} | "
                f"intent={out.get('intent')} | ms={out.get('duration_ms')} | "
                f"status={out['flow_status']} | tools={tools} | "
                f"Q={out['question'][:40]!r}"
            )

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
