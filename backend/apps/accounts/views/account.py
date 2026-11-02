"""账号管理视图."""

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.serializers.account import (
    AccountCreateSerializer,
    AccountListSerializer,
    AccountUpdateSerializer,
    StoreRoleItemSerializer,
)
from apps.logs.services.logger import log_operation
from apps.stores.models import Store
from core.codes import BizCode
from core.exceptions import BizException
from core.pagination import StandardPagination
from core.permissions import HasPerm
from core.responses import success

# ---------------------------------------------------------------------------
# 权限类
# ---------------------------------------------------------------------------


class CanListAccount(HasPerm):
    """账号列表及详情权限."""

    required_perm = "account:list"


class CanCreateAccount(HasPerm):
    """创建账号权限."""

    required_perm = "account:create"


class CanUpdateAccount(HasPerm):
    """编辑账号权限."""

    required_perm = "account:update"


# ---------------------------------------------------------------------------
# 公共方法
# ---------------------------------------------------------------------------


def _get_user(
    employee_code: str,
    *,
    for_update=False,
    store_id=None,
) -> User:
    """按工号获取账号,不存在时抛出业务异常.

    for_update=True 时加行锁,必须在事务内调用.
    for_update=False 时预加载门店角色,供序列化使用.
    """
    queryset = User.objects.all()

    # 普通门店管理员只能访问当前门店的账号
    if store_id is not None:
        queryset = queryset.filter(store_roles__store_id=store_id)

    if for_update:
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.prefetch_related(
            "store_roles__store",
            "store_roles__role",
        )

    user = queryset.filter(employee_code=employee_code).first()

    if user is None:
        raise BizException(
            code=BizCode.NOT_FOUND,
            message="账号不存在",
            http_status=status.HTTP_404_NOT_FOUND,
        )

    return user


def _get_account_queryset():
    """获取预加载门店角色的账号查询集,供列表使用."""
    return User.objects.prefetch_related(
        "store_roles__store",
        "store_roles__role",
    )


def _validate_store_roles(data):
    """校验门店角色数据,并返回门店角色列表及角色映射.

    必须在事务内调用(使用了 select_for_update).
    """
    serializer = StoreRoleItemSerializer(
        data=data,
        many=True,
        allow_empty=False,
    )
    serializer.is_valid(raise_exception=True)
    store_roles = serializer.validated_data

    store_ids = [item["store_id"] for item in store_roles]

    if len(store_ids) != len(set(store_ids)):
        raise BizException(
            code=BizCode.PARAM_INVALID,
            message="同一门店只能分配一个角色",
        )

    # 校验门店(加行锁,防止校验后被删)
    existing_store_ids = set(
        Store.objects.select_for_update()
        .filter(pk__in=store_ids, is_active=True)
        .values_list("pk", flat=True)
    )

    missing_store_ids = set(store_ids) - existing_store_ids

    if missing_store_ids:
        raise BizException(
            code=BizCode.STORE_NOT_FOUND,
            message=f"门店不存在或已停用：{sorted(missing_store_ids)}",
        )

    # 校验角色(加行锁,防止校验后被停用)
    role_codes = {item["role_code"] for item in store_roles}

    roles_by_code = {
        role.code: role
        for role in Role.objects.select_for_update().filter(
            code__in=role_codes,
            is_active=True,
        )
    }

    missing_role_codes = role_codes - set(roles_by_code)

    if missing_role_codes:
        raise BizException(
            code=BizCode.PARAM_INVALID,
            message=f"角色不存在或已停用：{sorted(missing_role_codes)}",
        )

    return store_roles, roles_by_code


# ---------------------------------------------------------------------------
# 账号列表与创建
# ---------------------------------------------------------------------------


class AccountListCreateView(APIView):
    """账号列表与创建."""

    def get_permissions(self):
        """根据请求方法分配权限."""
        permission_class = (
            CanListAccount if self.request.method == "GET" else CanCreateAccount
        )
        return [IsAuthenticated(), permission_class()]

    def get(self, request):
        """账号列表,分页."""
        queryset = _get_account_queryset()

        # 普通门店管理员只能查看当前门店的员工
        if not request.user.is_superuser:
            queryset = queryset.filter(
                store_roles__store_id=request.store_id
            ).distinct()

        queryset = queryset.order_by("employee_code", "pk")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = AccountListSerializer(
            page,
            many=True,
            context={
                "store_id": (None if request.user.is_superuser else request.store_id)
            },
        )

        return success(
            data={
                "items": serializer.data,
                "total": paginator.page.paginator.count,
                "page": paginator.page.number,
                "page_size": paginator.get_page_size(request),
            }
        )

    @transaction.atomic
    def post(self, request):
        """创建账号,自动生成工号并分配门店角色."""
        serializer = AccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        log_operation(
            user=request.user,
            module="account",
            action="create",
            target_type="User",
            target_id=user.employee_code,
            detail={
                "employee_code": user.employee_code,
                "phone": user.phone,
                "real_name": user.real_name,
                "store_roles": [
                    {
                        "store_id": item["store_id"],
                        "role_code": item["role_code"],
                    }
                    for item in serializer.validated_data.get("store_roles", [])
                ],
            },
        )

        # 重新加载,带出门店角色
        user = _get_account_queryset().get(pk=user.pk)

        return success(
            data=AccountListSerializer(user).data,
            http_status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# 账号详情与编辑
# ---------------------------------------------------------------------------


class AccountDetailView(APIView):
    """账号详情与编辑."""

    def get_permissions(self):
        """根据请求方法分配权限."""
        permission_class = (
            CanListAccount if self.request.method == "GET" else CanUpdateAccount
        )
        return [IsAuthenticated(), permission_class()]

    def get(self, request, employee_code):
        """账号详情."""
        store_id = None if request.user.is_superuser else request.store_id
        user = _get_user(employee_code, store_id=store_id)
        return success(
            data=AccountListSerializer(
                user,
                context={"store_id": store_id},
            ).data
        )

    @transaction.atomic
    def patch(self, request, employee_code):
        """编辑账号：手机号、姓名、密码."""
        store_id = None if request.user.is_superuser else request.store_id
        user = _get_user(
            employee_code,
            for_update=True,
            store_id=store_id,
        )

        serializer = AccountUpdateSerializer(
            user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        changed_fields = list(serializer.validated_data.keys())
        log_operation(
            user=request.user,
            module="account",
            action="update",
            target_type="User",
            target_id=user.employee_code,
            detail={
                "changed_fields": changed_fields,
                "password_changed": "password" in changed_fields,
            },
        )

        # 重新加载,带出门店角色
        user = _get_account_queryset().get(pk=user.pk)

        return success(
            data=AccountListSerializer(
                user,
                context={"store_id": store_id},
            ).data
        )


# ---------------------------------------------------------------------------
# 账号启用与停用
# ---------------------------------------------------------------------------


# 账号门店角色调整
# ---------------------------------------------------------------------------
