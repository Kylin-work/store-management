"""门店管理端视图。"""

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.logs.services.logger import log_operation
from apps.stores.models import Store
from apps.stores.permissions.store import IsSuperUser
from apps.stores.serializers.store_manage import StoreManageSerializer
from core.codes import BizCode
from core.exceptions import BizException
from core.pagination import StandardPagination
from core.responses import success


class StoreManageBaseView(APIView):
    """门店管理基础视图。"""

    permission_classes = (IsAuthenticated, IsSuperUser)

    @staticmethod
    def get_store(pk, *, for_update=False):
        """获取门店，不存在时抛出业务异常。"""
        queryset = Store.objects.all()

        if for_update:
            queryset = queryset.select_for_update()

        store = queryset.filter(pk=pk).first()

        if store is None:
            raise BizException(
                code=BizCode.STORE_NOT_FOUND,
                message="门店不存在",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        return store


class StoreManageListCreateView(StoreManageBaseView):
    """门店列表与创建。"""

    def get(self, request):
        """门店列表，分页。"""
        queryset = Store.objects.all().order_by("code", "pk")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = StoreManageSerializer(page, many=True)

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
        """创建门店。"""
        serializer = StoreManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.save()
        log_operation(
            user=request.user,
            module="store",
            action="create",
            target_type="Store",
            target_id=str(store.pk),
            detail={"code": store.code, "name": store.name},
        )
        return success(
            data=StoreManageSerializer(store).data,
            http_status=status.HTTP_201_CREATED,
        )


class StoreManageDetailView(StoreManageBaseView):
    """门店详情与编辑。"""

    def get(self, request, pk):
        """门店详情。"""
        store = self.get_store(pk)
        return success(data=StoreManageSerializer(store).data)

    @transaction.atomic
    def put(self, request, pk):
        """全量编辑门店。"""
        store = self.get_store(pk, for_update=True)

        serializer = StoreManageSerializer(
            store,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_operation(
            user=request.user,
            module="store",
            action="update",
            target_type="Store",
            target_id=str(store.pk),
            detail={"changed_fields": list(serializer.validated_data.keys())},
        )
        return success(data=serializer.data)

    @transaction.atomic
    def patch(self, request, pk):
        """部分编辑门店。"""
        store = self.get_store(pk, for_update=True)

        serializer = StoreManageSerializer(
            store,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_operation(
            user=request.user,
            module="store",
            action="update",
            target_type="Store",
            target_id=str(store.pk),
            detail={"changed_fields": list(serializer.validated_data.keys())},
        )
        return success(data=serializer.data)


class StoreManageStatusView(StoreManageBaseView):
    """门店启用/停用。"""

    @transaction.atomic
    def patch(self, request, pk):
        """切换门店启用状态。"""
        store = self.get_store(pk, for_update=True)

        is_active = request.data.get("is_active")

        if not isinstance(is_active, bool):
            raise BizException(
                code=BizCode.PARAM_INVALID,
                message="is_active 必须为布尔值",
            )

        if store.is_active == is_active:
            return success(
                data={
                    "id": store.pk,
                    "is_active": store.is_active,
                }
            )

        store.is_active = is_active
        store.save(update_fields=("is_active", "updated_at"))
        log_operation(
            user=request.user,
            module="store",
            action="enable" if is_active else "disable",
            target_type="Store",
            target_id=str(store.pk),
            detail={"is_active": is_active},
        )
        return success(
            data={
                "id": store.pk,
                "is_active": store.is_active,
            }
        )
