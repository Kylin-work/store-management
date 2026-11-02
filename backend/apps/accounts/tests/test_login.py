"""登录接口测试."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import Role, User, UserStoreRole
from apps.stores.models import Store


class LoginTestBase(APITestCase):
    """登录测试基类."""

    def setUp(self):
        # 测试期间禁用登录限流
        throttle_patcher = patch(
            "rest_framework.throttling.ScopedRateThrottle.get_rate",
            return_value=None,
        )
        throttle_patcher.start()
        self.addCleanup(throttle_patcher.stop)

        # 门店
        self.store = Store.objects.create(
            code="S001",
            name="测试门店A",
            store_type="direct",
        )

        # 角色
        self.role = Role.objects.create(
            code="store_manager",
            name="店长",
        )

        # 有门店角色的普通用户
        self.user = User.objects.create_user(
            employee_code=None,
            password="Test@123456",
            phone="13800000001",
            real_name="张三",
        )

        UserStoreRole.objects.create(
            user=self.user,
            store=self.store,
            role=self.role,
        )

        # 无门店角色的用户
        self.user_no_store = User.objects.create_user(
            employee_code=None,
            password="Test@123456",
            phone="13800000002",
            real_name="李四",
        )

        # 停用用户
        self.disabled_user = User.objects.create_user(
            employee_code=None,
            password="Test@123456",
            phone="13800000003",
            real_name="王五",
        )

        self.disabled_user.is_active = False
        self.disabled_user.save(update_fields=["is_active"])

        UserStoreRole.objects.create(
            user=self.disabled_user,
            store=self.store,
            role=self.role,
        )

        # 超级管理员
        self.admin = User.objects.create_superuser(
            employee_code=None,
            password="Admin@123456",
            phone="13900000001",
            real_name="超级管理员",
        )

    def _login(self, employee_code, password, store_id=None):
        """调用登录接口."""
        data = {
            "employee_code": employee_code,
            "password": password,
        }

        if store_id is not None:
            data["store_id"] = store_id

        return self.client.post(
            reverse("auth-login"),
            data,
            format="json",
        )

    def assert_login_success(self, response):
        """统一验证登录成功响应."""
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            msg=f"登录失败：{response.data}",
        )

        self.assertEqual(response.data["code"], 0)

        data = response.data["data"]

        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertIn("user", data)

        self.assertTrue(data["access"])
        self.assertTrue(data["refresh"])

        return data

    def assert_login_failed(self, response, expected_code, data_is_none=True):
        """统一验证登录失败响应.

        data_is_none=False 用于入参校验失败场景,此时 data 是字段级错误字典.
        """
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            msg=f"响应状态不符合预期：{response.data}",
        )

        self.assertEqual(
            response.data["code"],
            expected_code,
        )

        if data_is_none:
            self.assertIsNone(response.data["data"])

    def assert_token_context(
        self,
        access_token,
        refresh_token,
        store_id,
        role_code,
    ):
        """验证 Access Token 和 Refresh Token 中的门店上下文."""
        access = AccessToken(access_token)
        refresh = RefreshToken(refresh_token)

        for token in (access, refresh):
            self.assertEqual(token["store_id"], store_id)
            self.assertEqual(token["role_code"], role_code)


class LoginSuccessTest(LoginTestBase):
    """登录成功场景."""

    def test_login_with_store(self):
        """普通用户选门店登录成功,Token 带 store_id 和 role_code."""
        response = self._login(
            self.user.employee_code,
            "Test@123456",
            self.store.pk,
        )

        data = self.assert_login_success(response)

        # 验证用户信息
        self.assertEqual(
            data["user"]["employee_code"],
            self.user.employee_code,
        )
        self.assertEqual(
            data["user"]["store_id"],
            self.store.pk,
        )
        self.assertEqual(
            data["user"]["role_code"],
            self.role.code,
        )

        # 验证 JWT
        self.assert_token_context(
            access_token=data["access"],
            refresh_token=data["refresh"],
            store_id=self.store.pk,
            role_code=self.role.code,
        )

    def test_superuser_login_without_store(self):
        """超级管理员不选门店也能登录."""
        response = self._login(
            self.admin.employee_code,
            "Admin@123456",
        )

        data = self.assert_login_success(response)

        self.assertIsNone(data["user"]["store_id"])
        self.assertIsNone(data["user"]["role_code"])
        self.assertTrue(data["user"]["is_superuser"])

        self.assert_token_context(
            access_token=data["access"],
            refresh_token=data["refresh"],
            store_id=None,
            role_code=None,
        )

    def test_superuser_login_with_store_ignored(self):
        """超级管理员传入 store_id 也会被忽略."""
        response = self._login(
            self.admin.employee_code,
            "Admin@123456",
            self.store.pk,
        )

        data = self.assert_login_success(response)

        self.assertIsNone(data["user"]["store_id"])
        self.assertIsNone(data["user"]["role_code"])
        self.assertTrue(data["user"]["is_superuser"])

        self.assert_token_context(
            access_token=data["access"],
            refresh_token=data["refresh"],
            store_id=None,
            role_code=None,
        )


class LoginFailTest(LoginTestBase):
    """登录失败场景."""

    def test_wrong_password(self):
        """密码错误返回 20001."""
        response = self._login(
            self.user.employee_code,
            "WrongPassword",
            self.store.pk,
        )

        self.assert_login_failed(response, 20001)

    def test_employee_code_not_exist(self):
        """工号不存在返回 20001,防止用户枚举."""
        response = self._login(
            "99999999",
            "Test@123456",
            self.store.pk,
        )

        self.assert_login_failed(response, 20001)

    def test_store_not_assigned(self):
        """用户没有所选门店角色返回 20003."""
        response = self._login(
            self.user_no_store.employee_code,
            "Test@123456",
            self.store.pk,
        )

        self.assert_login_failed(response, 20003)

    def test_store_id_missing_for_normal_user(self):
        """普通用户不传 store_id 返回 20003."""
        response = self._login(
            self.user.employee_code,
            "Test@123456",
        )

        self.assert_login_failed(response, 20003)

    def test_disabled_user(self):
        """停用用户登录返回 20001,防止账号状态泄露."""
        response = self._login(
            self.disabled_user.employee_code,
            "Test@123456",
            self.store.pk,
        )

        self.assert_login_failed(response, 20001)

    def test_inactive_store(self):
        """门店停用后不能登录,返回 20003."""
        self.store.is_active = False
        self.store.save(update_fields=["is_active"])

        response = self._login(
            self.user.employee_code,
            "Test@123456",
            self.store.pk,
        )

        self.assert_login_failed(response, 20003)


    def test_inactive_store_role(self):
        """停用门店任职后不能登录该门店."""
        store_role = UserStoreRole.objects.get(
            user=self.user,
            store=self.store,
        )
        store_role.is_active = False
        store_role.save(update_fields=["is_active"])

        response = self._login(
            self.user.employee_code,
            "Test@123456",
            self.store.pk,
        )

        self.assert_login_failed(response, 20003)

    def test_inactive_store_role_invalidates_existing_token(self):
        """停用门店任职后旧 JWT 也不能继续使用."""
        refresh = RefreshToken.for_user(self.user)
        refresh["store_id"] = self.store.pk
        refresh["role_code"] = self.role.code
        access_token = str(refresh.access_token)

        store_role = UserStoreRole.objects.get(
            user=self.user,
            store=self.store,
        )
        store_role.is_active = False
        store_role.save(update_fields=["is_active"])

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LoginValidationTest(LoginTestBase):
    """登录入参校验测试."""

    def test_missing_employee_code(self):
        """缺少工号返回 10001."""
        response = self.client.post(
            reverse("auth-login"),
            {
                "password": "Test@123456",
                "store_id": self.store.pk,
            },
            format="json",
        )

        self.assert_login_failed(response, 10001, data_is_none=False)

    def test_missing_password(self):
        """缺少密码返回 10001."""
        response = self.client.post(
            reverse("auth-login"),
            {
                "employee_code": self.user.employee_code,
                "store_id": self.store.pk,
            },
            format="json",
        )

        self.assert_login_failed(response, 10001, data_is_none=False)

    def test_employee_code_too_long(self):
        """工号超过 8 位返回 10001."""
        response = self.client.post(
            reverse("auth-login"),
            {
                "employee_code": "123456789",
                "password": "Test@123456",
                "store_id": self.store.pk,
            },
            format="json",
        )

        self.assert_login_failed(response, 10001, data_is_none=False)

    def test_store_id_zero(self):
        """store_id 为 0 返回 10001."""
        response = self.client.post(
            reverse("auth-login"),
            {
                "employee_code": self.user.employee_code,
                "password": "Test@123456",
                "store_id": 0,
            },
            format="json",
        )

        self.assert_login_failed(response, 10001, data_is_none=False)
