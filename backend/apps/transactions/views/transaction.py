"""交易管理视图."""

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.transactions.models import Transaction
from apps.transactions.serializers.transaction import (
    TransactionCreateSerializer,
    TransactionListSerializer,
    TransactionRefundSerializer,
)
from apps.transactions.services.create_transaction import create_transaction
from apps.transactions.services.refund_transaction import refund_transaction
from core.codes import BizCode
from core.exceptions import BizException
from core.pagination import StandardPagination
from core.permissions import HasPerm
from core.responses import success

# ---------------------------------------------------------------------------
# 权限类
# ---------------------------------------------------------------------------


class CanListTransaction(HasPerm):
    """交易列表及详情权限."""

    required_perm = "transaction:list"


class CanCreateTransaction(HasPerm):
    """收银权限."""

    required_perm = "transaction:create"


class CanRefundTransaction(HasPerm):
    """退款权限."""

    required_perm = "transaction:refund"


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


def _is_manager(request) -> bool:
    """判断当前用户是否有退款权限 (店长)."""
    if request.user.is_superuser:
        return True
    perm_set = getattr(request, "perm_set", None) or set()
    return "transaction:refund" in perm_set


def _get_transaction(pk: int, store_id: int, request, *, for_update: bool = False):
    """按主键和门店获取交易, 店员只能看自己经手的."""
    queryset = Transaction.objects.filter(pk=pk, store_id=store_id)

    # 店员只能看自己经手的交易
    if not _is_manager(request):
        queryset = queryset.filter(staff=request.user)

    if for_update:
        queryset = queryset.select_for_update()

    tx = queryset.first()
    if tx is None:
        raise BizException(
            code=BizCode.TRANSACTION_NOT_FOUND,
            message="交易不存在",
            http_status=status.HTTP_404_NOT_FOUND,
        )
    return tx


# ---------------------------------------------------------------------------
# 交易列表与创建
# ---------------------------------------------------------------------------


class TransactionListCreateView(APIView):
    """交易列表与收银."""

    def get_permissions(self):
        """按方法挂权限码."""
        permission_class = (
            CanListTransaction if self.request.method == "GET" else CanCreateTransaction
        )
        return [IsAuthenticated(), permission_class()]

    def get(self, request):
        """交易列表, 分页, 按门店隔离, 店员只看自己经手的."""
        store_id = _get_store_id(request)
        queryset = Transaction.objects.filter(store_id=store_id)

        # 店员只看自己经手的交易
        if not _is_manager(request):
            queryset = queryset.filter(staff=request.user)

        queryset = queryset.prefetch_related("items__product").order_by("-created_at")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TransactionListSerializer(page, many=True)

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
        """收银: 创建交易."""
        store_id = _get_store_id(request)

        serializer = TransactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tx = create_transaction(
            store_id=store_id,
            staff=request.user,
            items=data["items"],
            payment_method=data["payment_method"],
            member_id=data.get("member_id"),
        )

        tx = (
            Transaction.objects.prefetch_related("items__product")
            .select_related("member", "staff")
            .get(pk=tx.pk)
        )

        return success(
            data=TransactionListSerializer(tx).data,
            http_status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# 交易详情
# ---------------------------------------------------------------------------


class TransactionDetailView(APIView):
    """交易详情."""

    permission_classes = (IsAuthenticated, CanListTransaction)

    def get(self, request, pk):
        """交易详情."""
        store_id = _get_store_id(request)
        tx = (
            Transaction.objects.filter(pk=pk, store_id=store_id)
            .select_related("member", "staff")
            .prefetch_related("items__product")
            .first()
        )

        if tx is None:
            raise BizException(
                code=BizCode.TRANSACTION_NOT_FOUND,
                message="交易不存在",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        # 店员只能看自己经手的
        if not _is_manager(request) and tx.staff_id != request.user.pk:
            raise BizException(
                code=BizCode.TRANSACTION_NOT_FOUND,
                message="交易不存在",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        return success(data=TransactionListSerializer(tx).data)


# ---------------------------------------------------------------------------
# 交易退款
# ---------------------------------------------------------------------------


class TransactionRefundView(APIView):
    """交易退款, 仅店长."""

    permission_classes = (IsAuthenticated, CanRefundTransaction)

    @transaction.atomic
    def post(self, request, pk):
        """退款, 支持全额和部分退款."""
        store_id = _get_store_id(request)

        serializer = TransactionRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items = serializer.validated_data.get("items") or None

        tx = refund_transaction(
            transaction_id=pk,
            store_id=store_id,
            staff=request.user,
            items=items,
        )

        tx = (
            Transaction.objects.prefetch_related("items__product")
            .select_related("member", "staff")
            .get(pk=tx.pk)
        )

        return success(data=TransactionListSerializer(tx).data)
