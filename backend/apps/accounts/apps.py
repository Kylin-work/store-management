from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "账号与权限"

    def ready(self):
        """应用就绪时注册权限码"""
        from core.permissions import register_permissions

        register_permissions(
            [
                {"code": "account:list", "name": "账号列表", "module": "account"},
                {"code": "account:create", "name": "创建账号", "module": "account"},
                {"code": "account:update", "name": "编辑账号", "module": "account"},
                {"code": "role:list", "name": "角色列表", "module": "role"},
                {"code": "role:manage", "name": "角色管理", "module": "role"},
                {
                    "code": "permission:list",
                    "name": "权限码列表",
                    "module": "permission",
                },
            ]
        )
