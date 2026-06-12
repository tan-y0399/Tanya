from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AuditRecord
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["审计"])

INTENT_LABELS = {
    "general_qa": "普通问答",
    "knowledge_qa": "知识查询",
    "ops_query": "运维查询",
    "fault_analysis": "故障分析",
    "high_risk": "高风险操作",
    "prompt_injection": "注入拦截",
}


def _parse_detail_json(record: AuditRecord) -> dict:
    import json as _json
    if not record or not record.detail_json:
        return {}
    try:
        raw = record.detail_json
        if isinstance(raw, dict):
            return raw
        return _json.loads(raw)
    except Exception:
        return {}


def _extract_intent(detail: dict) -> str:
    intent = detail.get("intent") or ""
    if intent:
        return intent
    for step in (detail.get("telemetry") or {}).get("steps") or []:
        if step.get("intent"):
            return step["intent"]
    return ""


def _build_replay_steps(record: AuditRecord, detail: dict, trace_id: str) -> list:
    question = detail.get("question", record.summary or "")
    tools = detail.get("tools") or []
    answer = detail.get("answer", "")
    intent = _extract_intent(detail)
    telemetry = detail.get("telemetry") or {}
    telemetry_steps = telemetry.get("steps") or []

    steps = [
        {
            "step": 1,
            "eventType": "用户输入",
            "title": "接收用户消息",
            "detail": question,
            "status": "info",
        },
    ]

    step_num = 1
    if telemetry_steps:
        for ts in telemetry_steps:
            step_num += 1
            name = ts.get("step", "处理步骤")
            status = ts.get("status", "ok")
            mapped = "success" if status == "ok" else ("error" if status == "error" else "warning")
            meta_bits = []
            if ts.get("intent"):
                meta_bits.append(f"意图: {INTENT_LABELS.get(ts['intent'], ts['intent'])}")
            if ts.get("guard_pass") is not None:
                meta_bits.append(f"安全: {'通过' if ts['guard_pass'] else '拦截'}")
            detail_text = " · ".join(meta_bits) if meta_bits else name
            steps.append({
                "step": step_num,
                "eventType": "链路步骤",
                "title": name.replace("_", " "),
                "detail": detail_text,
                "duration": ts.get("duration_ms"),
                "status": mapped,
            })
    else:
        steps.append({
            "step": 2,
            "eventType": "LLM 推理",
            "title": "Agent 分析意图",
            "detail": "模型分析用户请求，决定是否需要调用工具获取实时数据",
            "status": "success",
        })
        injection_result = detail.get("injection_result", {})
        if injection_result and injection_result.get("severity"):
            step_num += 1
            steps.append({
                "step": step_num,
                "eventType": "注入检测",
                "title": "意图安全过滤",
                "detail": f"严重级别: {injection_result.get('severity', 'none')}",
                "status": "warning" if injection_result.get("blocked") else "success",
            })
        rag_sources = detail.get("rag_sources") or []
        if rag_sources:
            step_num += 1
            steps.append({
                "step": step_num,
                "eventType": "知识检索",
                "title": "知识库 RAG 检索",
                "detail": f"检索到 {len(rag_sources)} 条相关知识",
                "status": "success",
            })
        if intent:
            step_num += 1
            steps.append({
                "step": step_num,
                "eventType": "意图分类",
                "title": "意图分类结果",
                "detail": INTENT_LABELS.get(intent, intent),
                "status": "warning" if intent == "high_risk" else "success",
            })
        tool_count = sum(1 for t in tools if t.get("name"))
        if tool_count > 0:
            step_num += 1
            steps.append({
                "step": step_num,
                "eventType": "安全校验",
                "title": "风险等级评估",
                "detail": f"计划调用 {tool_count} 个工具，最高风险 {record.risk_level or 'L1'}",
                "riskLevel": record.risk_level,
                "status": "success",
            })
        for t in tools:
            step_num += 1
            tname = t.get("name", "unknown")
            tstatus = t.get("status", "completed")
            trisk = t.get("risk", "L1")
            steps.append({
                "step": step_num,
                "eventType": "工具执行",
                "title": f"调用 {tname}",
                "detail": f"通过 SSH 在麒麟 VM 上执行 {tname}，状态: {tstatus}",
                "riskLevel": trisk,
                "status": "success" if tstatus == "completed" else "error",
            })
        step_num += 1
        steps.append({
            "step": step_num,
            "eventType": "生成回复",
            "title": "生成最终回复",
            "detail": answer[:200] if answer else "Agent 已生成回复",
            "status": "success",
        })

    step_num = len(steps) + 1
    steps.append({
        "step": step_num,
        "eventType": "审计记录",
        "title": "全链路审计保存",
        "detail": f"TraceId {trace_id} 已记录至数据库",
        "time": record.timestamp.isoformat() if record.timestamp else "",
        "status": "success",
    })
    return steps


@router.get("/stats")
async def audit_stats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await audit_service.get_audit_stats(db)
    return {"code": 0, "data": data}


@router.get("/replay/{trace_id}")
async def replay_trace(
    trace_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取执行回放数据 - 从真实对话记录重建推理链路"""
    result = await db.execute(
        select(AuditRecord).where(AuditRecord.trace_id == trace_id).order_by(AuditRecord.timestamp)
    )
    record = result.scalars().first()

    if not record:
        return {"code": 1002, "message": "TraceId 不存在"}

    detail = _parse_detail_json(record)
    detail = await audit_service.enrich_audit_detail_meta(
        db,
        detail,
        trace_id=trace_id,
        session_id=record.session_id,
    )
    question = detail.get("question", record.summary or "")
    tools = detail.get("tools") or []
    intent = _extract_intent(detail)
    telemetry = detail.get("telemetry") or {}
    tool_count = sum(1 for t in tools if t.get("name"))
    steps = _build_replay_steps(record, detail, trace_id)

    return {
        "code": 0,
        "data": {
            "traceId": trace_id,
            "sessionId": record.session_id,
            "steps": steps,
            "riskLevel": record.risk_level,
            "intent": intent,
            "intentLabel": INTENT_LABELS.get(intent, intent) if intent else "",
            "intentConfidence": detail.get("intent_confidence", 0),
            "diagnosticStage": detail.get("diagnostic_stage", ""),
            "diagnosticFindings": detail.get("diagnostic_findings", []),
            "toolCallCount": tool_count,
            "roundCount": detail.get("round_count", 0),
            "totalMs": telemetry.get("total_ms"),
            "question": question,
        },
    }


@router.get("/records")
async def list_records(
    page: int = 1,
    size: int = 20,
    userId: Optional[str] = None,
    username: Optional[str] = None,
    eventType: Optional[str] = None,
    riskLevel: Optional[str] = None,
    startTime: Optional[str] = None,
    endTime: Optional[str] = None,
    traceId: Optional[str] = None,
    keyword: Optional[str] = None,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await audit_service.get_audit_records(
        db,
        page,
        size,
        userId,
        username or userId,
        eventType,
        riskLevel,
        startTime,
        endTime,
        traceId,
        keyword,
    )
    return {"code": 0, "data": data}


@router.get("/records/{trace_id}")
async def record_detail(
    trace_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await audit_service.get_audit_detail(db, trace_id)
    if not data:
        return {"code": 1002, "message": "资源不存在"}
    return {"code": 0, "data": data}


@router.get("/evaluate/{trace_id}")
async def evaluate_trace(
    trace_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """评测指定追踪链路的 Agent 决策质量"""
    from app.services.evaluation_service import evaluate_trace as eval_func
    result = await eval_func(trace_id, db)
    return {"code": 0, "data": result.to_dict()}
