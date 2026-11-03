"""会员积分流水模型."""

from django.conf import settings
from django.db import models

from apps.members.models.member import Member


class PointsRecordType(models.TextChoices):
    """积分变动类型."""

    EARN = "earn", "消费获得"
    REFUND_DEDUCT = "refund_deduct", "退款扣回"
    ADJUST = "adjust", "人工调整"


class PointsRecord(models.Model):
    """会员积分变动记录."""

    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="points_records",
        verbose_name="会员",
        db_comment="积分变动所属会员",
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="points_records",
        verbose_name="操作人",
        db_comment="积分变动经办人",
    )
    transaction = models.ForeignKey(
        "transactions.Transaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="points_records",
        verbose_name="关联交易",
        db_comment="关联交易, 人工调整时为空",
    )
    earn_transaction = models.OneToOneField(
        "transactions.Transaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="points_earn_record",
        verbose_name="积分获得交易",
        db_comment="仅消费获得流水填写, 防止重复获得积分",
    )
    record_type = models.CharField(
        max_length=20,
        choices=PointsRecordType.choices,
        verbose_name="变动类型",
        db_comment="消费获得/退款扣回/人工调整",
    )
    points_delta = models.IntegerField(
        verbose_name="实际积分变动",
        db_comment="实际积分变动, 增加为正, 扣减为负",
    )
    points_expected_delta = models.IntegerField(
        verbose_name="预期积分变动",
        db_comment="业务预期积分变动, 增加为正, 扣减为负",
    )
    points_before = models.IntegerField(
        verbose_name="变动前积分",
        db_comment="变动前会员积分余额",
    )
    points_after = models.IntegerField(
        verbose_name="变动后积分",
        db_comment="变动后会员积分余额",
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="变动原因",
        db_comment="积分变动原因或备注",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="变动时间",
    )

    class Meta:
        db_table = "members_points_record"
        db_table_comment = "会员积分流水表"
        verbose_name = "积分流水"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)
        indexes = (
            models.Index(
                fields=("member", "-created_at"),
                name="points_member_created_idx",
            ),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(points_before__gte=0),
                name="points_record_before_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(points_after__gte=0),
                name="points_record_after_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    points_after=models.F("points_before") + models.F("points_delta")
                ),
                name="points_record_balance_consistent",
            ),
        )

    def __str__(self):
        return (
            f"{self.member_id} {self.points_delta:+d} "
            f"({self.get_record_type_display()})"
        )
