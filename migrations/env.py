import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

# 1. 将项目根目录加入 python path，确保能导入 app
sys.path.insert(0, os.getcwd())

# 2. 导入你的配置和模型
from app.config import settings
from sqlmodel import SQLModel

config = context.config
fileConfig(config.config_file_name)

# 3. 动态从 settings 读取数据库 URL，覆盖 alembic.ini 的配置
config.set_section_option("system", "sqlalchemy.url", settings.DATABASE_URL_SYSTEM)
config.set_section_option("blacklist", "sqlalchemy.url", settings.DATABASE_URL_BLACKLIST)

# 4. 指定目标元数据 (SQLModel 的 metadata 包含所有模型)
target_metadata = SQLModel.metadata


def run_migrations_offline():
    """离线模式 (即使不运行 Server 也能生成 SQL)"""
    databases = config.get_main_option("databases")
    for name in databases.split(","):
        # 获取对应数据库的 URL
        url = config.get_section_option(name, "sqlalchemy.url")
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            # 关键：开启 SQLite 批处理模式
            render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations(engine_name=name)


def run_migrations_online():
    """在线模式 (直接连接数据库进行迁移)"""
    databases = config.get_main_option("databases")

    # 遍历所有定义的数据库 (system, blacklist)
    for name in [n.strip() for n in databases.split(",")]:
        print(f"正在处理数据库: [{name}]")  # 增加打印方便调试

        # 获取配置
        cfg = config.get_section(name)
        if cfg is None:
            print(f"❌ 严重错误: 在 alembic.ini 中找不到 [{name}] 分段！")
            continue

        connectable = engine_from_config(
            cfg,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,  # 这里传入 SQLModel 的元数据
                # 关键：开启 SQLite 批处理模式，支持删除/修改列
                render_as_batch=True
            )

            with context.begin_transaction():
                context.run_migrations(engine_name=name)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
