"""数据看板接口测试."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.members.models import Member
from apps.products.models import Product
from apps.stores.models import Store
from apps.transactions.models import Transaction, TransactionItem, TransactionStatus


class DashboardTestBase(APITestCase):
    """看板测试基类."""

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

        # 权限码
        self.perm = Permission.objects.create(
            code="dashboard:view", name="看板", module="dashboard"
        )

        # 店长角色 (有看板权限)
        self.manager_role = Role.objects.create(code="store_manager", name="店长")
        self.manager_role.permissions.set([self.perm])

        # 店员角色 (无看板权限)
        self.staff_role = Role.objects.create(code="staff", name="店员")

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
        token = self._make_token(self.staff, store_id=self.store.pk, role_code="staff")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_transaction(
        self,
        *,
        member=None,
        quantity=1,
        status=TransactionStatus.COMPLETED,
        created_at=None,
    ):
        """创建一笔已完成交易."""
        subtotal = self.product.price * quantity
        tx = Transaction.objects.create(
            store=self.store,
            member=member,
            staff=self.manager,
            total_amount=subtotal,
            paid_amount=subtotal,
            payment_method="cash",
            status=status,
        )
        TransactionItem.objects.create(
            transaction=tx,
            product=self.product,
            quantity=quantity,
            unit_price=self.product.price,
            subtotal=subtotal,
        )
        if created_at:
            # auto_now_add 不允许直接赋值, 用 queryset.update 覆盖
            Transaction.objects.filter(pk=tx.pk).update(created_at=created_at)
        return tx

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


class DashboardPermissionTest(DashboardTestBase):
    """看板权限测试."""

    def test_staff_cannot_access(self):
        """店员无看板权限."""
        self._auth_staff()
        response = self.client.get(reverse("dashboard-summary"))
        self.assert_failed(response, status.HTTP_403_FORBIDDEN, expected_code=10002)

    def test_anonymous_cannot_access(self):
        response = self.client.get(reverse("dashboard-summary"))
        self.assert_failed(response, status.HTTP_401_UNAUTHORIZED)

    def test_manager_can_access(self):
        self._auth_manager()
        response = self.client.get(reverse("dashboard-summary"))
        self.assert_success(response)


class DashboardSummaryTest(DashboardTestBase):
    """概览接口测试."""

    def test_summary_with_data(self):
        """有今日交易和会员时的概览."""
        self._create_transaction(member=self.member, quantity=2)
        self._auth_manager()

        response = self.client.get(reverse("dashboard-summary"))
        data = self.assert_success(response)

        self.assertEqual(data["today_total_amount"], "100.00")
        self.assertEqual(data["today_order_count"], 1)
        self.assertEqual(data["today_new_members"], 1)
        self.assertEqual(data["total_members"], 1)

    def test_summary_empty(self):
        """无数据时的概览."""
        self.member.delete()
        self._auth_manager()

        response = self.client.get(reverse("dashboard-summary"))
        data = self.assert_success(response)

        self.assertEqual(data["today_total_amount"], "0.00")
        self.assertEqual(data["today_order_count"], 0)
        self.assertEqual(data["today_new_members"], 0)
        self.assertEqual(data["total_members"], 0)

    def test_refunded_transaction_excluded(self):
        """已退款交易不计入概览."""
        self._create_transaction(status=TransactionStatus.REFUNDED)
        self._auth_manager()

        response = self.client.get(reverse("dashboard-summary"))
        data = self.assert_success(response)

        self.assertEqual(data["today_total_amount"], "0.00")
        self.assertEqual(data["today_order_count"], 0)


class DashboardTopProductsTest(DashboardTestBase):
    """热销商品测试."""

    def test_top_products(self):
        self._create_transaction(quantity=3)
        self._create_transaction(quantity=1)
        self._auth_manager()

        response = self.client.get(reverse("dashboard-top-products"))
        data = self.assert_success(response)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["product_id"], self.product.pk)
        self.assertEqual(data[0]["total_quantity"], 4)
        self.assertEqual(data[0]["total_amount"], "200.00")

    def test_refunded_excluded(self):
        self._create_transaction(quantity=2)
        self._create_transaction(quantity=5, status=TransactionStatus.REFUNDED)
        self._auth_manager()

        response = self.client.get(reverse("dashboard-top-products"))
        data = self.assert_success(response)

        self.assertEqual(data[0]["total_quantity"], 2)


class DashboardTopMembersTest(DashboardTestBase):
    """会员消费排行测试."""

    def test_top_members(self):
        self._create_transaction(member=self.member, quantity=2)
        self._auth_manager()

        response = self.client.get(reverse("dashboard-top-members"))
        data = self.assert_success(response)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["member_id"], self.member.pk)
        self.assertEqual(data[0]["total_amount"], "100.00")
        self.assertEqual(data[0]["order_count"], 1)

    def test_guest_transactions_excluded(self):
        """散客交易不出现在会员排行."""
        self._create_transaction(member=None)
        self._auth_manager()

        response = self.client.get(reverse("dashboard-top-members"))
        data = self.assert_success(response)
        self.assertEqual(data, [])


class DashboardTrendTest(DashboardTestBase):
    """交易趋势测试."""

    def test_trend_returns_days_count(self):
        """返回的天数等于 days 参数."""
        self._auth_manager()
        response = self.client.get(reverse("dashboard-transaction-trend"), {"days": 7})
        data = self.assert_success(response)
        self.assertEqual(len(data), 7)

    def test_trend_today_has_data(self):
        """今天的交易出现在趋势里."""
        self._create_transaction(quantity=2)
        self._auth_manager()

        response = self.client.get(reverse("dashboard-transaction-trend"), {"days": 7})
        data = self.assert_success(response)

        today = timezone.localtime().date().isoformat()
        today_item = next(item for item in data if item["date"] == today)
        self.assertEqual(today_item["total_amount"], "100.00")
        self.assertEqual(today_item["order_count"], 1)

    def test_trend_past_day(self):
        """过去某天的交易出现在对应日期."""
        past = timezone.localtime() - timedelta(days=3)
        self._create_transaction(quantity=1, created_at=past)
        self._auth_manager()

        response = self.client.get(reverse("dashboard-transaction-trend"), {"days": 7})
        data = self.assert_success(response)

        past_day = past.date().isoformat()
        past_item = next(item for item in data if item["date"] == past_day)
        self.assertEqual(past_item["order_count"], 1)

    def test_trend_days_invalid(self):
        """days 参数非法被拦截."""
        self._auth_manager()
        response = self.client.get(reverse("dashboard-transaction-trend"), {"days": 0})
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

        response = self.client.get(reverse("dashboard-transaction-trend"), {"days": 31})
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

        response = self.client.get(
            reverse("dashboard-transaction-trend"), {"days": "abc"}
        )
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)
