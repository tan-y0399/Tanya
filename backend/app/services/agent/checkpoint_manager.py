"""
断点续传 — 工作流检查点持久化
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskState
from app.services.agent.state_machine import TaskStatus, WorkflowStateMachine


class CheckpointManager:
    @staticmethod
    async def save(
        db: AsyncSession,
        session_id: str,
        trace_id: str,
        user_id: str,
        payload: dict,
        status: str = "interrupted",
    ) -> str:
        task_id = payload.get("task_id") or f"ckpt-{trace_id[:12]}"
        existing = await db.execute(select(TaskState).where(TaskState.id == task_id))
        row = existing.scalar_one_or_none()
        data = json.dumps(payload, ensure_ascii=False, default=str)
        if row:
            row.state = status
            row.steps_json = data
            row.progress = payload.get("progress", 0)
            row.updated_at = datetime.utcnow()
        else:
            row = TaskState(
                id=task_id,
                session_id=session_id,
                trace_id=trace_id,
                user_id=user_id,
                state=status,
                steps_json=data,
                progress=payload.get("progress", 0),
            )
            db.add(row)
        await db.commit()
        return task_id

    @staticmethod
    async def load(db: AsyncSession, checkpoint_id: str) -> Optional[dict]:
        result = await db.execute(select(TaskState).where(TaskState.id == checkpoint_id))
        row = result.scalar_one_or_none()
        if not row or not row.steps_json:
            return None
        try:
            payload = json.loads(row.steps_json)
        except json.JSONDecodeError:
            return None
        return {
            "checkpoint_id": row.id,
            "session_id": row.session_id,
            "trace_id": row.trace_id,
            "user_id": row.user_id,
            "status": row.state,
            "payload": payload,
        }

    @staticmethod
    async def resume(db: AsyncSession, checkpoint_id: str) -> Optional[dict]:
        ckpt = await CheckpointManager.load(db, checkpoint_id)
        if not ckpt:
            return None
        fsm = WorkflowStateMachine()
        fsm.force(TaskStatus.EXECUTING, "checkpoint_resume")
        ckpt["fsm"] = fsm.to_dict()
        return ckpt

    @staticmethod
    def build_payload(
        *,
        workflow_link: str,
        plan_id: str = None,
        snapshot_id: str = None,
        round_count: int = 0,
        tool_calls: list = None,
        messages_snapshot: list = None,
        progress: int = 0,
    ) -> dict:
        return {
            "workflow_link": workflow_link,
            "plan_id": plan_id,
            "snapshot_id": snapshot_id,
            "round_count": round_count,
            "tool_calls": tool_calls or [],
            "messages_snapshot": messages_snapshot,
            "progress": progress,
            "saved_at": datetime.utcnow().isoformat(),
        }
