"""角色模型。

角色不写死,管理员可在后台添加(如区域经理、财务).
角色与权限码通过 M2M 关联，权限映射存数据库.
is_system=True 的内置角色不可删除.
"""

from django.db import models

from apps.accounts.models.permission import Permission


class Role(models.Model):
    """系统角色。一个角色拥有一组权限码。"""

    name = models.CharField(
        max_length=50, unique=True, verbose_name="角色名称", db_comment="如店长、店员"
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="角色编码",
        db_comment="如 store_manager、staff",
    )
    is_system = models.BooleanField(
        default=False, verbose_name="是否内置", db_comment="内置角色不可删除"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="是否启用",
        db_comment="停用后该角色的用户无法登录",
    )
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles",
        db_table="accounts_role_permission",
        verbose_name="权限码",
    )

    class Meta:
        db_table = "accounts_role"
        db_table_comment = "角色表"
        verbose_name = "角色"
        verbose_name_plural = verbose_name
        ordering = ("code",)

    def __str__(self):
        return f"{self.name} ({self.code})"
