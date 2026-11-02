"""transactions 应用配置."""

from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.transactions"
    verbose_name = "交易管理"

    def ready(self):
        """应用就绪时注册权限码."""
        from core.permissions import register_permissions

        register_permissions(
            [
                {
                    "code": "transaction:list",
                    "name": "交易列表",
                    "module": "transaction",
                },
                {
                    "code": "transaction:create",
                    "name": "收银",
                    "module": "transaction",
                },
                {
                    "code": "transaction:refund",
                    "name": "退款",
                    "module": "transaction",
                },
            ]
        )
