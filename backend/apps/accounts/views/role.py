"""角色管理视图。"""

from django.db import transaction
from django.db.models import Count
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import Permission, Role
from apps.accounts.serializers.role import (
    RoleCreateSerializer,
    RoleListSerializer,
    RoleUpdateSerializer,
)
from core.codes import BizCode
from core.exceptions import BizException
from core.pagination import StandardPagination
from core.permissions import HasPerm
from core.responses import success

# ---------------------------------------------------------------------------
# 权限类
# ---------------------------------------------------------------------------


class CanListRole(HasPerm):
    """角色列表及详情权限。"""

    required_perm = "role:list"


class CanManageRole(HasPerm):
    """创建、编辑角色权限。"""

    required_perm = "role:manage"


class CanListPermission(HasPerm):
    """权限码列表权限。"""

    required_perm = "permission:list"


# ---------------------------------------------------------------------------
# 公共方法
# ---------------------------------------------------------------------------


def _get_role(code: str, *, for_update=False) -> Role:
    """按角色编码获取角色。"""
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
    """获取带用户数量和权限的角色查询集。"""
    return Role.objects.annotate(
        user_count=Count(
            "user_store_roles__user",
            distinct=True,
        )
    ).prefetch_related("permissions")


def _get_role_detail(pk) -> Role:
    """获取角色详情，预加载权限和用户数量。"""
    return _get_role_queryset().get(pk=pk)


# ---------------------------------------------------------------------------
# 角色列表与创建
# ---------------------------------------------------------------------------


class RoleListCreateView(APIView):
    """角色列表与创建。"""

    def get_permissions(self):
        """根据请求方法分配权限。"""
        permission_class = (
            CanListRole if self.request.method == "GET" else CanManageRole
        )
        return [IsAuthenticated(), permission_class()]

    def get(self, request):
        """角色列表，分页。"""
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

    @transaction.atomic
    def post(self, request):
        """创建角色。"""
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save()

        role = _get_role_detail(role.pk)

        return success(
            data=RoleListSerializer(role).data,
            http_status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# 角色详情与编辑
# ---------------------------------------------------------------------------


class RoleDetailView(APIView):
    """角色详情与编辑。"""

    def get_permissions(self):
        """根据请求方法分配权限。"""
        permission_class = (
            CanListRole if self.request.method == "GET" else CanManageRole
        )
        return [IsAuthenticated(), permission_class()]

    def get(self, request, code):
        """角色详情。"""
        role = _get_role(code)
        role = _get_role_detail(role.pk)

        return success(data=RoleListSerializer(role).data)

    @transaction.atomic
    def patch(self, request, code):
        """编辑角色：名称、启用状态、权限码。"""
        role = _get_role(code, for_update=True)

        serializer = RoleUpdateSerializer(
            role,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        role = _get_role_detail(role.pk)

        return success(data=RoleListSerializer(role).data)


# ---------------------------------------------------------------------------
# 权限码列表
# ---------------------------------------------------------------------------


class PermissionListView(APIView):
    """权限码列表，按模块分组。"""

    permission_classes = (IsAuthenticated, CanListPermission)

    def get(self, request):
        """返回按模块分组的权限码。"""
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
