"""充值记录模型."""

from django.conf import settings
from django.db import models

from apps.members.models.member import Member


class RechargeRecord(models.Model):
    """会员充值记录."""

    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="recharge_records",
        verbose_name="会员",
        db_comment="充值的会员",
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recharge_records",
        verbose_name="操作人",
        db_comment="经办店员",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="充值金额",
        db_comment="本次充值金额",
    )
    balance_before = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="充值前余额",
        db_comment="充值前余额,用于对账",
    )
    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="充值后余额",
        db_comment="充值后余额,用于对账",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="充值时间")

    class Meta:
        db_table = "members_recharge_record"
        db_table_comment = "会员充值记录表"
        verbose_name = "充值记录"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.member_id} +{self.amount}"
