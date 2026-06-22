import json

from sqlmodel import Session, select, col, func

from app.routers.users import _delete_user
from app.utils.logging import logger
from app.utils.models import SyncEvent, Role, BlacklistEntry, User, unix_now
from app.utils.notifier import Notifier
from app.utils.permissions import check_role


async def get_blacklist(session: Session, user: User, payload: dict):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN, Role.USER])

    # [Change] 支持后端分页与搜索
    page = int(payload.get("page", 1))
    size = int(payload.get("size", 10))
    keyword = payload.get("keyword", "")
    offset = (page - 1) * size

    query = select(BlacklistEntry)
    if keyword:
        query = query.where(col(BlacklistEntry.user_id).contains(keyword))

    # 获取总数
    total_query = select(func.count()).select_from(query.subquery())
    total = session.exec(total_query).one()

    # 获取分页数据
    entries = session.exec(query.offset(offset).limit(size)).all()

    return {
        "items": [entry.model_dump() for entry in entries],
        "total": total,
        "page": page,
        "size": size
    }


async def add_blacklist(session: Session, user: User, payload: dict):
    """直接添加（覆盖插件功能）"""
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])
    # 构造对象，注意 payload 是 dict
    entry = BlacklistEntry(**payload)
    entry.operator_id = user.qq
    entry.source_id = user.qq

    # 确保 entry 如果有 updated_at 也是 UTC，或者依赖 Model 默认值
    # 如果 Model 已经修改为 default_factory=utc_now，这里不需要手动设，但为了保险可以显式刷新一下
    if not entry.updated_at:
        entry.updated_at = unix_now()

    session.merge(entry)
    session.add(SyncEvent(action="upsert", payload=json.dumps({
        "user_id": entry.user_id,
        "reason": entry.reason,
        "operator_id": user.qq,
        "source_id": user.qq,
        "disabled": entry.disabled,
        "updated_at": entry.updated_at
    })))
    session.commit()
    logger.warning(f"管理员 [{user.qq}] 手动添加黑名单: {entry.user_id} (原因: {entry.reason})")

    await Notifier.on_blacklist_created(session, user.qq, entry, source="manual")

    user_to_del = session.exec(select(User).where(User.qq == entry.user_id)).first()
    if user_to_del:
        await _delete_user(session, user_to_del.id)

    return {"msg": "Added"}


async def update_blacklist(session: Session, user: User, payload: dict):
    """编辑黑名单理由"""
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])

    user_id = payload.get("user_id")
    new_reason = payload.get("reason")

    if not user_id or not new_reason:
        raise Exception("参数不完整")

    entry = session.get(BlacklistEntry, user_id)
    if not entry:
        raise Exception("该用户不在黑名单中")

    # 更新字段
    old_reason = entry.reason
    entry.reason = new_reason
    entry.operator_id = user.qq
    entry.updated_at = unix_now()

    session.add(entry)

    # 记录同步事件 (Upsert 覆盖即可)
    session.add(SyncEvent(action="upsert", payload=json.dumps({
        "user_id": entry.user_id,
        "reason": entry.reason,
        "operator_id": user.qq,
        "source_id": entry.source_id,
        "disabled": entry.disabled,
        "updated_at": entry.updated_at
    })))

    session.commit()

    logger.info(f"管理员 [{user.qq}] 更新黑名单: {user_id} 原因: {old_reason} -> {new_reason}")

    # 推送更新通知
    await Notifier.on_blacklist_updated(session, user.qq, user_id, action="update_reason", reason=new_reason)
    return {"msg": "Updated"}


async def update_blacklist_status(session: Session, user: User, user_id: str, payload: dict):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])
    entry = session.get(BlacklistEntry, user_id)
    if not entry: raise Exception("黑名单记录不存在")

    new_disabled = payload.get("disabled")
    if new_disabled is None: raise Exception("状态参数缺失")

    # 更新状态和操作人
    entry.disabled = new_disabled
    entry.operator_id = user.qq
    entry.updated_at = unix_now()
    session.add(entry)

    # 生成同步事件
    if new_disabled:
        # 设置为失效 -> 视为删除
        # Bot 收到 delete 事件会移除本地黑名单
        sync_payload = json.dumps({"user_id": user_id})
        event = SyncEvent(action="delete", payload=sync_payload)
    else:
        # 设置为生效 -> 视为新增/更新
        # Bot 收到 upsert 事件会写入本地黑名单
        sync_payload = json.dumps({
            "user_id": entry.user_id,
            "reason": entry.reason,
            "operator_id": user.qq,
            "disabled": False,
            "updated_at": entry.updated_at
        })
        event = SyncEvent(action="upsert", payload=sync_payload)

    session.add(event)
    session.commit()

    action_str = "disable" if new_disabled else "enable"
    await Notifier.on_blacklist_updated(session, user.qq, user_id, action=action_str)
    return {"msg": "Updated"}


async def hard_delete_blacklist(session: Session, user: User, user_id: str):
    """从数据库彻底删除记录（不留痕迹）"""
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])
    entry = session.get(BlacklistEntry, user_id)
    logger.warning(f"管理员 [{user.qq}] 永久删除黑名单: {user_id}")
    if entry:
        session.delete(entry)
        # 注意：硬删除通常不推送 delete sync event，或者推送一个特殊的 cleanup event
        # 这里为了保持一致性，可以选择推送 delete 事件，让客户端也移除
        payload = json.dumps({"user_id": user_id})
        session.add(SyncEvent(action="delete", payload=payload))
        session.commit()

        await Notifier.on_blacklist_deleted(session, user.qq, user_id, type_="hard_delete")
    return {"msg": "Hard deleted"}


async def soft_delete_blacklist(session: Session, user: User, user_id: str):
    """软删除（标记为失效）"""
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])
    entry = session.get(BlacklistEntry, user_id)
    if entry:
        entry.disabled = True
        session.add(entry)

        payload = json.dumps({"user_id": user_id})
        session.add(SyncEvent(action="delete", payload=payload))
        session.commit()

        await Notifier.on_blacklist_deleted(session, user.qq, user_id, type_="soft_delete")
    return {"msg": "Soft deleted"}
