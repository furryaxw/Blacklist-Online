import secrets
import time
from threading import Lock
from typing import Dict, Any, Optional

from app.config import settings


class SessionStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def create(self, user_id: str, role: str, ip: str, fingerprint: str) -> str:
        """创建新会话，返回随机Token"""
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._store[token] = {
                "user_id": user_id,
                "role": role,
                "created_at": time.time(),
                "last_activity": time.time(),
                "bind_ip": ip,
                "bind_fp": fingerprint
            }
        return token

    def auth_get(self, token: str, current_ip: str, current_fp: str) -> Optional[Dict[str, Any]]:
        """获取会话并自动续期"""
        with self._lock:
            session = self._store.get(token)
            if not session:
                return None

            # 1. 检查过期
            if time.time() - session["last_activity"] > settings.SESSION_TIMEOUT:
                del self._store[token]
                return None

            # 2. 检查 IP 绑定
            if current_ip and session.get("bind_ip") != current_ip:
                del self._store[token]
                return None

            # 3. 检查指纹绑定
            if current_fp and session.get("bind_fp") != current_fp:
                del self._store[token]
                return None

            # 续期 (Sliding Expiration)
            session["last_activity"] = time.time()
            return session


    def get(self, token: str) -> Optional[Dict[str, Any]]:
        """获取会话并自动续期"""
        with self._lock:
            session = self._store.get(token)
            if not session:
                return None

            # 检查过期
            if time.time() - session["last_activity"] > settings.SESSION_TIMEOUT:
                del self._store[token]
                return None

            return session

    def delete(self, token: str):
        """销毁会话"""
        with self._lock:
            if token in self._store:
                del self._store[token]

    def delete_by_user(self, user_id: str):
        """强制下线指定用户的所有会话"""
        with self._lock:
            # 找出所有属于该用户的 token
            to_delete = [
                token for token, data in self._store.items()
                if str(data.get("user_id")) == str(user_id)
            ]
            for token in to_delete:
                del self._store[token]

    def list_all(self):
        """列出当前所有活跃会话 (供管理后台使用)"""
        sessions_list = []
        now = time.time()
        with self._lock:
            # 遍历并简单过滤已过期的
            for token, data in self._store.items():
                if now - data["last_activity"] <= settings.SESSION_TIMEOUT:
                    # 返回脱敏或必要信息，Token 本身可以返回以便管理员通过 ID 踢人
                    sessions_list.append({
                        "token": token,  # 完整 Token 用于删除操作
                        "user_id": data["user_id"],
                        "role": data["role"],
                        "created_at": data["created_at"],
                        "last_activity": data["last_activity"],
                        "ip": data.get("ip", "Unknown")  # 预留字段
                    })
        # 按最后活跃时间倒序
        return sorted(sessions_list, key=lambda x: x["last_activity"], reverse=True)

    def cleanup(self):
        """清理过期会话"""
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._store.items() if now - v["last_activity"] > settings.SESSION_TIMEOUT]
            for k in expired:
                del self._store[k]


class CodeStore:
    """修复漏洞3: 内存耗尽。自动清理过期验证码"""

    def __init__(self):
        self._codes: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def set_code(self, key: str, code: str):
        with self._lock:
            self._codes[key] = {
                "code": code,
                "expires_at": time.time() + settings.CODE_TIMEOUT
            }

    def verify_code(self, key: str, code: str) -> bool:
        with self._lock:
            data = self._codes.get(key)
            if not data:
                return False
            if time.time() > data["expires_at"]:
                del self._codes[key]
                return False
            # 验证码只能用一次（防止重放）
            if data["code"] == code:
                del self._codes[key]
                return True
            return False

    def cleanup(self):
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._codes.items() if now > v["expires_at"]]
            for k in expired:
                del self._codes[k]


class RateLimiter:
    """修复漏洞2: 暴力破解"""

    def __init__(self):
        # 结构: { key: [timestamp1, timestamp2, ...] }
        self._records: Dict[str, list] = {}
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """
        简单滑动窗口限流
        :param key: 标识 (如 IP 或 QQ)
        :param limit: 窗口内最大请求数
        :param window: 窗口时间 (秒)
        :return: True (允许) / False (拒绝)
        """
        now = time.time()
        with self._lock:
            if key not in self._records:
                self._records[key] = []

            # 清理窗口外的记录
            self._records[key] = [t for t in self._records[key] if now - t < window]

            # 检查数量
            if len(self._records[key]) >= limit:
                return False

            # 记录本次请求
            self._records[key].append(now)
            return True

    def cleanup(self):
        """清理长期不活跃的限流记录，防止内存泄露"""
        now = time.time()
        with self._lock:
            # 清理超过 1 小时没活动的 key
            expired = [k for k, v in self._records.items() if not v or (now - v[-1] > 3600)]
            for k in expired:
                del self._records[k]


# 全局单例
session_store = SessionStore()
code_store = CodeStore()
rate_limiter = RateLimiter()
