"""
性能遥测 —— 追踪 Agent 处理链各步骤的耗时与资源消耗。

记录各阶段:
  Step 1 · 安全预检
  Step 2 · prompt_guard 注入检测
  Step 3 ∥ 意图分类 + RAG 检索（并行）
  Step 4 · 注入二次确认
  Step 5 · 路由分发
  Step 6 · ReAct 循环 / Handler
  Step 7 · 安全护栏检查
  Step 8 · 工具执行（MCP + 沙箱）
  Step 9 · 结果汇总
  Step 10 · 审计写入
  Step 11 · 遥测反馈

每步记录: 开始时间、耗时(ms)、状态(ok/warn/error)
"""

import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class StepSpan:
    """单步耗时记录"""
    __slots__ = ("name", "start_ts", "end_ts", "duration_ms", "status", "metadata")

    def __init__(self, name: str):
        self.name = name
        self.start_ts = time.perf_counter()
        self.end_ts: float = 0
        self.duration_ms: float = 0
        self.status = "running"
        self.metadata: Dict = {}

    def done(self, status: str = "ok", **meta):
        self.end_ts = time.perf_counter()
        self.duration_ms = round((self.end_ts - self.start_ts) * 1000, 2)
        self.status = status
        self.metadata = meta


class TraceTelemetry:
    """单次请求的全链路追踪"""

    def __init__(self, trace_id: str, session_id: str = "", user_id: str = ""):
        self.trace_id = trace_id
        self.session_id = session_id
        self.user_id = user_id
        self.steps: List[StepSpan] = []
        self.start_ts = time.perf_counter()
        self._current_step: Optional[StepSpan] = None

    def start_step(self, name: str) -> StepSpan:
        span = StepSpan(name)
        self.steps.append(span)
        self._current_step = span
        return span

    def end_step(self, status: str = "ok", **meta):
        if self._current_step and self._current_step.status == "running":
            self._current_step.done(status, **meta)

    @property
    def total_duration_ms(self) -> float:
        if not self.steps:
            return 0
        return round((time.perf_counter() - self.start_ts) * 1000, 2)

    @property
    def step_summary(self) -> List[Dict]:
        return [
            {
                "step": s.name,
                "duration_ms": s.duration_ms,
                "status": s.status,
                **s.metadata,
            }
            for s in self.steps
        ]

    def to_audit_json(self) -> str:
        """序列化为审计记录可用的 JSON 字符串"""
        slowest = max(self.steps, key=lambda s: s.duration_ms) if self.steps else None
        return json.dumps({
            "trace_id": self.trace_id,
            "total_ms": self.total_duration_ms,
            "steps": self.step_summary,
            "slowest_step": slowest.name if slowest else None,
            "slowest_ms": slowest.duration_ms if slowest else 0,
            "step_count": len(self.steps),
        }, ensure_ascii=False)

    def log_summary(self):
        """输出遥测摘要到日志"""
        logger.info(
            "[Telemetry] trace=%s total=%sms steps=%d | %s",
            self.trace_id,
            self.total_duration_ms,
            len(self.steps),
            " → ".join(
                "{}({}ms)".format(s.name, s.duration_ms)
                for s in self.steps
            ),
        )
        # 标记慢步骤（> 500ms）
        for s in self.steps:
            if s.duration_ms > 500:
                logger.warning(
                    "[Telemetry] SLOW trace=%s step=%s duration=%sms",
                    self.trace_id, s.name, s.duration_ms,
                )


# 全局遥测缓冲区（最近 200 条，供仪表盘读取）
_telemetry_buffer: List[Dict] = []
_MAX_BUFFER = 200


def record_trace(t: TraceTelemetry):
    """记录一次追踪到全局缓冲区"""
    summary = {
        "trace_id": t.trace_id,
        "session_id": t.session_id,
        "total_ms": round(t.total_duration_ms, 2),
        "steps": t.step_summary,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _telemetry_buffer.append(summary)
    if len(_telemetry_buffer) > _MAX_BUFFER:
        _telemetry_buffer.pop(0)
    t.log_summary()


def get_recent_telemetry(limit: int = 50) -> List[Dict]:
    """获取最近 N 条遥测记录"""
    return _telemetry_buffer[-limit:]


def get_aggregate_stats() -> Dict:
    """获取聚合统计：平均耗时、P95、各步骤占比"""
    if not _telemetry_buffer:
        return {"count": 0}

    totals = [t["total_ms"] for t in _telemetry_buffer]
    totals.sort()

    # 各步骤平均耗时
    step_totals: Dict[str, List[float]] = {}
    for t in _telemetry_buffer:
        for s in t.get("steps", []):
            step_totals.setdefault(s["step"], []).append(s["duration_ms"])

    step_avgs = {
        k: round(sum(v) / len(v), 2)
        for k, v in step_totals.items()
    }

    return {
        "count": len(_telemetry_buffer),
        "avg_total_ms": round(sum(totals) / len(totals), 2),
        "p50_ms": totals[len(totals) // 2] if totals else 0,
        "p95_ms": totals[int(len(totals) * 0.95)] if totals else 0,
        "p99_ms": totals[int(len(totals) * 0.99)] if totals else 0,
        "step_avg_ms": step_avgs,
    }
