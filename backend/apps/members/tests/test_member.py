"""会员管理接口测试."""

from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.logs.models import OperationLog
from apps.members.models import Member, RechargeRecord
from apps.stores.models import Store


class MemberTestBase(APITestCase):
    """会员测试基类."""

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
            code: Permission.objects.create(code=code, name=code, module="member")
            for code in (
                "member:list",
                "member:create",
                "member:update",
                "member:recharge",
                "member:change_level",
            )
        }

        # 店长角色：全部权限
        self.manager_role = Role.objects.create(code="store_manager", name="店长")
        self.manager_role.permissions.set(self.perms.values())

        # 店员角色：除等级调整外的权限
        self.staff_role = Role.objects.create(code="staff", name="店员")
        self.staff_role.permissions.set(
            [
                self.perms["member:list"],
                self.perms["member:create"],
                self.perms["member:update"],
                self.perms["member:recharge"],
            ]
        )

        # 用户
        self.superuser = User.objects.create_superuser(
            employee_code=None,
            password="Admin@123456",
            phone="13900000001",
            real_name="超级管理员",
        )
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

    def _auth_superuser(self):
        token = self._make_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_member(self, store=None, phone="13700000001", name="测试会员"):
        return Member.objects.create(store=store or self.store, name=name, phone=phone)

    def assert_success(self, response, expected_status=status.HTTP_200_OK):
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"接口响应异常：{response.data}",
        )
        self.assertEqual(response.data["code"], 0)
        return response.data["data"]

    def assert_failed(self, response, expected_status, expected_code=None):
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"接口响应异常：{response.data}",
        )
        if expected_code is not None:
            self.assertEqual(response.data["code"], expected_code)


class MemberListTest(MemberTestBase):
    """会员列表测试."""

    def test_manager_sees_own_store_members(self):
        self._create_member(phone="13700000001")
        self._create_member(store=self.other_store, phone="13700000002")
        self._auth_manager()

        response = self.client.get(reverse("member-list"))
        data = self.assert_success(response)

        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["phone"], "13700000001")

    def test_staff_sees_own_store_members(self):
        self._create_member()
        self._auth_staff()
        response = self.client.get(reverse("member-list"))
        data = self.assert_success(response)
        self.assertEqual(data["total"], 1)

    def test_superuser_rejected(self):
        self._auth_superuser()
        response = self.client.get(reverse("member-list"))
        self.assert_failed(response, status.HTTP_403_FORBIDDEN, expected_code=10002)

    def test_anonymous_rejected(self):
        response = self.client.get(reverse("member-list"))
        self.assert_failed(response, status.HTTP_401_UNAUTHORIZED)


class MemberCreateTest(MemberTestBase):
    """创建会员测试."""

    def setUp(self):
        super().setUp()
        self._auth_manager()

    def test_create_success(self):
        response = self.client.post(
            reverse("member-list"),
            {"name": "王会员", "phone": "13700000003"},
            format="json",
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)
        self.assertEqual(data["name"], "王会员")
        self.assertEqual(data["balance"], "0.00")
        self.assertEqual(data["level"], "normal")

    def test_duplicate_phone_same_store(self):
        self._create_member(phone="13700000004")
        response = self.client.post(
            reverse("member-list"),
            {"name": "重复会员", "phone": "13700000004"},
            format="json",
        )
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_same_phone_different_store_ok(self):
        self._create_member(store=self.other_store, phone="13700000005")
        response = self.client.post(
            reverse("member-list"),
            {"name": "跨店会员", "phone": "13700000005"},
            format="json",
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)
        self.assertEqual(data["phone"], "13700000005")


class MemberDetailTest(MemberTestBase):
    """会员详情与编辑测试."""

    def setUp(self):
        super().setUp()
        self._auth_manager()
        self.member = self._create_member()

    def test_detail_success(self):
        response = self.client.get(
            reverse("member-detail", kwargs={"pk": self.member.pk})
        )
        data = self.assert_success(response)
        self.assertEqual(data["name"], "测试会员")

    def test_detail_cross_store_404(self):
        other = self._create_member(store=self.other_store, phone="13700000099")
        response = self.client.get(reverse("member-detail", kwargs={"pk": other.pk}))
        self.assert_failed(response, status.HTTP_404_NOT_FOUND)

    def test_update_name(self):
        response = self.client.patch(
            reverse("member-detail", kwargs={"pk": self.member.pk}),
            {"name": "改名会员"},
            format="json",
        )
        data = self.assert_success(response)
        self.assertEqual(data["name"], "改名会员")

    def test_update_duplicate_phone(self):
        other = self._create_member(phone="13700000006")
        response = self.client.patch(
            reverse("member-detail", kwargs={"pk": self.member.pk}),
            {"phone": other.phone},
            format="json",
        )
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)


class MemberRechargeTest(MemberTestBase):
    """会员充值测试."""

    def setUp(self):
        super().setUp()
        self.member = self._create_member()

    def _recharge(self, amount):
        return self.client.post(
            reverse("member-recharge", kwargs={"pk": self.member.pk}),
            {"amount": amount},
            format="json",
        )

    def test_recharge_success(self):
        self._auth_manager()
        response = self._recharge("100.00")
        data = self.assert_success(response)

        self.assertEqual(data["balance_before"], "0.00")
        self.assertEqual(data["balance_after"], "100.00")
        self.assertEqual(data["member"]["balance"], "100.00")

        self.member.refresh_from_db()
        self.assertEqual(self.member.balance, Decimal("100.00"))
        self.assertEqual(RechargeRecord.objects.count(), 1)

        logs = OperationLog.objects.filter(
            module="member", action="recharge", target_id=str(self.member.pk)
        )
        self.assertEqual(logs.count(), 1)

    def test_recharge_staff_can(self):
        self._auth_staff()
        response = self._recharge("50.00")
        self.assert_success(response)

    def test_recharge_amount_too_small(self):
        self._auth_manager()
        response = self._recharge("0")
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_recharge_amount_too_large(self):
        self._auth_manager()
        response = self._recharge("60000.00")
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_recharge_inactive_member(self):
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])
        self._auth_manager()
        response = self._recharge("100.00")
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_recharge_cross_store_404(self):
        other = self._create_member(store=self.other_store, phone="13700000099")
        self._auth_manager()
        response = self.client.post(
            reverse("member-recharge", kwargs={"pk": other.pk}),
            {"amount": "100.00"},
            format="json",
        )
        self.assert_failed(response, status.HTTP_404_NOT_FOUND, expected_code=40001)


class MemberChangeLevelTest(MemberTestBase):
    """会员等级调整测试."""

    def setUp(self):
        super().setUp()
        self.member = self._create_member()

    def test_manager_can_change_level(self):
        self._auth_manager()
        response = self.client.patch(
            reverse("member-change-level", kwargs={"pk": self.member.pk}),
            {"level": "gold"},
            format="json",
        )
        data = self.assert_success(response)
        self.assertEqual(data["level"], "gold")

    def test_staff_cannot_change_level(self):
        self._auth_staff()
        response = self.client.patch(
            reverse("member-change-level", kwargs={"pk": self.member.pk}),
            {"level": "gold"},
            format="json",
        )
        self.assert_failed(response, status.HTTP_403_FORBIDDEN, expected_code=10002)
