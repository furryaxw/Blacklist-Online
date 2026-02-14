import secrets

from sqlmodel import Session, select

from app.utils.logging import logger
from app.utils.models import Role, User, ApiKey
from app.utils.notifier import Notifier


async def get_keys(session: Session, user: User):
    # 构建查询：查 ApiKey 的全部字段 + User 表的 qq 字段
    stmt = select(ApiKey, User.qq).join(User, ApiKey.created_by == User.id, isouter=True)

    # 权限隔离
    if user.role in [Role.USER, Role.ADMIN]:
        stmt = stmt.where(ApiKey.created_by == user.id)
    # Role.OWNER 和 Role.SUPER_ADMIN 可以看到所有 Key

    results = session.exec(stmt).all()

    # 构造返回数据
    data = []
    for key_obj, creator_qq in results:
        # 将 SQLModel 对象转为字典
        key_dict = key_obj.model_dump()
        # 注入 QQ 号字段，如果没找到用户则显示 "Unknown"
        key_dict["created_by_qq"] = creator_qq or "Unknown"
        data.append(key_dict)

    return data


async def create_key(session: Session, user: User, payload: dict):
    new_key = ApiKey(
        key=secrets.token_urlsafe(32),
        description=payload.get("description"),
        permissions=payload.get("permissions", "read,write"),
        created_by=user.id
    )
    session.add(new_key)
    session.commit()

    logger.success(f"用户 [{user.qq}] 创建 API Key: {new_key.key[:8]}...")

    await Notifier.on_key_created(session, user.qq, new_key)
    return new_key.model_dump()


async def delete_key(session: Session, user: User, key_id: int):
    key = session.get(ApiKey, key_id)
    if not key: raise Exception("Key not found")

    # 权限校验
    is_owner_or_super = user.role in [Role.OWNER, Role.SUPER_ADMIN]
    is_creator = (key.created_by == user.id)

    if not (is_owner_or_super or is_creator):
        raise Exception("只能删除自己创建的 Key")

    session.delete(key)
    session.commit()

    await Notifier.on_key_deleted(session, user.qq, key_id, key.description)
    return {"msg": "Deleted"}


async def update_key(session: Session, user: User, payload: dict):
    key_id = payload.get("id")
    key_entry = session.get(ApiKey, key_id)
    if not key_entry:
        raise Exception("Key not found")

    # 权限校验
    is_owner_or_super = user.role in [Role.OWNER, Role.SUPER_ADMIN]
    is_creator = (key_entry.created_by == user.id)

    if not (is_owner_or_super or is_creator):
        raise Exception("权限不足")

    if "description" in payload:
        key_entry.description = payload["description"]
    if "permissions" in payload:
        # 如果需要限制普通用户修改权限，可以在这里加判断
        key_entry.permissions = payload["permissions"]

    # 允许更新绑定的实例 ID (如果需要)
    if "instance_uuid" in payload:
        key_entry.instance_uuid = payload["instance_uuid"]

    session.add(key_entry)
    session.commit()

    await Notifier.on_key_updated(session, user.qq, key_id, payload)
    return key_entry.model_dump()
