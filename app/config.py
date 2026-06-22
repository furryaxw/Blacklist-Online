from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 后端版本号
    BACKEND_VERSION: str = "1.2.0"

    # --- 1. 基础环境配置 (保留在 .env) ---
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # 数据库地址
    DATABASE_URL_SYSTEM: str = "sqlite:///./data/system.db"
    DATABASE_URL_BLACKLIST: str = "sqlite:///./data/blacklist.db"

    # === 2. 动态配置 (提供默认值，启动后会被数据库值覆盖) ===

    # 默认为空，需要在前端设置
    ONEBOT_API_URL: str = ""

    # 动态配置 (默认值)
    SESSION_TIMEOUT: int = 1800  # 30分钟
    CODE_TIMEOUT: int = 300  # 5分钟

    class Config:
        env_file = ".env"
        # 允许 .env 中存在多余字段 (例如旧的配置未清理)
        extra = "ignore"


settings = Settings()
