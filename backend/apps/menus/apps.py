"""menus 应用配置。"""

from django.apps import AppConfig


class MenusConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.menus"
    verbose_name = "菜单管理"
