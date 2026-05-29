"""
任务编排器 —— 多阶段状态机，含失败回滚、重试、超时、中断恢复

增强功能:
  - 每步骤超时控制
  - 失败自动重试（指数退避）
  - 失败回滚（执行逆操作）
  - 条件分支（失败→备用步骤）
  - 任务挂起/恢复（持久化）
  - 并发步骤执行
"""

import json
import asyncio
import logging
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.task import TaskState

logger = logging.getLogger(__name__)


class TaskStage(Enum):
    INIT = "init"
    PERCEIVING = "perceiving"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    EXECUTING = "executing"
    WRITEBACK = "writeback"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"


class StepStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    ROLLED_BACK = "rolled_back"
    TIMEOUT = "timeout"


STAGE_ORDER = [
    TaskStage.INIT,
    TaskStage.PERCEIVING,
    TaskStage.ANALYZING,
    TaskStage.VALIDATING,
    TaskStage.EXECUTING,
    TaskStage.WRITEBACK,
    TaskStage.SUMMARIZING,
    TaskStage.COMPLETED,
]

STAGE_LABELS = {
    TaskStage.INIT.value: "初始化",
    TaskStage.PERCEIVING.value: "环境感知",
    TaskStage.ANALYZING.value: "分析诊断",
    TaskStage.VALIDATING.value: "安全校验",
    TaskStage.EXECUTING.value: "执行操作",
    TaskStage.WRITEBACK.value: "结果回写",
    TaskStage.SUMMARIZING.value: "总结报告",
    TaskStage.COMPLETED.value: "完成",
    TaskStage.INTERRUPTED.value: "已中断",
    TaskStage.CANCELLED.value: "已取消",
    TaskStage.FAILED.value: "执行失败",
    TaskStage.ROLLING_BACK.value: "正在回滚",
}


class TaskStep:
    def __init__(self, name: str, tool_name: str = "", tool_args: dict = None,
                 timeout: int = 30, max_retries: int = 1,
                 rollback_tool: str = "", rollback_args: dict = None,
                 on_failure: str = "fail"):  # fail | skip | rollback
        self.name = name
        self.tool_name = tool_name
        self.tool_args = tool_args or {}
        self.status = StepStatus.PENDING
        self.result = None
        self.error = None
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_count = 0
        # 失败回滚
        self.rollback_tool = rollback_tool
        self.rollback_args = rollback_args or {}
        self.on_failure = on_failure  # "fail" | "skip" | "rollback"

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "toolName": self.tool_name,
            "toolArgs": self.tool_args,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "durationMs": round(self.duration_ms),
            "retryCount": self.retry_count,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskStep":
        step = cls(
            data["name"],
            data.get("toolName", ""),
            data.get("toolArgs", {}),
            timeout=data.get("timeout", 30),
            max_retries=data.get("maxRetries", 1),
            on_failure=data.get("onFailure", "fail"),
        )
        step.status = data.get("status", StepStatus.PENDING)
        step.result = data.get("result")
        step.error = data.get("error")
        step.retry_count = data.get("retryCount", 0)
        return step


