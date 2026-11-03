"""账号门店角色管理视图."""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import UserStoreRole
from apps.accounts.serializers.account import AccountListSerializer
from apps.accounts.views.account import (
    CanUpdateAccount,
    _get_account_queryset,
    _get_user,
    _validate_store_roles,
)
from apps.logs.services.logger import log_operation
from core.codes import BizCode
from core.exceptions import BizException
from core.responses import success


class StoreRoleItemRequestSerializer(serializers.Serializer):
    """单个门店角色."""

    store_id = serializers.IntegerField(
        label="门店 ID",
        min_value=1,
    )
    role_code = serializers.CharField(
        label="角色编码",
    )


class AccountStoreRolesRequestSerializer(serializers.Serializer):
    """账号门店角色调整请求."""

    store_roles = StoreRoleItemRequestSerializer(
        many=True,
        label="门店角色列表",
    )


class AccountStoreRolesView(APIView):
    """账号门店角色调整."""

    permission_classes = (IsAuthenticated, CanUpdateAccount)

    @extend_schema(
        operation_id="account_store_roles_update",
        summary="调整账号门店角色",
        description=(
            "替换账号的门店角色配置。超级管理员可以调整多个门店；"
            "门店管理员只能调整当前门店的角色。"
        ),
        request=AccountStoreRolesRequestSerializer,
        responses={200: AccountListSerializer},
    )
    @transaction.atomic
    def put(self, request, employee_code):
        """调整账号的门店角色."""
        is_superuser = request.user.is_superuser
        store_id = None if is_superuser else getattr(request, "store_id", None)

        if not is_superuser and store_id is None:
            raise BizException(
                code=BizCode.NOT_FOUND,
                message="账号不存在",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        user = _get_user(
            employee_code,
            for_update=True,
            store_id=store_id,
        )

        store_roles, roles_by_code = _validate_store_roles(
            request.data.get("store_roles")
        )

        # 门店管理员只能调整当前门店的角色
        if not is_superuser and any(
            item["store_id"] != store_id for item in store_roles
        ):
            raise BizException(
                code=BizCode.PARAM_INVALID,
                message="门店管理员只能调整当前门店角色",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # 锁定现有任职记录,避免并发修改
        existing_roles = UserStoreRole.objects.select_for_update().filter(
            user=user,
        )
        list(existing_roles)

        store_ids = [item["store_id"] for item in store_roles]

        # 超级管理员全局替换,未提交的任职记录只停用,不物理删除
        if is_superuser:
            existing_roles.exclude(store_id__in=store_ids).update(
                is_active=False,
            )

        # 更新已有任职,或创建新任职
        for item in store_roles:
            UserStoreRole.objects.update_or_create(
                user=user,
                store_id=item["store_id"],
                defaults={
                    "role": roles_by_code[item["role_code"]],
                    "is_active": True,
                },
            )

        log_operation(
            user=request.user,
            module="account",
            action="update_store_roles",
            target_type="User",
            target_id=user.employee_code,
            detail={
                "store_roles": [
                    {
                        "store_id": item["store_id"],
                        "role_code": item["role_code"],
                    }
                    for item in store_roles
                ]
            },
        )

        # 重新加载门店角色,避免使用旧的预取缓存
        user = _get_account_queryset().get(pk=user.pk)

        return success(
            data=AccountListSerializer(
                user,
                context={"store_id": store_id},
            ).data
        )
