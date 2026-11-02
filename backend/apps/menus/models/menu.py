"""菜单模型.

菜单树存数据库,data migration 初始化.
每个节点关联一个权限码,登录后按用户权限过滤返回.
"""

from django.db import models


class Menu(models.Model):
    """系统菜单节点"""

    name = models.CharField(
        max_length=50, verbose_name="菜单名称", db_comment="显示名称"
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="菜单编码",
        db_comment="唯一标识,如 member_manage",
    )
    path = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="路由路径",
        db_comment="前端路由,如 /members",
    )
    permission_code = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="权限码",
        db_comment="关联 Permission.code,为空表示不校验权限",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name="父菜单",
    )
    sort = models.IntegerField(
        default=0, verbose_name="排序", db_comment="同级菜单按此升序"
    )
    is_active = models.BooleanField(
        default=True, verbose_name="是否启用", db_comment="停用后不返回"
    )

    class Meta:
        db_table = "menus_menu"
        db_table_comment = "菜单表"
        verbose_name = "菜单"
        verbose_name_plural = verbose_name
        ordering = ("sort", "id")

    def __str__(self):
        return f"{self.code} {self.name}"
