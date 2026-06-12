"""
审批管理 API — 完整实现待审批列表、历史、通过/拒绝
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_optional, get_current_user
from app.services.approval_service import (
    get_pending,
    get_history,
    approve,
    reject,
    get_stats,
    get_by_id,
    delete_approval,
    update_approval,
)
from app.schemas.approval import ApproveRequest, RejectRequest, UpdateApprovalRequest

router = APIRouter(tags=['approval'])


def _require_admin(user: dict):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")


@router.get('/approval/pending')
async def list_pending_approvals(db: AsyncSession = Depends(get_db), _=Depends(get_current_user_optional)):
    """获取待审批操作列表（自动清理过期项）"""
    result = await get_pending(db)
    return {"code": 0, "data": result}


@router.get('/approval/history')
async def list_approval_history(page: int = 1, size: int = 20, db: AsyncSession = Depends(get_db),
                                _=Depends(get_current_user_optional)):
    """获取审批历史记录"""
    result = await get_history(db, page=page, size=size)
    return {"code": 0, "data": result}


@router.get('/approval/stats')
async def approval_statistics(db: AsyncSession = Depends(get_db), _=Depends(get_current_user_optional)):
    """获取审批统计数据"""
    result = await get_stats(db)
    return {"code": 0, "data": result}


@router.get('/approval/{approval_id}')
async def get_approval_detail(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user_optional),
):
    """查询单条审批记录（用于对话页轮询审批结果）"""
    approval = await get_by_id(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在")
    from app.services.approval_service import _format_approval
    return {"code": 0, "data": await _format_approval(db, approval)}


@router.post('/approval/{approval_id}/approve')
async def approve_operation(
    approval_id: str,
    payload: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """管理员审批通过 — 仅标记审批状态，工具执行由用户端恢复时触发"""
    approval = await approve(db, approval_id, approver=current_user["username"], comment=payload.comment)
    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在、已处理或已过期")

    # 更新 PendingExecution 状态，但不执行工具（由用户端 resume 触发）
    from app.models.pending_execution import PendingExecution
    from sqlalchemy import select
    result = await db.execute(
        select(PendingExecution).where(
            PendingExecution.approval_id == approval_id,
            PendingExecution.status == "pending",
        )
    )
    pe = result.scalar_one_or_none()
    if pe:
        pe.status = "approved"
        await db.commit()

    from app.services.chat_service import preview_tool_command
    tool_params = {}
    if approval.tool_params_json:
        try:
            import json
            tool_params = json.loads(approval.tool_params_json)
        except Exception:
            pass

    return {
        "code": 0,
        "data": {
            "approved": True,
            "message": "已批准，请在对话页面确认执行命令",
            "approvalId": approval.id,
            "sessionId": approval.session_id,
            "toolName": approval.tool_name,
            "toolParams": tool_params,
            "commandPreview": preview_tool_command(approval.tool_name, tool_params),
            "riskLevel": approval.risk_level,
        },
    }


@router.post('/approval/{approval_id}/reject')
async def reject_operation(
    approval_id: str,
    payload: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """管理员拒绝审批"""
    approval = await reject(db, approval_id, approver=current_user["username"], reason=payload.reason)
    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在、已处理或已过期")

    # 更新 PendingExecution 状态为已拒绝
    from app.models.pending_execution import PendingExecution
    from sqlalchemy import select
    result = await db.execute(
        select(PendingExecution).where(
            PendingExecution.approval_id == approval_id,
            PendingExecution.status == "pending",
        )
    )
    pe = result.scalar_one_or_none()
    if pe:
        pe.status = "rejected"
        await db.commit()

    from app.services.chat_service import finalize_approval_rejection_in_session
    try:
        await finalize_approval_rejection_in_session(db, approval.session_id, approval_id)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("approval rejection finalize failed")

    return {
        "code": 0,
        "data": {
            "approved": False,
            "message": "已拒绝：{}".format(payload.reason or '不予执行'),
        },
    }


@router.patch('/approval/{approval_id}')
async def patch_approval(
    approval_id: str,
    payload: UpdateApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """管理员修改审批记录"""
    _require_admin(current_user)
    approval = await update_approval(
        db,
        approval_id,
        detail=payload.detail,
        comment=payload.comment,
        risk_level=payload.riskLevel,
    )
    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在")
    from app.services.approval_service import _format_approval
    return {"code": 0, "data": await _format_approval(db, approval)}


@router.delete('/approval/{approval_id}')
async def remove_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """管理员删除审批记录"""
    _require_admin(current_user)
    ok = await delete_approval(db, approval_id)
    if not ok:
        raise HTTPException(status_code=404, detail="审批不存在")
    return {"code": 0, "data": {"deleted": True}}
