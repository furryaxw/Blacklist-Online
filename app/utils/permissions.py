from app.utils.models import User, Role


def check_role(user: User, allowed_roles: list[Role]):
    if user.role not in allowed_roles:
        raise Exception(f"权限不足: 需要 {allowed_roles}")


def check_manage_permission(operator: User, target_role_str: str):
    target_role = Role(target_role_str)
    # 1. 不能创建/修改为 Owner
    if target_role == Role.OWNER:
        raise Exception("不能添加或修改为拥有者")

    # 2. Owner 可以操作一切
    if operator.role == Role.OWNER:
        return True

    # 3. SuperAdmin 可以操作 Admin 和 User
    if operator.role == Role.SUPER_ADMIN:
        if target_role in [Role.ADMIN, Role.USER]:
            return True
        raise Exception("超级管理员权限不足")

    # 4. Admin 只能查看，不能修改用户权限（在路由层拦截）
    raise Exception("权限不足")
