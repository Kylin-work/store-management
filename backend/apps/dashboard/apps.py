"""dashboard 应用配置."""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
    verbose_name = "数据看板"

    def ready(self):
        """应用就绪时注册权限码."""
        from core.permissions import register_permissions

        register_permissions(
            [
                {
                    "code": "dashboard:view",
                    "name": "数据看板",
                    "module": "dashboard",
                },
            ]
        )
