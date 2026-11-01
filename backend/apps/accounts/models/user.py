"""自定义用户模型。

- 去掉 username,用 employee_code(8 位纯数字,自动生成)登录
- phone 作为联系方式，唯一但不参与认证
- first_name / last_name 保留但不暴露给前端
- 所有用户由后台管理员创建，不开放注册
"""

from typing import ClassVar

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models, transaction
from django.db.models import F

from apps.accounts.models.sequence import Sequence


class CustomUserManager(UserManager):
    """自定义管理器：去掉 username 依赖，适配 employee_code 为登录字段。"""

    def create_user(self, employee_code=None, password=None, **extra_fields):
        """employee_code 为 None 时由 save() 自动生成。"""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(employee_code=employee_code, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, employee_code=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("超级用户必须 is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("超级用户必须 is_superuser=True")
        return self.create_user(employee_code, password, **extra_fields)


class User(AbstractUser):
    """系统用户:登录凭证为工号,平台管理员用 is_superuser 区分。"""

    username = None
    employee_code = models.CharField(
        max_length=8, unique=True, blank=True, verbose_name="工号", db_comment="工号"
    )
    phone = models.CharField(
        max_length=11, unique=True, verbose_name="手机号", db_comment="手机号"
    )
    real_name = models.CharField(max_length=50, verbose_name="姓名", db_comment="姓名")

    USERNAME_FIELD = "employee_code"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["phone", "real_name"]

    objects = CustomUserManager()

    class Meta:
        db_table = "accounts_user"
        db_table_comment = "用户表"
        verbose_name = "用户"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.employee_code} {self.real_name}"

    def save(self, *args, **kwargs):
        """创建时自动生成工号。

        序列行由 data migration 预置，此处直接锁定、加一、格式化为 8 位。
        与 User 创建同一事务，任一环节失败整体回滚。
        """
        if not self.employee_code:
            with transaction.atomic():
                # 锁定序列行，防止并发拿到相同工号
                seq = Sequence.objects.select_for_update().get(name="employee_code")
                Sequence.objects.filter(pk=seq.pk).update(
                    current_value=F("current_value") + 1
                )
                seq.refresh_from_db()
                self.employee_code = f"{seq.current_value:08d}"
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)
