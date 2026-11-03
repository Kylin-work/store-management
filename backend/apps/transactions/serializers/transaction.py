"""交易序列化器."""

from rest_framework import serializers

from apps.transactions.models import (
    PaymentMethod,
    Transaction,
    TransactionItem,
)


class TransactionItemSerializer(serializers.ModelSerializer):
    """交易明细序列化器."""

    product_name = serializers.CharField(
        source="product.name", read_only=True, label="商品名称"
    )

    class Meta:
        model = TransactionItem
        fields = (
            "id",
            "product_id",
            "product_name",
            "quantity",
            "unit_price",
            "subtotal",
        )
        read_only_fields = fields


class TransactionListSerializer(serializers.ModelSerializer):
    """交易列表/详情序列化器."""

    member_name = serializers.CharField(
        source="member.name", read_only=True, default=None, label="会员姓名"
    )
    staff_name = serializers.CharField(
        source="staff.real_name", read_only=True, label="经办人"
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True, label="支付方式"
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True, label="状态"
    )
    items = TransactionItemSerializer(many=True, read_only=True, label="明细")

    class Meta:
        model = Transaction
        fields = (
            "id",
            "member_id",
            "member_name",
            "staff_name",
            "total_amount",
            "paid_amount",
            "payment_method",
            "payment_method_display",
            "status",
            "status_display",
            "created_at",
            "items",
        )
        read_only_fields = fields


class TransactionItemInputSerializer(serializers.Serializer):
    """创建交易时的商品明细入参."""

    product_id = serializers.IntegerField(min_value=1, label="商品ID")
    quantity = serializers.IntegerField(min_value=1, label="数量")


class TransactionCreateSerializer(serializers.Serializer):
    """创建交易入参序列化器."""

    member_id = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, label="会员ID"
    )
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices, label="支付方式"
    )
    items = TransactionItemInputSerializer(
        many=True, allow_empty=False, label="商品明细"
    )

    def validate_items(self, value):
        """校验明细里同一商品不重复 (合并逻辑在 service 层做, 这里不拦截)."""
        return value


class TransactionRefundItemSerializer(serializers.Serializer):
    """退款明细项."""

    item_id = serializers.IntegerField(min_value=1, label="交易明细ID")
    quantity = serializers.IntegerField(min_value=1, label="退款数量")


class TransactionRefundSerializer(serializers.Serializer):
    """退款入参序列化器.

    items 为空或未传表示全额退款, 传了则按明细部分退款.
    """

    items = TransactionRefundItemSerializer(
        many=True, required=False, allow_empty=True, label="退款明细"
    )
