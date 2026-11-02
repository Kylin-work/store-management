"""
登录序列化器.

校验工号、密码及用户门店关联关系.
认证通过后,将用户、门店及角色信息交给视图层签发 JWT.
"""

from django.contrib.auth import authenticate
from rest_framework import serializers

from apps.accounts.models import UserStoreRole
from core.codes import BizCode
from core.exceptions import BizException


class LoginSerializer(serializers.Serializer):
    """用户登录入参校验及身份认证."""

    employee_code = serializers.CharField(
        max_length=8,
        trim_whitespace=True,
        allow_blank=False,
        required=True,
        error_messages={
            "required": "请输入工号",
            "blank": "工号不能为空",
            "max_length": "工号长度不能超过8位",
        },
        label="工号",
    )

    password = serializers.CharField(
        max_length=128,
        write_only=True,
        trim_whitespace=False,
        required=True,
        allow_blank=False,
        error_messages={
            "required": "请输入密码",
            "blank": "密码不能为空",
            "max_length": "密码长度不能超过128位",
        },
        label="密码",
    )

    store_id = serializers.IntegerField(
        required=False,
        default=None,
        min_value=1,
        error_messages={
            "invalid": "门店ID必须为整数",
            "min_value": "门店ID必须大于0",
        },
        label="门店ID",
    )

    def validate(self, attrs):
        """验证登录凭证及用户门店权限."""

        employee_code = attrs["employee_code"]
        password = attrs["password"]
        store_id = attrs.get("store_id")

        # 1. 验证工号和密码
        # username 是 Django authenticate 的固定参数名,实际传入的是工号
        user = authenticate(
            request=self.context.get("request"),
            username=employee_code,
            password=password,
        )

        if user is None:
            raise BizException(
                BizCode.LOGIN_FAILED,
                "工号或密码错误",
            )

        # 2. 验证账号状态
        if not user.is_active:
            raise BizException(
                BizCode.ACCOUNT_DISABLED,
                "账号状态错误,请联系管理员",
            )

        # 3. 平台超级管理员不绑定具体门店
        if user.is_superuser:
            attrs.update(
                {
                    "user": user,
                    "store_id": None,
                    "role_code": None,
                }
            )
            return attrs

        # 4. 普通用户必须选择有效门店
        if not store_id:
            raise BizException(
                BizCode.STORE_NOT_ASSIGNED,
                "请选择门店",
            )

        # 5. 验证用户与门店的关联关系
        user_store_role = (
            UserStoreRole.objects.select_related("role", "store")
            .filter(
                user=user,
                store_id=store_id,
                store__is_active=True,
                is_active=True,
            )
            .first()
        )

        if user_store_role is None:
            raise BizException(
                BizCode.STORE_NOT_ASSIGNED,
                "门店选择错误,请重试",
            )

        # 6. 组装认证结果
        attrs.update(
            {
                "user": user,
                "store_id": user_store_role.store_id,
                "role_code": user_store_role.role.code,
            }
        )

        return attrs
