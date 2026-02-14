import asyncio
import io
import os
import time
import uuid
from contextlib import asynccontextmanager

from PIL import Image, UnidentifiedImageError
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session, select, text
from starlette.staticfiles import StaticFiles

from app.config import settings
from app.routers import bot, sync
from app.utils.database import init_db, engine_sys, engine_bl
from app.utils.logging import logger
from app.utils.models import SystemConfig
from app.utils.sessions import session_store, code_store, rate_limiter
from app.utils.ws_manager import ws_manager

DATA_DIR = "data"
UPLOAD_DIR = "data/uploads"

# 1. 定义后缀白名单
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
# 2. 限制最大文件大小，防止 DoS
MAX_FILE_SIZE = 20 * 1024 * 1024


# 后台清理任务
async def cleanup_loop():
    logger.info("⏳ 启动后台清理任务...")
    while True:
        try:
            await asyncio.sleep(600)  # 每 10 分钟
            session_store.cleanup()
            code_store.cleanup()
            rate_limiter.cleanup()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"清理任务执行出错: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 初始化数据库 & 迁移
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    init_db()

    # === 自动执行数据库迁移 (Alembic) ===
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ALEMBIC_INI_PATH = os.path.join(BASE_DIR, "alembic.ini")

        if os.path.exists(ALEMBIC_INI_PATH):
            logger.info(f"正在加载迁移配置: {ALEMBIC_INI_PATH}")
            alembic_cfg = Config(ALEMBIC_INI_PATH)

            # 关键：显式设置脚本路径，防止相对路径失效
            alembic_cfg.set_main_option("script_location", os.path.join(BASE_DIR, "migrations"))

            # 执行升级
            command.upgrade(alembic_cfg, "head")
            logger.success("✅ 数据库自动迁移完成")
        else:
            logger.warning("⚠️ 未找到 alembic.ini，跳过自动迁移")
    except Exception as e:
        # 如果迁移失败，记录严重错误，通常建议此时停止服务器以免数据损坏
        logger.error(f"❌ 数据库自动迁移失败: {e}")
        import traceback
        traceback.print_exc()
        raise e

    # 2. 初始化系统配置默认值
    try:
        with Session(engine_sys) as session:
            if not session.get(SystemConfig, "ONEBOT_API_URL"):
                session.add(SystemConfig(key="ONEBOT_API_URL", value="", description="Bot API 地址"))
            if not session.get(SystemConfig, "DEFAULT_KEY_PERMS"):
                session.add(SystemConfig(key="DEFAULT_KEY_PERMS", value="read", description="API Key 默认权限"))
            if not session.get(SystemConfig, "ENABLE_AUTO_REG"):
                session.add(SystemConfig(key="ENABLE_AUTO_REG", value="false", description="是否开启自动注册"))
            if not session.get(SystemConfig, "DEFAULT_AUTO_ROLE"):
                session.add(SystemConfig(key="DEFAULT_AUTO_ROLE", value="user", description="自动注册默认权限"))
            if not session.get(SystemConfig, "SESSION_TIMEOUT"):
                session.add(SystemConfig(key="SESSION_TIMEOUT", value="1800", description="会话超时时间(秒)"))
            if not session.get(SystemConfig, "CODE_TIMEOUT"):
                session.add(SystemConfig(key="CODE_TIMEOUT", value="300", description="验证码有效期(秒)"))
            if not session.get(SystemConfig, "MAIL_HOST"):
                session.add(SystemConfig(key="MAIL_HOST", value="smtp.qq.com", description="SMTP服务器"))
            if not session.get(SystemConfig, "MAIL_PORT"):
                session.add(SystemConfig(key="MAIL_PORT", value="465", description="SMTP端口(SSL)"))
            if not session.get(SystemConfig, "MAIL_USER"):
                session.add(SystemConfig(key="MAIL_USER", value="", description="发件人账号"))
            if not session.get(SystemConfig, "MAIL_PASS"):
                session.add(SystemConfig(key="MAIL_PASS", value="", description="发件人密码/授权码"))
            if not session.get(SystemConfig, "MAIL_FROM"):
                session.add(SystemConfig(key="MAIL_FROM", value="", description="发件人邮箱(如与账号不同)"))
            session.commit()

        logger.info("正在从数据库加载系统配置...")
        db_configs = session.exec(select(SystemConfig)).all()
        for conf in db_configs:
            if hasattr(settings, conf.key):
                # 获取原始类型，进行正确转换 (因为数据库存的是字符串)
                current_val = getattr(settings, conf.key)
                target_type = type(current_val)

                try:
                    new_value = conf.value
                    if target_type is int:
                        new_value = int(conf.value)
                    elif target_type is bool:
                        new_value = conf.value.lower() == "true"

                    setattr(settings, conf.key, new_value)
                    # logger.info(f"已加载配置: {conf.key}={new_value}")
                except Exception as e:
                    logger.warning(f"配置加载类型转换失败 {conf.key}: {e}")
    except Exception as e:
        logger.error(f"系统配置初始化失败: {e}")

    # 3. 启动后台任务
    task = asyncio.create_task(cleanup_loop())

    logger.info(f"🚀 Server running on port {settings.PORT}")

    yield  # 服务运行中...

    # === 4. 关闭清理任务 ===
    logger.info("⏳ 正在停止服务，开始清理资源...")
    task.cancel()

    # === 强制数据落盘 ===
    try:
        # 1. 强制执行 Checkpoint
        # TRUNCATE 模式会将 WAL 里的所有数据移动到 DB 主文件，并把 WAL 文件大小截断为 0
        # 这是最彻底的“保存并关闭”方式
        with Session(engine_sys) as session:
            session.exec(text("PRAGMA wal_checkpoint(TRUNCATE);"))
            logger.info("✅ System DB: WAL Checkpoint 完成")

        # engine_bl 也要做同样的操作
        with Session(engine_bl) as session:
            session.exec(text("PRAGMA wal_checkpoint(TRUNCATE);"))
            logger.info("✅ Blacklist DB: WAL Checkpoint 完成")

    except Exception as e:
        logger.error(f"❌ Checkpoint 执行失败: {e}")

    # 2. 彻底释放连接池
    # 这步很重要，它会关闭所有文件句柄，解除文件锁定
    engine_sys.dispose()
    engine_bl.dispose()

    logger.info("🛑 服务已停止")


