"""账号门店角色管理视图."""

from django.db import transaction
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
from core.responses import success


class AccountStoreRolesView(APIView):
    """账号门店角色调整."""

    permission_classes = (IsAuthenticated, CanUpdateAccount)

    @transaction.atomic
    def put(self, request, employee_code):
        """全量替换账号的门店角色."""
        user = _get_user(employee_code, for_update=True)

        store_roles, roles_by_code = _validate_store_roles(
            request.data.get("store_roles")
        )

        # 全量替换
        UserStoreRole.objects.filter(user=user).delete()

        UserStoreRole.objects.bulk_create(
            [
                UserStoreRole(
                    user=user,
                    store_id=item["store_id"],
                    role=roles_by_code[item["role_code"]],
                )
                for item in store_roles
            ]
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

        return success(data=AccountListSerializer(user).data)
