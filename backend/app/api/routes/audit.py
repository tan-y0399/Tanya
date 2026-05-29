from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AuditRecord
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["审计"])


@router.get("/replay/{trace_id}")
async def replay_trace(trace_id: str, db: AsyncSession = Depends(get_db)):
    """获取执行回放数据 - 从真实对话记录重建推理链路"""
    result = await db.execute(
        select(AuditRecord).where(AuditRecord.trace_id == trace_id).order_by(AuditRecord.timestamp))
    record = result.scalars().first()

    if not record:
        return {"code": 1002, "message": "TraceId 不存在"}

    import json as _json
    detail = {}
    if record.detail_json:
        try:
            detail = _json.loads(record.detail_json)
        except Exception:
            pass

    question = detail.get("question", record.summary or "")
    tools = detail.get("tools", [])
    answer = detail.get("answer", "")

    steps = [
        {"step": 1, "eventType": "用户输入", "title": "接收用户消息",
         "detail": question, "status": "info"},
        {"step": 2, "eventType": "LLM 推理", "title": "Agent 分析意图",
         "detail": "模型分析用户请求，决定是否需要调用工具获取实时数据", "status": "success"},
    ]

    # 注入检测步骤
    injection_result = detail.get("injection_result", {})
    if injection_result and injection_result.get("severity"):
        steps.append({"step": 3, "eventType": "注入检测", "title": "意图安全过滤",
                      "detail": f"严重级别: {injection_result.get('severity', 'none')}",
                      "status": "warning" if injection_result.get("blocked") else "success"})

    # RAG 检索步骤
    rag_sources = detail.get("rag_sources", [])
    if rag_sources:
        steps.append({"step": 4, "eventType": "知识检索", "title": "知识库RAG检索",
                      "detail": f"检索到 {len(rag_sources)} 条相关知识",
                      "status": "success"})

    # 意图分类步骤
    intent = detail.get("intent", "")
    if intent:
        intent_labels = {"general_qa": "普通问答", "knowledge_qa": "知识查询",
                         "ops_query": "运维查询", "fault_analysis": "故障分析",
                         "high_risk": "高风险操作"}
        steps.append({"step": 5, "eventType": "意图分类", "title": "意图分类结果",
                      "detail": intent_labels.get(intent, intent),
                      "status": "warning" if intent == "high_risk" else "success"})

    # 安全校验步骤
    tool_count = sum(1 for t in tools if t.get("name"))
    if tool_count > 0:
        steps.append({"step": 6, "eventType": "安全校验", "title": "风险等级评估",
                      "detail": f"计划调用 {tool_count} 个工具，最高风险 {record.risk_level or 'L1'}",
                      "riskLevel": record.risk_level, "status": "success"})

    # 工具执行步骤
    step_num = len(steps)
    for t in tools:
        step_num += 1
        tname = t.get("name", "unknown")
        tstatus = t.get("status", "completed")
        trisk = t.get("risk", "L1")
        steps.append({
            "step": step_num, "eventType": "工具执行",
            "title": f"调用 {tname}",
            "detail": f"通过 SSH 在麒麟VM上执行 {tname}，状态: {tstatus}",
            "riskLevel": trisk,
            "status": "success" if tstatus == "completed" else "error",
        })

    # 分析结果
    step_num += 1
    steps.append({"step": step_num, "eventType": "LLM 推理", "title": "Agent 分析结果",
                  "detail": "基于工具返回的真实数据进行分析汇总", "status": "success"})

    # 生成回复
    step_num += 1
    steps.append({"step": step_num, "eventType": "生成回复", "title": "生成最终回复",
                  "detail": answer[:200] if answer else "Agent 已生成回复", "status": "success"})

    # 审计保存
    step_num += 1
    steps.append({"step": step_num, "eventType": "审计记录", "title": "全链路审计保存",
                  "detail": f"TraceId {trace_id} 已记录至数据库",
                  "time": record.timestamp.isoformat() if record.timestamp else "",
                  "status": "success"})

    # 诊断阶段
    diagnostic_stage = detail.get("diagnostic_stage", "")
    diagnostic_findings = detail.get("diagnostic_findings", [])

    return {
        "code": 0,
        "data": {
            "traceId": trace_id,
            "steps": steps,
            "riskLevel": record.risk_level,
            "intent": intent,
            "intentConfidence": detail.get("intent_confidence", 0),
            "diagnosticStage": diagnostic_stage,
            "diagnosticFindings": diagnostic_findings,
            "toolCallCount": tool_count,
            "roundCount": detail.get("round_count", 0),
        }
    }


@router.get("/records")
async def list_records(
    page: int = 1, size: int = 20,
    userId: Optional[str] = None,
    eventType: Optional[str] = None,
    riskLevel: Optional[str] = None,
    startTime: Optional[str] = None,
    endTime: Optional[str] = None,
    traceId: Optional[str] = None,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await audit_service.get_audit_records(
        db, page, size, userId, eventType, riskLevel, startTime, endTime, traceId)
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
