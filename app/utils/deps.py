from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.utils.database import get_session
from app.utils.models import User, ApiKey
from app.utils.sessions import session_store

# 这里只是为了让 Swagger UI 显示锁图标，并不真正执行 OAuth2 流程
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str, session: Session, client_ip: str, fingerprint: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. 查内存 Session
    session_data = session_store.auth_get(token, client_ip, fingerprint)
    if not session_data:
        raise credentials_exception

    # 2. 获取用户 ID (QQ)
    qq = session_data.get("user_id")

    # 3. 查数据库确保用户还存在
    user = session.exec(select(User).where(User.qq == qq)).first()
    if user is None:
        raise credentials_exception

    return user


def require_role(allowed_roles: list):
    def dependency(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return user

    return dependency


async def verify_bot_token(authorization: str = Header(...), session: Session = Depends(get_session)):
    """
    基础 Token 校验：检查是否存在且激活
    """
    # 支持 Bearer Token 或直接 Token
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    else:
        token = authorization

    key_entry = session.exec(select(ApiKey).where(ApiKey.key == token)).first()

    # 校验有效性
    if not key_entry:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    if not key_entry.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API Key is disabled")

    return key_entry


def check_api_permission(required_perm: str):
    """
    权限校验工厂函数：先验证 Token 有效性，再检查是否包含指定权限
    """

    async def dependency(key: ApiKey = Depends(verify_bot_token)):
        # 解析权限字段 (例如 "read,write")
        perms = [p.strip() for p in key.permissions.split(",")]

        # 检查是否拥有所需权限或超级权限 "all"
        if required_perm not in perms and "all" not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {required_perm}"
            )
        return key

    return dependency
