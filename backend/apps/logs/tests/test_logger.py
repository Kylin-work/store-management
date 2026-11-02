"""操作日志记录函数与模型约束测试."""

from django.test import TestCase

from apps.accounts.models import User
from apps.logs.services.logger import log_operation


class OperationLogModelTest(TestCase):
    """日志模型约束测试."""

    def setUp(self):
        self.user = User.objects.create_user(
            employee_code=None,
            password="Test@123456",
            phone="13800000001",
            real_name="张三",
        )

    def test_create_log(self):
        """创建日志记录,字段正确."""
        log = log_operation(
            user=self.user,
            module="account",
            action="create",
            target_type="User",
            target_id="00000002",
            detail={"phone": "13800000002"},
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.module, "account")
        self.assertEqual(log.action, "create")
        self.assertEqual(log.target_type, "User")
        self.assertEqual(log.target_id, "00000002")
        self.assertEqual(log.detail, {"phone": "13800000002"})
        self.assertIsNotNone(log.created_at)

    def test_detail_defaults_to_empty_dict(self):
        """不传 detail 时默认为空字典."""
        log = log_operation(
            user=self.user,
            module="account",
            action="create",
            target_type="User",
            target_id="00000002",
        )
        self.assertEqual(log.detail, {})

    def test_log_cannot_be_updated(self):
        """日志创建后不可修改."""
        log = log_operation(
            user=self.user,
            module="account",
            action="create",
            target_type="User",
            target_id="00000002",
        )
        log.action = "update"
        with self.assertRaises(ValueError):
            log.save()

    def test_log_cannot_be_deleted(self):
        """日志不可删除."""
        log = log_operation(
            user=self.user,
            module="account",
            action="create",
            target_type="User",
            target_id="00000002",
        )
        with self.assertRaises(ValueError):
            log.delete()

    def test_default_permissions(self):
        """模型默认权限只有 add 和 view,没有 change 和 delete."""
        from django.contrib.auth.models import Permission

        perms = Permission.objects.filter(
            content_type__app_label="logs",
            content_type__model="operationlog",
        ).values_list("codename", flat=True)
        self.assertEqual(set(perms), {"add_operationlog", "view_operationlog"})
