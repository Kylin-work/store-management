"""交易明细模型."""

from django.db import models

from apps.products.models import Product
from apps.transactions.models.transaction import Transaction


class TransactionItem(models.Model):
    """交易明细."""

    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="交易",
        db_comment="所属交易",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="transaction_items",
        verbose_name="商品",
        db_comment="购买的商品",
    )
    quantity = models.IntegerField(
        verbose_name="数量", db_comment="购买数量"
    )
    refunded_quantity = models.IntegerField(
        default=0, verbose_name="已退数量", db_comment="已退款的数量"
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="单价",
        db_comment="成交单价, 快照",
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="小计",
        db_comment="单价 * 数量",
    )

    class Meta:
        db_table = "transactions_transaction_item"
        db_table_comment = "交易明细表"
        verbose_name = "交易明细"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.transaction_id}-{self.product_id}x{self.quantity}"
