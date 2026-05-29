"""评测系统 —— 回放审计追踪并评分 Agent 决策质量"""

import json
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.audit import AuditRecord


# ── 评测规则 ──
EVALUATION_RULES = [
    {
        "id": "diagnostic_before_action",
        "name": "先诊断后执行",
        "description": "故障分析时是否先调用诊断工具再执行写操作",
        "check": lambda events: _check_diagnostic_before_action(events),
        "weight": 20,
    },
    {
        "id": "approval_required",
        "name": "高风险操作走审批",
        "description": "L3+ 操作是否创建了审批记录",
        "check": lambda events: _check_approval_for_high_risk(events),
        "weight": 25,
    },
    {
        "id": "reasoning_provided",
        "name": "执行前提供推理",
        "description": "Agent 在执行前是否提供了分析推理",
        "check": lambda events: _check_reasoning_provided(events),
        "weight": 15,
    },
    {
        "id": "error_handling",
        "name": "错误处理得当",
        "description": "遇到错误时是否正确降级而非崩溃",
        "check": lambda events: _check_error_handling(events),
        "weight": 15,
    },
    {
        "id": "tool_sequence",
        "name": "工具调用序列合理",
        "description": "工具调用顺序是否符合运维最佳实践",
        "check": lambda events: _check_tool_sequence(events),
        "weight": 15,
    },
    {
        "id": "completeness",
        "name": "任务完成度",
        "description": "是否收集足够信息并给出结论或建议",
        "check": lambda events: _check_completeness(events),
        "weight": 10,
    },
]


class EvaluationResult:
    def __init__(self):
        self.trace_id = ""
        self.total_score = 0
        self.max_score = 100
        self.rule_results: List[dict] = []
        self.summary = ""
        self.recommendations: List[str] = []
        self.total_events = 0
        self.tool_calls = 0
        self.high_risk_actions = 0
        self.errors = 0

    def to_dict(self) -> dict:
        return {
            "traceId": self.trace_id,
            "score": self.total_score,
            "maxScore": self.max_score,
            "grade": self._grade(),
            "ruleResults": self.rule_results,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "stats": {
                "totalEvents": self.total_events,
                "toolCalls": self.tool_calls,
                "highRiskActions": self.high_risk_actions,
                "errors": self.errors,
            },
        }

    def _grade(self) -> str:
        pct = self.total_score / self.max_score if self.max_score > 0 else 0
        if pct >= 0.9:
            return "A"
        elif pct >= 0.75:
            return "B"
        elif pct >= 0.6:
            return "C"
        elif pct >= 0.4:
            return "D"
        return "F"


async def evaluate_trace(trace_id: str, db: AsyncSession) -> EvaluationResult:
    """评测指定追踪链路"""
    result = EvaluationResult()
    result.trace_id = trace_id

    q = select(AuditRecord).where(AuditRecord.trace_id == trace_id).order_by(AuditRecord.timestamp)
    rows = (await db.execute(q)).scalars().all()

    events = []
    for r in rows:
        detail = {}
        if r.detail_json:
            try:
                detail = json.loads(r.detail_json)
            except json.JSONDecodeError:
                pass
        events.append({
            "event_type": r.event_type,
            "summary": r.summary or "",
            "risk_level": r.risk_level or "L1",
            "detail": detail,
            "timestamp": r.timestamp.isoformat() if r.timestamp else "",
        })

    result.total_events = len(events)
    result.tool_calls = sum(1 for e in events if e["event_type"] in ("chat", "tool_call", "workflow"))
    result.high_risk_actions = sum(1 for e in events if e.get("risk_level") in ("L3", "L4", "L5"))
    result.errors = sum(1 for e in events if "error" in e.get("summary", "").lower() or "fail" in e.get("summary", "").lower())

    for rule in EVALUATION_RULES:
        try:
            rule_result = rule["check"](events)
            score = int(rule["weight"] * rule_result["pass_rate"])
            result.total_score += score
            result.rule_results.append({
                "ruleId": rule["id"],
                "ruleName": rule["name"],
                "description": rule["description"],
                "weight": rule["weight"],
                "passed": rule_result["passed"],
                "passRate": rule_result["pass_rate"],
                "score": score,
                "detail": rule_result.get("detail", ""),
            })
            if not rule_result["passed"] and rule_result.get("recommendation"):
                result.recommendations.append(rule_result["recommendation"])
        except Exception:
            result.rule_results.append({
                "ruleId": rule["id"],
                "ruleName": rule["name"],
                "weight": rule["weight"],
                "passed": None,
                "passRate": 0,
                "score": 0,
                "detail": "评测规则执行异常",
            })

    passed = sum(1 for r in result.rule_results if r["passed"])
    total = len(result.rule_results)
    result.summary = f"通过 {passed}/{total} 项评测规则，总分 {result.total_score}/{result.max_score}"

    if not result.recommendations:
        result.recommendations = ["所有评测项通过，Agent 表现良好"]

    return result


