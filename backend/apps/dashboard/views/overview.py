"""数据看板视图.

全部为只读聚合查询, 按门店隔离, 仅店长可访问.
"""

from datetime import timedelta

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    Sum,
)
from django.db.models.functions import TruncDay
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.members.models import Member
from apps.transactions.models import TransactionItem, TransactionStatus
from core.codes import BizCode
from core.exceptions import BizException
from core.permissions import HasPerm
from core.responses import success

# ---------------------------------------------------------------------------
# 权限类
# ---------------------------------------------------------------------------


class CanViewDashboard(HasPerm):
    """看板查看权限."""

    required_perm = "dashboard:view"


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


def _today_range():
    """返回今日的起止时间 (本地时区)."""
    now = timezone.localtime()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _net_quantity_expression():
    """商品净销量表达式."""
    return ExpressionWrapper(
        F("quantity") - F("refunded_quantity"),
        output_field=IntegerField(),
    )


def _net_amount_expression():
    """商品净销售金额表达式."""
    return ExpressionWrapper(
        F("unit_price") * (F("quantity") - F("refunded_quantity")),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def _valid_transaction_items():
    """返回本店有效交易的未退款商品明细."""
    return TransactionItem.objects.filter(
        transaction__status__in=(
            TransactionStatus.COMPLETED,
            TransactionStatus.PARTIAL_REFUNDED,
        ),
        quantity__gt=F("refunded_quantity"),
    )


# ---------------------------------------------------------------------------
# 概览
# ---------------------------------------------------------------------------


class DashboardSummaryView(APIView):
    """今日概览: 交易额, 订单数, 新增会员, 会员总数."""

    permission_classes = (IsAuthenticated, CanViewDashboard)

    def get(self, request):
        """返回本店今日概览."""
        store_id = _get_store_id(request)
        start, end = _today_range()

        today_stats = (
            _valid_transaction_items()
            .filter(
                transaction__store_id=store_id,
                transaction__created_at__gte=start,
                transaction__created_at__lt=end,
            )
            .annotate(net_amount=_net_amount_expression())
            .aggregate(
                total_amount=Sum("net_amount"),
                order_count=Count("transaction_id", distinct=True),
            )
        )

        new_members = Member.objects.filter(
            store_id=store_id,
            created_at__gte=start,
            created_at__lt=end,
        ).count()

        total_members = Member.objects.filter(store_id=store_id, is_active=True).count()

        return success(
            data={
                "today_total_amount": str(today_stats["total_amount"] or "0.00"),
                "today_order_count": today_stats["order_count"] or 0,
                "today_new_members": new_members,
                "total_members": total_members,
            }
        )


# ---------------------------------------------------------------------------
# 热销商品排行
# ---------------------------------------------------------------------------


class DashboardTopProductsView(APIView):
    """热销商品排行 (按净销量)."""

    permission_classes = (IsAuthenticated, CanViewDashboard)

    def get(self, request):
        """返回本店净销量前 10 的商品."""
        top = (
            _valid_transaction_items()
            .filter(transaction__store_id=_get_store_id(request))
            .annotate(
                net_quantity=_net_quantity_expression(),
                net_amount=_net_amount_expression(),
            )
            .values("product_id", "product__name")
            .annotate(
                total_quantity=Sum("net_quantity"),
                total_amount=Sum("net_amount"),
            )
            .order_by("-total_quantity")[:10]
        )

        return success(
            data=[
                {
                    "product_id": item["product_id"],
                    "product_name": item["product__name"],
                    "total_quantity": item["total_quantity"],
                    "total_amount": str(item["total_amount"]),
                }
                for item in top
            ]
        )


# ---------------------------------------------------------------------------
# 会员消费排行
# ---------------------------------------------------------------------------


class DashboardTopMembersView(APIView):
    """会员消费排行 (按净消费金额)."""

    permission_classes = (IsAuthenticated, CanViewDashboard)

    def get(self, request):
        """返回本店净消费金额前 10 的会员."""
        top = (
            _valid_transaction_items()
            .filter(
                transaction__store_id=_get_store_id(request),
                transaction__member__isnull=False,
            )
            .annotate(net_amount=_net_amount_expression())
            .values(
                "transaction__member_id",
                "transaction__member__name",
                "transaction__member__phone",
            )
            .annotate(
                total_amount=Sum("net_amount"),
                order_count=Count("transaction_id", distinct=True),
            )
            .order_by("-total_amount")[:10]
        )

        return success(
            data=[
                {
                    "member_id": item["transaction__member_id"],
                    "member_name": item["transaction__member__name"],
                    "member_phone": item["transaction__member__phone"],
                    "total_amount": str(item["total_amount"]),
                    "order_count": item["order_count"],
                }
                for item in top
            ]
        )


# ---------------------------------------------------------------------------
# 交易趋势
# ---------------------------------------------------------------------------


class DashboardTransactionTrendView(APIView):
    """交易趋势 (按天聚合, 默认最近 7 天)."""

    permission_classes = (IsAuthenticated, CanViewDashboard)

    def get(self, request):
        """返回最近 N 天的每日净交易额和有效订单数."""
        store_id = _get_store_id(request)

        try:
            days = int(request.query_params.get("days", 7))
        except (TypeError, ValueError):
            raise BizException(
                code=BizCode.PARAM_INVALID,
                message="days 必须为整数",
            )
        if not 1 <= days <= 30:
            raise BizException(
                code=BizCode.PARAM_INVALID,
                message="days 必须在 1 到 30 之间",
            )

        now = timezone.localtime()
        start = (now - timedelta(days=days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tz = timezone.get_current_timezone()

        trend = (
            _valid_transaction_items()
            .filter(
                transaction__store_id=store_id,
                transaction__created_at__gte=start,
            )
            .annotate(
                day=TruncDay("transaction__created_at", tzinfo=tz),
                net_amount=_net_amount_expression(),
            )
            .values("day")
            .annotate(
                total_amount=Sum("net_amount"),
                order_count=Count("transaction_id", distinct=True),
            )
            .order_by("day")
        )

        trend_map = {}
        for item in trend:
            day_value = item["day"]
            if day_value is None:
                continue
            trend_map[day_value.date().isoformat()] = {
                "total_amount": str(item["total_amount"]),
                "order_count": item["order_count"],
            }

        result = []
        for i in range(days):
            day = (start + timedelta(days=i)).date()
            day_str = day.isoformat()
            data = trend_map.get(day_str, {"total_amount": "0.00", "order_count": 0})
            result.append(
                {
                    "date": day_str,
                    "total_amount": data["total_amount"],
                    "order_count": data["order_count"],
                }
            )

        return success(data=result)
