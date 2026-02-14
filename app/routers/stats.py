import platform
import time
from datetime import datetime, timezone

from sqlmodel import select, desc, text, func, Session

from app.utils.models import OperationLog, BlacklistEntry, Application, User, WhitelistEntry, Role
from app.utils.permissions import check_role
from app.utils.ws_manager import ws_manager


async def get_dashboard_stats(session: Session, user: User):
    # 允许所有登录用户查看基础统计
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN, Role.USER])

    # --- 1. 基础总数 ---
    total_blacklist = session.exec(select(func.count()).select_from(BlacklistEntry)).one()
    total_whitelist = session.exec(select(func.count()).select_from(WhitelistEntry)).one()
    total_users = session.exec(select(func.count()).select_from(User)).one()
    pending_apps = session.exec(
        select(func.count()).select_from(Application).where(Application.status == "pending")).one()

    # --- 2. 今日新增 ---
    # 获取当前 UTC 时间
    now_utc = datetime.now(timezone.utc)
    # 获取 UTC 当天的 0 点
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    today_blacklist = session.exec(
        select(func.count())
        .select_from(OperationLog)
        .where(OperationLog.event == "blacklist.created")
        .where(OperationLog.created_at >= today_start)
    ).one()

    # --- 3. 原因分布 (Top 5) ---
    reason_stats = session.exec(
        select(BlacklistEntry.reason, func.count(BlacklistEntry.reason).label("count"))
        .group_by(BlacklistEntry.reason)
        .order_by(desc("count"))
        .limit(5)
    ).all()

    # --- 4. 来源构成分析 ---
    # 逻辑：如果 operator_id == source_id，视为“手动添加”；否则视为“举报/审批”
    # 注意：SQLite 的 case/when 语法

    # 统计手动添加的数量
    manual_count = session.exec(
        select(func.count())
        .select_from(BlacklistEntry)
        .where(BlacklistEntry.operator_id == BlacklistEntry.source_id)
    ).one()

    # 统计举报/审批的数量
    report_count = session.exec(
        select(func.count())
        .select_from(BlacklistEntry)
        .where(BlacklistEntry.operator_id != BlacklistEntry.source_id)
    ).one()

    # --- 5. 最近动态 (Timeline) ---
    recent_logs = session.exec(
        select(OperationLog)
        .where(OperationLog.event.in_(["app.created", "app.handled", "blacklist.created", "blacklist.updated", "blacklist.deleted"]))
        .order_by(OperationLog.created_at.desc())
        .limit(10)
    ).all()

    # --- 6. 系统自检逻辑 ---
    db_status = "ok"
    db_latency = 0
    try:
        t0 = time.perf_counter()
        session.exec(text("SELECT 1")).first()  # 真实执行 SQL
        db_latency = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        db_status = "error"

    ws_count = len(ws_manager.authenticated_connections)

    return {
        "counts": {
            "blacklist": total_blacklist,
            "blacklist_today": today_blacklist,
            "whitelist": total_whitelist,
            "users": total_users,
            "pending": pending_apps
        },
        "charts": {
            "reasons": [{"name": r or "未分类", "value": c} for r, c in reason_stats],
            "sources": [
                {"name": "手动添加", "value": manual_count},
                {"name": "举报审批", "value": report_count}
            ]
        },
        "recent_logs": [log.model_dump() for log in recent_logs],
        "system_info": {
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "db_status": db_status,
            "db_latency": db_latency,
            "ws_active": ws_count,
            "server_time": datetime.now(timezone.utc).isoformat()
        }
    }
