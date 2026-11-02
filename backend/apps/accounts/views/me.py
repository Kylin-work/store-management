"""
当前用户信息视图。

返回当前登录用户的基本信息及认证上下文,
用于前端初始化用户信息、门店信息和权限信息。
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import success


class MeView(APIView):
    """获取当前登录用户信息。"""

    permission_classes = (IsAuthenticated,)

    # 如果全局已经配置 StoreJWTAuthentication,可以省略此配置
    # authentication_classes = (StoreJWTAuthentication,)

    def get(self, request):
        user = request.user

        # 获取当前认证上下文
        store_id = getattr(request, "store_id", None)
        role_code = getattr(request, "role_code", None)
        perm_set = getattr(request, "perm_set", None)

        # 超级管理员使用 None 表示拥有全部权限
        permissions = None if user.is_superuser else sorted(perm_set or set())

        return success(
            data={
                "user": {
                    "id": user.pk,
                    "employee_code": user.employee_code,
                    "real_name": user.real_name,
                    "is_superuser": user.is_superuser,
                },
                "context": {
                    "store_id": store_id,
                    "role_code": role_code,
                },
                "permissions": permissions,
            }
        )