class TaskOrchestrator:
    def __init__(self, task_id: str = None, session_id: str = "", trace_id: str = "",
                 user_id: str = "", task_timeout: int = 300):
        self.task_id = task_id or f"task-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{id(self) % 10000:04d}"
        self.session_id = session_id
        self.trace_id = trace_id
        self.user_id = user_id
        self.current_stage = TaskStage.INIT
        self.steps: List[TaskStep] = []
        self._completed = False
        self._interrupted = False
        self._cancelled = False
        self.task_timeout = task_timeout  # 整体超时秒数
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        # 上下文：跨步骤共享数据
        self.context: Dict = {}
        # 事件回调
        self._on_stage_change: Optional[Callable] = None
        self._on_step_complete: Optional[Callable] = None

    @property
    def progress(self) -> int:
        if not self.steps:
            return 0
        done = sum(1 for s in self.steps
                   if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.ROLLED_BACK))
        return min(int(done / len(self.steps) * 100), 99)

    @property
    def is_completed(self) -> bool:
        return self.current_stage == TaskStage.COMPLETED

    @property
    def is_running(self) -> bool:
        return self.current_stage not in (
            TaskStage.COMPLETED, TaskStage.CANCELLED,
            TaskStage.FAILED, TaskStage.INTERRUPTED
        )

    @property
    def duration_seconds(self) -> float:
        if self.started_at:
            end = self.ended_at or datetime.utcnow()
            return (end - self.started_at).total_seconds()
        return 0

    @property
    def is_timed_out(self) -> bool:
        return self.duration_seconds > self.task_timeout

    def add_step(self, name: str, tool_name: str = "", tool_args: dict = None,
                 timeout: int = 30, max_retries: int = 1,
                 rollback: str = "", rollback_args: dict = None,
                 on_failure: str = "fail") -> "TaskStep":
        step = TaskStep(name, tool_name, tool_args, timeout, max_retries,
                        rollback_tool=rollback, rollback_args=rollback_args,
                        on_failure=on_failure)
        self.steps.append(step)
        return step

    def transition(self, stage: TaskStage) -> None:
        old = self.current_stage
        self.current_stage = stage
        if self._on_stage_change:
            self._on_stage_change(old.value, stage.value)

    def advance(self) -> Optional[TaskStage]:
        try:
            idx = STAGE_ORDER.index(self.current_stage)
            if idx + 1 < len(STAGE_ORDER):
                self.current_stage = STAGE_ORDER[idx + 1]
                return self.current_stage
        except ValueError:
            pass
        return None

    # ── 执行 ──
    async def execute_step(self, step: TaskStep,
                           executor: Callable[[str, dict], Awaitable[dict]] = None) -> dict:
        """执行单个步骤，含重试和超时"""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow()

        while step.retry_count <= step.max_retries:
            try:
                if executor:
                    result = await asyncio.wait_for(
                        executor(step.tool_name, step.tool_args),
                        timeout=step.timeout
                    )
                else:
                    result = {"success": False, "error": "no executor provided"}

                if isinstance(result, dict) and result.get("success", True):
                    step.status = StepStatus.COMPLETED
                    step.result = result
                    step.completed_at = datetime.utcnow()
                    if self._on_step_complete:
                        self._on_step_complete(step)
                    return result

                # 工具返回失败
                step.retry_count += 1
                if step.retry_count <= step.max_retries:
                    step.status = StepStatus.RETRYING
                    await asyncio.sleep(2 ** step.retry_count)  # 指数退避
                else:
                    step.status = StepStatus.FAILED
                    step.error = result.get("error", "执行失败") if isinstance(result, dict) else str(result)
                    step.completed_at = datetime.utcnow()

            except asyncio.TimeoutError:
                step.retry_count += 1
                if step.retry_count <= step.max_retries:
                    step.status = StepStatus.RETRYING
                else:
                    step.status = StepStatus.TIMEOUT
                    step.error = f"超时 (>{step.timeout}秒)"
                    step.completed_at = datetime.utcnow()

            except Exception as e:
                step.retry_count += 1
                if step.retry_count <= step.max_retries:
                    step.status = StepStatus.RETRYING
                    await asyncio.sleep(1)
                else:
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    step.completed_at = datetime.utcnow()

        return {"success": False, "error": step.error}

    async def execute_parallel(self, steps: List[TaskStep],
                               executor: Callable[[str, dict], Awaitable[dict]] = None) -> List[dict]:
        """并行执行多个步骤"""
        tasks = [self.execute_step(s, executor) for s in steps]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def rollback_step(self, step: TaskStep,
                            executor: Callable[[str, dict], Awaitable[dict]] = None) -> dict:
        """回滚单个步骤"""
        if not step.rollback_tool:
            step.status = StepStatus.ROLLED_BACK
            return {"success": True, "rolled_back": "noop"}

        step.status = StepStatus.RETRYING
        try:
            result = await asyncio.wait_for(
                executor(step.rollback_tool, step.rollback_args),
                timeout=30
            )
            step.status = StepStatus.ROLLED_BACK
            return result
        except Exception as e:
            step.error = f"回滚失败: {e}"
            return {"success": False, "error": step.error}

    async def rollback(self, from_step_index: int,
                       executor: Callable[[str, dict], Awaitable[dict]] = None) -> dict:
        """从指定步骤开始向前回滚所有已完成的步骤"""
        self.transition(TaskStage.ROLLING_BACK)
        results = []
        for i in range(from_step_index, -1, -1):
            step = self.steps[i]
            if step.status == StepStatus.COMPLETED:
                result = await self.rollback_step(step, executor)
                results.append({"step": step.name, "result": result})
        return {"rolled_back": len(results), "steps": results}

    # ── 生命周期 ──
    def interrupt(self, reason: str = "") -> dict:
        self._interrupted = True
        self.ended_at = datetime.utcnow()
        self.transition(TaskStage.INTERRUPTED)
        return self.to_dict()

    def cancel(self) -> dict:
        self._cancelled = True
        self.ended_at = datetime.utcnow()
        self.transition(TaskStage.CANCELLED)
        return self.to_dict()

    def complete(self) -> dict:
        self._completed = True
        self.ended_at = datetime.utcnow()
        self.transition(TaskStage.COMPLETED)
        return self.to_dict()

    def fail(self, error: str = "") -> dict:
        self.ended_at = datetime.utcnow()
        self.transition(TaskStage.FAILED)
        return {**self.to_dict(), "error": error}

    # ── 恢复 ──
    def get_resume_point(self) -> int:
        """获取恢复点：第一个未完成的步骤索引"""
        for i, step in enumerate(self.steps):
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.RETRYING,
                               StepStatus.FAILED, StepStatus.TIMEOUT):
                return i
        return len(self.steps)

    def get_pending_steps(self) -> List[TaskStep]:
        resume = self.get_resume_point()
        return self.steps[resume:]

    # ── 序列化 ──
    def get_progress_event(self) -> dict:
        return {
            "taskId": self.task_id,
            "stage": self.current_stage.value,
            "stageLabel": STAGE_LABELS.get(self.current_stage.value, ""),
            "progress": self.progress,
            "steps": [s.to_dict() for s in self.steps],
            "isCompleted": self.is_completed,
            "isRunning": self.is_running,
            "durationSeconds": round(self.duration_seconds, 1),
        }

    def to_dict(self) -> dict:
        return {
            "taskId": self.task_id,
            "sessionId": self.session_id,
            "traceId": self.trace_id,
            "userId": self.user_id,
            "stage": self.current_stage.value,
            "stageLabel": STAGE_LABELS.get(self.current_stage.value, ""),
            "progress": self.progress,
            "steps": [s.to_dict() for s in self.steps],
            "context": self.context,
            "durationSeconds": round(self.duration_seconds, 1),
            "isCompleted": self.is_completed,
        }

    # ── 持久化 ──
    async def save(self, db: AsyncSession) -> None:
        existing = await db.execute(select(TaskState).where(TaskState.id == self.task_id))
        record = existing.scalar_one_or_none()
        if record:
            record.state = self.current_stage.value
            record.steps_json = json.dumps([s.to_dict() for s in self.steps], ensure_ascii=False)
            record.progress = self.progress
            record.updated_at = datetime.utcnow()
        else:
            record = TaskState(
                id=self.task_id, session_id=self.session_id,
                trace_id=self.trace_id, user_id=self.user_id,
                state=self.current_stage.value,
                steps_json=json.dumps([s.to_dict() for s in self.steps], ensure_ascii=False),
                progress=self.progress,
            )
            db.add(record)
        await db.commit()

    @classmethod
    async def load(cls, task_id: str, db: AsyncSession) -> Optional["TaskOrchestrator"]:
        result = await db.execute(select(TaskState).where(TaskState.id == task_id))
        record = result.scalar_one_or_none()
        if not record:
            return None
        orch = cls(task_id=record.id, session_id=record.session_id,
                   trace_id=record.trace_id, user_id=record.user_id)
        try:
            stage = TaskStage(record.state)
        except ValueError:
            stage = TaskStage.INIT
        orch.current_stage = stage
        if record.steps_json:
            try:
                steps_data = json.loads(record.steps_json)
                orch.steps = [TaskStep.from_dict(s) for s in steps_data]
            except (json.JSONDecodeError, KeyError):
                pass
        return orch
