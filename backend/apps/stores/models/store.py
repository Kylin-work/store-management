"""门店模型。

所有业务数据都挂在门店下,是数据隔离的锚点.
门店不物理删除,停用用 is_active=False.
"""

from django.db import models


class StoreType(models.TextChoices):
    DIRECT = "direct", "直营店"
    FRANCHISE = "franchise", "加盟店"
    FLAGSHIP = "flagship", "旗舰店"


class Store(models.Model):
    """门店"""

    name = models.CharField(
        max_length=200, unique=True, verbose_name="门店名称", db_comment="门店名称"
    )
    code = models.CharField(
        max_length=50, unique=True, verbose_name="门店编码", db_comment="门店编码"
    )
    store_type = models.CharField(
        max_length=20,
        choices=StoreType.choices,
        default=StoreType.DIRECT,
        verbose_name="门店类型",
        db_comment="直营店/加盟店/旗舰店",
    )
    address = models.CharField(
        max_length=200, blank=True, verbose_name="地址", db_comment="门店地址"
    )
    is_active = models.BooleanField(
        default=True, verbose_name="是否启用", db_comment="停用后不再出现在登录门店列表"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "stores_store"
        db_table_comment = "门店表"
        verbose_name = "门店"
        verbose_name_plural = verbose_name
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} {self.name}"
