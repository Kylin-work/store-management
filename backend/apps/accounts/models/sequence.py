"""工号序列模型。

只服务员工工号,表里固定一行(name='employee_code').
创建用户时在事务内锁定该行、加一、格式化为 8 位纯数字.
"""

from django.db import models


class Sequence(models.Model):
    """全局序列，用于生成连续、无空洞的业务编号。"""

    name = models.CharField(
        max_length=50, unique=True, verbose_name="序列名", db_comment="序列名"
    )
    current_value = models.PositiveIntegerField(
        default=0, verbose_name="当前值", db_comment="当前值"
    )

    class Meta:
        db_table = "accounts_sequence"
        verbose_name = "序列"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name}={self.current_value}"
