import json

from sqlmodel import Session, select

from app.utils.models import User, Role, WhitelistEntry, SyncEvent, BlacklistEntry
from app.utils.notifier import Notifier
from app.utils.permissions import check_role


async def get_whitelist(session: Session, user: User):
    # 白名单数据量通常较小，暂不分页
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN, Role.USER])
    return session.exec(select(WhitelistEntry).order_by(WhitelistEntry.created_at.desc())).all()


async def add_whitelist(session: Session, user: User, payload: dict):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])
    user_id = payload.get("user_id")
    if not user_id: raise Exception("QQ号不能为空")

    # 检查是否已存在
    if session.get(WhitelistEntry, user_id):
        raise Exception("该用户已在白名单中")

    entry = WhitelistEntry(
        user_id=user_id,
        reason=payload.get("reason", ""),
        operator_id=user.qq
    )
    session.add(entry)

    # 自动从黑名单移除 (如果有)
    bl_entry = session.get(BlacklistEntry, user_id)
    if bl_entry:
        session.delete(bl_entry)
        session.add(SyncEvent(action="delete", payload=json.dumps({"user_id": user_id})))

    # 生成白名单同步事件 (这里复用 SyncEvent，使用 type 区分，或仅作为记录)
    # 为了让 Bot 知道，我们在 payload 里加个 tag
    session.add(SyncEvent(action="upsert", payload=json.dumps({
        "table": "whitelist",  # 新版 Bot 识别此字段
        "user_id": user_id,
        "disabled": True,  # 旧版 Bot 识别此字段 -> 视为移除黑名单
        "reason": entry.reason,
        "operator_id": user.qq,
        "updated_at": entry.created_at.isoformat(),
    })))

    session.commit()
    await Notifier.on_whitelist_added(session, user.qq, user_id, payload.get("reason", ""))
    return entry.model_dump()


async def delete_whitelist(session: Session, user: User, user_id: str):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])
    entry = session.get(WhitelistEntry, user_id)
    if entry:
        session.delete(entry)
        session.add(SyncEvent(action="delete", payload=json.dumps({
            "table": "whitelist",
            "user_id": user_id
        })))
        session.commit()
        await Notifier.on_whitelist_deleted(session, user.qq, user_id)
    return {"msg": "Deleted"}
