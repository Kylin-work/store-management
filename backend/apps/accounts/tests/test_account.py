"""账号管理接口测试."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.stores.models import Store


class AccountTestBase(APITestCase):
    """账号管理测试基类."""

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

        self.list_url = reverse("account-list")

        self._create_stores()
        self._create_permissions()
        self._create_roles()
        self._create_users()

    def _create_stores(self):
        """创建测试门店."""
        self.store = Store.objects.create(
            code="S001",
            name="测试门店A",
            store_type="direct",
        )
        self.store_inactive = Store.objects.create(
            code="S002",
            name="停用门店B",
            store_type="direct",
            is_active=False,
        )

    def _create_permissions(self):
        """创建账号管理权限."""
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
        self.perm_update = Permission.objects.create(
            code="account:update",
            name="编辑账号",
            module="account",
        )

    def _create_roles(self):
        """创建测试角色."""
        self.admin_role = Role.objects.create(
            code="account_admin",
            name="账号管理员",
        )
        self.admin_role.permissions.set(
            [
                self.perm_list,
                self.perm_create,
                self.perm_update,
            ]
        )

        self.staff_role = Role.objects.create(
            code="staff",
            name="店员",
        )

        self.disabled_role = Role.objects.create(
            code="disabled_role",
            name="停用角色",
            is_active=False,
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
            real_name="账号管理员",
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

    def _create_payload(self, **overrides):
        """生成账号创建请求数据."""
        data = {
            "phone": "13800000010",
            "real_name": "新员工",
            "password": "NewStaff@123456",
            "store_roles": [
                {
                    "store_id": self.store.pk,
                    "role_code": self.staff_role.code,
                }
            ],
        }
        data.update(overrides)
        return data

    def _detail_url(self, employee_code):
        return reverse(
            "account-detail",
            kwargs={"employee_code": employee_code},
        )

    def _status_url(self, employee_code):
        return reverse(
            "account-status",
            kwargs={"employee_code": employee_code},
        )

    def _store_roles_url(self, employee_code):
        return reverse(
            "account-store-roles",
            kwargs={"employee_code": employee_code},
        )

    def assert_success(self, response, expected_status=status.HTTP_200_OK):
        """断言接口请求成功."""
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"接口响应异常：{response.data}",
        )
        self.assertEqual(response.data["code"], 0)
        self.assertIsNotNone(response.data["data"])
        return response.data["data"]

    def assert_failed(self, response, expected_status, expected_code=None):
        """断言接口请求失败."""
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"接口响应异常：{response.data}",
        )
        if expected_code is not None:
            self.assertEqual(response.data["code"], expected_code)


class AccountListTest(AccountTestBase):
    """账号列表测试."""

    def test_superuser_can_list(self):
        self._auth_superuser()

        response = self.client.get(self.list_url)
        data = self.assert_success(response)

        self.assertGreaterEqual(data["total"], 3)

    def test_manager_with_perm_can_list(self):
        self._auth_manager()

        response = self.client.get(self.list_url)
        self.assert_success(response)

    def test_staff_without_perm_cannot_list(self):
        self._auth_staff()

        response = self.client.get(self.list_url)
        self.assert_failed(
            response,
            status.HTTP_403_FORBIDDEN,
            expected_code=10002,
        )

    def test_anonymous_cannot_list(self):
        response = self.client.get(self.list_url)
        self.assert_failed(
            response,
            status.HTTP_401_UNAUTHORIZED,
        )


class AccountCreateTest(AccountTestBase):
    """创建账号测试."""

    def setUp(self):
        super().setUp()
        self._auth_superuser()

    def test_create_success(self):
        response = self.client.post(
            self.list_url,
            self._create_payload(),
            format="json",
        )
        data = self.assert_success(
            response,
            expected_status=status.HTTP_201_CREATED,
        )

        # 工号自动生成,8 位纯数字.
        self.assertEqual(len(data["employee_code"]), 8)
        self.assertTrue(data["employee_code"].isdigit())
        self.assertEqual(data["phone"], "13800000010")

        self.assertEqual(len(data["store_roles"]), 1)
        self.assertEqual(
            data["store_roles"][0]["store_id"],
            self.store.pk,
        )
        self.assertEqual(
            data["store_roles"][0]["role_code"],
            self.staff_role.code,
        )

    def test_employee_code_increments(self):
        """连续创建账号,工号递增."""
        response1 = self.client.post(
            self.list_url,
            self._create_payload(phone="13800000011"),
            format="json",
        )
        data1 = self.assert_success(
            response1,
            expected_status=status.HTTP_201_CREATED,
        )

        response2 = self.client.post(
            self.list_url,
            self._create_payload(phone="13800000012"),
            format="json",
        )
        data2 = self.assert_success(
            response2,
            expected_status=status.HTTP_201_CREATED,
        )

        code1 = int(data1["employee_code"])
        code2 = int(data2["employee_code"])

        self.assertEqual(code2, code1 + 1)

    def test_duplicate_phone(self):
        """手机号重复时创建失败."""
        response = self.client.post(
            self.list_url,
            self._create_payload(phone="13800000001"),
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_empty_store_roles(self):
        """门店角色列表为空时创建失败."""
        response = self.client.post(
            self.list_url,
            self._create_payload(store_roles=[]),
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_inactive_store(self):
        """不能为账号分配停用门店."""
        response = self.client.post(
            self.list_url,
            self._create_payload(
                store_roles=[
                    {
                        "store_id": self.store_inactive.pk,
                        "role_code": self.staff_role.code,
                    }
                ],
            ),
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_inactive_role(self):
        """不能分配停用角色."""
        response = self.client.post(
            self.list_url,
            self._create_payload(
                store_roles=[
                    {
                        "store_id": self.store.pk,
                        "role_code": self.disabled_role.code,
                    }
                ],
            ),
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_duplicate_store_in_roles(self):
        """同一账号不能重复分配同一个门店."""
        response = self.client.post(
            self.list_url,
            self._create_payload(
                store_roles=[
                    {
                        "store_id": self.store.pk,
                        "role_code": self.staff_role.code,
                    },
                    {
                        "store_id": self.store.pk,
                        "role_code": self.admin_role.code,
                    },
                ],
            ),
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_weak_password(self):
        """弱密码不能通过验证."""
        response = self.client.post(
            self.list_url,
            self._create_payload(password="123456"),
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )


class AccountDetailTest(AccountTestBase):
    """账号详情与编辑测试."""

    def setUp(self):
        super().setUp()
        self._auth_superuser()

        self.target = User.objects.create_user(
            employee_code=None,
            password="Target@123456",
            phone="13800000020",
            real_name="目标用户",
        )
        UserStoreRole.objects.create(
            user=self.target,
            store=self.store,
            role=self.staff_role,
        )

        self.url = self._detail_url(self.target.employee_code)

    def test_detail_success(self):
        """查询账号详情."""
        response = self.client.get(self.url)
        data = self.assert_success(response)

        self.assertEqual(
            data["employee_code"],
            self.target.employee_code,
        )

    def test_detail_not_found(self):
        """查询不存在的账号."""
        response = self.client.get(
            self._detail_url("99999999"),
        )
        self.assert_failed(
            response,
            status.HTTP_404_NOT_FOUND,
        )

    def test_manager_cannot_view_other_store_account(self):
        """门店管理员不能查看其他门店员工."""
        other_store = Store.objects.create(
            code="S003",
            name="测试门店C",
            store_type="direct",
        )
        other_user = User.objects.create_user(
            employee_code=None,
            password="Other@123456",
            phone="13800000022",
            real_name="其他门店员工",
        )
        UserStoreRole.objects.create(
            user=other_user,
            store=other_store,
            role=self.staff_role,
        )

        self._auth_manager()
        response = self.client.get(
            self._detail_url(other_user.employee_code),
        )

        self.assert_failed(response, status.HTTP_404_NOT_FOUND)

    def test_manager_cannot_update_other_store_account(self):
        """门店管理员不能修改其他门店员工."""
        other_store = Store.objects.create(
            code="S003",
            name="测试门店C",
            store_type="direct",
        )
        other_user = User.objects.create_user(
            employee_code=None,
            password="Other@123456",
            phone="13800000022",
            real_name="其他门店员工",
        )
        UserStoreRole.objects.create(
            user=other_user,
            store=other_store,
            role=self.staff_role,
        )

        self._auth_manager()
        response = self.client.patch(
            self._detail_url(other_user.employee_code),
            {"phone": "13800000023"},
            format="json",
        )

        self.assert_failed(response, status.HTTP_404_NOT_FOUND)
        other_user.refresh_from_db()
        self.assertEqual(other_user.phone, "13800000022")

    def test_update_phone(self):
        """修改账号手机号."""
        response = self.client.patch(
            self.url,
            {"phone": "13800000021"},
            format="json",
        )
        data = self.assert_success(response)

        self.assertEqual(data["phone"], "13800000021")

    def test_update_duplicate_phone(self):
        """不能修改为其他账号已使用的手机号."""
        response = self.client.patch(
            self.url,
            {"phone": "13800000001"},
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_update_password(self):
        """修改账号密码."""
        new_password = "NewPassword@123456"

        response = self.client.patch(
            self.url,
            {"password": new_password},
            format="json",
        )
        self.assert_success(response)

        self.target.refresh_from_db()
        self.assertTrue(
            self.target.check_password(new_password),
        )


class AccountStatusTest(AccountTestBase):
    """账号状态切换测试."""

    def setUp(self):
        super().setUp()
        self._auth_superuser()

        self.target = User.objects.create_user(
            employee_code=None,
            password="Target@123456",
            phone="13800000030",
            real_name="状态测试",
        )
        UserStoreRole.objects.create(
            user=self.target,
            store=self.store,
            role=self.staff_role,
        )

        self.url = self._status_url(self.target.employee_code)

    def test_disable_account(self):
        """停用账号."""
        response = self.client.patch(
            self.url,
            {"is_active": False},
            format="json",
        )
        data = self.assert_success(response)

        self.assertFalse(data["is_active"])

        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_manager_disable_store_role_only(self):
        """门店管理员停用员工时只影响当前门店任职."""
        other_store = Store.objects.create(
            code="S003",
            name="测试门店C",
            store_type="direct",
        )
        other_role = UserStoreRole.objects.create(
            user=self.target,
            store=other_store,
            role=self.staff_role,
        )

        self._auth_manager()
        response = self.client.patch(
            self.url,
            {"is_active": False},
            format="json",
        )
        data = self.assert_success(response)

        self.assertFalse(data["is_active"])

        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

        current_role = UserStoreRole.objects.get(
            user=self.target,
            store=self.store,
        )
        other_role.refresh_from_db()

        self.assertFalse(current_role.is_active)
        self.assertTrue(other_role.is_active)

    def test_manager_enable_store_role_only(self):
        """门店管理员只能恢复当前门店的任职."""
        current_role = UserStoreRole.objects.get(
            user=self.target,
            store=self.store,
        )
        current_role.is_active = False
        current_role.save(update_fields=["is_active"])

        self._auth_manager()
        response = self.client.patch(
            self.url,
            {"is_active": True},
            format="json",
        )
        data = self.assert_success(response)

        self.assertTrue(data["is_active"])

        current_role.refresh_from_db()
        self.target.refresh_from_db()

        self.assertTrue(current_role.is_active)
        self.assertTrue(self.target.is_active)

    def test_manager_cannot_change_other_store_account(self):
        """门店管理员不能修改其他门店员工的任职状态."""
        other_store = Store.objects.create(
            code="S003",
            name="测试门店C",
            store_type="direct",
        )
        other_user = User.objects.create_user(
            employee_code=None,
            password="Other@123456",
            phone="13800000031",
            real_name="其他门店员工",
        )
        UserStoreRole.objects.create(
            user=other_user,
            store=other_store,
            role=self.staff_role,
        )

        self._auth_manager()
        response = self.client.patch(
            self._status_url(other_user.employee_code),
            {"is_active": False},
            format="json",
        )

        self.assert_failed(response, status.HTTP_404_NOT_FOUND)

        other_user.refresh_from_db()
        self.assertTrue(other_user.is_active)

    def test_invalid_is_active(self):
        """拒绝非布尔类型的状态值."""
        response = self.client.patch(
            self.url,
            {"is_active": "yes"},
            format="json",
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )


class AccountStoreRolesTest(AccountTestBase):
    """账号门店角色调整测试."""

    def setUp(self):
        super().setUp()
        self._auth_superuser()

        self.target = User.objects.create_user(
            employee_code=None,
            password="Target@123456",
            phone="13800000040",
            real_name="角色测试",
        )
        UserStoreRole.objects.create(
            user=self.target,
            store=self.store,
            role=self.staff_role,
        )

        self.store2 = Store.objects.create(
            code="S003",
            name="门店C",
            store_type="direct",
        )

        self.url = self._store_roles_url(
            self.target.employee_code,
        )

    def _replace_store_roles(self, store_roles):
        """提交门店角色全量替换请求."""
        return self.client.put(
            self.url,
            {"store_roles": store_roles},
            format="json",
        )

    def test_replace_store_roles(self):
        """全量替换为两个门店的角色."""
        response = self._replace_store_roles(
            [
                {
                    "store_id": self.store.pk,
                    "role_code": self.admin_role.code,
                },
                {
                    "store_id": self.store2.pk,
                    "role_code": self.staff_role.code,
                },
            ],
        )
        data = self.assert_success(response)

        self.assertEqual(len(data["store_roles"]), 2)

        # 原有关联被替换,最终保留两个新关联.
        self.assertEqual(
            UserStoreRole.objects.filter(user=self.target).count(),
            2,
        )

    def test_replace_store_roles_deactivates_removed_roles(self):
        """超级管理员全局替换时停用未提交的任职记录."""
        removed_role = UserStoreRole.objects.create(
            user=self.target,
            store=self.store2,
            role=self.staff_role,
        )

        response = self._replace_store_roles(
            [
                {
                    "store_id": self.store.pk,
                    "role_code": self.admin_role.code,
                }
            ],
        )
        self.assert_success(response)

        removed_role.refresh_from_db()
        self.assertFalse(removed_role.is_active)

        # 原任职记录保留,没有被物理删除
        self.assertTrue(
            UserStoreRole.objects.filter(
                pk=removed_role.pk,
                user=self.target,
                store=self.store2,
            ).exists()
        )

        current_role = UserStoreRole.objects.get(
            user=self.target,
            store=self.store,
        )
        self.assertEqual(current_role.role, self.admin_role)
        self.assertTrue(current_role.is_active)

    def test_manager_updates_current_store_role_only(self):
        """门店管理员修改当前门店角色时保留其他门店任职."""
        other_role = UserStoreRole.objects.create(
            user=self.target,
            store=self.store2,
            role=self.staff_role,
        )

        self._auth_manager()
        response = self._replace_store_roles(
            [
                {
                    "store_id": self.store.pk,
                    "role_code": self.admin_role.code,
                }
            ],
        )
        self.assert_success(response)

        current_role = UserStoreRole.objects.get(
            user=self.target,
            store=self.store,
        )
        other_role.refresh_from_db()

        self.assertEqual(current_role.role, self.admin_role)
        self.assertTrue(current_role.is_active)
        self.assertEqual(other_role.role, self.staff_role)
        self.assertTrue(other_role.is_active)

    def test_manager_cannot_assign_other_store_role(self):
        """门店管理员不能分配其他门店的角色."""
        self._auth_manager()
        response = self._replace_store_roles(
            [
                {
                    "store_id": self.store2.pk,
                    "role_code": self.staff_role.code,
                }
            ],
        )

        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_manager_cannot_change_other_store_account_roles(self):
        """门店管理员不能调整仅属于其他门店的员工角色."""
        other_user = User.objects.create_user(
            employee_code=None,
            password="Other@123456",
            phone="13800000041",
            real_name="其他门店员工",
        )
        UserStoreRole.objects.create(
            user=other_user,
            store=self.store2,
            role=self.staff_role,
        )

        self._auth_manager()
        response = self.client.put(
            self._store_roles_url(other_user.employee_code),
            {
                "store_roles": [
                    {
                        "store_id": self.store.pk,
                        "role_code": self.admin_role.code,
                    }
                ]
            },
            format="json",
        )

        self.assert_failed(response, status.HTTP_404_NOT_FOUND)

    def test_inactive_store_rejected(self):
        """拒绝分配停用门店."""
        response = self._replace_store_roles(
            [
                {
                    "store_id": self.store_inactive.pk,
                    "role_code": self.staff_role.code,
                }
            ],
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=30001,
        )

    def test_inactive_role_rejected(self):
        """拒绝分配停用角色."""
        response = self._replace_store_roles(
            [
                {
                    "store_id": self.store.pk,
                    "role_code": self.disabled_role.code,
                }
            ],
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_duplicate_store_rejected(self):
        """拒绝重复分配同一个门店."""
        response = self._replace_store_roles(
            [
                {
                    "store_id": self.store.pk,
                    "role_code": self.staff_role.code,
                },
                {
                    "store_id": self.store.pk,
                    "role_code": self.admin_role.code,
                },
            ],
        )
        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

    def test_empty_list_rejected(self):
        """拒绝空门店角色列表."""
        response = self._replace_store_roles([])

        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )
