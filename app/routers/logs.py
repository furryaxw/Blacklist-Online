from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select, func, delete, col

from app.utils.models import User, Role, OperationLog
from app.utils.notifier import Notifier
from app.utils.permissions import check_role


async def get_operation_logs(session: Session, user: User, payload: dict):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])

    page = int(payload.get("page", 1))
    size = int(payload.get("size", 20))
    offset = (page - 1) * size

    # 查询总数
    total = session.exec(select(func.count()).select_from(OperationLog)).one()

    # 分页查询，倒序
    logs = session.exec(
        select(OperationLog)
        .order_by(OperationLog.created_at.desc())
        .offset(offset)
        .limit(size)
    ).all()

    return {
        "items": [log.model_dump() for log in logs],
        "total": total,
        "page": page,
        "size": size
    }


async def clean_operation_logs(session: Session, user: User, payload: dict):
    check_role(user, [Role.OWNER])
    days = int(payload.get("days", 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # 定义不可删除的敏感事件类型
    immutable_events = [
        "system.secret_refreshed",
        "key.created",
        "key.deleted",
        "user.created",
        "user.deleted",
        "user.updated"
    ]

    statement = delete(OperationLog).where(
        OperationLog.created_at < cutoff,
        OperationLog.event.not_in(immutable_events)
    )
    result = session.exec(statement)
    session.commit()
    deleted_count = result.rowcount

    await Notifier.on_logs_cleaned(session, user.qq, deleted_count, days)
    return {"msg": f"已清理 {deleted_count} 条旧日志"}


async def export_operation_logs(session: Session, user: User):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])
    # 导出全部日志，倒序
    logs = session.exec(select(OperationLog).order_by(OperationLog.created_at.desc())).all()
    return [log.model_dump() for log in logs]


async def get_target_history(session: Session, user: User, payload: dict):
    """获取指定目标的黑名单变更历史"""
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN])
    target = payload.get("target")
    if not target:
        return []

    # 筛选相关事件
    target_events = [
        "blacklist.created",
        "blacklist.updated",
        "blacklist.deleted",
        "app.handled"  # 也可以加上审批记录
    ]

    # 在 JSON 字符串中模糊搜索 target ID
    # 注意：这依赖于 Notifier 中将 QQ 号存为了 "target": "QQ号" 或类似的结构
    logs = session.exec(
        select(OperationLog)
        .where(col(OperationLog.event).in_(target_events))
        .where(col(OperationLog.details).contains(str(target)))
        .order_by(OperationLog.created_at.desc())
    ).all()

    return [log.model_dump() for log in logs]
