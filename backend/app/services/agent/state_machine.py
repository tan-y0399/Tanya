"""
统一全流程状态机 — 规范多轮中断与恢复
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Set


class TaskStatus(str, Enum):
    PENDING = "pending"
    SECURITY_BLOCKED = "security_blocked"
    ROUTING = "routing"
    AWAITING_PLAN_CONFIRM = "awaiting_plan_confirm"
    ENV_PRECHECK = "env_precheck"
    EXECUTING = "executing"
    AWAITING_CONFIRM = "awaiting_confirm"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_USER_RUN = "awaiting_user_run"
    ROLLING_BACK = "rolling_back"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


# 合法状态转移表
TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.ROUTING, TaskStatus.SECURITY_BLOCKED},
    TaskStatus.ROUTING: {
        TaskStatus.EXECUTING, TaskStatus.AWAITING_PLAN_CONFIRM,
        TaskStatus.SUMMARIZING, TaskStatus.COMPLETED,
    },
    TaskStatus.AWAITING_PLAN_CONFIRM: {
        TaskStatus.ENV_PRECHECK, TaskStatus.CANCELLED, TaskStatus.INTERRUPTED,
    },
    TaskStatus.ENV_PRECHECK: {TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.EXECUTING: {
        TaskStatus.AWAITING_CONFIRM, TaskStatus.AWAITING_APPROVAL,
        TaskStatus.AWAITING_USER_RUN, TaskStatus.SUMMARIZING,
        TaskStatus.INTERRUPTED, TaskStatus.FAILED,
    },
    TaskStatus.AWAITING_CONFIRM: {TaskStatus.EXECUTING, TaskStatus.CANCELLED, TaskStatus.INTERRUPTED},
    TaskStatus.AWAITING_APPROVAL: {TaskStatus.AWAITING_USER_RUN, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.AWAITING_USER_RUN: {TaskStatus.EXECUTING, TaskStatus.CANCELLED},
    TaskStatus.ROLLING_BACK: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.SUMMARIZING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.INTERRUPTED: {TaskStatus.EXECUTING, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.SECURITY_BLOCKED: set(),
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}

STATUS_LABELS = {
    TaskStatus.PENDING.value: "待处理",
    TaskStatus.SECURITY_BLOCKED.value: "安全拦截",
    TaskStatus.ROUTING.value: "路由中",
    TaskStatus.AWAITING_PLAN_CONFIRM.value: "待确认方案",
    TaskStatus.ENV_PRECHECK.value: "环境预检",
    TaskStatus.EXECUTING.value: "执行中",
    TaskStatus.AWAITING_CONFIRM.value: "待用户确认",
    TaskStatus.AWAITING_APPROVAL.value: "待管理员审批",
    TaskStatus.AWAITING_USER_RUN.value: "待确认执行",
    TaskStatus.ROLLING_BACK.value: "回滚中",
    TaskStatus.SUMMARIZING.value: "生成报告",
    TaskStatus.COMPLETED.value: "已完成",
    TaskStatus.FAILED.value: "失败",
    TaskStatus.CANCELLED.value: "已取消",
    TaskStatus.INTERRUPTED.value: "已中断",
}


class WorkflowStateMachine:
    def __init__(self, initial: TaskStatus = TaskStatus.PENDING):
        self.status = initial
        self.history: List[str] = [initial.value]

    def can_transition(self, target: TaskStatus) -> bool:
        allowed = TRANSITIONS.get(self.status, set())
        return target in allowed

    def transition(self, target: TaskStatus, reason: str = "") -> bool:
        if not self.can_transition(target):
            return False
        self.status = target
        entry = target.value
        if reason:
            entry += f":{reason}"
        self.history.append(entry)
        return True

    def force(self, target: TaskStatus, reason: str = "") -> None:
        """中断恢复场景允许强制设置状态"""
        self.status = target
        self.history.append(f"force→{target.value}" + (f":{reason}" if reason else ""))

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "label": STATUS_LABELS.get(self.status.value, self.status.value),
            "history": self.history[-20:],
        }


def map_final_status_to_task(status: str) -> TaskStatus:
    mapping = {
        "awaiting_plan_confirm": TaskStatus.AWAITING_PLAN_CONFIRM,
        "awaiting_user_action": TaskStatus.AWAITING_CONFIRM,
        "awaiting_approval": TaskStatus.AWAITING_APPROVAL,
        "env_failed": TaskStatus.FAILED,
        "blocked_injection": TaskStatus.SECURITY_BLOCKED,
        "completed": TaskStatus.COMPLETED,
        "failed": TaskStatus.FAILED,
        "cancelled": TaskStatus.CANCELLED,
    }
    return mapping.get(status, TaskStatus.EXECUTING)
