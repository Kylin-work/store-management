"""商品管理视图."""

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.logs.services.logger import log_operation
from apps.products.models import Product
from apps.products.serializers.product import (
    ProductAdjustStockSerializer,
    ProductCreateSerializer,
    ProductListSerializer,
    ProductUpdateSerializer,
)
from core.codes import BizCode
from core.exceptions import BizException
from core.pagination import StandardPagination
from core.permissions import HasPerm
from core.responses import success

# ---------------------------------------------------------------------------
# 权限类
# ---------------------------------------------------------------------------


class CanListProduct(HasPerm):
    """商品列表及详情权限."""

    required_perm = "product:list"


class CanCreateProduct(HasPerm):
    """创建商品权限."""

    required_perm = "product:create"


class CanUpdateProduct(HasPerm):
    """编辑商品权限."""

    required_perm = "product:update"


class CanAdjustStock(HasPerm):
    """商品库存调整权限."""

    required_perm = "product:adjust_stock"


class CanDeleteProduct(HasPerm):
    """删除商品权限."""

    required_perm = "product:delete"


# ---------------------------------------------------------------------------
# 公共方法
# ---------------------------------------------------------------------------


def _get_store_id(request) -> int:
    """从请求上下文获取当前门店 ID."""
    store_id = getattr(request, "store_id", None)
    if store_id is None:
        raise BizException(
            code=BizCode.PERMISSION_DENIED,
            message="当前账号未绑定门店",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return store_id


def _get_product(pk: int, store_id: int, *, for_update: bool = False) -> Product:
    """按主键和门店获取商品, 不存在时抛业务异常."""
    queryset = Product.objects.filter(pk=pk, store_id=store_id)

    if for_update:
        queryset = queryset.select_for_update()

    product = queryset.first()

    if product is None:
        raise BizException(
            code=BizCode.PRODUCT_NOT_FOUND,
            message="商品不存在",
            http_status=status.HTTP_404_NOT_FOUND,
        )

    return product


# ---------------------------------------------------------------------------
# 商品列表与创建
# ---------------------------------------------------------------------------


class ProductListCreateView(APIView):
    """商品列表与创建."""

    def get_permissions(self):
        """按方法挂权限码."""
        permission_class = (
            CanListProduct if self.request.method == "GET" else CanCreateProduct
        )
        return [IsAuthenticated(), permission_class()]

    def get(self, request):
        """商品列表, 分页, 按门店隔离."""
        store_id = _get_store_id(request)
        queryset = Product.objects.filter(store_id=store_id).order_by("-created_at")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ProductListSerializer(
            page, many=True, context={"request": request}
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
        """创建商品."""
        store_id = _get_store_id(request)
        serializer = ProductCreateSerializer(
            data=request.data, context={"store_id": store_id}
        )
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        log_operation(
            user=request.user,
            module="product",
            action="create",
            target_type="Product",
            target_id=str(product.pk),
            detail={
                "name": product.name,
                "price": str(product.price),
                "stock": product.stock,
            },
        )

        return success(
            data=ProductListSerializer(product, context={"request": request}).data,
            http_status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# 商品详情与编辑
# ---------------------------------------------------------------------------


class ProductDetailView(APIView):
    """商品详情, 编辑, 删除."""

    def get_permissions(self):
        """按方法挂权限码."""
        if self.request.method == "GET":
            permission_class = CanListProduct
        elif self.request.method == "DELETE":
            permission_class = CanDeleteProduct
        else:
            permission_class = CanUpdateProduct
        return [IsAuthenticated(), permission_class()]

    def get(self, request, pk):
        """商品详情."""
        store_id = _get_store_id(request)
        product = _get_product(pk, store_id)
        return success(
            data=ProductListSerializer(product, context={"request": request}).data
        )

    @transaction.atomic
    def patch(self, request, pk):
        """编辑商品."""
        store_id = _get_store_id(request)
        product = _get_product(pk, store_id, for_update=True)

        serializer = ProductUpdateSerializer(
            product,
            data=request.data,
            partial=True,
            context={"store_id": store_id, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        log_operation(
            user=request.user,
            module="product",
            action="update",
            target_type="Product",
            target_id=str(product.pk),
            detail={"changed_fields": list(serializer.validated_data.keys())},
        )

        return success(
            data=ProductListSerializer(product, context={"request": request}).data
        )

    @transaction.atomic
    def delete(self, request, pk):
        """停用商品(软删除)."""
        store_id = _get_store_id(request)
        product = _get_product(pk, store_id, for_update=True)

        if not product.is_active:
            return success(data={"id": product.pk, "is_active": False})

        product.is_active = False
        product.save(update_fields=("is_active", "updated_at"))

        log_operation(
            user=request.user,
            module="product",
            action="delete",
            target_type="Product",
            target_id=str(product.pk),
            detail={"name": product.name},
        )

        return success(data={"id": product.pk, "is_active": False})

# ---------------------------------------------------------------------------
# 商品库存调整
# ---------------------------------------------------------------------------

class ProductAdjustStockView(APIView):
    """商品库存调整, 仅店长."""

    permission_classes = (IsAuthenticated, CanAdjustStock)

    @transaction.atomic
    def patch(self, request, pk):
        """调整商品库存."""
        store_id = _get_store_id(request)
        product = _get_product(pk, store_id, for_update=True)

        serializer = ProductAdjustStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity_delta = serializer.validated_data["quantity"]
        reason = serializer.validated_data["reason"]

        stock_before = product.stock
        new_stock = stock_before + quantity_delta
        if new_stock < 0:
            raise BizException(
                code=BizCode.PARAM_INVALID,
                message=f"库存不足, 当前库存 {stock_before}, 调整后不能为负",
            )

        product.stock = new_stock
        product.save(update_fields=("stock", "updated_at"))

        log_operation(
            user=request.user,
            module="product",
            action="adjust_stock",
            target_type="Product",
            target_id=str(product.pk),
            detail={
                "stock_before": stock_before,
                "stock_after": new_stock,
                "reason": reason,
            },
        )

        return success(
            data=ProductListSerializer(
                product, context={"request": request}
            ).data
        )
