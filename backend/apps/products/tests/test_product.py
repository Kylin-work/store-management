"""商品管理接口测试."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.logs.models import OperationLog
from apps.products.models import Product
from apps.stores.models import Store


class ProductTestBase(APITestCase):
    """商品测试基类."""

    def setUp(self):
        throttle_patcher = patch(
            "rest_framework.throttling.ScopedRateThrottle.get_rate",
            return_value=None,
        )
        throttle_patcher.start()
        self.addCleanup(throttle_patcher.stop)

        # 两个门店
        self.store = Store.objects.create(
            code="S001", name="门店A", store_type="direct"
        )
        self.other_store = Store.objects.create(
            code="S002", name="门店B", store_type="direct"
        )

        # 权限码
        self.perms = {
            code: Permission.objects.create(code=code, name=code, module="product")
            for code in (
                "product:list",
                "product:create",
                "product:update",
                "product:delete",
                "product:edit_cost",
                "product:adjust_stock",
            )
        }

        # 店长角色: 全部权限
        self.manager_role = Role.objects.create(code="store_manager", name="店长")
        self.manager_role.permissions.set(self.perms.values())

        # 店员角色: 只有 list 和 update
        self.staff_role = Role.objects.create(code="staff", name="店员")
        self.staff_role.permissions.set(
            [
                self.perms["product:list"],
                self.perms["product:update"],
            ]
        )

        # 用户
        self.manager = User.objects.create_user(
            employee_code=None,
            password="Manager@123456",
            phone="13800000001",
            real_name="店长",
        )
        UserStoreRole.objects.create(
            user=self.manager, store=self.store, role=self.manager_role
        )
        self.staff = User.objects.create_user(
            employee_code=None,
            password="Staff@123456",
            phone="13800000002",
            real_name="店员",
        )
        UserStoreRole.objects.create(
            user=self.staff, store=self.store, role=self.staff_role
        )

    def _make_token(self, user, store_id=None, role_code=None):
        refresh = RefreshToken.for_user(user)
        refresh["store_id"] = store_id
        refresh["role_code"] = role_code
        return str(refresh.access_token)

    def _auth_manager(self):
        token = self._make_token(
            self.manager, store_id=self.store.pk, role_code="store_manager"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _auth_staff(self):
        token = self._make_token(self.staff, store_id=self.store.pk, role_code="staff")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_product(self, store=None, name="测试商品", price="50.00", cost="30.00"):
        return Product.objects.create(
            store=store or self.store,
            name=name,
            price=price,
            cost=cost,
            stock=100,
        )

    def assert_success(self, response, expected_status=status.HTTP_200_OK):
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"接口响应异常: {response.data}",
        )
        self.assertEqual(response.data["code"], 0)
        return response.data["data"]

    def assert_failed(self, response, expected_status, expected_code=None):
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"接口响应异常: {response.data}",
        )
        if expected_code is not None:
            self.assertEqual(response.data["code"], expected_code)


class ProductListTest(ProductTestBase):
    """商品列表测试."""

    def test_manager_sees_own_store_products(self):
        self._create_product(name="商品A")
        self._create_product(store=self.other_store, name="商品B")

        self._auth_manager()
        response = self.client.get(reverse("product-list"))
        data = self.assert_success(response)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["name"], "商品A")

    def test_manager_sees_cost(self):
        self._create_product()
        self._auth_manager()
        response = self.client.get(reverse("product-list"))
        data = self.assert_success(response)
        self.assertIn("cost", data["items"][0])
        self.assertEqual(data["items"][0]["cost"], "30.00")

    def test_staff_cannot_see_cost(self):
        """店员看不到 cost 字段."""
        self._create_product()
        self._auth_staff()
        response = self.client.get(reverse("product-list"))
        data = self.assert_success(response)
        self.assertNotIn("cost", data["items"][0])

    def test_anonymous_rejected(self):
        response = self.client.get(reverse("product-list"))
        self.assert_failed(response, status.HTTP_401_UNAUTHORIZED)


class ProductCreateTest(ProductTestBase):
    """创建商品测试."""

    def setUp(self):
        super().setUp()
        self._auth_manager()

    def test_create_success(self):
        response = self.client.post(
            reverse("product-list"),
            {
                "name": "新商品",
                "price": "50.00",
                "cost": "30.00",
                "stock": 10,
            },
            format="json",
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)
        self.assertEqual(data["name"], "新商品")
        self.assertEqual(data["price"], "50.00")

    @patch(
        "apps.products.views.product.log_operation",
        side_effect=RuntimeError("日志写入失败"),
    )
    def test_create_rollback_when_log_fails(self, mock_log):
        """操作日志写入失败时，商品创建应回滚."""
        response = self.client.post(
            reverse("product-list"),
            {
                "name": "事务回滚商品",
                "price": "50.00",
                "cost": "30.00",
                "stock": 10,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertFalse(
            Product.objects.filter(
                store=self.store,
                name="事务回滚商品",
            ).exists()
        )

    def test_duplicate_name_same_store(self):
        self._create_product(name="重复商品")
        response = self.client.post(
            reverse("product-list"),
            {"name": "重复商品", "price": "50.00", "cost": "30.00"},
            format="json",
        )
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_same_name_different_store_ok(self):
        self._create_product(store=self.other_store, name="同名商品")
        response = self.client.post(
            reverse("product-list"),
            {"name": "同名商品", "price": "50.00", "cost": "30.00"},
            format="json",
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)
        self.assertEqual(data["name"], "同名商品")


class ProductDetailTest(ProductTestBase):
    """商品详情与编辑测试."""

    def setUp(self):
        super().setUp()
        self.product = self._create_product()

    def test_manager_detail_with_cost(self):
        self._auth_manager()
        response = self.client.get(
            reverse("product-detail", kwargs={"pk": self.product.pk})
        )
        data = self.assert_success(response)
        self.assertIn("cost", data)

    def test_staff_detail_without_cost(self):
        self._auth_staff()
        response = self.client.get(
            reverse("product-detail", kwargs={"pk": self.product.pk})
        )
        data = self.assert_success(response)
        self.assertNotIn("cost", data)

    def test_detail_cross_store_404(self):
        other = self._create_product(store=self.other_store, name="他店商品")
        self._auth_manager()
        response = self.client.get(reverse("product-detail", kwargs={"pk": other.pk}))
        self.assert_failed(response, status.HTTP_404_NOT_FOUND)

    def test_manager_update_cost(self):
        self._auth_manager()
        response = self.client.patch(
            reverse("product-detail", kwargs={"pk": self.product.pk}),
            {"cost": "99.00"},
            format="json",
        )
        data = self.assert_success(response)
        self.assertEqual(data["cost"], "99.00")

    def test_staff_cannot_update_cost(self):
        """店员有 update 权限但无 edit_cost 权限, 改成本价被拒."""
        self._auth_staff()
        response = self.client.patch(
            reverse("product-detail", kwargs={"pk": self.product.pk}),
            {"cost": "99.00"},
            format="json",
        )
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_staff_can_update_name(self):
        """店员有 update 权限, 改名称成功."""
        self._auth_staff()
        response = self.client.patch(
            reverse("product-detail", kwargs={"pk": self.product.pk}),
            {"name": "改名商品"},
            format="json",
        )
        data = self.assert_success(response)
        self.assertEqual(data["name"], "改名商品")

    def test_cannot_update_stock(self):
        """普通商品编辑接口禁止修改库存."""
        self._auth_manager()
        response = self.client.patch(
            reverse("product-detail", kwargs={"pk": self.product.pk}),
            {"stock": 200},
            format="json",
        )

        self.assert_failed(
            response,
            status.HTTP_400_BAD_REQUEST,
            expected_code=10001,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)


class ProductDeleteTest(ProductTestBase):
    """商品删除测试."""

    def setUp(self):
        super().setUp()
        self.product = self._create_product()

    def test_manager_delete_soft(self):
        self._auth_manager()
        response = self.client.delete(
            reverse("product-detail", kwargs={"pk": self.product.pk})
        )
        data = self.assert_success(response)
        self.assertFalse(data["is_active"])

        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_delete_idempotent(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        self._auth_manager()
        response = self.client.delete(
            reverse("product-detail", kwargs={"pk": self.product.pk})
        )
        self.assert_success(response)

    def test_staff_cannot_delete(self):
        """店员无 delete 权限, 被拒."""
        self._auth_staff()
        response = self.client.delete(
            reverse("product-detail", kwargs={"pk": self.product.pk})
        )
        self.assert_failed(response, status.HTTP_403_FORBIDDEN, expected_code=10002)


class ProductAdjustStockTest(ProductTestBase):
    """商品库存调整测试."""

    def setUp(self):
        super().setUp()
        self.manager_role.permissions.add(self.perms["product:adjust_stock"])
        self.product = self._create_product()

    def _adjust(self, quantity, reason="测试调整"):
        return self.client.patch(
            reverse("product-adjust-stock", kwargs={"pk": self.product.pk}),
            {"quantity": quantity, "reason": reason},
            format="json",
        )

    def test_add_stock(self):
        """入库."""
        self._auth_manager()
        response = self._adjust(50)
        data = self.assert_success(response)
        self.assertEqual(data["stock"], 150)

    def test_deduct_stock(self):
        """出库."""
        self._auth_manager()
        response = self._adjust(-30)
        data = self.assert_success(response)
        self.assertEqual(data["stock"], 70)

    def test_deduct_to_zero(self):
        """扣减到 0."""
        self._auth_manager()
        response = self._adjust(-100)
        data = self.assert_success(response)
        self.assertEqual(data["stock"], 0)

    def test_deduct_exceed(self):
        """扣减超过当前库存被拒."""
        self._auth_manager()
        response = self._adjust(-150)
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_zero_rejected(self):
        """调整数量为 0 被拒."""
        self._auth_manager()
        response = self._adjust(0)
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_staff_cannot_adjust(self):
        """店员无库存调整权限."""
        self._auth_staff()
        response = self._adjust(50)
        self.assert_failed(response, status.HTTP_403_FORBIDDEN, expected_code=10002)

    def test_cross_store_404(self):
        """跨店调整库存返回 404."""
        other = self._create_product(store=self.other_store, name="他店商品")
        self._auth_manager()
        response = self.client.patch(
            reverse("product-adjust-stock", kwargs={"pk": other.pk}),
            {"quantity": 10, "reason": "测试"},
            format="json",
        )
        self.assert_failed(response, status.HTTP_404_NOT_FOUND)

    def test_log_written(self):
        """库存调整写入操作日志."""
        self._auth_manager()
        self._adjust(50, reason="新到货")

        logs = OperationLog.objects.filter(
            module="product",
            action="adjust_stock",
            target_id=str(self.product.pk),
        )
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.detail["stock_before"], 100)
        self.assertEqual(log.detail["stock_after"], 150)
        self.assertEqual(log.detail["reason"], "新到货")
