import os
import sys

from loguru import logger

# 确保日志目录存在
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 移除默认的控制台输出（默认是 DEBUG 级别，我们重新配置）
logger.remove()

# 1. 输出到控制台 (INFO 级别)
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# 2. 输出到文件 (每天 0 点轮转，保留 30 天，记录所有操作)
logger.add(
    os.path.join(log_dir, "server_{time:YYYY-MM-DD}.log"),
    rotation="00:00",  # 每天午夜轮转
    retention="30 days",  # 保留最近 30 天的日志
    level="INFO",  # 记录 INFO 及以上级别
    encoding="utf-8",  # 确保中文不乱码
    enqueue=True  # 异步写入，防止阻塞主线程
)

# 导出 logger 供其他模块使用
__all__ = ["logger"]
