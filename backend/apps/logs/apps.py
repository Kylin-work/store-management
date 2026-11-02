"""logs 应用配置。"""

from django.apps import AppConfig


class LogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.logs"
    verbose_name = "操作日志"
