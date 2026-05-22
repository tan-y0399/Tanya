import json
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.services import approval_service

router = APIRouter(prefix="/approval", tags=["审批"])


@router.get("/pending")
async def pending_list(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    data = await approval_service.get_pending(db)
    return {"code": 0, "data": data}


@router.get("/history")
async def history_list(page: int = 1, size: int = 20,
                       user: dict = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    data = await approval_service.get_history(db, page, size)
    return {"code": 0, "data": data}


@router.post("/{approval_id}/approve")
async def do_approve(approval_id: str, req: dict = Body(default={}),
                     user: dict = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    comment = req.get("comment", "")
    result = await approval_service.approve(db, approval_id, user["username"], comment)
    if not result:
        raise HTTPException(status_code=404, detail="审批单不存在或已处理")
    # 实际执行由前端通过 /chat/send (pendingApprovalId) 恢复 ReAct 循环完成
    return {"code": 0, "message": "审批通过", "approvalId": approval_id}


@router.post("/{approval_id}/reject")
async def do_reject(approval_id: str, req: dict = Body(default={}),
                    user: dict = Depends(get_current_user),
                    db: AsyncSession = Depends(get_db)):
    reason = req.get("reason", "")
    result = await approval_service.reject(db, approval_id, user["username"], reason)
    if not result:
        raise HTTPException(status_code=404, detail="审批单不存在或已处理")
    return {"code": 0, "message": "审批拒绝"}


@router.post("/execute")
async def execute_with_approval(req: dict = Body(...),
                                user: dict = Depends(get_current_user),
                                db: AsyncSession = Depends(get_db)):
    command = req.get("command", "")
    session_id = req.get("sessionId", "")
    
    if not command:
        raise HTTPException(status_code=400, detail="命令不能为空")
    
    from app.core.command_security import analyze_command, get_risk_level_info
    
    analysis = analyze_command(command)
    if not analysis["success"]:
        raise HTTPException(status_code=400, detail=analysis.get("error", "命令分析失败"))
    
    if analysis.get("blocked", False):
        raise HTTPException(status_code=403, detail=analysis.get("block_message", "命令被阻止"))
    
    if not analysis.get("require_approval", False):
        result = execute_tool("run_command", command=command, timeout=30)
        return {"code": 0, "message": "命令已执行", "result": result, "riskLevel": analysis["risk_level"]}
    
    approval = await approval_service.create_approval(
        db,
        trace_id="",
        session_id=session_id,
        tool_name="execute_command",
        tool_params_json=json.dumps({"command": command}),
        risk_level=analysis["risk_level"],
        detail=f"执行命令: {command}",
        requested_by=user["id"],
    )
    
    risk_info = get_risk_level_info(analysis["risk_level"])
    return {
        "code": 0,
        "message": f"命令需要审批 ({risk_info['name']})",
        "approvalId": approval.id,
        "riskLevel": analysis["risk_level"],
        "riskInfo": risk_info,
    }
