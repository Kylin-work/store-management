"""members 应用配置."""

from django.apps import AppConfig


class MembersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.members"
    verbose_name = "会员管理"

    def ready(self):
        """应用就绪时注册权限码."""
        from core.permissions import register_permissions

        register_permissions(
            [
                {"code": "member:list", "name": "会员列表", "module": "member"},
                {"code": "member:create", "name": "创建会员", "module": "member"},
                {"code": "member:update", "name": "编辑会员", "module": "member"},
                {"code": "member:recharge", "name": "会员充值", "module": "member"},
                {
                    "code": "member:change_level",
                    "name": "会员等级调整",
                    "module": "member",
                },
            ]
        )
