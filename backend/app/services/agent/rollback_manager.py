"""
回滚管理 — 单步回滚与全量快照恢复
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession


class RollbackManager:
    def __init__(self, session_id: str, snapshot_id: str = None):
        self.session_id = session_id
        self.snapshot_id = snapshot_id

    async def get_status(self, db: AsyncSession) -> dict:
        from app.services.human_supervision import get_session_rollback_status
        return await get_session_rollback_status(db, self.session_id)

    async def rollback_step(self, db: AsyncSession, execution_log_id: str = None) -> dict:
        from app.services.human_supervision import run_session_rollback
        return await run_session_rollback(
            db, self.session_id, mode="step", execution_log_id=execution_log_id,
        )

    async def rollback_full(self, db: AsyncSession) -> dict:
        from app.services.human_supervision import run_session_rollback
        return await run_session_rollback(
            db, self.session_id, mode="full", snapshot_id=self.snapshot_id,
        )

    @staticmethod
    async def execute_langgraph_rollback(state: dict, db: AsyncSession) -> dict:
        """LangGraph 节点调用的回滚入口。"""
        session_id = state.get("session_id")
        snapshot_id = state.get("snapshot_id")
        mgr = RollbackManager(session_id, snapshot_id)
        return await mgr.rollback_full(db)
