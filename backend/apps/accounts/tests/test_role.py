"""角色管理接口测试."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.stores.models import Store


class RoleTestBase(APITestCase):
    """角色管理测试基类."""

    ADMIN_PASSWORD = "Admin@123456"
    MANAGER_PASSWORD = "Manager@123456"
    STAFF_PASSWORD = "Staff@123456"

    def setUp(self):
        # 禁用限流,避免测试受到请求频率影响.
        throttle_patcher = patch(
            "rest_framework.throttling.ScopedRateThrottle.get_rate",
            return_value=None,
        )
        throttle_patcher.start()
        self.addCleanup(throttle_patcher.stop)

        self.list_url = reverse("role-list")

        self._create_store()
        self._create_permissions()
        self._create_roles()
        self._create_users()

    def _create_store(self):
        """创建测试门店."""
        self.store = Store.objects.create(
            code="S001",
            name="测试门店A",
            store_type="direct",
        )

    def _create_permissions(self):
        """创建测试权限码."""
        self.perm_account_list = Permission.objects.create(
            code="account:list",
            name="账号列表",
            module="account",
        )
        self.perm_account_create = Permission.objects.create(
            code="account:create",
            name="创建账号",
            module="account",
        )
        self.perm_role_manage = Permission.objects.create(
            code="role:manage",
            name="角色管理",
            module="role",
        )
        self.perm_inactive = Permission.objects.create(
            code="account:update",
            name="编辑账号",
            module="account",
            is_active=False,
        )
        self.perm_role_list = Permission.objects.create(
            code="role:list",
            name="角色列表",
            module="role",
        )

    def _create_roles(self):
        """创建测试角色及权限关系."""
        self.admin_role = Role.objects.create(
            code="role_admin",
            name="角色管理员",
            is_system=False,
        )
        self.admin_role.permissions.set(
            [
                self.perm_role_list,
                self.perm_role_manage,
            ]
        )

        self.system_role = Role.objects.create(
            code="store_manager",
            name="店长",
            is_system=True,
        )
        self.system_role.permissions.set(
            [self.perm_account_list],
        )

        self.staff_role = Role.objects.create(
            code="staff",
            name="店员",
        )

    def _create_users(self):
        """创建测试用户及门店角色关系."""
        self.superuser = User.objects.create_superuser(
            employee_code=None,
            password=self.ADMIN_PASSWORD,
            phone="13900000001",
            real_name="超级管理员",
        )

        self.manager = User.objects.create_user(
            employee_code=None,
            password=self.MANAGER_PASSWORD,
            phone="13800000001",
            real_name="角色管理员",
        )
        UserStoreRole.objects.create(
            user=self.manager,
            store=self.store,
            role=self.admin_role,
        )

        self.staff = User.objects.create_user(
            employee_code=None,
            password=self.STAFF_PASSWORD,
            phone="13800000002",
            real_name="店员",
        )
        UserStoreRole.objects.create(
            user=self.staff,
            store=self.store,
            role=self.staff_role,
        )

    def _make_token(self, user, store_id=None, role_code=None):
        """直接签发 JWT,绕过登录接口."""
        refresh = RefreshToken.for_user(user)
        refresh["store_id"] = store_id
        refresh["role_code"] = role_code
        return str(refresh.access_token)

    def _authenticate(self, user, store_id=None, role_code=None):
        """设置用户认证信息."""
        token = self._make_token(
            user=user,
            store_id=store_id,
            role_code=role_code,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def _auth_superuser(self):
        self._authenticate(self.superuser)

    def _auth_manager(self):
        self._authenticate(
            self.manager,
            store_id=self.store.pk,
            role_code=self.admin_role.code,
        )

    def _auth_staff(self):
        self._authenticate(
            self.staff,
            store_id=self.store.pk,
            role_code=self.staff_role.code,
        )

    def _detail_url(self, code):
        return reverse(
            "role-detail",
            kwargs={"code": code},
        )

    def _permission_list_url(self):
        return reverse("permission-list")

    def assert_success(
        self,
        response,
        expected_status=status.HTTP_200_OK,
    ):
        """断言接口请求成功."""
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"接口响应异常：{response.data}",
        )
        self.assertEqual(response.data["code"], 0)
        self.assertIsNotNone(response.data["data"])
        return response.data["data"]

    def assert_failed(
        self,
        response,
        expected_status,
        expected_code=None,
    ):
        """断言接口请求失败."""
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"接口响应异常：{response.data}",
        )
        if expected_code is not None:
            self.assertEqual(
                response.data["code"],
                expected_code,
            )


class RoleListTest(RoleTestBase):
    """角色列表测试."""

    def test_superuser_can_list(self):
        """超级管理员可以查看角色列表."""
        self._auth_superuser()

        response = self.client.get(self.list_url)
        data = self.assert_success(response)

        self.assertGreaterEqual(data["total"], 3)

    def test_manager_with_perm_can_list(self):
        """拥有角色列表权限的用户可以查看列表."""
        self._auth_manager()

        response = self.client.get(self.list_url)
        self.assert_success(response)

    def test_staff_without_perm_cannot_list(self):
        """没有角色列表权限的用户不能查看列表."""
        self._auth_staff()

        response = self.client.get(self.list_url)
        self.assert_failed(
            response,
            status.HTTP_403_FORBIDDEN,
            expected_code=10002,
        )

    def test_anonymous_cannot_list(self):
        """匿名用户不能查看角色列表."""
        response = self.client.get(self.list_url)

        self.assert_failed(
            response,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_list_contains_user_count(self):
        """列表返回 user_count,按用户去重."""
        self._auth_superuser()

        response = self.client.get(self.list_url)
        data = self.assert_success(response)

        roles_by_code = {item["code"]: item for item in data["items"]}

        self.assertEqual(
            roles_by_code["role_admin"]["user_count"],
            1,
        )
        self.assertEqual(
            roles_by_code["staff"]["user_count"],
            1,
        )
        self.assertEqual(
            roles_by_code["store_manager"]["user_count"],
            0,
        )

    def test_list_contains_permissions(self):
        """列表返回角色的权限码详情."""
        self._auth_superuser()

        response = self.client.get(self.list_url)
        data = self.assert_success(response)

        roles_by_code = {item["code"]: item for item in data["items"]}

        admin_codes = {
            permission["code"]
            for permission in roles_by_code["role_admin"]["permissions"]
        }

        self.assertEqual(
            admin_codes,
            {"role:list", "role:manage"},
        )


class RoleCreateTest(RoleTestBase):
    """创建角色测试."""

    def setUp(self):
        super().setUp()
        self._auth_superuser()

    def _create_role(self, **overrides):
        """提交角色创建请求."""
        data = {
            "code": "warehouse",
            "name": "仓管",
            "permission_codes": ["account:list"],
        }
        data.update(overrides)

        return self.client.post(
            self.list_url,
            data,
            format="json",
        )

    def test_create_success(self):
        """成功创建角色并分配权限."""
        response = self._create_role()
        data = self.assert_success(
            response,
            expected_status=status.HTTP_201_CREATED,
        )

        self.assertEqual(data["code"], "warehouse")
        self.assertEqual(data["name"], "仓管")
        self.assertFalse(data["is_system"])

        self.assertEqual(
            {permission["code"] for permission in data["permissions"]},
            {"account:list"},
        )

    def test_create_empty_permissions(self):
        """创建角色时允许权限码为空."""
        response = self._create_role(
            code="empty_role",
            name="空权限角色",
            permission_codes=[],
        )
        data = self.assert_success(
            response,
            expected_status=status.HTTP_201_CREATED,
        )

        self.assertEqual(data["permissions"], [])

    def test_create_code_uppercase_to_lower(self):
        """角色编码自动转换为小写."""
        response = self._create_role(
            code="WAREHOUSE",
            permission_codes=[],
        )
        data = self.assert_success(
            response,
            expected_status=status.HTTP_201_CREATED,
        )

        self.assertEqual(data["code"], "warehouse")

    def test_create_duplicate_code(self):
        """角色编码重复时创建失败."""
        response = self._create_role(
            code="staff",
            name="重复编码",
            permission_codes=[],
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_create_duplicate_name(self):
        """角色名称重复时创建失败."""
        response = self._create_role(
            code="new_staff",
            name="店员",
            permission_codes=[],
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_create_nonexistent_permission(self):
        """不能分配不存在的权限码."""
        response = self._create_role(
            code="bad_role",
            name="非法权限",
            permission_codes=["nonexistent:perm"],
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_create_inactive_permission(self):
        """不能分配停用的权限码."""
        response = self._create_role(
            code="inactive_perm_role",
            name="停用权限角色",
            permission_codes=["account:update"],
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )


class RoleDetailTest(RoleTestBase):
    """角色详情与编辑测试."""

    def setUp(self):
        super().setUp()
        self._auth_superuser()

    def test_detail_success(self):
        """查询角色详情."""
        response = self.client.get(
            self._detail_url("role_admin"),
        )
        data = self.assert_success(response)

        self.assertEqual(data["code"], "role_admin")
        self.assertEqual(data["user_count"], 1)

    def test_detail_not_found(self):
        """查询不存在的角色."""
        response = self.client.get(
            self._detail_url("nonexistent"),
        )
        self.assert_failed(
            response,
            status.HTTP_404_NOT_FOUND,
        )

    def test_update_name(self):
        """修改角色名称."""
        response = self.client.patch(
            self._detail_url("staff"),
            {"name": "新店员名"},
            format="json",
        )
        data = self.assert_success(response)

        self.assertEqual(data["name"], "新店员名")

    def test_update_duplicate_name(self):
        """角色名称保持不变时不应报重复."""
        response = self.client.patch(
            self._detail_url("staff"),
            {"name": "店员"},
            format="json",
        )
        self.assert_success(response)

    def test_update_name_conflict(self):
        """不能修改为其他角色已使用的名称."""
        response = self.client.patch(
            self._detail_url("staff"),
            {"name": "店长"},
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_replace_permissions(self):
        """全量替换角色权限."""
        response = self.client.patch(
            self._detail_url("staff"),
            {
                "permission_codes": [
                    "account:list",
                    "account:create",
                ],
            },
            format="json",
        )
        data = self.assert_success(response)

        self.assertEqual(
            {permission["code"] for permission in data["permissions"]},
            {"account:list", "account:create"},
        )

    def test_clear_permissions(self):
        """允许清空角色权限."""
        response = self.client.patch(
            self._detail_url("role_admin"),
            {"permission_codes": []},
            format="json",
        )
        data = self.assert_success(response)

        self.assertEqual(data["permissions"], [])

    def test_system_role_can_update(self):
        """系统角色允许修改名称和权限码."""
        response = self.client.patch(
            self._detail_url("store_manager"),
            {
                "name": "店长改名",
                "permission_codes": ["account:create"],
            },
            format="json",
        )
        data = self.assert_success(response)

        self.assertEqual(data["name"], "店长改名")
        self.assertTrue(data["is_system"])
        self.assertEqual(
            {permission["code"] for permission in data["permissions"]},
            {"account:create"},
        )

    def test_disable_role(self):
        """停用角色."""
        response = self.client.patch(
            self._detail_url("staff"),
            {"is_active": False},
            format="json",
        )
        data = self.assert_success(response)

        self.assertFalse(data["is_active"])


class PermissionListTest(RoleTestBase):
    """权限码列表测试."""

    def setUp(self):
        super().setUp()
        self.url = self._permission_list_url()

    def test_superuser_can_list(self):
        """超级管理员可以查看权限码列表."""
        self._auth_superuser()

        response = self.client.get(self.url)
        data = self.assert_success(response)

        modules = {group["module"] for group in data}
        self.assertIn("account", modules)
        self.assertIn("role", modules)

    def test_inactive_permission_excluded(self):
        """停用的权限码不出现在列表."""
        self._auth_superuser()

        response = self.client.get(self.url)
        data = self.assert_success(response)

        all_codes = {
            permission["code"] for group in data for permission in group["permissions"]
        }

        self.assertNotIn("account:update", all_codes)

    def test_staff_without_perm_cannot_list(self):
        """没有权限的用户不能查看权限码列表."""
        self._auth_staff()

        response = self.client.get(self.url)
        self.assert_failed(
            response,
            status.HTTP_403_FORBIDDEN,
            expected_code=10002,
        )
