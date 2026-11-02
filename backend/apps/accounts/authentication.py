"""
自定义 JWT 认证类.

在 SimpleJWT 默认认证的基础上：
1. 解析 JWT 中的用户、门店及角色上下文.
2. 验证用户当前是否仍拥有对应门店及角色.
3. 加载当前角色有效的权限码集合.
4. 将认证上下文挂载到 request,供权限类使用.
"""

from django.core.exceptions import MultipleObjectsReturned
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.models import UserStoreRole


class StoreJWTAuthentication(JWTAuthentication):
    """JWT 认证及门店权限上下文加载."""

    def authenticate(self, request):
        """认证 JWT 并加载当前用户权限."""

        # 1. 执行 SimpleJWT 默认认证
        result = super().authenticate(request)

        if result is None:
            return None

        user, validated_token = result

        # 2. 初始化请求上下文
        request.store_id = None
        request.role_code = None
        request.perm_set = None

        # 3. 平台超级管理员不绑定门店角色
        # HasPerm 必须单独判断 is_superuser 并放行
        if user.is_superuser:
            return result

        # 4. 获取 JWT 中的门店及角色信息
        store_id = validated_token.get("store_id")
        role_code = validated_token.get("role_code")

        if (
            not isinstance(store_id, int)
            or isinstance(store_id, bool)
            or store_id <= 0
            or not isinstance(role_code, str)
            or not role_code
        ):
            raise AuthenticationFailed("Token 权限上下文无效")

        # 5. 验证用户、门店及角色关联关系
        try:
            user_store_role = (
                UserStoreRole.objects.select_related("store", "role")
                .prefetch_related("role__permissions")
                .get(
                    user=user,
                    store_id=store_id,
                    store__is_active=True,
                    role__code=role_code,
                    role__is_active=True,
                )
            )
        except UserStoreRole.DoesNotExist:
            raise AuthenticationFailed("用户门店权限已失效,请重新登录")
        except MultipleObjectsReturned:
            # 数据异常：同一用户、门店、角色存在重复关联
            raise AuthenticationFailed("用户权限数据异常,请联系管理员")

        # 6. 加载当前角色有效权限码
        perm_set = {
            permission.code
            for permission in user_store_role.role.permissions.all()
            if permission.is_active
        }

        # 7. 挂载认证上下文
        request.store_id = user_store_role.store_id
        request.role_code = user_store_role.role.code
        request.perm_set = perm_set

        return result
