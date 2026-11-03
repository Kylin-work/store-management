"""
当前用户信息视图.

返回当前登录用户的基本信息及认证上下文,
用于前端初始化用户信息、门店信息和权限信息.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import success


class MeUserResponseSerializer(serializers.Serializer):
    """当前用户基本信息."""

    id = serializers.IntegerField(label="用户 ID")
    employee_code = serializers.CharField(label="工号")
    real_name = serializers.CharField(label="姓名")
    is_superuser = serializers.BooleanField(label="是否超级管理员")


class MeContextResponseSerializer(serializers.Serializer):
    """当前用户认证上下文."""

    store_id = serializers.IntegerField(
        label="门店 ID",
        allow_null=True,
    )
    role_code = serializers.CharField(
        label="角色编码",
        allow_null=True,
    )


class MeResponseSerializer(serializers.Serializer):
    """当前用户信息响应."""

    user = MeUserResponseSerializer(label="用户信息")
    context = MeContextResponseSerializer(label="认证上下文")
    permissions = serializers.ListField(
        child=serializers.CharField(),
        label="权限编码列表",
        allow_null=True,
    )


class MeView(APIView):
    """获取当前登录用户信息."""

    permission_classes = (IsAuthenticated,)

    # 如果全局已经配置 StoreJWTAuthentication,可以省略此配置
    # authentication_classes = (StoreJWTAuthentication,)

    @extend_schema(
        operation_id="auth_me",
        summary="获取当前用户信息",
        description=(
            "获取当前登录用户的基本信息、门店及角色上下文和权限列表。"
            "超级管理员的 permissions 返回 null，表示拥有全部权限。"
        ),
        responses={200: MeResponseSerializer},
    )
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
