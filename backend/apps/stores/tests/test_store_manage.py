"""门店管理端接口测试."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role, User, UserStoreRole
from apps.stores.models import Store


class StoreManageTestBase(APITestCase):
    """门店管理测试基类."""

    def setUp(self):
        # 门店
        self.store = Store.objects.create(
            code="S001",
            name="测试门店A",
            store_type="direct",
        )

        # 店员角色
        self.staff_role = Role.objects.create(
            code="staff",
            name="店员",
        )

        # 平台管理员
        self.admin = User.objects.create_superuser(
            employee_code="ADMIN001",
            password="Admin@123456",
            phone="13900000001",
            real_name="超级管理员",
        )

        # 普通用户
        self.normal_user = User.objects.create_user(
            employee_code="EMP001",
            password="Test@123456",
            phone="13800000001",
            real_name="普通用户",
        )

        # 分配门店角色
        UserStoreRole.objects.create(
            user=self.normal_user,
            store=self.store,
            role=self.staff_role,
        )

    def _generate_token(self, user, store_id=None, role_code=None):
        """直接生成测试 JWT."""
        refresh = RefreshToken.for_user(user)

        if store_id is not None:
            refresh["store_id"] = store_id

        if role_code is not None:
            refresh["role_code"] = role_code

        return str(refresh.access_token)

    def _admin_token(self):
        """获取平台管理员 Token."""
        return self._generate_token(self.admin)

    def _normal_token(self):
        """获取普通用户 Token."""
        return self._generate_token(
            user=self.normal_user,
            store_id=self.store.pk,
            role_code=self.staff_role.code,
        )

    def _authenticate_admin(self):
        """使用平台管理员身份访问接口."""
        token = self._admin_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _authenticate_normal_user(self):
        """使用普通用户身份访问接口."""
        token = self._normal_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class StoreManagePermissionTest(StoreManageTestBase):
    """门店管理端权限测试."""

    def test_anonymous_cannot_access(self):
        """未登录访问管理端返回 401."""
        response = self.client.get(reverse("store-manage-list"))

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_normal_user_cannot_access(self):
        """普通用户访问管理端返回 403."""
        self._authenticate_normal_user()

        response = self.client.get(reverse("store-manage-list"))

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(response.data["code"], 10002)


class StoreManageCrudTest(StoreManageTestBase):
    """门店管理端 CRUD 测试."""

    def setUp(self):
        super().setUp()
        self._authenticate_admin()

    def test_list_stores(self):
        """管理员能列出全部门店."""
        response = self.client.get(reverse("store-manage-list"))

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["data"]["total"],
            1,
        )
        self.assertEqual(
            response.data["data"]["items"][0]["code"],
            "S001",
        )

    def test_create_store_code_uppercase(self):
        """创建门店时 code 自动转大写."""
        response = self.client.post(
            reverse("store-manage-list"),
            {
                "code": "s002",
                "name": "测试门店B",
                "store_type": "franchise",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            msg=f"创建失败：{response.data}",
        )
        self.assertEqual(
            response.data["data"]["code"],
            "S002",
        )

        self.assertTrue(Store.objects.filter(code="S002").exists())

    def test_create_store_duplicate_code(self):
        """重复 code 被拦截."""
        response = self.client.post(
            reverse("store-manage-list"),
            {
                "code": "S001",
                "name": "重复编码店",
                "store_type": "franchise",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(response.data["code"], 10001)

    def test_create_store_duplicate_name(self):
        """重复门店名称被拦截."""
        response = self.client.post(
            reverse("store-manage-list"),
            {
                "code": "S002",
                "name": "测试门店A",
                "store_type": "franchise",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(response.data["code"], 10001)

    def test_update_store(self):
        """编辑门店名称."""
        url = reverse(
            "store-manage-detail",
            kwargs={"pk": self.store.pk},
        )

        response = self.client.patch(
            url,
            {"name": "改名门店"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["data"]["name"],
            "改名门店",
        )

        self.store.refresh_from_db()
        self.assertEqual(
            self.store.name,
            "改名门店",
        )

    def test_update_empty_data(self):
        """禁止空更新门店."""
        self._authenticate_admin()
        url = reverse(
            "store-manage-detail",
            kwargs={"pk": self.store.pk},
        )

        response = self.client.patch(
            url,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], 10001)

    def test_disable_store(self):
        """停用门店."""
        url = reverse(
            "store-manage-status",
            kwargs={"pk": self.store.pk},
        )

        response = self.client.patch(
            url,
            {"is_active": False},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(response.data["data"]["is_active"])

        self.store.refresh_from_db()
        self.assertFalse(self.store.is_active)

    def test_enable_store(self):
        """重新启用门店."""
        self.store.is_active = False
        self.store.save(update_fields=["is_active"])

        url = reverse(
            "store-manage-status",
            kwargs={"pk": self.store.pk},
        )

        response = self.client.patch(
            url,
            {"is_active": True},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(response.data["data"]["is_active"])

        self.store.refresh_from_db()
        self.assertTrue(self.store.is_active)

    def test_status_invalid_type(self):
        """is_active 传非布尔值被拦截."""
        url = reverse(
            "store-manage-status",
            kwargs={"pk": self.store.pk},
        )

        response = self.client.patch(
            url,
            {"is_active": "yes"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(response.data["code"], 10001)

    def test_store_not_found(self):
        """访问不存在的门店返回 404."""
        url = reverse(
            "store-manage-detail",
            kwargs={"pk": 999999},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_update_store_not_found(self):
        """编辑不存在的门店返回 404."""
        url = reverse(
            "store-manage-detail",
            kwargs={"pk": 999999},
        )

        response = self.client.patch(
            url,
            {"name": "不存在的门店"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_disable_store_not_found(self):
        """停用不存在的门店返回 404."""
        url = reverse(
            "store-manage-status",
            kwargs={"pk": 999999},
        )

        response = self.client.patch(
            url,
            {"is_active": False},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )


class StoreOptionListTest(StoreManageTestBase):
    """公开门店列表测试."""

    def test_anonymous_can_access(self):
        """未登录也能访问公开门店列表."""
        response = self.client.get(reverse("store-list"))

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["data"]),
            1,
        )

    def test_inactive_store_excluded(self):
        """停用门店不出现在公开列表."""
        Store.objects.create(
            code="S002",
            name="停用门店",
            store_type="direct",
            is_active=False,
        )

        response = self.client.get(reverse("store-list"))

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(response.data["data"]),
            1,
        )
        self.assertEqual(
            response.data["data"][0]["code"],
            "S001",
        )
