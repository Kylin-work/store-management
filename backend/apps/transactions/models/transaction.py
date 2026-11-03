"""交易模型."""

from django.conf import settings
from django.db import models

from apps.members.models import Member
from apps.stores.models import Store


class PaymentMethod(models.TextChoices):
    """支付方式."""

    CASH = "cash", "现金"
    WECHAT = "wechat", "微信"
    ALIPAY = "alipay", "支付宝"
    CARD = "card", "银行卡"


class TransactionStatus(models.TextChoices):
    """交易状态."""

    COMPLETED = "completed", "已完成"
    PARTIAL_REFUNDED = "partial_refunded", "部分退款"
    REFUNDED = "refunded", "已退款"


class Transaction(models.Model):
    """交易记录."""

    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="门店",
        db_comment="交易发生的门店",
    )
    member = models.ForeignKey(
        Member,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="会员",
        db_comment="关联会员, 散客交易为空",
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="操作人",
        db_comment="经办店员",
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="总金额",
        db_comment="交易总金额",
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="实收金额",
        db_comment="实际收款金额",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        verbose_name="支付方式",
        db_comment="现金/微信/支付宝/银行卡",
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.COMPLETED,
        verbose_name="状态",
        db_comment="已完成/已退款",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="交易时间", db_index=True
    )

    class Meta:
        db_table = "transactions_transaction"
        db_table_comment = "交易表"
        verbose_name = "交易"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.store_id}-{self.pk}-{self.total_amount}"
