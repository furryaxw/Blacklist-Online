import json
import time
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


def unix_now() -> int:
    return int(time.time())


class Role(str, Enum):
    OWNER = "owner"
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    qq: str = Field(index=True, unique=True)
    role: Role = Field(default=Role.USER)
    created_at: int = Field(default_factory=unix_now)
    subscriptions: str = Field(default=json.dumps({"account": True, "approval": False}))

    def get_subscriptions(self) -> dict:
        try:
            return json.loads(self.subscriptions)
        except (json.JSONDecodeError, TypeError):
            return {"account": True, "approval": False}

    def set_subscriptions(self, subs: dict):
        current = self.get_subscriptions()
        current.update(subs)
        self.subscriptions = json.dumps(current)


class ApiKey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    description: str
    permissions: str = Field(default="read,write")
    instance_uuid: Optional[str] = None
    is_active: bool = True
    created_by: int = Field(default=None, foreign_key="user.id")
    created_at: int = Field(default_factory=unix_now)


class BlacklistEntry(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    reason: str
    disabled: bool = False
    updated_at: int = Field(default_factory=unix_now)
    operator_id: Optional[str] = None
    source_id: Optional[str] = None


class WhitelistEntry(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    created_at: int = Field(default_factory=unix_now)
    operator_id: Optional[str] = None
    reason: Optional[str] = None


class SyncEvent(SQLModel, table=True):
    revision: Optional[int] = Field(default=None, primary_key=True)
    action: str  # "upsert" | "delete"
    payload: str  # JSON string
    created_at: int = Field(default_factory=unix_now)


class Application(SQLModel, table=True):
    id: str = Field(primary_key=True)
    type: str  # ADD | REMOVE
    applicant_id: str
    target_user_id: str
    reason: str
    guild_id: Optional[str] = None
    # 专门存储提交该申请的 Bot 实例 ID
    submitter_instance_id: Optional[str] = None
    status: str = Field(default="pending")  # pending, approved, rejected
    evidence: str = Field(default="[]")
    created_at: int = Field(default_factory=unix_now)
    processed_by: Optional[str] = None
    processed_at: Optional[int] = None


class SystemConfig(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
    description: Optional[str] = None


class OperationLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event: str  # 例如 "blacklist.created"
    operator: str = "System"  # 尝试从数据中提取操作人
    details: str = "{}"  # 存储广播数据的 JSON
    created_at: int = Field(default_factory=unix_now)
