from sqlmodel import Session, select

from app.utils.logging import logger
from app.utils.models import Role, User
from app.utils.notifier import Notifier
from app.utils.permissions import check_manage_permission, check_role
from app.utils.sessions import session_store


async def get_users(session: Session, user: User):
    # 根据角色返回不同数据
    if user.role in [Role.OWNER, Role.SUPER_ADMIN]:
        # 高级管理员：查看所有用户
        return session.exec(select(User)).all()
    elif user.role in [Role.ADMIN, Role.USER]:
        # 普通管理员/用户：只看自己
        return [user]
    else:
        return []


async def get_online_sessions(session: Session, user: User):
    # 1. 获取所有活跃会话
    all_sessions = session_store.list_all()

    # 2. 权限判断
    if user.role in [Role.OWNER, Role.SUPER_ADMIN]:
        # 高级管理员：查看所有人
        return all_sessions
    else:
        # Admin / User：只返回属于自己的会话
        # 注意：这里我们要确保数据类型一致，user.qq 可能是 int 或 str，建议都转 str 对比
        my_qq = str(user.qq)
        return [s for s in all_sessions if str(s["user_id"]) == my_qq]


async def kill_session(session: Session, user: User, payload: dict):
    target_token = payload.get("token")
    if not target_token: raise Exception("Token不能为空")

    # 1. 先查询该会话是否存在（这里调用 get 会刷新一次活跃时间，但反正马上要删了，没影响）
    target_session = session_store.get(target_token)
    if not target_session:
        return {"msg": "会话已过期或不存在"}

    # 2. 权限校验
    is_high_priv = user.role in [Role.OWNER, Role.SUPER_ADMIN]
    is_self = str(target_session["user_id"]) == str(user.qq)

    if not is_high_priv and not is_self:
        raise Exception("权限不足：你只能下线自己的设备")

    await Notifier.on_session_killed(session, target_token, target_session["user_id"], user.qq)

    # 3. 执行删除
    session_store.delete(target_token)

    # 4. 日志记录
    log_msg = f"强制下线会话 (Target: {target_session['user_id']})"
    logger.warning(f"用户 {user.qq} {log_msg}")

    return {"msg": "已强制下线"}


async def create_user(session: Session, operator: User, payload: dict):
    check_role(operator, [Role.OWNER, Role.SUPER_ADMIN])
    target_qq = payload.get("qq")
    target_role = payload.get("role")

    # 1. 检查是否存在
    if session.exec(select(User).where(User.qq == target_qq)).first():
        raise Exception("QQ号已存在")

    # 2. 检查权限 (Owner可以创建任意角色，SuperAdmin只能创建Admin)
    check_manage_permission(operator, target_role)

    new_user = User(qq=target_qq, role=target_role)
    session.add(new_user)
    session.commit()
    logger.success(f"管理员 [{operator.qq}] 创建新用户: {target_qq} (角色: {target_role})")

    await Notifier.on_user_created(session, operator.qq, new_user)
    return new_user.model_dump()


async def update_user_role(session: Session, operator: User, user_id: int, payload: dict):
    """切换用户权限，避免删除重建"""
    check_role(operator, [Role.OWNER, Role.SUPER_ADMIN])
    target_user = session.get(User, user_id)
    if not target_user: raise Exception("用户不存在")
    new_role = payload.get("role")

    # 检查操作者是否有权设置该目标角色
    check_manage_permission(operator, new_role)
    # 检查操作者是否有权修改该用户当前的角色
    check_manage_permission(operator, target_user.role)

    old_role = target_user.role
    target_user.role = new_role
    session.add(target_user)
    session.commit()

    await Notifier.on_user_role_changed(session, operator.qq, target_user, old_role)
    return target_user.model_dump()


async def delete_user(session: Session, operator: User, target_id: int):
    check_role(operator, [Role.OWNER, Role.SUPER_ADMIN])
    target_user = session.get(User, target_id)
    if not target_user: raise Exception("用户不存在")
    if target_user.id == operator.id: raise Exception("不能删除自己")

    check_manage_permission(operator, target_user.role)
    deleted_qq = target_user.qq
    session.delete(target_user)
    session.commit()
    logger.warning(f"管理员 [{operator.qq}] 删除了用户: {target_user.qq}")

    await Notifier.on_user_deleted(session, operator.qq, deleted_qq, target_id)
    session_store.delete_by_user(target_user.qq)
    return {"msg": "User deleted"}


async def _delete_user(session: Session, target_id: int):
    target_user = session.get(User, target_id)
    if not target_user: raise Exception("用户不存在")

    deleted_qq = target_user.qq
    session.delete(target_user)
    session.commit()

    await Notifier.on_user_deleted(session, 'System', deleted_qq, target_id)
    session_store.delete_by_user(target_user.qq)
    return {"msg": "User deleted"}
