"""
预执行快照管理 — 逻辑快照 + 环境状态绑定
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.config import settings


class SnapshotManager:
    def __init__(self, session_id: str, trace_id: str, task_id: str = None):
        self.session_id = session_id
        self.trace_id = trace_id
        self.task_id = task_id or f"task-{uuid.uuid4().hex[:10]}"
        self.snapshot_id: Optional[str] = None
        self.created_at: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

    async def create(self, server_id: str = None) -> dict:
        from app.services.human_supervision import run_env_precheck

        env = await run_env_precheck(server_id)
        self.snapshot_id = env.get("snapshot_id") or f"snap-{uuid.uuid4().hex[:10]}"
        self.created_at = datetime.utcnow().isoformat()
        self.metadata = {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "env_checks": env.get("checks", []),
            "passed": env.get("passed", False),
            "note": env.get("snapshot_note", "逻辑快照元数据"),
        }
        return {
            "snapshot_id": self.snapshot_id,
            "task_id": self.task_id,
            "passed": env.get("passed", False),
            "checks": env.get("checks", []),
            "created_at": self.created_at,
        }

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


async def check_disk_space_ok(server_id: str = None, min_pct: float = 10.0) -> dict:
    """磁盘剩余空间预检（≥ min_pct%）。"""
    from app.services.remote_executor import get_ssh_for_server_sync

    try:
        ssh = get_ssh_for_server_sync(server_id)
        out, _, code = ssh.execute("df -P / | tail -1 | awk '{print $5}'")
        if code != 0:
            return {"ok": False, "detail": "无法读取磁盘使用率"}
        pct_str = out.strip().replace("%", "")
        used = float(pct_str) if pct_str.isdigit() else 100.0
        free_pct = 100.0 - used
        return {"ok": free_pct >= min_pct, "free_pct": free_pct, "detail": f"根分区剩余约 {free_pct:.0f}%"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:200]}
