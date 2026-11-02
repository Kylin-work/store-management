"""权限码模型。

权限码由各业务模块在 apps.py 中声明,sync_permissions 命令同步到此表。
管理员只能从已同步的权限码里给角色分配,不能自由创建。
"""

from django.db import models


class Permission(models.Model):
    """系统权限点。每个权限码背后应对应一个真实的接口校验。"""

    code = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="权限码",
        db_comment="格式 模块:动作,如 member:recharge",
    )
    name = models.CharField(
        max_length=50, verbose_name="权限名称", db_comment="权限对应中文名称"
    )
    module = models.CharField(
        max_length=100, verbose_name="所属模块", db_comment="用于分组展示的所属模块名称"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="状态",
        db_comment="是否启用？停用后不再出现在角色授权列表",
    )

    class Meta:
        db_table = "accounts_permission"
        db_table_comment = "权限码表"
        verbose_name = "权限码"
        verbose_name_plural = verbose_name
        ordering = ("module", "code")

    def __str__(self):
        return f"{self.code} ({self.name})"
