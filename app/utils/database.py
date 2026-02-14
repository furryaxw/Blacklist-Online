from sqlalchemy import event
from sqlmodel import SQLModel, create_engine, Session

from app.config import settings
from app.utils.models import User, ApiKey, BlacklistEntry, SyncEvent, Application, SystemConfig, OperationLog, \
    WhitelistEntry

# 1. 创建两个独立的引擎
# check_same_thread=False 是 SQLite 必须的
connect_args = {"check_same_thread": False}

engine_sys = create_engine(settings.DATABASE_URL_SYSTEM, echo=False, connect_args=connect_args)
engine_bl = create_engine(settings.DATABASE_URL_BLACKLIST, echo=False, connect_args=connect_args)


# 为每个 SQLite 引擎开启 WAL 模式
def _enable_wal(dbapi_con, con_record):
    dbapi_con.execute("PRAGMA journal_mode=WAL;")
    dbapi_con.execute("PRAGMA synchronous=NORMAL;")  # 兼顾性能与安全


event.listen(engine_sys, "connect", _enable_wal)
event.listen(engine_bl, "connect", _enable_wal)

# 2. 定义模型到引擎的映射 (Binds)
# 只要在这里定义好，后续代码 session.add(user) 会自动去 system.db，session.add(entry) 会去 blacklist.db
binds = {
    # --- 系统库 ---
    User: engine_sys,
    ApiKey: engine_sys,
    SystemConfig: engine_sys,
    OperationLog: engine_sys,

    # --- 业务库 ---
    BlacklistEntry: engine_bl,
    WhitelistEntry: engine_bl,
    SyncEvent: engine_bl,
    Application: engine_bl
}


def init_db():
    """
    初始化数据库表结构
    需要分别在对应的引擎上创建表
    """
    # 在 System 引擎创建 User 和 ApiKey
    SQLModel.metadata.create_all(engine_sys)

    # 在 Blacklist 引擎创建业务表
    # 注意：如果不指定 binds，create_all 默认会在该引擎创建所有表
    # 所以这里我们还是利用 SQLModel 的自动识别，或者简单粗暴地让两个库都拥有所有表结构（但只用其中一部分）
    # 为了洁癖，我们可以手动指定创建哪些表，但 SQLAlchemy 的 create_all 比较宽容
    # 最简单的做法：直接全量 create，多余的空表不影响使用。
    # 或者使用更高级的迁移工具 (Alembic)。
    # 这里为了简便，我们让两个库都跑一次 create_all，虽然会有冗余空表，但最稳定。
    SQLModel.metadata.create_all(engine_bl)


def get_session():
    """
    创建一个绑定了多个引擎的 Session
    """
    # 将主引擎设为 sys，并将其他表 bind 到 bl
    with Session(engine_sys, binds=binds) as session:
        yield session
