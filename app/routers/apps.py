import json
import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.routers.users import _delete_user
from app.utils.logging import logger
from app.utils.models import Application, Role, User, BlacklistEntry, SyncEvent
from app.utils.notifier import Notifier
from app.utils.permissions import check_role
from app.utils.sessions import rate_limiter


async def get_applications(session: Session, user: User, status: str):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])

    # 获取申请列表
    apps = session.exec(
        select(Application)
        .where(Application.status == status)
        .order_by(Application.created_at.desc())
    ).all()

    # 增强数据：检查是否存在冲突/重复的黑名单
    result = []
    for app in apps:
        # 转为字典以便注入额外字段
        item = app.model_dump()
        # 默认无冲突
        item["existing_entry"] = None

        # 如果是添加申请，检查库里是否已经有这个人
        if app.type == "ADD":
            # 查一下库里有没有这个人
            existing = session.get(BlacklistEntry, app.target_user_id)
            if existing:
                # 如果有，把旧数据带回去
                item["existing_entry"] = existing.model_dump()

        result.append(item)

    return result


async def handle_application(session: Session, user: User, app_id: str, payload: dict):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])
    app = session.get(Application, app_id)
    if not app: raise Exception("申请不存在")
    if app.status != "pending": raise Exception("申请已被处理")

    action = payload.get("action")
    # 获取管理员重写的理由 (如果有)
    override_reason = payload.get("reason")

    app.status = "approved" if action == "approve" else "rejected"
    app.processed_by = user.qq
    app.processed_at = datetime.now(timezone.utc)
    session.add(app)

    # 标记是否为更新操作 (目标已存在即视为更新/覆盖)
    is_update = False
    if app.type == "ADD":
        existing = session.get(BlacklistEntry, app.target_user_id)
        if existing:
            is_update = True

    # 如果批准，自动执行黑名单操作
    if action == "approve":
        if app.type == "ADD":
            # 确定最终理由：优先使用管理员重写的，否则用申请自带的
            final_reason = override_reason if override_reason else app.reason

            entry = BlacklistEntry(
                user_id=app.target_user_id,
                reason=final_reason,
                operator_id=user.qq,  # 批准人 = 当前操作的管理员
                source_id=app.applicant_id  # 申请人 = 原始申请里的 ID
            )
            session.merge(entry)  # merge 会自动处理覆盖

            session.add(SyncEvent(action="upsert", payload=json.dumps({
                "user_id": entry.user_id,
                "reason": entry.reason,
                "operator_id": user.qq,
                "source_id": app.applicant_id,
                "disabled": False,
                "updated_at": entry.updated_at.isoformat()
            })))

            if is_update:
                # 如果是更新，记录为 updated 事件而不是 created
                await Notifier.on_blacklist_updated(session, user.qq, entry.user_id, "update", entry.reason)
            else:
                # 如果是新建：记入 blacklist.created
                await Notifier.on_blacklist_created(session, user.qq, entry, source="approval")

                user_to_del = session.exec(select(User).where(User.qq == entry.user_id)).first()
                if user_to_del:
                    await _delete_user(session, user_to_del.id)

        elif app.type in ["REMOVE", "APPEAL"]:
            # 软删除黑名单
            entry = session.get(BlacklistEntry, app.target_user_id)
            if entry:
                entry.disabled = True
                session.add(entry)
                sync_payload = json.dumps({"user_id": app.target_user_id})
                session.add(SyncEvent(action="delete", payload=sync_payload))

                await Notifier.on_blacklist_deleted(session, user.qq, app.target_user_id, type_="soft_delete")

    session.commit()
    action_cn = "批准" if action == "approve" else "拒绝"  # 动作汉化
    logger.info(f"管理员 [{user.qq}] {action_cn}了来自 {app.applicant_id} 的申请 (申请ID: {app_id})")

    # 传递 is_update 参数给通知器
    await Notifier.on_application_handled(session, app, is_update=is_update)

    # 返回明确的结果信息
    msg = f"Application {action}d"
    if action == "approve" and is_update:
        msg = "已批准并更新了现有的黑名单记录"

    return {"msg": msg, "is_update": is_update}


async def get_application_history(session: Session, user: User):
    """获取所有非 pending 状态的申请记录"""
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])
    return session.exec(
        select(Application)
        .where(Application.status != "pending")
        .order_by(Application.processed_at.desc())
    ).all()


async def cancel_application(session: Session, payload: dict):
    # 不需要特殊权限检查，因为只是撤回 pending
    target_id = payload.get("targetRequestId")
    app = session.get(Application, target_id)
    if app and app.status == "pending":
        app.status = "cancelled"
        app.processed_at = datetime.now(timezone.utc)
        session.add(app)
        session.commit()

        await Notifier.on_application_handled(session, app)
        return {"msg": "Cancelled"}
    raise Exception("申请不存在或已处理")


async def get_my_applications(session: Session, user: User):
    """获取当前用户提交的所有申请"""
    # 允许所有登录用户
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN, Role.USER])

    apps = session.exec(
        select(Application)
        .where(Application.applicant_id == user.qq)
        .order_by(Application.created_at.desc())
    ).all()

    return [app.model_dump() for app in apps]


async def submit_my_application(session: Session, user: User, payload: dict):
    """用户提交申请"""
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN, Role.USER])

    target_id = payload.get("target_user_id")
    reason = payload.get("reason")
    type_ = payload.get("type", "ADD")  # ADD or REMOVE
    images = payload.get("images", [])

    if not target_id or not reason:
        raise Exception("参数不完整")

    # 创建申请
    evidence_list = []
    if images:
        evidence_list.append({
            "type": "system",
            "data": images
        })
    app = Application(
        id=str(uuid.uuid4()),
        type=type_,
        applicant_id=user.qq,
        target_user_id=target_id,
        reason=reason,
        evidence=json.dumps(evidence_list, ensure_ascii=False),
        status="pending"
    )
    session.add(app)
    session.commit()

    # 通知管理员
    await Notifier.on_application_created(session, app)

    return app.model_dump()


async def submit_appeal(session: Session, payload: dict, client_ip: str):
    qq = payload.get("qq")
    email = payload.get("email")
    reason = payload.get("reason")
    images = payload.get("images", [])

    if not qq or not reason:
        raise Exception("请填写 QQ 号和申诉理由")

    if not email or not email.strip():
        email = f"{qq}@qq.com"

    # 1. 检查 QQ 是否真的在黑名单中 (且处于生效状态)
    entry = session.exec(
        select(BlacklistEntry).where(BlacklistEntry.user_id == qq, BlacklistEntry.disabled == False)
    ).first()

    if not entry:
        raise Exception("该账号当前未处于黑名单中，无需申诉")

    # 2. 检查是否重复提交
    existing_app = session.exec(
        select(Application).where(
            Application.target_user_id == qq,
            Application.type == "APPEAL",
            Application.status == "pending"
        )
    ).first()
    if existing_app:
        raise Exception("您已提交过申诉，请耐心等待管理员处理")

    # 3. 创建申请
    evidence_list = []
    if images:
        evidence_list.append({
            "type": "system",
            "data": images
        })
    app = Application(
        id=str(uuid.uuid4()),
        type="APPEAL",
        applicant_id=email,
        target_user_id=qq,
        reason=reason,
        evidence=json.dumps(evidence_list, ensure_ascii=False),
        status="pending"
    )
    session.add(app)
    session.commit()

    # 通知管理员
    await Notifier.on_application_created(session, app)

    return {"msg": "申诉已提交，处理结果将发送至您的邮箱"}
