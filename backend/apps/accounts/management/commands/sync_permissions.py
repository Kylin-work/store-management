"""同步权限码到数据库。

遍历 core.permissions.PERMISSION_REGISTRY(各业务模块在 apps.py 中注册),
把权限码同步到 accounts.Permission 表：
- 不存在则创建
- 已存在则更新名称和模块
不删除数据库中已存在但注册表里没有的权限码,避免误删被角色引用的记录。
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Permission
from core.permissions import PERMISSION_REGISTRY


class Command(BaseCommand):
    help = "同步权限码注册表到数据库"

    def handle(self, *args, **options):
        created = 0
        updated = 0

        with transaction.atomic():
            for code, item in PERMISSION_REGISTRY.items():
                _, is_created = Permission.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": item["name"],
                        "module": item["module"],
                        "is_active": True,
                    },
                )
                if is_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"权限码同步完成：新增 {created} 条,更新 {updated} 条,"
                f"注册表共 {len(PERMISSION_REGISTRY)} 条"
            )
        )
