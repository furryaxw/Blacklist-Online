import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import Session, select, delete

from app.config import settings
from app.utils.models import User, Role, SystemConfig, BlacklistEntry, SyncEvent
from app.utils.notifier import Notifier, send_bot_msg, send_email_sync
from app.utils.permissions import check_role

SENSITIVE_KEYS = {
    "MAIL_PASS",
    "SECRET_KEY",
    "ONEBOT_ACCESS_TOKEN",
    "DB_PASSWORD"
}


# === 基础配置管理 ===
async def get_system_config(session: Session, user: User):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])
    configs = session.exec(select(SystemConfig)).all()

    # 将所有配置预先转换为字典，方便查找开关和遍历
    config_map = {c.key: c.value for c in configs}

    # 获取全局脱敏开关
    # Key: ENABLE_SENSITIVE_MASKING
    # 默认为 "true" (开启安全模式/脱敏)。如果设置为 "false"，则显示明文。
    enable_masking = config_map.get("ENABLE_SENSITIVE_MASKING", "true").lower() == "true"

    result = {}
    for key, value in config_map.items():
        # 判断逻辑：如果开启了脱敏 且 是敏感字段 且 值不为空，则脱敏
        if enable_masking and key in SENSITIVE_KEYS and value:
            result[key] = "******"
        else:
            result[key] = value

    return result


async def get_public_system_config(session: Session, user: User):
    # 1. 允许所有登录用户访问 (包括 USER, ADMIN, SUPER_ADMIN, OWNER)
    # 只要能过 websocket 的 auth 检查 user 肯定存在，这里甚至可以不加 check_role，
    # 或者显式允许所有角色：
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN, Role.USER])

    # 2. 定义允许公开的配置 Key (白名单)
    public_keys = [
        "DEFAULT_KEY_PERMS"
    ]

    # 3. 查询并过滤
    # 使用 .in_() 进行筛选
    configs = session.exec(select(SystemConfig).where(SystemConfig.key.in_(public_keys))).all()

    result = {c.key: c.value for c in configs}
    return result


async def update_system_config(session: Session, user: User, payload: dict):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])

    # 记录修改了哪些 Key，用于日志
    updated_keys = []

    for key, value in payload.items():
        if key == "SECRET_KEY": continue  # 密钥不能通过此通用接口修改

        # 写入数据库
        conf = session.get(SystemConfig, key)
        if not conf:
            conf = SystemConfig(key=key, value=str(value))
        else:
            conf.value = str(value)
        session.add(conf)
        updated_keys.append(key)

        # 实时更新内存
        if hasattr(settings, key):
            # 类型转换
            orig_type = type(getattr(settings, key))
            if orig_type is int:
                setattr(settings, key, int(value))
            else:
                setattr(settings, key, str(value))

    session.commit()

    await Notifier.on_system_updated(session, user.qq, payload)
    return {"msg": "配置已保存"}


async def get_qq_profile(session: Session, user: User, payload: dict):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN, Role.USER])
    target_qq = payload.get("qq")
    if not target_qq: raise Exception("QQ号不能为空")

    url = settings.ONEBOT_API_URL
    if not url: raise Exception("未配置 OneBot API")

    try:
        async with httpx.AsyncClient() as client:
            # no_cache=true 避免获取旧信息
            resp = await client.post(f"{url}/get_stranger_info", json={"user_id": int(target_qq), "no_cache": True},
                                     timeout=10.0)
            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get("status") == "ok" or res_json.get("retcode") == 0:
                    return res_json.get("data")
                else:
                    raise Exception(f"Bot API Error: {res_json}")
            raise Exception(f"HTTP Error: {resp.status_code}")
    except Exception as e:
        raise Exception(f"查询失败: {str(e)}")


# === 数据管理 ===
async def export_data(session: Session, user: User):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])
    entries = session.exec(select(BlacklistEntry)).all()
    # 返回列表，前端可以转存为 JSON
    return [entry.model_dump() for entry in entries]


async def import_data(session: Session, user: User, payload: list):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])
    count = 0
    for item in payload:
        # 简单的 upsert 逻辑
        if "user_id" not in item: continue

        entry = BlacklistEntry(**item)
        # 强制修正操作人为当前导入者
        entry.operator_id = user.qq
        entry.source_id = "import"

        session.merge(entry)

        # 记录同步事件
        sync_payload = json.dumps({
            "user_id": entry.user_id,
            "reason": entry.reason,
            "disabled": entry.disabled,
            "updated_at": entry.updated_at.isoformat()
        })
        session.add(SyncEvent(action="upsert", payload=sync_payload))
        count += 1

    session.commit()

    await Notifier.on_blacklist_imported(session, user.qq, count)
    return {"msg": f"成功导入 {count} 条数据"}


async def clean_logs(session: Session, user: User, payload: dict):
    """清理 SyncEvent (同步日志)"""
    check_role(user, [Role.OWNER])
    days = int(payload.get("days", 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # SQLModel 的 delete 语句
    statement = delete(SyncEvent).where(SyncEvent.created_at < cutoff)
    result = session.exec(statement)
    session.commit()

    await Notifier.on_sync_logs_cleaned(session, user.qq, result.rowcount)
    return {"msg": f"清理完成，删除了 {result.rowcount} 条同步记录"}


async def test_bot_connection(session: Session, user: User):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])
    url = settings.ONEBOT_API_URL
    if not url:
        raise Exception("未配置 OneBot API 地址")

    try:
        # 尝试调用 get_status 或 get_login_info
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}/get_status", timeout=5.0)
            if resp.status_code == 200:
                return {"status": "ok", "detail": resp.json()}
            else:
                raise Exception(f"HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        raise Exception(f"连接失败: {str(e)}")


async def test_bot_message(session: Session, user: User, target_qq: str):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])
    if not target_qq:
        raise Exception("需要指定接收测试消息的 QQ 号")

    try:
        # 构造一个测试消息
        msg = f"【系统测试】这是一条来自 Blacklist Server 的测试消息。\n如果是您刚刚点击了测试按钮，请忽略此消息。"

        # 调用 Notifier 发送 (假设 Notifier.send_like_bot 存在，或者直接用 broadcast 的底层)
        # 这里我们假设 Notifier 内部有 send_private_msg 静态方法，如果没有，我们需要简单实现一个
        # 既然项目里已经有 Notifier，我们直接用它发送通知
        await send_bot_msg(target_qq, msg)

        return {"msg": "测试消息已发送，请检查 QQ"}
    except Exception as e:
        raise Exception(f"发送失败: {str(e)}")


async def test_email_settings(session: Session, user: User, target_email: str):
    check_role(user, [Role.OWNER, Role.SUPER_ADMIN])
    if not target_email:
        raise Exception("需要指定接收测试邮件的邮箱")

    # 1. 读取配置
    configs = session.exec(select(SystemConfig)).all()
    conf_dict = {c.key: c.value for c in configs}

    # 2. 校验配置是否存在
    if not conf_dict.get("MAIL_HOST") or not conf_dict.get("MAIL_PASS"):
        raise Exception("请先保存邮件配置")

    # 3. 发送测试邮件
    subject = "【系统测试】邮件服务配置验证"
    content = "恭喜！您的邮件服务配置正确。\n\n这是一条测试邮件，无需回复。"

    try:
        # 在线程池中执行同步发送
        await asyncio.to_thread(send_email_sync, conf_dict, target_email, subject, content)
        return {"msg": f"测试邮件已发送至 {target_email}"}
    except Exception as e:
        # 捕获 smtplib 的错误并返回给前端
        raise Exception(f"邮件发送失败: {str(e)}")
