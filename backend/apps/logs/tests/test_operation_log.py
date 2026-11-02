"""操作日志查询接口测试。"""

from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role, User, UserStoreRole
from apps.logs.models import OperationLog
from apps.stores.models import Store


class OperationLogTestBase(APITestCase):
    """操作日志查询测试基类。"""

    def setUp(self):
        throttle_patcher = patch(
            "rest_framework.throttling.ScopedRateThrottle.get_rate",
            return_value=None,
        )
        throttle_patcher.start()
        self.addCleanup(throttle_patcher.stop)

        self.url = reverse("operation-log-list")

        # 门店
        self.store = Store.objects.create(
            code="S001", name="测试门店A", store_type="direct"
        )

        # 角色
        self.role = Role.objects.create(code="staff", name="店员")

        # 超级管理员
        self.superuser = User.objects.create_superuser(
            employee_code=None,
            password="Admin@123456",
            phone="13900000001",
            real_name="超级管理员",
        )

        # 普通用户
        self.staff = User.objects.create_user(
            employee_code=None,
            password="Staff@123456",
            phone="13800000001",
            real_name="店员",
        )
        UserStoreRole.objects.create(user=self.staff, store=self.store, role=self.role)

        # 造日志数据
        self.log_create = OperationLog.objects.create(
            user=self.superuser,
            module="store",
            action="create",
            target_type="Store",
            target_id="1",
            detail={"code": "S001"},
        )
        self.log_account = OperationLog.objects.create(
            user=self.superuser,
            module="account",
            action="create",
            target_type="User",
            target_id="00000002",
            detail={"phone": "13800000002"},
        )
        self.log_role = OperationLog.objects.create(
            user=self.staff,
            module="role",
            action="update",
            target_type="Role",
            target_id="staff",
            detail={"changed_fields": ["name"]},
        )

    def _make_token(self, user, store_id=None, role_code=None):
        refresh = RefreshToken.for_user(user)
        refresh["store_id"] = store_id
        refresh["role_code"] = role_code
        return str(refresh.access_token)

    def _auth_superuser(self):
        token = self._make_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _auth_staff(self):
        token = self._make_token(
            self.staff, store_id=self.store.pk, role_code=self.role.code
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _get_logs(self, params=None):
        response = self.client.get(self.url, params or {})
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            msg=f"接口响应异常：{response.data}",
        )
        self.assertEqual(response.data["code"], 0)
        return response.data["data"]


class OperationLogPermissionTest(OperationLogTestBase):
    """查询权限测试。"""

    def test_anonymous_cannot_access(self):
        """未登录返回 401。"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_cannot_access(self):
        """普通用户返回 403。"""
        self._auth_staff()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], 10002)

    def test_superuser_can_access(self):
        """超级管理员可查。"""
        self._auth_superuser()
        data = self._get_logs()
        self.assertEqual(data["total"], 3)


class OperationLogFilterTest(OperationLogTestBase):
    """筛选测试。"""

    def setUp(self):
        super().setUp()
        self._auth_superuser()

    def test_filter_by_module(self):
        data = self._get_logs({"module": "store"})
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["module"], "store")

    def test_filter_by_action(self):
        data = self._get_logs({"action": "create"})
        self.assertEqual(data["total"], 2)

    def test_filter_by_user_employee_code(self):
        data = self._get_logs({"user_employee_code": self.staff.employee_code})
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["module"], "role")

    def test_filter_by_start_time(self):
        """start_time 过滤。"""
        future = (timezone.now() + timedelta(hours=1)).isoformat()
        data = self._get_logs({"start_time": future})
        self.assertEqual(data["total"], 0)

    def test_filter_by_end_time(self):
        """end_time 过滤。"""
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        data = self._get_logs({"end_time": past})
        self.assertEqual(data["total"], 0)

    def test_invalid_start_time(self):
        """非法时间格式返回 10001。"""
        response = self.client.get(self.url, {"start_time": "invalid"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], 10001)


class OperationLogOrderTest(OperationLogTestBase):
    """排序和字段测试。"""

    def test_ordered_by_created_at_desc(self):
        """按创建时间倒序。"""
        self._auth_superuser()
        data = self._get_logs()
        ids = [item["id"] for item in data["items"]]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_user_info_included(self):
        """返回操作人工号和姓名。"""
        self._auth_superuser()
        data = self._get_logs({"module": "store"})
        item = data["items"][0]
        self.assertEqual(item["user_employee_code"], self.superuser.employee_code)
        self.assertEqual(item["user_real_name"], "超级管理员")
