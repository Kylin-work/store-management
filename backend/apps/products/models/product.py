"""商品模型。"""

from django.db import models

from apps.stores.models import Store


class Product(models.Model):
    """门店商品。"""

    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="门店",
        db_comment="所属门店",
    )
    name = models.CharField(
        max_length=100, verbose_name="商品名称", db_comment="商品名称"
    )
    barcode = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="条码",
        db_comment="商品条码，可选",
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="售价",
        db_comment="商品售价",
    )
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="成本价",
        db_comment="成本价，店员不可见",
    )
    stock = models.IntegerField(
        default=0, verbose_name="库存", db_comment="当前库存数量"
    )
    is_active = models.BooleanField(
        default=True, verbose_name="是否启用", db_comment="停用后不可销售"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "products_product"
        db_table_comment = "商品表"
        verbose_name = "商品"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)
        constraints = (
            models.UniqueConstraint(
                fields=("store", "name"),
                name="uniq_store_product_name",
            ),
        )

    def __str__(self):
        return f"{self.store_id}-{self.name}"
