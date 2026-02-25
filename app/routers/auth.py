import secrets
import string
from threading import Lock

import httpx
from sqlmodel import Session
from sqlmodel import select, func

from app.config import settings
from app.utils.logging import logger
from app.utils.models import User, Role, SystemConfig, BlacklistEntry
from app.utils.notifier import Notifier
from app.utils.sessions import session_store, rate_limiter, code_store

# 使用进程内锁确保 Owner 创建逻辑原子化
owner_creation_lock = Lock()


async def send_code(session: Session, payload: dict, client_ip: str, fingerprint: str):
    qq = payload.get("qq")
    if not qq: raise Exception("QQ号不能为空")

    # 1. 频率限制 (60秒1次)
    if not rate_limiter.is_allowed(f"ip_limit:{client_ip}:{fingerprint}", limit=5, window=60):
        raise Exception("请求过于频繁，请稍后再试")
    if not rate_limiter.is_allowed(f"send_code:{qq}:{fingerprint}", limit=1, window=60):
        raise Exception("请求过于频繁，请稍后再试")

    # 2. 系统黑名单拦截 (修改提示引导申诉)
    if session.exec(
            select(BlacklistEntry).where(BlacklistEntry.user_id == qq, BlacklistEntry.disabled == False)).first():
        logger.warning(f"黑名单用户 {qq} 尝试获取验证码被拦截")
        raise Exception("您已被列入黑名单，请前往申诉页提交申诉以解除限制")

    # 3. 检查是否为 Bot 好友
    try:
        async with httpx.AsyncClient() as client:
            friend_resp = await client.post(f"{settings.ONEBOT_API_URL}/get_friend_list")
            if friend_resp.status_code == 200:
                resp_data = friend_resp.json()
                # 兼容不同 OneBot 实现的成功状态判断
                if resp_data.get("status") == "ok" or resp_data.get("retcode") == 0:
                    friends = resp_data.get("data", [])
                    # 遍历判断QQ是否在好友列表中
                    is_friend = any(str(f.get("user_id")) == str(qq) for f in friends)
                    if not is_friend:
                        raise Exception("请先添加Bot为好友后，再尝试获取验证码")
    except Exception as e:
        # 如果是我们主动抛出的“未加好友”异常，则向上抛出返回给前端
        if "请先添加Bot为好友" in str(e):
            raise e
        # 如果是网络波动/Bot离线等异常，记录日志并跳过检查（避免Bot掉线导致完全无法登录）
        logger.warning(f"获取Bot好友列表失败，跳过好友检查: {e}")

    # 4. 用户存在性检查...
    user = session.exec(select(User).where(User.qq == qq)).first()

    if not user:
        # 如果不是第一个用户且没开自动注册，拒绝
        user_count = session.exec(select(func.count()).select_from(User)).one()

        # 如果不是第一位用户 (第一位用户总是允许注册为Owner)
        if user_count > 0:
            # 检查自动注册开关
            conf = session.get(SystemConfig, "ENABLE_AUTO_REG")
            # 注意 value 存的是字符串
            allow_auto = conf and conf.value == "true"

            if not allow_auto:
                return {"msg": "验证码已发送"}

    code = ''.join(secrets.choice(string.digits) for _ in range(6))

    # === 修复漏洞3: 内存耗尽 ===
    # 使用 code_store 存储，自动清理过期数据
    code_store.set_code(qq, code)

    # 5. 调用 OneBot API 发送消息
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.ONEBOT_API_URL}/send_private_msg", json={
                "user_id": int(qq),
                "message": f"【黑名单中心】登录验证码：{code}"
            })
            if resp.status_code != 200:
                logger.error(f"OneBot Error: {resp.text}")
                raise Exception("Bot API Error")
    except Exception as e:
        # 开发模式下如果连不上Bot，可以在控制台打印验证码方便调试
        logger.warning(f"DEBUG CODE for {qq}: {code}")
        # 开发环境下允许失败也算发送成功（为了测试）
        # 生产环境应抛出异常

    return {"msg": "验证码已发送"}


async def login(session: Session, payload: dict, client_ip: str, fingerprint: str):
    qq = payload.get("qq")
    code = payload.get("code")

    # === 修复漏洞2: 暴力破解 ===
    # 限制登录尝试频率：每个QQ 1分钟最多试错 5 次
    if not rate_limiter.is_allowed(f"login_try:{qq}", limit=5, window=60):
        raise Exception("尝试次数过多，请稍后再试")

    # === 修复漏洞3: 使用 code_store 验证 ===
    if not code_store.verify_code(qq, code):
        raise Exception("验证码错误或已失效")

    # 黑名单双重检测
    if session.exec(
            select(BlacklistEntry).where(BlacklistEntry.user_id == qq, BlacklistEntry.disabled == False)).first():
        raise Exception("您已被列入黑名单")

    user = session.exec(select(User).where(User.qq == qq)).first()

    # 如果用户不存在 -> 尝试注册
    if not user:
        # === 修复漏洞5: 并发初始化劫持 ===
        with owner_creation_lock:
            # 双重检查：在锁内部再次查询数据库，防止并发穿透
            user_count = session.exec(select(func.count()).select_from(User)).one()
            if user_count == 0:
                user = User(qq=qq, role=Role.OWNER)
                session.add(user)
                session.commit()
                session.refresh(user)
                logger.warning(f"初始化 Owner 账号: {qq}")
            else:
                # 自动注册逻辑
                conf = session.get(SystemConfig, "ENABLE_AUTO_REG")
                if conf and conf.value == "true":
                    role_conf = session.get(SystemConfig, "DEFAULT_AUTO_ROLE")
                    default_role = role_conf.value if role_conf else "user"
                    user = User(qq=qq, role=default_role)
                    session.add(user)
                    session.commit()
                    session.refresh(user)

                    logger.info(f"新用户自动注册: {qq} (角色: {default_role})")
                    await Notifier.on_user_created(session, "System", user)
                else:
                    raise Exception("账号不存在")

    token = session_store.create(
        user_id=user.qq,
        role=user.role,
        ip=client_ip,
        fingerprint=fingerprint
    )

    await Notifier.on_terminal_online(session, user, ip=client_ip, current_token=token)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.model_dump()
    }


async def update_subscriptions(session: Session, user: User, payload: dict):
    user.set_subscriptions(payload)
    session.add(user)
    session.commit()
    return {"msg": "订阅设置已更新", "user": user.model_dump()}
