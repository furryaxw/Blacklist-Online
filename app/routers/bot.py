from fastapi import APIRouter, Depends, Body, HTTPException
from sqlmodel import Session

from app.utils.database import get_session
from app.utils.deps import check_api_permission
from app.utils.logging import logger
from app.utils.models import Application, ApiKey
from app.utils.notifier import Notifier

router = APIRouter(tags=["Bot"])


@router.post("/applications")
async def submit_application(
        app: Application,
        session: Session = Depends(get_session),
        token: ApiKey = Depends(check_api_permission("write"))
):
    # 安全修复：强制要求 Key 绑定实例
    if not token.instance_uuid:
        raise HTTPException(
            status_code=403,
            detail="API Key must be bound to a bot instance (instance_uuid) to perform this action"
        )

    # 记录提交者 Bot 的 ID
    app.submitter_instance_id = token.instance_uuid

    # Bot 提交申请
    # 如果是离线重试 (isOfflineRetry)，可以记录日志
    session.merge(app)  # 使用 merge 防止重复提交 ID 冲突
    session.commit()

    logger.info(f"Bot [{token.instance_uuid}] 提交新申请: {app.id} (类型: {app.type}) 申请人: {app.applicant_id}")

    await Notifier.on_application_created(session, app)

    return {"msg": "Application received"}


@router.post("/applications/cancel")
async def cancel_application(
        payload: dict = Body(...),
        session: Session = Depends(get_session),
        token: ApiKey = Depends(check_api_permission("write"))
):
    target_id = payload.get("targetRequestId")
    if not target_id:
        raise HTTPException(status_code=400, detail="Missing targetRequestId")

    # 安全修复：强制要求 Key 绑定实例
    if not token.instance_uuid:
        raise HTTPException(
            status_code=403,
            detail="API Key must be bound to a bot instance (instance_uuid) to perform this action"
        )

    app = session.get(Application, target_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # 权限校验逻辑
    # 只有提交该申请的 Bot 实例 (submitter_instance_id) 才能撤回
    if app.submitter_instance_id != token.instance_uuid:
        raise HTTPException(status_code=403, detail="Permission denied: You can only cancel applications submitted by your own instance")

    session.delete(app)
    session.commit()

    await Notifier.on_application_cancelled(session, app)

    return {"msg": "Cancelled"}