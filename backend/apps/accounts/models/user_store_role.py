"""用户门店角色模型.

表达"谁、在哪个门店、是什么角色".
同一个用户在不同门店可以有不同角色,但同一门店只能有一个角色.
"""

from django.db import models

from apps.accounts.models.role import Role
from apps.accounts.models.user import User


class UserStoreRole(models.Model):
    """用户在某门店的角色."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="store_roles",
        verbose_name="用户",
        db_comment="用户",
    )
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="user_roles",
        verbose_name="门店",
        db_comment="门店",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="user_store_roles",
        verbose_name="角色",
        db_comment="角色",
    )
    # 当前员工在该门店的任职状态
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="任职状态",
        db_comment="是否在该门店任职",
    )

    class Meta:
        db_table = "accounts_user_store_role"
        db_table_comment = "用户门店角色关联表"
        verbose_name = "用户门店角色"
        verbose_name_plural = verbose_name
        constraints = (
            models.UniqueConstraint(
                fields=("user", "store"),
                name="uniq_user_store_role",
            ),
        )

    def __str__(self):
        return f"{self.user.employee_code}@{self.store_id}:{self.role.code}"
