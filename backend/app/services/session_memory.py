"""
会话记忆 — 跨轮上下文追踪

记忆维度:
  1. 当前目标服务器 (server_id)
  2. 当前任务上下文 (task_id, task_type, task_stage)
  3. 最近操作记录 (最近5个操作)
  4. 待审批状态 (pending_approvals)
  5. 查询范围/上下文窗口 (active_context)
  6. 用户偏好 (language, format)
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import update as sql_update


class SessionMemory:
    """每个会话独立的内存空间，跨请求持续"""

    def __init__(self, session_id: str, user_id: str = ""):
        self.session_id = session_id
        self.user_id = user_id

        # 当前目标服务器
        self.current_server: Optional[str] = None
        self.current_server_name: Optional[str] = None

        # 当前任务
        self.current_task_id: Optional[str] = None
        self.current_task_type: Optional[str] = None

        # 最近操作 (最多保留5个)
        self.recent_operations: List[dict] = []

        # 待审批项
        self.pending_approvals: List[dict] = []

        # 查询上下文 (上次查询的服务器/目录/服务名等)
        self.last_query_context: Dict = {}

        # 用户偏好
        self.preferences: Dict = {
            "language": "zh",
            "output_format": "markdown",  # markdown | table | plain
        }

        # 会话统计
        self.total_messages: int = 0
        self.total_tool_calls: int = 0
        self.created_at: str = datetime.utcnow().isoformat()

    # ── 操作追踪 ──
    def record_operation(self, tool_name: str, tool_args: dict,
                         result: dict = None, status: str = "completed"):
        self.recent_operations.append({
            "tool": tool_name,
            "args": {k: str(v)[:50] for k, v in (tool_args or {}).items()},
            "status": status,
            "at": datetime.utcnow().isoformat(),
        })
        if len(self.recent_operations) > 5:
            self.recent_operations = self.recent_operations[-5:]
        self.total_tool_calls += 1

    def get_last_operation(self) -> Optional[dict]:
        return self.recent_operations[-1] if self.recent_operations else None

    def get_recent_tools(self) -> List[str]:
        return [op["tool"] for op in self.recent_operations[-3:]]

    # ── 服务器上下文 ──
    def set_server(self, server_id: str, server_name: str = ""):
        self.current_server = server_id
        self.current_server_name = server_name

    def get_server_context(self) -> dict:
        return {
            "server_id": self.current_server,
            "server_name": self.current_server_name,
        }

    # ── 任务追踪 ──
    def set_task(self, task_id: str, task_type: str = ""):
        self.current_task_id = task_id
        self.current_task_type = task_type

    def clear_task(self):
        self.current_task_id = None
        self.current_task_type = None

    def get_task_context(self) -> dict:
        return {
            "task_id": self.current_task_id,
            "task_type": self.current_task_type,
        }

    # ── 审批追踪 ──
    def add_approval(self, approval_id: str, tool_name: str, risk_level: str):
        self.pending_approvals.append({
            "approval_id": approval_id,
            "tool": tool_name,
            "risk": risk_level,
            "since": datetime.utcnow().isoformat(),
        })

    def remove_approval(self, approval_id: str):
        self.pending_approvals = [a for a in self.pending_approvals
                                   if a["approval_id"] != approval_id]

    def has_pending_approvals(self) -> bool:
        return len(self.pending_approvals) > 0

    # ── 查询上下文 ──
    def set_query_context(self, key: str, value):
        self.last_query_context[key] = value

    def get_query_context(self, key: str, default=None):
        return self.last_query_context.get(key, default)

    # ── 上下文提示词生成 ──
    def build_memory_prompt(self) -> str:
        """生成可嵌入系统提示词的记忆上下文"""
        lines = ["\n[会话记忆]"]

        if self.current_server_name:
            lines.append(f"- 当前目标服务器: {self.current_server_name}")
            if self.current_task_type:
                lines.append(f"- 当前任务: {self.current_task_type}")

        if self.recent_operations:
            recent = self.recent_operations[-3:]
            ops_text = ", ".join(op["tool"] for op in recent)
            lines.append(f"- 最近操作: {ops_text}")

            last = self.get_last_operation()
            if last and last["status"] != "completed":
                lines.append(f"- 最近一次操作「{last['tool']}」状态: {last['status']}")

        if self.pending_approvals:
            lines.append(f"- 待审批: {len(self.pending_approvals)} 项")

        if self.last_query_context:
            ctx_items = [f"{k}={v}" for k, v in self.last_query_context.items()
                        if v and k != "_raw"]
            if ctx_items:
                lines.append(f"- 上次查询上下文: {', '.join(ctx_items[:3])}")

        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    # ── 序列化 ──
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "current_server": self.current_server,
            "current_server_name": self.current_server_name,
            "current_task_id": self.current_task_id,
            "current_task_type": self.current_task_type,
            "recent_operations": self.recent_operations,
            "pending_approvals": self.pending_approvals,
            "last_query_context": self.last_query_context,
            "preferences": self.preferences,
            "total_messages": self.total_messages,
            "total_tool_calls": self.total_tool_calls,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMemory":
        mem = cls(data.get("session_id", ""), data.get("user_id", ""))
        mem.current_server = data.get("current_server")
        mem.current_server_name = data.get("current_server_name")
        mem.current_task_id = data.get("current_task_id")
        mem.current_task_type = data.get("current_task_type")
        mem.recent_operations = data.get("recent_operations", [])
        mem.pending_approvals = data.get("pending_approvals", [])
        mem.last_query_context = data.get("last_query_context", {})
        mem.preferences = data.get("preferences", {})
        mem.total_messages = data.get("total_messages", 0)
        mem.total_tool_calls = data.get("total_tool_calls", 0)
        return mem


# 全局会话内存池 (按 session_id 索引)
_session_memories: Dict[str, SessionMemory] = {}


def get_memory(session_id: str, user_id: str = "") -> SessionMemory:
    if session_id not in _session_memories:
        _session_memories[session_id] = SessionMemory(session_id, user_id)
    return _session_memories[session_id]


def clear_memory(session_id: str):
    _session_memories.pop(session_id, None)
