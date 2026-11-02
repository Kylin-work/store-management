"""会员模型。"""

from django.db import models

from apps.stores.models import Store


class MemberLevel(models.TextChoices):
    """会员等级。"""

    NORMAL = "normal", "普通会员"
    SILVER = "silver", "银卡会员"
    GOLD = "gold", "金卡会员"


class Member(models.Model):
    """门店会员。"""

    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="members",
        verbose_name="门店",
        db_comment="所属门店",
    )
    name = models.CharField(max_length=50, verbose_name="姓名", db_comment="会员姓名")
    phone = models.CharField(
        max_length=20, verbose_name="手机号", db_comment="会员联系方式"
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="余额",
        db_comment="储值余额",
    )
    points = models.IntegerField(default=0, verbose_name="积分", db_comment="会员积分")
    level = models.CharField(
        max_length=20,
        choices=MemberLevel.choices,
        default=MemberLevel.NORMAL,
        verbose_name="等级",
        db_comment="会员等级",
    )
    is_active = models.BooleanField(
        default=True, verbose_name="是否启用", db_comment="停用后不可操作"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "members_member"
        db_table_comment = "会员表"
        verbose_name = "会员"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)
        constraints = (
            models.UniqueConstraint(
                fields=("store", "phone"),
                name="uniq_store_member_phone",
            ),
        )

    def __str__(self):
        return f"{self.store_id}-{self.name}({self.phone})"
