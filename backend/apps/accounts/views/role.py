"""角色管理视图."""

from django.db import transaction
from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import Permission, Role
from apps.accounts.serializers.role import (
    RoleCreateSerializer,
    RoleListSerializer,
    RoleUpdateSerializer,
)
from apps.logs.services.logger import log_operation
from core.codes import BizCode
from core.exceptions import BizException
from core.pagination import StandardPagination
from core.permissions import HasPerm
from core.responses import success

# ---------------------------------------------------------------------------
# 文档响应序列化器
# ---------------------------------------------------------------------------


class RoleListResponseSerializer(serializers.Serializer):
    """角色分页响应."""

    items = RoleListSerializer(many=True, label="角色列表")
    total = serializers.IntegerField(label="总数量")
    page = serializers.IntegerField(label="当前页码")
    page_size = serializers.IntegerField(label="每页数量")


class PermissionItemResponseSerializer(serializers.Serializer):
    """权限码项响应."""

    id = serializers.IntegerField(label="权限 ID")
    code = serializers.CharField(label="权限编码")
    name = serializers.CharField(label="权限名称")


class PermissionGroupResponseSerializer(serializers.Serializer):
    """权限码分组响应."""

    module = serializers.CharField(label="权限模块")
    permissions = PermissionItemResponseSerializer(
        many=True,
        label="权限码列表",
    )


# ---------------------------------------------------------------------------
# 权限类
# ---------------------------------------------------------------------------


class IsPlatformAdmin(BasePermission):
    """仅允许平台超级管理员访问角色管理接口."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_superuser
        )


class CanListPermission(HasPerm):
    """权限码列表权限."""

    required_perm = "permission:list"


# ---------------------------------------------------------------------------
# 公共方法
# ---------------------------------------------------------------------------


def _get_role(code: str, *, for_update=False) -> Role:
    """按角色编码获取角色."""
    queryset = Role.objects.all()

    if for_update:
        queryset = queryset.select_for_update()

    role = queryset.filter(code=code).first()

    if role is None:
        raise BizException(
            code=BizCode.NOT_FOUND,
            message="角色不存在",
            http_status=status.HTTP_404_NOT_FOUND,
        )

    return role


def _get_role_queryset():
    """获取带用户数量和权限的角色查询集."""
    return Role.objects.annotate(
        user_count=Count(
            "user_store_roles__user",
            distinct=True,
        )
    ).prefetch_related("permissions")


def _get_role_detail(pk) -> Role:
    """获取角色详情,预加载权限和用户数量."""
    return _get_role_queryset().get(pk=pk)


# ---------------------------------------------------------------------------
# 角色列表与创建
# ---------------------------------------------------------------------------


class RoleListCreateView(APIView):
    """角色列表与创建."""

    def get_permissions(self):
        """根据请求方法分配权限."""
        return [IsPlatformAdmin()]

    @extend_schema(
        operation_id="role_list",
        summary="角色列表",
        description="分页查询系统角色及其权限和关联用户数量。",
        responses={200: RoleListResponseSerializer},
    )
    def get(self, request):
        """角色列表,分页."""
        queryset = _get_role_queryset().order_by("code", "pk")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = RoleListSerializer(page, many=True)

        return success(
            data={
                "items": serializer.data,
                "total": paginator.page.paginator.count,
                "page": paginator.page.number,
                "page_size": paginator.get_page_size(request),
            }
        )

    @extend_schema(
        operation_id="role_create",
        summary="创建角色",
        description="创建系统角色，并分配权限码。",
        request=RoleCreateSerializer,
        responses={201: RoleListSerializer},
    )
    @transaction.atomic
    def post(self, request):
        """创建角色."""
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save()

        log_operation(
            user=request.user,
            module="role",
            action="create",
            target_type="Role",
            target_id=role.code,
            detail={
                "code": role.code,
                "name": role.name,
                "permission_codes": [p.code for p in role.permissions.all()],
            },
        )

        role = _get_role_detail(role.pk)

        return success(
            data=RoleListSerializer(role).data,
            http_status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# 角色详情与编辑
# ---------------------------------------------------------------------------


class RoleDetailView(APIView):
    """角色详情与编辑."""

    def get_permissions(self):
        """根据请求方法分配权限."""
        return [IsPlatformAdmin()]

    @extend_schema(
        operation_id="role_detail",
        summary="角色详情",
        description="根据角色编码查询角色详情，包括权限码和关联用户数量。",
        responses={200: RoleListSerializer},
    )
    def get(self, request, code):
        """角色详情."""
        role = _get_role(code)
        role = _get_role_detail(role.pk)

        return success(data=RoleListSerializer(role).data)

    @extend_schema(
        operation_id="role_update",
        summary="编辑角色",
        description=(
            "修改角色名称、启用状态或权限码。"
            "permission_codes 为全量替换，未提供的字段保持不变。"
        ),
        request=RoleUpdateSerializer,
        responses={200: RoleListSerializer},
    )
    @transaction.atomic
    def patch(self, request, code):
        """编辑角色：名称、启用状态、权限码."""
        role = _get_role(code, for_update=True)

        serializer = RoleUpdateSerializer(
            role,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        changed_fields = list(serializer.validated_data.keys())
        log_operation(
            user=request.user,
            module="role",
            action="update",
            target_type="Role",
            target_id=role.code,
            detail={
                "changed_fields": changed_fields,
                "permission_codes": [p.code for p in role.permissions.all()],
            },
        )

        role = _get_role_detail(role.pk)

        return success(data=RoleListSerializer(role).data)


# ---------------------------------------------------------------------------
# 权限码列表
# ---------------------------------------------------------------------------


class PermissionListView(APIView):
    """权限码列表,按模块分组."""

    permission_classes = (IsAuthenticated, CanListPermission)

    @extend_schema(
        operation_id="permission_list",
        summary="权限码列表",
        description="查询所有启用的权限码，并按所属模块分组。",
        responses={200: PermissionGroupResponseSerializer(many=True)},
    )
    def get(self, request):
        """返回按模块分组的权限码."""
        permissions = (
            Permission.objects.filter(
                is_active=True,
            )
            .order_by("module", "code")
            .values(
                "id",
                "code",
                "name",
                "module",
            )
        )

        grouped = {}

        for perm in permissions:
            module = perm["module"] or "其他"

            grouped.setdefault(module, []).append(
                {
                    "id": perm["id"],
                    "code": perm["code"],
                    "name": perm["name"],
                }
            )

        return success(
            data=[
                {
                    "module": module,
                    "permissions": items,
                }
                for module, items in grouped.items()
            ]
        )
