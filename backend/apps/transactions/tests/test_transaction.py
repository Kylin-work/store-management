"""交易管理接口测试."""

from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.members.models import Member
from apps.products.models import Product
from apps.stores.models import Store


class TransactionTestBase(APITestCase):
    """交易测试基类."""

    def setUp(self):
        throttle_patcher = patch(
            "rest_framework.throttling.ScopedRateThrottle.get_rate",
            return_value=None,
        )
        throttle_patcher.start()
        self.addCleanup(throttle_patcher.stop)

        # 门店
        self.store = Store.objects.create(
            code="S001", name="门店A", store_type="direct"
        )
        self.other_store = Store.objects.create(
            code="S002", name="门店B", store_type="direct"
        )

        # 权限码
        self.perms = {
            code: Permission.objects.create(
                code=code, name=code, module="transaction"
            )
            for code in (
                "transaction:list",
                "transaction:create",
                "transaction:refund",
            )
        }

        # 角色
        self.manager_role = Role.objects.create(code="store_manager", name="店长")
        self.manager_role.permissions.set(self.perms.values())

        self.staff_role = Role.objects.create(code="staff", name="店员")
        self.staff_role.permissions.set(
            [
                self.perms["transaction:list"],
                self.perms["transaction:create"],
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

        # 商品
        self.product = Product.objects.create(
            store=self.store,
            name="测试商品",
            price=Decimal("50.00"),
            cost=Decimal("30.00"),
            stock=100,
        )

        # 会员
        self.member = Member.objects.create(
            store=self.store, name="测试会员", phone="13700000001"
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
        token = self._make_token(
            self.staff, store_id=self.store.pk, role_code="staff"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_transaction_payload(self, **overrides):
        data = {
            "payment_method": "cash",
            "items": [{"product_id": self.product.pk, "quantity": 2}],
        }
        data.update(overrides)
        return data

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


class TransactionCreateTest(TransactionTestBase):
    """创建交易测试."""

    def setUp(self):
        super().setUp()
        self._auth_manager()

    def test_create_success(self):
        """创建交易, 扣库存, 算积分."""
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(member_id=self.member.pk),
            format="json",
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)

        self.assertEqual(data["total_amount"], "100.00")
        self.assertEqual(data["member_name"], "测试会员")
        self.assertEqual(len(data["items"]), 1)

        # 库存扣减
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 98)

        # 积分增加
        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 100)

    def test_create_without_member(self):
        """散客交易, 不关联会员, 不加积分."""
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(),
            format="json",
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)
        self.assertIsNone(data["member_id"])

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 0)

    def test_create_insufficient_stock(self):
        """库存不足时创建失败."""
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(
                items=[{"product_id": self.product.pk, "quantity": 200}]
            ),
            format="json",
        )
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=50002)

        # 库存未变
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

    def test_create_inactive_product(self):
        """停用商品不能交易."""
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(),
            format="json",
        )
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_create_cross_store_product(self):
        """跨店商品不能交易."""
        other_product = Product.objects.create(
            store=self.other_store,
            name="他店商品",
            price=Decimal("10.00"),
            cost=Decimal("5.00"),
            stock=100,
        )
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(
                items=[{"product_id": other_product.pk, "quantity": 1}]
            ),
            format="json",
        )
        self.assert_failed(response, status.HTTP_404_NOT_FOUND, expected_code=50001)

    def test_create_empty_items(self):
        """空明细被拦截."""
        response = self.client.post(
            reverse("transaction-list"),
            {"payment_method": "cash", "items": []},
            format="json",
        )
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)


class TransactionListTest(TransactionTestBase):
    """交易列表测试."""

    def test_manager_sees_all_store_transactions(self):
        """店长看到全店交易."""
        self._auth_manager()
        self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(),
            format="json",
        )
        self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(),
            format="json",
        )

        response = self.client.get(reverse("transaction-list"))
        data = self.assert_success(response)
        self.assertEqual(data["total"], 2)

    def test_staff_only_sees_own_transactions(self):
        """店员只看到自己经手的交易."""
        # 店长创建一笔
        self._auth_manager()
        self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(),
            format="json",
        )
        # 店员创建一笔
        self._auth_staff()
        self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(),
            format="json",
        )

        response = self.client.get(reverse("transaction-list"))
        data = self.assert_success(response)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["staff_name"], "店员")


class TransactionRefundTest(TransactionTestBase):
    """交易退款测试."""

    def setUp(self):
        super().setUp()
        # 先创建一笔交易
        self._auth_manager()
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(member_id=self.member.pk),
            format="json",
        )
        self.tx_id = response.data["data"]["id"]

    def _refund(self):
        return self.client.post(
            reverse("transaction-refund", kwargs={"pk": self.tx_id})
        )

    def test_manager_refund_success(self):
        """店长退款成功, 回滚库存, 扣回积分."""
        self._auth_manager()
        response = self._refund()
        data = self.assert_success(response)
        self.assertEqual(data["status"], "refunded")

        # 库存回滚
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

        # 积分扣回
        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 0)

    def test_staff_cannot_refund(self):
        """店员无退款权限."""
        self._auth_staff()
        response = self._refund()
        self.assert_failed(response, status.HTTP_403_FORBIDDEN, expected_code=10002)

    def test_refund_twice_fails(self):
        """重复退款被拒."""
        self._auth_manager()
        self._refund()
        response = self._refund()
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=60002)

    def test_refund_cross_store_404(self):
        """跨店退款返回 404."""
        # 用另一家店的店长身份退款
        other_manager = User.objects.create_user(
            employee_code=None,
            password="Manager2@123456",
            phone="13800000003",
            real_name="另一店长",
        )
        UserStoreRole.objects.create(
            user=other_manager, store=self.other_store, role=self.manager_role
        )
        token = self._make_token(
            other_manager, store_id=self.other_store.pk, role_code="store_manager"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self._refund()
        self.assert_failed(response, status.HTTP_404_NOT_FOUND, expected_code=60001)

    def test_refund_points_not_negative(self):
        """积分不足时扣到 0 为止, 不产生负积分."""
        # 手动把会员积分清零 (模拟积分已被消费)
        self.member.points = 0
        self.member.save(update_fields=["points"])

        self._auth_manager()
        self._refund()

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 0)


class TransactionDetailTest(TransactionTestBase):
    """交易详情测试."""

    def setUp(self):
        super().setUp()
        self._auth_manager()
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(),
            format="json",
        )
        self.tx_id = response.data["data"]["id"]

    def test_manager_detail(self):
        response = self.client.get(
            reverse("transaction-detail", kwargs={"pk": self.tx_id})
        )
        self.assert_success(response)

    def test_staff_cannot_see_others_detail(self):
        """店员看不到店长创建的交易详情."""
        self._auth_staff()
        response = self.client.get(
            reverse("transaction-detail", kwargs={"pk": self.tx_id})
        )
        self.assert_failed(response, status.HTTP_404_NOT_FOUND, expected_code=60001)
