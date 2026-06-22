import json
import smtplib
from datetime import datetime, timezone
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import List

import httpx
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from app.config import settings
from app.utils.logging import logger
from app.utils.models import User, Role, ApiKey, Application, BlacklistEntry, OperationLog, SystemConfig, unix_now
from app.utils.ws_manager import ws_manager


# === 基础工具 ===
async def send_bot_msg(qq: str, message: str):
    """底层：发送 OneBot 私聊消息"""
    if not settings.ONEBOT_API_URL:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{settings.ONEBOT_API_URL}/send_private_msg", json={
                "user_id": int(qq),
                "message": message
            }, timeout=4.0)
    except Exception as e:
        logger.warning(f"Bot通知失败 [{qq}]: {e}")


def send_email_sync(config: dict, to_addr: str, subject: str, content: str):
    try:
        smtp_server = config.get("MAIL_HOST")
        smtp_port = int(config.get("MAIL_PORT", 465))
        smtp_user = config.get("MAIL_USER")  # 登录账号 (如 resend)
        smtp_pass = config.get("MAIL_PASS")  # 登录密码 (如 API Key)
        # 获取发件人显示地址
        # 如果配置了 MAIL_FROM 则使用它，否则默认使用登录账号
        mail_from = config.get("MAIL_FROM") or smtp_user

        if not all([smtp_server, smtp_user, smtp_pass]):
            logger.warning("邮件配置不完整，跳过发送")
            return

        msg = MIMEText(content, 'plain', 'utf-8')

        # From 头使用 mail_from
        # formataddr 可以让发件人显示更正规，例如: "admin@domain.com"
        msg['From'] = formataddr((None, mail_from))
        msg['To'] = to_addr
        msg['Subject'] = Header(subject, 'utf-8')

        # 默认使用 SSL
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)

        # 使用 smtp_user 进行登录认证
        server.login(smtp_user, smtp_pass)

        # 使用 mail_from 作为信封发件人 (Envelope Sender)
        server.sendmail(mail_from, [to_addr], msg.as_string())
        server.quit()

        logger.info(f"邮件已发送至 {to_addr}")
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")


