"""工号生成测试。"""

import re

from django.test import TestCase

from apps.accounts.models import Sequence, User


class EmployeeCodeTest(TestCase):
    """工号生成逻辑测试。"""

    SEQUENCE_NAME = "employee_code"
    DEFAULT_PASSWORD = "Test@123456"

    def setUp(self):
        # 序列行由 data migration 预置
        self.sequence = Sequence.objects.get(name=self.SEQUENCE_NAME)

    def _create_user(
        self,
        phone="13800000001",
        real_name="测试用户",
        employee_code=None,
        password=None,
        superuser=False,
    ):
        """统一创建普通用户或超级管理员。"""
        create_method = (
            User.objects.create_superuser if superuser else User.objects.create_user
        )

        return create_method(
            employee_code=employee_code,
            password=password or self.DEFAULT_PASSWORD,
            phone=phone,
            real_name=real_name,
        )

    def _assert_generated_code(self, user, expected_code):
        """断言工号格式及预期值。"""
        self.assertIsNotNone(user.employee_code)
        self.assertRegex(user.employee_code, re.compile(r"^[0-9]{8}$"))
        self.assertEqual(user.employee_code, expected_code)

    def test_sequence_seeded(self):
        """序列行由 data migration 预置,初始值为 0。"""
        self.assertEqual(self.sequence.current_value, 0)

    def test_auto_generate_8_digit(self):
        """创建用户时工号自动生成,8 位纯数字。"""
        user = self._create_user()

        self._assert_generated_code(user, "00000001")

    def test_sequence_increments(self):
        """连续创建用户,工号递增。"""
        users = [
            self._create_user(
                phone=f"1380000000{i}",
                real_name=name,
            )
            for i, name in enumerate(("张三", "李四", "王五"), start=1)
        ]

        expected_codes = ("00000001", "00000002", "00000003")

        for user, expected_code in zip(users, expected_codes):
            with self.subTest(employee_code=expected_code):
                self._assert_generated_code(user, expected_code)

        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.current_value, 3)

    def test_manual_code_not_overridden(self):
        """手动指定工号时不走序列生成。"""
        user = self._create_user(employee_code="99999999")

        self.assertEqual(user.employee_code, "99999999")

        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.current_value, 0)

    def test_manual_code_does_not_consume_sequence(self):
        """手动指定工号后,下一次自动生成仍从 00000001 开始。"""
        self._create_user(employee_code="99999999")

        user = self._create_user(
            phone="13800000002",
            real_name="李四",
        )

        self._assert_generated_code(user, "00000001")

    def test_superuser_also_generates_code(self):
        """超级管理员也走工号生成。"""
        admin = self._create_user(
            phone="13900000001",
            real_name="超级管理员",
            superuser=True,
            password="Admin@123456",
        )

        self._assert_generated_code(admin, "00000001")
