"""
权限码注册表 + 权限校验基类.

各业务模块的 apps.py 在 ready() 中调用 register_permissions() 登记本模块权限码,
sync_permissions 管理命令把注册表同步到 accounts.Permission 表.

DRF 权限类继承 HasPerm,声明 required_perm,
校验时从 request.auth 里的权限码集合判断是否放行.
"""

from rest_framework.permissions import BasePermission

from core.codes import BizCode
from core.exceptions import BizException

# 全局权限码注册表：{ code: {"code": ..., "name": ..., "module": ...} }
PERMISSION_REGISTRY: dict[str, dict] = {}


def register_permissions(items: list[dict]) -> None:
    """业务模块注册权限码.items 每项形如：
    {"code": "member:recharge", "name": "会员充值", "module": "member"}
    """
    for item in items:
        code = item["code"]
        if code in PERMISSION_REGISTRY:
            # 重复注册说明两个模块声明了同一个权限码,属于开发错误
            raise ValueError(f"权限码重复注册: {code}")
        PERMISSION_REGISTRY[code] = item


class HasPerm(BasePermission):
    """接口级权限基类.子类声明 required_perm,校验当前请求的权限集合."""

    required_perm: str = ""

    def has_permission(self, request, view) -> bool:
        # 未认证直接拒绝(认证类通常已拦截,这里兜底)
        if not request.user or not request.user.is_authenticated:
            return False

        # 平台管理员跳过权限码校验
        if request.user.is_superuser:
            return True

        # 权限码集合由认证阶段写入 request.auth(JWT payload)或 request.user 的缓存属性
        perm_set = getattr(request, "perm_set", None)
        if perm_set is None:
            # 兜底：从 request.auth 里取(JWT payload 中带 perms)
            perm_set = (request.auth or {}).get("perms", [])

        if self.required_perm not in perm_set:
            raise BizException(
                code=BizCode.PERMISSION_DENIED,
                message="无权限执行该操作",
                http_status=403,
            )
        return True
