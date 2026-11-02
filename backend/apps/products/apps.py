"""products 应用配置."""

from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products"
    verbose_name = "商品管理"

    def ready(self):
        """应用就绪时注册权限码."""
        from core.permissions import register_permissions

        register_permissions(
            [
                {"code": "product:list", "name": "商品列表", "module": "product"},
                {"code": "product:create", "name": "创建商品", "module": "product"},
                {"code": "product:update", "name": "编辑商品", "module": "product"},
                {"code": "product:delete", "name": "删除商品", "module": "product"},
                {
                    "code": "product:edit_cost",
                    "name": "查看/修改成本价",
                    "module": "product",
                },
            ]
        )
