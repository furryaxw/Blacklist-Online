import asyncio
import time
import traceback
from typing import List, Dict

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from app.utils.database import engine_sys, binds
from app.utils.logging import logger
from app.utils.models import User, unix_now
from app.utils.sessions import session_store, rate_limiter

# 定义动作限流规则配置 (次数, 秒数)
# 越敏感、消耗越大的操作，限制越严
ACTION_LIMITS = {
    "admin.logs.export": (1, 300),  # 5分钟1次 (高IO操作)
    "admin.system.backup": (1, 3600),  # 1小时1次
    "public.appeal.submit": (5, 3600),  # 1小时5次
    "admin.blacklist.list": (20, 60),  # 1分钟20次
    "default": (120, 60)  # 默认 1分钟120次
}


class WebSocketManager:
    def __init__(self):
        logger.info("WebSocket Manager")
        # 原始连接池
        self.active_connections: List[WebSocket] = []
        # 已认证连接: WebSocket -> User
        self.authenticated_connections: Dict[WebSocket, User] = {}
        # 连接对应的 Token: WebSocket -> Token (用于精准踢人)
        self.socket_tokens: Dict[WebSocket, str] = {}
        # IP 计数
        self.ip_counts: Dict[str, int] = {}

    async def connect(self, websocket: WebSocket):
        # 尝试获取真实 IP (处理反向代理情况)
        real_ip = websocket.client.host
        if websocket.headers.get("x-forwarded-for"):
            real_ip = websocket.headers.get("x-forwarded-for").split(",")[0].strip()
        elif websocket.headers.get("x-real-ip"):
            real_ip = websocket.headers.get("x-real-ip")

        client_ip = real_ip if real_ip else "unknown"

        # 调高限制，或者仅在能获取真实IP时限制
        current_count = self.ip_counts.get(client_ip, 0)
        if current_count >= 50:  # 建议调大到 50 或更多
            logger.warning(f"IP {client_ip} 达到最大连接数限制，拒绝连接")
            await websocket.close(code=1008)
            return

        await websocket.accept()
        self.active_connections.append(websocket)
        self.ip_counts[client_ip] = self.ip_counts.get(client_ip, 0) + 1

    def disconnect(self, websocket: WebSocket):

        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # 清理认证信息
        if websocket in self.authenticated_connections:
            del self.authenticated_connections[websocket]

        # 清理 Token 映射
        if websocket in self.socket_tokens:
            del self.socket_tokens[websocket]

        # 清理 IP 计数
        client_ip = websocket.client.host if websocket.client else "unknown"
        if websocket.headers.get("x-forwarded-for"):
            client_ip = websocket.headers.get("x-forwarded-for").split(",")[0].strip()

        if self.ip_counts.get(client_ip, 0) > 0:
            self.ip_counts[client_ip] -= 1

    async def handle_message(self, websocket: WebSocket, message: dict):
        """
        消息格式约定:
        {
            "req_id": "uuid",
            "action": "auth/login",  # 对应 URL
            "data": { ... },         # 对应 Body 或 Query
            "token": "..."           # 可选，鉴权用
        }
        """
        # 在此处延迟导入，解决循环依赖
        from app.routers import auth, system, stats, logs, keys, users, apps, blacklist, whitelist

        req_id = message.get("req_id")
        action = message.get("action")
        payload = message.get("data", {})

        _real_ip = websocket.client.host
        if websocket.headers.get("x-forwarded-for"):
            _real_ip = websocket.headers.get("x-forwarded-for").split(",")[0].strip()
        elif websocket.headers.get("x-real-ip"):
            _real_ip = websocket.headers.get("x-real-ip")
        client_ip = _real_ip if _real_ip else "unknown"

        # --- 业务级限流检查 ---
        # 1. 确定限流键 (优先使用 User ID，未登录使用 IP)
        session_user = self.authenticated_connections.get(websocket)
        limit_key = f"ws:{session_user.qq}" if session_user else f"ws_ip:{client_ip}"

        # 2. 获取该动作的限制规则
        limit_count, limit_window = ACTION_LIMITS.get(action, ACTION_LIMITS["default"])

        # 3. 构造具体的限流标识 (Key + Action)
        # 这样同一个用户，搜索和导出日志的限流是分开计算的
        specific_key = f"{limit_key}:{action}"

        if not rate_limiter.is_allowed(specific_key, limit_count, limit_window):
            # 触发限流，直接返回错误，不处理业务
            logger.warning(f"Rate limit exceeded: {specific_key}")
            await websocket.send_json({
                "req_id": req_id,
                "code": 429,
                "msg": "操作过于频繁，请稍后再试"
            })
            return

        # 默认响应
        response = {"req_id": req_id, "code": 200, "data": None, "msg": "ok"}
        start_time = time.time()

        try:
            # 传入 binds 参数，确保 User 表去 engine_sys，BlacklistEntry 表去 engine_bl
            with Session(engine_sys, binds=binds) as session:
                # 1. 免鉴权白名单
                public_actions = [
                    "auth.login",
                    "auth.send_code",
                    "system.ping",
                    "admin.system.get_public",
                    "public.appeal.submit"
                ]

                if websocket not in self.authenticated_connections and action not in public_actions:
                    await websocket.send_json({
                        "req_id": req_id, "code": 401, "msg": "请先登录"
                    })
                    return

                # 2. 获取当前用户 (如果已认证)
                session_user = self.authenticated_connections.get(websocket)
                # 这里的 session_user 是之前登录时查出来的，已经过期(Detached)了。
                # 必须用 merge 把它“复制”一份到当前的 session 里，才能正常使用。
                if session_user:
                    session_user = session.merge(session_user)

                response = {"req_id": req_id, "code": 200, "msg": "ok", "data": None}

                # === 路由分发 ===

                # [System]
                if action == "system.ping":
                    response["data"] = {"timestamp": unix_now()}

                # [Auth]
                elif action == "auth.login":
                    fingerprint = payload.get("fingerprint", "unknown")
                    # === 区分验证码登录与Token恢复 ===
                    if "code" in payload:
                        # A. 验证码登录 (payload包含 qq, code)
                        login_result = await auth.login(session, payload, client_ip, fingerprint)
                        response["data"] = login_result

                        # 登录成功后，自动将连接设为已认证
                        user_data = login_result.get("user")
                        token = login_result.get("access_token")
                        if user_data:
                            stmt = select(User).where(User.qq == user_data["qq"])
                            user_obj = session.execute(stmt).scalars().first()

                            if user_obj:
                                self.authenticated_connections[websocket] = user_obj
                                if token:
                                    self.socket_tokens[websocket] = token
                    else:
                        # B. Token 恢复会话 (payload包含 token)
                        token = payload.get("token")
                        try:
                            user_obj = self.get_current_user(session, token, client_ip, fingerprint)
                            self.authenticated_connections[websocket] = user_obj
                            self.socket_tokens[websocket] = token
                            response["data"] = {"user": user_obj.model_dump(), "msg": "认证成功"}
                        except Exception as e:
                            # 明确返回 401 以便前端跳转登录页
                            response["code"] = 401
                            response["msg"] = str(e)

                elif action == "auth.send_code":
                    fingerprint = payload.get("fingerprint", "unknown")
                    response["data"] = await auth.send_code(session, payload, client_ip, fingerprint)

                # [User Info]
                elif action == "auth.get_current_user":
                    response["data"] = session_user
                elif action == "auth.update_subscriptions":
                    response["data"] = await auth.update_subscriptions(session, session_user, payload)

                # [Dashboard]
                elif action == "dashboard.stats":
                    response["data"] = await stats.get_dashboard_stats(session, session_user)

                # [Admin: Logs]
                elif action == "admin.logs.list":
                    response["data"] = await logs.get_operation_logs(session, session_user, payload)
                elif action == "admin.logs.clean":
                    response["data"] = await logs.clean_operation_logs(session, session_user, payload)
                elif action == "admin.logs.export":
                    response["data"] = await logs.export_operation_logs(session, session_user)
                elif action == "admin.logs.history":
                    response["data"] = await logs.get_target_history(session, session_user, payload)

                # [Admin: Keys]
                elif action == "admin.keys.list":
                    response["data"] = await keys.get_keys(session, session_user)
                elif action == "admin.keys.create":
                    response["data"] = await keys.create_key(session, session_user, payload)
                elif action == "admin.keys.delete":
                    response["data"] = await keys.delete_key(session, session_user, payload.get("key_id"))
                elif action == "admin.keys.update":
                    response["data"] = await keys.update_key(session, session_user, payload)

                # [Admin: System]
                elif action == "admin.system.get":
                    response["data"] = await system.get_system_config(session, session_user)
                elif action == "admin.system.get_public":
                    response["data"] = await system.get_public_system_config(session, session_user)
                elif action == "admin.system.update":
                    response["data"] = await system.update_system_config(session, session_user, payload)
                elif action == "admin.system.get_qq_profile":
                    response["data"] = await system.get_qq_profile(session, session_user, payload)
                elif action == "admin.system.clean_logs":
                    response["data"] = await system.clean_logs(session, session_user, payload)
                elif action == "admin.system.export":
                    response["data"] = await system.export_data(session, session_user)
                elif action == "admin.system.import":
                    response["data"] = await system.import_data(session, session_user, payload)

                # [Admin: Testing]
                elif action == "admin.system.test_bot":
                    response["data"] = await system.test_bot_connection(session, session_user)
                elif action == "admin.system.test_msg":
                    response["data"] = await system.test_bot_message(session, session_user, payload.get("target_qq"))
                elif action == "admin.system.test_email":
                    response["data"] = await system.test_email_settings(session, session_user,
                                                                        payload.get("target_email"))

                # [Admin: Users]
                elif action == "admin.users.list":
                    response["data"] = await users.get_users(session, session_user)
                elif action == "admin.users.create":
                    response["data"] = await users.create_user(session, session_user, payload)
                elif action == "admin.users.set_role":
                    response["data"] = await users.update_user_role(session, session_user, payload.get("user_id"),
                                                                    payload)
                elif action == "admin.users.delete":
                    response["data"] = await users.delete_user(session, session_user, payload.get("target_id"))

                # [Admin: Sessions]
                elif action == "admin.sessions.list":
                    response["data"] = await users.get_online_sessions(session, session_user)
                elif action == "admin.sessions.kill":
                    response["data"] = await users.kill_session(session, session_user, payload)

                # [Admin: Applications]
                elif action == "admin.apps.list":
                    response["data"] = await apps.get_applications(session, session_user,
                                                                   payload.get("status", "pending"))
                elif action == "admin.apps.handle":
                    response["data"] = await apps.handle_application(session, session_user, payload.get("app_id"),
                                                                     payload)
                elif action == "admin.apps.history":
                    response["data"] = await apps.get_application_history(session, session_user)
                elif action == "admin.apps.cancel":
                    response["data"] = await apps.cancel_application(session, payload)
                elif action == "public.appeal.submit":
                    response["data"] = await apps.submit_appeal(session, payload, client_ip)

                # [Admin: Blacklist]
                elif action == "admin.blacklist.list":
                    response["data"] = await blacklist.get_blacklist(session, session_user, payload)
                elif action == "admin.blacklist.add":
                    response["data"] = await blacklist.add_blacklist(session, session_user, payload)
                elif action == "admin.blacklist.update_info":
                    response["data"] = await blacklist.update_blacklist(session, session_user, payload)
                elif action == "admin.blacklist.set_status":
                    response["data"] = await blacklist.update_blacklist_status(session, session_user,
                                                                               payload.get("user_id"), payload)
                elif action == "admin.blacklist.hard_delete":
                    response["data"] = await blacklist.hard_delete_blacklist(session, session_user,
                                                                             payload.get("user_id"))
                elif action == "admin.blacklist.soft_delete":
                    response["data"] = await blacklist.soft_delete_blacklist(session, session_user,
                                                                             payload.get("user_id"))

                # [Admin: Whitelist]
                elif action == "admin.whitelist.list":
                    response["data"] = await whitelist.get_whitelist(session, session_user)
                elif action == "admin.whitelist.add":
                    response["data"] = await whitelist.add_whitelist(session, session_user, payload)
                elif action == "admin.whitelist.delete":
                    response["data"] = await whitelist.delete_whitelist(session, session_user, payload.get("user_id"))

                # [User: Applications]
                elif action == "user.apps.list":
                    response["data"] = await apps.get_my_applications(session, session_user)
                elif action == "user.apps.submit":
                    response["data"] = await apps.submit_my_application(session, session_user, payload)

                else:
                    response["code"] = 404
                    response["msg"] = f"Action {action} not found"

        except Exception as e:
            logger.error(f"WS Error [{action}]: {str(e)}")
            traceback.print_exc()
            response["code"] = 500
            response["msg"] = str(e)

        await websocket.send_json(jsonable_encoder(response))

        # 记录日志
        if action not in ["system.ping", "dashboard.stats"]:
            status_code = response["code"]
            process_time = (time.time() - start_time) * 1000
            log_msg = f"请求: {action} | 数据: {payload} | 状态: {status_code} | 耗时: {process_time:.2f}ms"
            if status_code >= 400:
                logger.warning(log_msg)  # 错误请求用 warning
            else:
                logger.info(log_msg)  # 正常请求用 info

    def get_current_user(self, session: Session, token: str, client_ip: str, fingerprint: str) -> User:
        try:
            # 使用 session_store 获取会话信息
            session_data = session_store.auth_get(token, client_ip, fingerprint)
            if not session_data:
                raise Exception("会话已失效或环境发生变化，请重新登录")

            qq = session_data.get("user_id")

            stmt = select(User).where(User.qq == qq)
            user = session.execute(stmt).scalars().first()

            if not user: raise Exception("用户不存在")
            return user
        except Exception as e:
            logger.warning(f"认证失败: {e}")
            raise Exception("身份验证失败")

    async def broadcast(self, event: str, data: dict = None):
        """全员广播 (仅限已登录用户)"""
        message = {
            "type": "broadcast",
            "event": event,
            "data": jsonable_encoder(data) if data else {},
            "timestamp": unix_now()
        }

        if not self.authenticated_connections:
            return

        # 创建所有发送任务
        tasks = [
            connection.send_json(message)
            for connection in self.authenticated_connections.keys()
        ]

        # 并发执行，return_exceptions=True 防止某个连接断开影响其他人
        await asyncio.gather(*tasks, return_exceptions=True)

    # 发送给特定用户 (支持多设备)
    async def send_to_user(self, target_user_qq: str, event: str, data: dict = None, exclude_token: str = None):
        """
        向指定用户发送消息
        """
        message = {
            "type": "broadcast",
            "event": event,
            "data": jsonable_encoder(data) if data else {},
            "timestamp": unix_now()
        }

        # 筛选出属于该用户的连接
        target_conns = [
            ws for ws, user in self.authenticated_connections.items()
            if str(user.qq) == str(target_user_qq)
        ]

        for ws in target_conns:
            # 过滤掉指定的 Token (自己)
            if exclude_token and self.socket_tokens.get(ws) == exclude_token:
                continue

            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Push to {target_user_qq} failed: {e}")

    # 精准踢人方法
    async def kick_token(self, token: str, reason: str = "强制下线"):
        """
        根据 Token 找到对应的 WebSocket 并强制断开
        """
        # 找到对应 Token 的 WebSocket
        target_ws = None
        for ws, t in self.socket_tokens.items():
            if t == token:
                target_ws = ws
                break

        if target_ws:
            try:
                # 发送最后一条消息通知前端
                await target_ws.send_json({
                    "type": "broadcast",
                    "event": "system.kicked",
                    "data": {"reason": reason},
                    "timestamp": unix_now()
                })
                # 给一点时间让消息发出
                await asyncio.sleep(0.1)
                # 关闭连接
                await target_ws.close(code=1008)
                # 清理 (disconnect 会自动调用，但这里显式调用更安全)
                self.disconnect(target_ws)
                logger.info(f"已精准踢出 Token: {token[:8]}...")
            except Exception as e:
                logger.warning(f"踢出 Token 失败: {e}")

    # 批量发送给一组用户 (用于推送给所有管理员)
    async def send_to_users(self, target_qqs: list[str], event: str, data: dict = None):
        """
        向一组用户发送消息
        """
        if not target_qqs:
            return

        message = {
            "type": "broadcast",
            "event": event,
            "data": jsonable_encoder(data) if data else {},
            "timestamp": unix_now()
        }

        # 转为集合以提高查找效率
        target_set = set(str(qq) for qq in target_qqs)

        # 1. 收集所有需要发送的任务
        tasks = []
        # 注意：此处遍历字典时尽量不要修改它，如果担心线程安全可以加 list() 复制 keys
        # 但在单线程 asyncio 模型下，只要不发生 await 切换，遍历是安全的
        for ws, user in self.authenticated_connections.items():
            if str(user.qq) in target_set:
                tasks.append(ws.send_json(message))

        # 2. 使用 asyncio.gather 并行执行所有发送任务
        if tasks:
            # return_exceptions=True 非常关键：防止因为某一个连接断开抛错导致其他人收不到消息
            await asyncio.gather(*tasks, return_exceptions=True)


ws_manager = WebSocketManager()
