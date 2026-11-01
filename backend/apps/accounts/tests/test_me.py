"""me 接口测试。"""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.stores.models import Store


class MeTestBase(APITestCase):
    """me 接口测试基类。"""

    password = "Test@123456"
    admin_password = "Admin@123456"

    def setUp(self):
        # 禁用 ScopedRateThrottle，避免限流影响测试。
        throttle_patcher = patch(
            "rest_framework.throttling.ScopedRateThrottle.get_rate",
            return_value=None,
        )
        throttle_patcher.start()
        self.addCleanup(throttle_patcher.stop)

        self.me_url = reverse("auth-me")

        self.store = Store.objects.create(
            code="S001",
            name="测试门店A",
            store_type="direct",
        )

        self.perm_list = Permission.objects.create(
            code="account:list",
            name="账号列表",
            module="account",
        )
        self.perm_create = Permission.objects.create(
            code="account:create",
            name="创建账号",
            module="account",
        )
        self.perm_inactive = Permission.objects.create(
            code="account:update",
            name="编辑账号",
            module="account",
            is_active=False,
        )

        self.role = Role.objects.create(
            code="store_manager",
            name="店长",
        )
        self.role.permissions.set(
            [
                self.perm_list,
                self.perm_create,
                self.perm_inactive,
            ]
        )

        self.user = User.objects.create_user(
            employee_code=None,
            password=self.password,
            phone="13800000001",
            real_name="张三",
        )
        self.user_store_role = UserStoreRole.objects.create(
            user=self.user,
            store=self.store,
            role=self.role,
        )

        self.admin = User.objects.create_superuser(
            employee_code=None,
            password=self.admin_password,
            phone="13900000001",
            real_name="超级管理员",
        )

    def _make_token(self, user, store_id=None, role_code=None):
        """直接签发访问令牌，绕过登录接口。"""
        refresh = RefreshToken.for_user(user)
        refresh["store_id"] = store_id
        refresh["role_code"] = role_code

        return str(refresh.access_token)

    def _authenticate(self, token):
        """设置 Bearer 认证头。"""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def _normal_token(self):
        """生成普通用户访问令牌。"""
        return self._make_token(
            user=self.user,
            store_id=self.store.pk,
            role_code=self.role.code,
        )

    def _admin_token(self):
        """生成超级管理员访问令牌。"""
        return self._make_token(user=self.admin)

    def _get_me(self):
        return self.client.get(self.me_url)

    def assert_success(self, response):
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            msg=f"接口响应异常：{response.data}",
        )
        self.assertEqual(response.data["code"], 0)
        self.assertIsNotNone(response.data["data"])
        return response.data["data"]

    def assert_unauthorized(self, response):
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            msg=f"预期返回 401，实际响应：{response.data}",
        )


class MeSuccessTest(MeTestBase):
    """me 接口成功场景。"""

    def test_normal_user_me(self):
        """普通用户返回用户信息、门店上下文和有效权限码。"""
        self._authenticate(self._normal_token())

        response = self._get_me()
        data = self.assert_success(response)

        self.assertEqual(
            data["user"]["employee_code"],
            self.user.employee_code,
        )
        self.assertEqual(data["user"]["real_name"], "张三")
        self.assertFalse(data["user"]["is_superuser"])

        self.assertEqual(data["context"]["store_id"], self.store.pk)
        self.assertEqual(data["context"]["role_code"], self.role.code)

        # 仅返回启用的权限码，并保持稳定排序。
        self.assertEqual(
            data["permissions"],
            ["account:create", "account:list"],
        )
        self.assertNotIn(
            self.perm_inactive.code,
            data["permissions"],
        )

    def test_superuser_me(self):
        """超级管理员的 permissions 为 None，表示拥有全部权限。"""
        self._authenticate(self._admin_token())

        response = self._get_me()
        data = self.assert_success(response)

        self.assertTrue(data["user"]["is_superuser"])
        self.assertIsNone(data["context"]["store_id"])
        self.assertIsNone(data["context"]["role_code"])
        self.assertIsNone(data["permissions"])


class MeFailTest(MeTestBase):
    """me 接口失败场景。"""

    def test_anonymous_cannot_access(self):
        """未认证用户不能访问。"""
        response = self._get_me()
        self.assert_unauthorized(response)

    def test_invalid_token(self):
        """无效 JWT 不能访问。"""
        self._authenticate("invalid.token.here")

        response = self._get_me()
        self.assert_unauthorized(response)

    def test_store_role_removed(self):
        """用户门店角色关系被删除后，旧 token 失效。"""
        token = self._normal_token()
        self.user_store_role.delete()

        self._authenticate(token)
        response = self._get_me()

        self.assert_unauthorized(response)

    def test_store_disabled(self):
        """门店停用后，旧 token 失效。"""
        token = self._normal_token()

        self.store.is_active = False
        self.store.save(update_fields=["is_active"])

        self._authenticate(token)
        response = self._get_me()

        self.assert_unauthorized(response)

    def test_role_disabled(self):
        """角色停用后，旧 token 失效。"""
        token = self._normal_token()

        self.role.is_active = False
        self.role.save(update_fields=["is_active"])

        self._authenticate(token)
        response = self._get_me()

        self.assert_unauthorized(response)

    def test_user_disabled(self):
        """用户停用后，旧 token 失效。"""
        token = self._normal_token()

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self._authenticate(token)
        response = self._get_me()

        self.assert_unauthorized(response)
