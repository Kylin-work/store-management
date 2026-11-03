"""账号模块 OpenAPI 文档专用序列化器."""

from rest_framework import serializers

from apps.accounts.serializers.role import RoleListSerializer


class AccountStoreRoleResponseSerializer(serializers.Serializer):
    """账号关联的门店角色响应项."""

    store_id = serializers.IntegerField(label="门店 ID")
    store_name = serializers.CharField(label="门店名称")
    role_code = serializers.CharField(label="角色编码")
    role_name = serializers.CharField(label="角色名称")


class StoreRoleItemRequestSerializer(serializers.Serializer):
    """门店角色请求项."""

    store_id = serializers.IntegerField(min_value=1, label="门店 ID")
    role_code = serializers.CharField(
        max_length=50,
        allow_blank=False,
        trim_whitespace=True,
        label="角色编码",
    )


class AccountStoreRolesRequestSerializer(serializers.Serializer):
    """账号门店角色调整请求."""

    store_roles = StoreRoleItemRequestSerializer(
        many=True,
        allow_empty=False,
        label="门店角色列表",
    )


class AccountStatusResponseSerializer(serializers.Serializer):
    """账号状态调整响应."""

    employee_code = serializers.CharField(label="员工编号")
    is_active = serializers.BooleanField(label="是否启用")


class LoginUserResponseSerializer(serializers.Serializer):
    """登录用户信息."""

    employee_code = serializers.CharField(label="工号")
    real_name = serializers.CharField(label="姓名")
    is_superuser = serializers.BooleanField(label="是否超级管理员")
    store_id = serializers.IntegerField(label="门店 ID", allow_null=True)
    role_code = serializers.CharField(label="角色编码", allow_null=True)


class LoginResponseSerializer(serializers.Serializer):
    """登录响应."""

    access = serializers.CharField(label="Access Token")
    refresh = serializers.CharField(label="Refresh Token")
    user = LoginUserResponseSerializer(label="用户信息")


class MeUserResponseSerializer(serializers.Serializer):
    """当前用户信息."""

    id = serializers.IntegerField(label="用户 ID")
    employee_code = serializers.CharField(label="工号")
    real_name = serializers.CharField(label="姓名")
    is_superuser = serializers.BooleanField(label="是否超级管理员")


class MeContextResponseSerializer(serializers.Serializer):
    """当前用户门店上下文."""

    store_id = serializers.IntegerField(label="门店 ID", allow_null=True)
    role_code = serializers.CharField(label="角色编码", allow_null=True)


class MeResponseSerializer(serializers.Serializer):
    """当前用户信息响应."""

    user = MeUserResponseSerializer(label="用户信息")
    context = MeContextResponseSerializer(label="认证上下文")
    permissions = serializers.ListField(
        child=serializers.CharField(),
        label="权限编码列表",
        allow_null=True,
    )


class RoleListResponseSerializer(serializers.Serializer):
    """角色列表响应."""

    items = RoleListSerializer(many=True, label="角色列表")
    total = serializers.IntegerField(label="总数量")
    page = serializers.IntegerField(label="当前页码")
    page_size = serializers.IntegerField(label="每页数量")


class PermissionItemResponseSerializer(serializers.Serializer):
    """权限项响应."""

    id = serializers.IntegerField(label="权限 ID")
    code = serializers.CharField(label="权限编码")
    name = serializers.CharField(label="权限名称")


class PermissionGroupResponseSerializer(serializers.Serializer):
    """权限分组响应."""

    module = serializers.CharField(label="权限模块")
    permissions = PermissionItemResponseSerializer(
        many=True,
        label="权限码列表",
    )


class AccountListItemResponseSerializer(serializers.Serializer):
    """账号列表响应项."""

    employee_code = serializers.CharField(label="工号")
    phone = serializers.CharField(label="手机号")
    real_name = serializers.CharField(label="姓名")
    is_active = serializers.BooleanField(label="有效")
    is_superuser = serializers.BooleanField(label="超级用户状态")
    date_joined = serializers.DateTimeField(label="加入日期")
    store_roles = AccountStoreRoleResponseSerializer(
        many=True,
        label="门店角色",
    )


class AccountListResponseSerializer(serializers.Serializer):
    """账号分页列表响应."""

    items = AccountListItemResponseSerializer(many=True, label="账号列表")
    total = serializers.IntegerField(label="总数量")
    page = serializers.IntegerField(label="当前页码")
    page_size = serializers.IntegerField(label="每页数量")