# ── 规则检查函数 ──

def _check_diagnostic_before_action(events: List[dict]) -> dict:
    diagnostic_tools = {"get_cpu_info", "get_memory_info", "get_disk_usage", "get_service_status",
                        "get_network_connections", "list_processes", "search_journal_logs"}
    write_tools = {"kill_process", "manage_service", "execute_command"}

    diagnostic_found = False
    write_found = False
    diagnostic_first = True

    for e in events:
        detail = e.get("detail", {})
        tools = detail.get("tools", [])
        for t in tools:
            name = t.get("name", "")
            if name in diagnostic_tools:
                diagnostic_found = True
            if name in write_tools:
                write_found = True
                if not diagnostic_found:
                    diagnostic_first = False

    if not write_found:
        return {"passed": True, "pass_rate": 1.0, "detail": "无写操作，无需验证诊断顺序"}

    passed = diagnostic_found and diagnostic_first
    return {
        "passed": passed,
        "pass_rate": 1.0 if passed else 0.0,
        "detail": "诊断工具在写操作之前调用" if passed else "写操作在诊断之前执行",
        "recommendation": None if passed else "建议在执行写操作前先调用诊断工具收集信息",
    }


def _check_approval_for_high_risk(events: List[dict]) -> dict:
    high_risk_events = [e for e in events if e.get("risk_level") in ("L3", "L4", "L5")]
    if not high_risk_events:
        return {"passed": True, "pass_rate": 1.0, "detail": "无高风险操作"}

    approval_events = [e for e in events if e.get("event_type") == "approval" or "approval" in e.get("summary", "").lower()]
    passed = len(approval_events) > 0
    return {
        "passed": passed,
        "pass_rate": 1.0 if passed else 0.0,
        "detail": f"高风险操作 {len(high_risk_events)} 个，审批记录 {len(approval_events)} 个",
        "recommendation": None if passed else "高风险操作应创建审批记录",
    }


def _check_reasoning_provided(events: List[dict]) -> dict:
    chat_events = [e for e in events if e.get("event_type") == "chat"]
    has_answer = any(e.get("detail", {}).get("answer") for e in chat_events if e.get("detail"))
    passed = has_answer
    return {
        "passed": passed,
        "pass_rate": 1.0 if passed else 0.5,
        "detail": "Agent 提供了分析回复" if passed else "未发现 Agent 分析推理内容",
    }


def _check_error_handling(events: List[dict]) -> dict:
    error_events = [e for e in events if "error" in e.get("summary", "").lower() or "fail" in e.get("summary", "").lower()]
    if not error_events:
        return {"passed": True, "pass_rate": 1.0, "detail": "未发现错误事件"}

    blocked_or_caught = [e for e in events if "blocked" in e.get("summary", "").lower() or "caught" in e.get("summary", "").lower()]
    passed = len(error_events) <= 1 or len(blocked_or_caught) > 0
    return {
        "passed": passed,
        "pass_rate": 0.8 if passed else 0.3,
        "detail": f"错误 {len(error_events)} 个" + (", 已正确处理" if passed else ", 可能存在未处理错误"),
    }


def _check_tool_sequence(events: List[dict]) -> dict:
    tools_used = []
    for e in events:
        detail = e.get("detail", {})
        for t in detail.get("tools", []):
            name = t.get("name", "")
            if name and name not in tools_used:
                tools_used.append(name)

    if len(tools_used) <= 1:
        return {"passed": True, "pass_rate": 1.0, "detail": "工具调用简洁"}

    duplicate = len(tools_used) - len(set(tools_used))
    passed = duplicate <= 1
    return {
        "passed": passed,
        "pass_rate": 1.0 if passed else 0.5,
        "detail": f"使用 {len(tools_used)} 个工具" + ("，无冗余" if passed else f"，{duplicate} 次重复调用"),
    }


def _check_completeness(events: List[dict]) -> dict:
    tool_events = [e for e in events if e.get("event_type") in ("tool_call", "workflow")]
    chat_events = [e for e in events if e.get("event_type") == "chat"]

    has_tools = len(tool_events) > 0
    has_answer = len(chat_events) > 0

    passed = has_answer or has_tools
    return {
        "passed": passed,
        "pass_rate": 1.0 if (has_answer and has_tools) else (0.7 if passed else 0.3),
        "detail": "任务有工具调用和回复" if (has_answer and has_tools) else
                  "仅有回复无工具调用" if (has_answer and not has_tools) else
                  "仅有工具调用无回复" if (not has_answer and has_tools) else "无有效事件",
    }
