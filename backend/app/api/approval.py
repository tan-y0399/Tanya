from fastapi import APIRouter

from app.schemas.approval import ApprovalRequest, ApprovalResponse

router = APIRouter(prefix='/api', tags=['approval'])


@router.post('/approval', response_model=ApprovalResponse)
def submit_approval(payload: ApprovalRequest) -> ApprovalResponse:
    return ApprovalResponse(
        approved=True,
        message=f'已审批动作：{payload.action}，原因：{payload.reason}',
    )
