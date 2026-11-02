"""账号状态管理视图."""

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import UserStoreRole
from apps.accounts.views.account import CanUpdateAccount, _get_user
from apps.logs.services.logger import log_operation
from core.codes import BizCode
from core.exceptions import BizException
from core.responses import success


class AccountStatusView(APIView):
    """账号启用/停用."""

    permission_classes = (IsAuthenticated, CanUpdateAccount)

    @transaction.atomic
    def patch(self, request, employee_code):
        """切换全局账号或当前门店任职状态."""
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

        is_active = request.data.get("is_active")

        if not isinstance(is_active, bool):
            raise BizException(
                code=BizCode.PARAM_INVALID,
                message="is_active 必须为布尔值",
            )

        if is_superuser:
            if user.is_active == is_active:
                return success(
                    data={
                        "employee_code": user.employee_code,
                        "is_active": user.is_active,
                    }
                )

            user.is_active = is_active
            user.save(update_fields=("is_active",))

            target_type = "User"
            target_id = user.employee_code
            detail = {"is_active": is_active}
        else:
            store_role = (
                UserStoreRole.objects.select_for_update()
                .filter(user=user, store_id=store_id)
                .first()
            )

            if store_role is None:
                raise BizException(
                    code=BizCode.NOT_FOUND,
                    message="账号不存在",
                    http_status=status.HTTP_404_NOT_FOUND,
                )

            if store_role.is_active == is_active:
                return success(
                    data={
                        "employee_code": user.employee_code,
                        "is_active": store_role.is_active,
                    }
                )

            store_role.is_active = is_active
            store_role.save(update_fields=("is_active",))

            target_type = "UserStoreRole"
            target_id = str(store_role.pk)
            detail = {
                "employee_code": user.employee_code,
                "store_id": store_id,
                "is_active": is_active,
            }

        log_operation(
            user=request.user,
            module="account",
            action="enable" if is_active else "disable",
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )

        return success(
            data={
                "employee_code": user.employee_code,
                "is_active": is_active,
            }
        )
