"""操作日志模型.

审计日志,记录敏感业务操作.模型层禁止 update/delete,保证不可篡改.
"""

from django.conf import settings
from django.db import models


class OperationLog(models.Model):
    """操作日志."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="operation_logs",
        verbose_name="操作人",
        db_comment="操作人,离职后仍保留",
    )
    store = models.ForeignKey(
        "stores.Store",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operation_logs",
        verbose_name="门店",
        db_comment="操作发生的门店,平台管理员操作时为空",
    )
    module = models.CharField(
        max_length=50, verbose_name="模块", db_comment="如 account、role、store"
    )
    action = models.CharField(
        max_length=50, verbose_name="动作", db_comment="如 create、update、disable"
    )
    target_type = models.CharField(
        max_length=50, verbose_name="对象类型", db_comment="如 User、Role、Store"
    )
    target_id = models.CharField(
        max_length=50, verbose_name="对象标识", db_comment="对象的业务标识或主键"
    )
    detail = models.JSONField(
        default=dict, blank=True, verbose_name="详情", db_comment="业务语义变更详情"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="操作时间", db_index=True
    )

    class Meta:
        db_table = "logs_operation_log"
        db_table_comment = "操作日志表"
        verbose_name = "操作日志"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)
        default_permissions = ("add", "view")

    def __str__(self):
        return f"{self.user_id} {self.module}:{self.action} {self.target_type}#{self.target_id}"

    def save(self, *args, **kwargs):
        """禁止更新已有日志,只允许创建."""
        if self.pk is not None:
            raise ValueError("操作日志不可修改")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """禁止删除日志."""
        raise ValueError("操作日志不可删除")
