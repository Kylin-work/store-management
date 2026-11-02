"""初始化菜单数据.

一级菜单按模块划分,permission_code 对应各模块的列表权限.
后续业务模块开发时,通过新的 data migration 追加二级节点.
"""

from django.db import migrations

MENUS = [
    {
        "code": "member_manage",
        "name": "会员管理",
        "path": "/members",
        "permission_code": "member:list",
        "sort": 10,
    },
    {
        "code": "product_manage",
        "name": "商品管理",
        "path": "/products",
        "permission_code": "product:list",
        "sort": 20,
    },
    {
        "code": "transaction_manage",
        "name": "交易管理",
        "path": "/transactions",
        "permission_code": "transaction:list",
        "sort": 30,
    },
    {
        "code": "dashboard_view",
        "name": "数据看板",
        "path": "/dashboard",
        "permission_code": "dashboard:view",
        "sort": 40,
    },
    {
        "code": "account_manage",
        "name": "账号管理",
        "path": "/accounts",
        "permission_code": "account:list",
        "sort": 90,
    },
    {
        "code": "role_manage",
        "name": "角色管理",
        "path": "/roles",
        "permission_code": "role:list",
        "sort": 100,
    },
]


def seed_menus(apps, schema_editor):
    """创建一级菜单,已存在则跳过."""
    Menu = apps.get_model("menus", "Menu")
    for item in MENUS:
        Menu.objects.get_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "path": item["path"],
                "permission_code": item["permission_code"],
                "sort": item["sort"],
                "parent": None,
                "is_active": True,
            },
        )


def remove_menus(apps, schema_editor):
    """回滚时删除本迁移创建的菜单."""
    Menu = apps.get_model("menus", "Menu")
    Menu.objects.filter(code__in=[m["code"] for m in MENUS]).delete()


class Migration(migrations.Migration):
    dependencies = (("menus", "0001_initial"),)

    operations = (migrations.RunPython(seed_menus, remove_menus),)