class Notifier:
    """
    全系统统一通知中心
    职责：接收业务事件 -> 决定分发策略 (WS广播 / WS私信 / Bot私聊)
    """

    # === 辅助：获取系统管理员列表 ===
    @staticmethod
    def _get_super_admins(session: Session) -> List[str]:
        """获取所有 Owner 和 SuperAdmin 的 QQ"""
        admins = session.exec(
            select(User.qq).where(User.role.in_([Role.OWNER, Role.SUPER_ADMIN]))
        ).all()
        return [str(qq) for qq in admins]

    @staticmethod
    def _get_all_admins(session: Session) -> List[str]:
        """获取所有 Owner, SuperAdmin 和 Admin 的 QQ"""
        admins = session.exec(
            select(User.qq).where(User.role.in_([Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN]))
        ).all()
        return [str(qq) for qq in admins]

    # === 内部辅助：写入操作日志 ===
    @staticmethod
    def _save_log(session: Session, event: str, operator: str, data: dict):
        try:
            # 某些高频或无需记录的事件可以跳过
            if event in ["system.ping", "account.login"]:
                return

            safe_data = jsonable_encoder(data)
            json_str = json.dumps(safe_data, ensure_ascii=False)
            log = OperationLog(
                event=event,
                operator=str(operator),
                details=json_str
            )
            session.add(log)
            # 注意：这里需要 session.commit()，否则记录会失败
            session.commit()
        except Exception as e:
            logger.error(f"写入操作日志失败: {e}")

    # ===========================
    # 1. API Key 相关 (定向推送)
    # ===========================
    @staticmethod
    async def on_key_created(session: Session, operator_qq: str, new_key: ApiKey):
        """推送范围: 操作者 + 超管 + 拥有者"""
        recipients = set(Notifier._get_super_admins(session))
        recipients.add(str(operator_qq))
        if new_key.created_by:
            creator = session.get(User, new_key.created_by)
            if creator: recipients.add(str(creator.qq))

        # 2. 构造安全数据 (脱敏，只发前几位)
        data = {
            "operator": operator_qq,
            "key_prefix": new_key.key[:8] + "***",
            "description": new_key.description,
            "permissions": new_key.permissions,
            "created_at": new_key.created_at
        }

        # 3. 定向推送
        await ws_manager.send_to_users(list(recipients), "key.created", data)
        Notifier._save_log(session, "key.created", operator_qq, data)

    @staticmethod
    async def on_key_deleted(session: Session, operator_qq: str, key_id: int, key_desc: str):
        recipients = set(Notifier._get_super_admins(session))
        recipients.add(str(operator_qq))

        data = {
            "operator": operator_qq,
            "target_key_id": key_id,
            "key_desc": key_desc
        }
        await ws_manager.send_to_users(list(recipients), "key.deleted", data)
        Notifier._save_log(session, "key.deleted", operator_qq, data)

    @staticmethod
    async def on_key_updated(session: Session, operator_qq: str, key_id: int, updates: dict):
        recipients = set(Notifier._get_super_admins(session))
        recipients.add(str(operator_qq))

        data = {
            "operator": operator_qq,
            "target_key_id": key_id,
            "updates": updates
        }
        await ws_manager.send_to_users(list(recipients), "key.updated", data)
        Notifier._save_log(session, "key.updated", operator_qq, data)

    # ===========================
    # 2. 用户管理 (定向 + 广播)
    # ===========================
    @staticmethod
    async def on_user_created(session: Session, operator_qq: str, new_user: User):
        # 1. 向所有管理员广播 (刷新列表)
        recipients = Notifier._get_all_admins(session)
        data = {
            "operator": operator_qq,
            "target_qq": new_user.qq,
            "role": new_user.role
        }
        await ws_manager.send_to_users(recipients, "user.created", data)
        Notifier._save_log(session, "user.created", operator_qq, data)

        # 2. Bot 通知用户
        msg = (
            f"🛡️ [Blacklist Online 账号创建]\n"
            f"您好！管理员 {operator_qq} 已为您开通了后台权限。\n\n"
            f"📝 账号信息：\n"
            f" - 当前权限: {new_user.role}\n"
            f" - 绑定QQ: {new_user.qq}\n\n"
            f"🌐 管理后台入口：\n"
            f"https://www.furryaxw.top/Blacklist"
        )
        await send_bot_msg(new_user.qq, msg)

    @staticmethod
    async def on_user_role_changed(session: Session, operator_qq: str, target_user: User, old_role: str):
        # 1. 列表刷新 (推给管理员)
        admins = Notifier._get_all_admins(session)
        data = {
            "operator": operator_qq,
            "target_qq": target_user.qq,
            "change": f"{old_role} -> {target_user.role}"
        }
        await ws_manager.send_to_users(admins, "user.updated", data)
        Notifier._save_log(session, "user.updated", operator_qq, data)

        # 2. WS 私信 (通知当事人刷新页面)
        await ws_manager.send_to_user(target_user.qq, "user.updated", {
            "target_qq": target_user.qq,
            "msg": "您的权限已被修改",
            "role": target_user.role
        })

        # 3. Bot 通知
        if target_user.get_subscriptions().get("account", True):
            await send_bot_msg(target_user.qq, f"🛡️ [权限变更]\n您的权限已变更为: {target_user.role}")

    @staticmethod
    async def on_user_deleted(session: Session, operator_qq: str, target_qq: str, target_id: int):
        # 1. 通知管理员
        admins = Notifier._get_all_admins(session)
        data = {
            "operator": operator_qq,
            "target_qq": target_qq,
            "target_id": target_id
        }
        await ws_manager.send_to_users(admins, "user.deleted", data)
        Notifier._save_log(session, "user.deleted", operator_qq, data)

        # 2. 强制踢下线 (如果还在)
        await ws_manager.send_to_user(target_qq, "system.kicked", {"reason": "账号已被删除"})

    # ===========================
    # 3. 安全与会话 (点对点)
    # ===========================
    @staticmethod
    async def on_session_killed(session: Session, target_token: str, target_qq: str, operator_qq: str):
        """
        [强制下线]
        1. 精准踢掉对应的 WebSocket (WS层)
        2. 发送 Bot 通知 (Bot层)
        """
        # 1. WS 精准踢人
        # ws_manager 会根据 token 找到特定连接发送 system.kicked 并 close
        await ws_manager.kick_token(target_token, reason=f"管理员 {operator_qq} 强制下线")
        Notifier._save_log(session, "session.killed", operator_qq, {"target": target_qq})

        # 2. Bot 警报 (还是发给 QQ)
        await send_bot_msg(target_qq, f"⚠️ [安全警报]\n您的某个会话已被管理员 {operator_qq} 强制下线。")

    @staticmethod
    async def on_terminal_online(session: Session, user: User, ip: str = "Unknown", current_token: str = None):
        """
        [终端上线]
        通知该用户的*其他*设备
        """
        # 1. WS 推送 (排除当前 Token)
        await ws_manager.send_to_user(
            user.qq,
            "account.login",
            {
                "time": unix_now(),
                "ip": ip,
                "msg": "新设备登录通知"
            },
            exclude_token=current_token  # 关键参数
        )

        # 2. Bot 通知
        if user.get_subscriptions().get("account", True):
            await send_bot_msg(user.qq, f"🛡️ [登录通知]\n检测到新登录\nIP: {ip}")

    # ===========================
    # 4. 审批 (管理员组)
    # ===========================
    @staticmethod
    async def on_application_created(session: Session, app: Application):
        # 1. 推给所有管理员
        data = {
            "applicant": app.applicant_id,
            "type": app.type,
            "target": app.target_user_id,
            "reason": app.reason,
            "evidence": app.evidence,
        }
        await ws_manager.send_to_users(Notifier._get_all_admins(session), "app.created", data)
        Notifier._save_log(session, "app.created", app.applicant_id, data)

        # 2. Bot 通知 (仅限订阅者)
        admin_users = session.exec(
            select(User).where(User.role.in_([Role.OWNER, Role.SUPER_ADMIN, Role.ADMIN]))
        ).all()

        for admin in admin_users:
            if admin.get_subscriptions().get("approval", False):
                msg = (
                    f"🔔 [新审批申请]\n"
                    f"类型: {app.type}\n"
                    f"申请人: {app.applicant_id}\n"
                    f"目标: {app.target_user_id}\n"
                    f"请登录后台处理。"
                )
                await send_bot_msg(admin.qq, msg)

    @staticmethod
    async def on_application_handled(session: Session, app: Application, is_update: bool = False):
        # 1. 推给所有管理员
        data = {
            "app_id": app.id,
            "action": app.status,
            "operator": app.applicant_id,
            "target_user": app.target_user_id
        }
        await ws_manager.send_to_users(Notifier._get_all_admins(session), "app.updated", data)
        operator = app.processed_by if app.processed_by else "System"
        Notifier._save_log(session, "app.handled", operator, data)

        # 2. 通知申请人 (WS + Bot)
        if app.status == "approved":
            action_cn = "通过"
        elif app.status == "rejected":
            action_cn = "拒绝"
        elif app.status == "cancelled":
            action_cn = "取消"
        else:
            action_cn = "系统错误，请联系管理员"

        if app.type == "ADD":
            type_cn = "添加"
        elif app.type == "REMOVE":
            type_cn = "删除"
        else:
            type_cn = "系统错误，请联系管理员"

        req_type_str = "更新黑名单" if is_update and app.type == "ADD" else f"{type_cn}申请"

        # 如果是更新请求被拒绝，额外提示
        extra_hint = ""
        if is_update and app.status == "rejected":
            extra_hint = "\n(注: 目标已在黑名单中，仅驳回了本次修改)"

        msg_content = f"📝 [审批结果]\n您提交的 [{req_type_str}] 已被 {action_cn}。{extra_hint}"

        await ws_manager.send_to_user(app.applicant_id, "app.result", {
            "app_id": app.id,
            "status": app.status,
            "msg": f"申请已{action_cn}"
        })

        if app.type == "APPEAL":
            email = app.applicant_id

            # 读取数据库配置
            configs = session.exec(select(SystemConfig)).all()
            conf_dict = {c.key: c.value for c in configs}

            status_cn = "通过" if app.status == "approved" else "驳回"
            subject = f"【申诉结果通知】您的申诉已{status_cn}"

            content = (
                f"您好，您对 QQ {app.target_user_id} 的黑名单申诉已处理。\n\n"
                f"处理结果：{status_cn}\n"
                f"处理人：{app.applicant_id}\n"
                f"处理时间：{datetime.fromtimestamp(unix_now(), timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            )

            if app.status == "approved":
                content += "您的账号已被移出黑名单，现在可以正常使用了。\n数据同步可能需要一些时间，请耐心等待。"
            else:
                content += "很遗憾，您的申诉未通过，请联系管理员或稍后重试。"

            # 异步执行发送，避免阻塞主线程
            import asyncio
            await asyncio.to_thread(send_email_sync, conf_dict, email, subject, content)
        await send_bot_msg(app.applicant_id, msg_content)

    @staticmethod
    async def on_application_cancelled(session: Session, app: Application):
        data = {
            "app_id": app.id,
            "status": "cancelled",
            "applicant": app.applicant_id
        }
        await ws_manager.send_to_users(Notifier._get_all_admins(session), "app.updated", data)
        Notifier._save_log(session, "app.cancelled", app.applicant_id, data)

    # ===========================
    # 5. 黑白名单 (全局广播)
    # ===========================
    # 黑白名单通常是公共数据，保持 Broadcast 以让所有在线客户端实时更新

    @staticmethod
    async def on_blacklist_created(session: Session, operator_qq: str, entry: BlacklistEntry, source: str = "manual"):
        data = {
            "operator": operator_qq,
            "target": entry.user_id,
            "reason": entry.reason,
            "source": source,
            "timestamp": unix_now()
        }
        await ws_manager.broadcast("blacklist.created", data)
        Notifier._save_log(session, "blacklist.created", operator_qq, data)

    @staticmethod
    async def on_blacklist_updated(session: Session, operator_qq: str, target_qq: str, action: str, reason: str = None):
        data = {
            "operator": operator_qq,
            "target": target_qq,
            "action": action,  # 'disable', 'enable'
            "reason": reason
        }
        await ws_manager.broadcast("blacklist.updated", data)
        Notifier._save_log(session, "blacklist.updated", operator_qq, data)

    @staticmethod
    async def on_blacklist_deleted(session: Session, operator_qq: str, target_qq: str, type_: str):
        data = {
            "operator": operator_qq,
            "target": target_qq,
            "type": type_
        }
        await ws_manager.broadcast("blacklist.deleted", data)
        Notifier._save_log(session, "blacklist.deleted", operator_qq, data)

    @staticmethod
    async def on_blacklist_imported(session: Session, operator_qq: str, count: int):
        data = {
            "operator": operator_qq,
            "count": count,
            "msg": f"批量导入了 {count} 条黑名单"
        }
        admins = Notifier._get_all_admins(session)
        await ws_manager.send_to_users(admins, "blacklist.imported", data)
        Notifier._save_log(session, "blacklist.imported", operator_qq, data)

    # ===========================
    # 2. 白名单管理 (全员广播)
    # ===========================
    @staticmethod
    async def on_whitelist_added(session: Session, operator_qq: str, target_qq: str, reason: str = ""):
        data = {
            "operator": operator_qq,
            "target": target_qq,
            "reason": reason
        }
        await ws_manager.broadcast("whitelist.added", data)
        Notifier._save_log(session, "whitelist.added", operator_qq, data)

    @staticmethod
    async def on_whitelist_deleted(session: Session, operator_qq: str, target_qq: str):
        data = {
            "operator": operator_qq,
            "target": target_qq
        }
        await ws_manager.broadcast("whitelist.deleted", data)
        Notifier._save_log(session, "whitelist.deleted", operator_qq, data)

    # ===========================
    # 3. 系统维护 (仅管理员)
    # ===========================
    @staticmethod
    async def on_system_updated(session: Session, operator_qq: str, updates: dict):
        data = {
            "operator": operator_qq,
            "updates": updates,  # 例如 {'allow_register': True}
            "msg": "系统配置已更新"
        }
        admins = Notifier._get_all_admins(session)
        await ws_manager.send_to_users(admins, "system.updated", data)
        Notifier._save_log(session, "system.updated", operator_qq, data)

    @staticmethod
    async def on_sync_logs_cleaned(session: Session, operator_qq: str, count: int):
        """同步日志/操作日志清理"""
        admins = Notifier._get_all_admins(session)
        await ws_manager.send_to_users(admins, "system.sync_logs_cleaned", {
            "operator": operator_qq,
            "count": count
        })
        Notifier._save_log(session, "system.sync_logs_cleaned", operator_qq, {"count": count})

    @staticmethod
    async def on_logs_cleaned(session: Session, operator_qq: str, count: int, days: int):
        data = {
            "operator": operator_qq,
            "count": count,
            "days": days
        }
        admins = Notifier._get_super_admins(session)
        await ws_manager.send_to_users(admins, "system.op_logs_cleaned", data)
        Notifier._save_log(session, "system.op_logs_cleaned", operator_qq, data)