app = FastAPI(title="Blacklist Server", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(bot.router)
app.include_router(sync.router)


# =======================
# 📝 请求日志中间件
# =======================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url}")
    # 跳过 WebSocket 握手请求
    # WebSocket 握手是 GET 请求且包含 Upgrade 头，读取 body 可能导致阻塞或失败
    if request.url.path == "/ws" or request.headers.get("upgrade", "").lower() == "websocket":
        return await call_next(request)

    start_time = time.time()

    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000

    method = request.method
    url = request.url.path
    log_msg = f"请求: {method} {url} | 状态: {response.status_code} | 耗时: {process_time:.2f}ms"

    if response.status_code >= 400:
        logger.warning(log_msg)  # 错误请求用 warning
    else:
        logger.info(log_msg)  # 正常请求用 info

    return response


# =======================
# 🛡️ 异常处理
# =======================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "msg": exc.detail, "data": None})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled Error: {exc}")
    return JSONResponse(status_code=500, content={"code": 500, "msg": f"Internal Error: {str(exc)}", "data": None})


@app.get("/")
def health_check():
    return {"status": "ok", "version": "1.2.0"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # --- 阶段一：基础过滤 ---
    filename_parts = file.filename.split(".")
    if len(filename_parts) < 2:
        raise HTTPException(400, "文件名格式错误")

    ext = filename_parts[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "不支持的文件类型")

    # --- 阶段二：内存级安全检查 ---
    # 读取文件内容到内存
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件大小超过限制")

    try:
        # 使用 Pillow 尝试打开，这会自动校验 Magic Number 和文件结构的完整性
        image = Image.open(io.BytesIO(content))
        image.verify()  # 仅校验结构，不解码图像数据，速度快

        # 重新打开以便处理（verify后需要重新打开）
        image = Image.open(io.BytesIO(content))
    except (UnidentifiedImageError, Exception):
        raise HTTPException(400, "无效的图像文件或文件已损坏")

    # --- 阶段三：清洗与重构 (最关键的一步) ---
    # 生成随机文件名
    safe_filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, safe_filename)

    # ⚠️ 极其重要：不要直接保存原文件！
    # 而是将 Pillow 读取到的图像对象，重新保存到磁盘。
    # 这将剥离掉文件中所有非像素数据（包括潜在的 PHP/JS 恶意载荷）
    try:
        # 转换模式以兼容某些格式 (如把 P 模式转为 RGB)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGBA")
        else:
            image = image.convert("RGB")

        image.save(filepath, quality=90)  # 重新编码保存
    except Exception as e:
        logger.error(f"文件清洗失败: {e}")
        raise HTTPException(500, "文件处理失败")

    return {"url": f"/blacklist-api/uploads/{safe_filename}"}


# =======================
# 🔌 WebSocket 入口
# =======================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 连接逻辑：先 connect 再 loop
    try:
        await ws_manager.connect(websocket)

        while True:
            # 接收前端消息
            data = await websocket.receive_json()
            # 捕获处理逻辑中的错误，防止导致 WS 断开
            try:
                await ws_manager.handle_message(websocket, data)
            except Exception as e:
                logger.error(f"WS Handling Error: {e}")
                if isinstance(data, dict) and "req_id" in data:
                    await websocket.send_json({
                        "req_id": data["req_id"],
                        "code": 500,
                        "msg": f"Internal Error: {str(e)}"
                    })
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        # 如果是 connect 阶段抛出的异常 (如 IP 限制)，这里捕获
        logger.warning(f"WS连接中断或被拒绝: {e}")
        # 尝试安全断开，如果已经断开了会抛错，忽略即可
        try:
            await websocket.close()
        except:
            pass
        ws_manager.disconnect(websocket)
