"""门店管理端权限类."""

from rest_framework.permissions import BasePermission

from core.codes import BizCode
from core.exceptions import BizException


class IsSuperUser(BasePermission):
    """仅允许平台超级管理员访问."""

    message = "仅平台管理员可操作"

    def has_permission(self, request, view) -> bool:
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if not user.is_superuser:
            raise BizException(
                code=BizCode.PERMISSION_DENIED,
                message=self.message,
                http_status=403,
            )

        return True
