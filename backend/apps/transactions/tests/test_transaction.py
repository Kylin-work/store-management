"""交易管理接口测试."""

from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.logs.models import OperationLog
from apps.members.models import Member, PointsRecord, PointsRecordType
from apps.products.models import Product
from apps.stores.models import Store
from apps.transactions.models import Transaction, TransactionItem


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
            code: Permission.objects.create(code=code, name=code, module="transaction")
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
        token = self._make_token(self.staff, store_id=self.store.pk, role_code="staff")
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
        """创建交易, 扣库存, 算积分并记录积分流水."""
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(member_id=self.member.pk),
            format="json",
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)

        self.assertEqual(data["total_amount"], "100.00")
        self.assertEqual(data["member_name"], "测试会员")
        self.assertEqual(len(data["items"]), 1)

        tx = Transaction.objects.get(pk=data["id"])

        # 库存扣减
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 98)

        # 积分增加
        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 100)

        # 积分流水
        records = PointsRecord.objects.filter(
            transaction=tx,
            record_type=PointsRecordType.EARN,
        )
        self.assertEqual(records.count(), 1)

        record = records.get()
        self.assertEqual(record.member_id, self.member.pk)
        self.assertEqual(record.staff_id, self.manager.pk)
        self.assertEqual(record.earn_transaction_id, tx.pk)
        self.assertEqual(record.points_delta, 100)
        self.assertEqual(record.points_expected_delta, 100)
        self.assertEqual(record.points_before, 0)
        self.assertEqual(record.points_after, 100)

    @patch(
        "apps.transactions.services.create_transaction.PointsRecord.objects.create",
        side_effect=RuntimeError("积分流水写入失败"),
    )
    def test_create_rollback_when_points_record_fails(self, mock_create):
        """积分流水写入失败时, 交易、库存和会员积分全部回滚."""
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(member_id=self.member.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_create.assert_called_once()

        # 交易和明细回滚
        self.assertEqual(Transaction.objects.filter(store=self.store).count(), 0)
        self.assertEqual(TransactionItem.objects.count(), 0)

        # 库存回滚
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

        # 会员积分回滚
        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 0)

        # 积分流水回滚
        self.assertEqual(PointsRecord.objects.count(), 0)

    @patch(
        "apps.transactions.services.create_transaction.log_operation",
        side_effect=RuntimeError("日志写入失败"),
    )
    def test_create_rollback_when_log_fails(self, mock_log):
        """操作日志写入失败时, 交易、库存、积分和积分流水全部回滚."""
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(member_id=self.member.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_log.assert_called_once()

        self.assertEqual(Transaction.objects.filter(store=self.store).count(), 0)
        self.assertEqual(TransactionItem.objects.count(), 0)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 0)

        self.assertEqual(PointsRecord.objects.count(), 0)

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
        self.assertEqual(PointsRecord.objects.count(), 0)

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
        self._auth_manager()
        self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(),
            format="json",
        )

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

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

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
        """积分不足时扣到 0 为止, 并记录预期与实际扣回积分."""
        self.member.points = 0
        self.member.save(update_fields=["points"])

        self._auth_manager()
        response = self._refund()
        self.assert_success(response)

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 0)

        earn_record = PointsRecord.objects.get(
            earn_transaction_id=self.tx_id,
            record_type=PointsRecordType.EARN,
        )
        refund_record = PointsRecord.objects.get(
            transaction_id=self.tx_id,
            record_type=PointsRecordType.REFUND_DEDUCT,
        )

        self.assertEqual(earn_record.points_delta, 100)
        self.assertEqual(refund_record.points_expected_delta, -100)
        self.assertEqual(refund_record.points_delta, 0)
        self.assertEqual(refund_record.points_before, 0)
        self.assertEqual(refund_record.points_after, 0)


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


class TransactionPartialRefundTest(TransactionTestBase):
    """交易部分退款测试."""

    def setUp(self):
        super().setUp()
        self._auth_manager()
        response = self.client.post(
            reverse("transaction-list"),
            self._create_transaction_payload(
                member_id=self.member.pk,
                items=[{"product_id": self.product.pk, "quantity": 3}],
            ),
            format="json",
        )
        data = response.data["data"]
        self.tx_id = data["id"]
        self.item_id = data["items"][0]["id"]

    def _partial_refund(self, items):
        return self.client.post(
            reverse("transaction-refund", kwargs={"pk": self.tx_id}),
            {"items": items},
            format="json",
        )

    def test_partial_refund(self):
        """退 1 件, 状态变为部分退款, 库存和积分按比例变化."""
        self._auth_manager()
        response = self._partial_refund([{"item_id": self.item_id, "quantity": 1}])
        data = self.assert_success(response)
        self.assertEqual(data["status"], "partial_refunded")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 98)

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 100)

    def test_partial_refund_all_quantities(self):
        """分三次退完, 状态最终变为已退款."""
        self._auth_manager()

        r1 = self._partial_refund([{"item_id": self.item_id, "quantity": 1}])
        self.assertEqual(r1.data["data"]["status"], "partial_refunded")

        r2 = self._partial_refund([{"item_id": self.item_id, "quantity": 1}])
        self.assertEqual(r2.data["data"]["status"], "partial_refunded")

        r3 = self._partial_refund([{"item_id": self.item_id, "quantity": 1}])
        self.assertEqual(r3.data["data"]["status"], "refunded")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

    def test_refund_exceed_remaining(self):
        """退款数量超过剩余可退数量被拒."""
        self._auth_manager()
        response = self._partial_refund([{"item_id": self.item_id, "quantity": 4}])
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_refund_invalid_item(self):
        """明细不属于该交易被拒."""
        self._auth_manager()
        response = self._partial_refund([{"item_id": 99999, "quantity": 1}])
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_refund_zero_quantity(self):
        """退款数量为 0 被序列化器拦截."""
        self._auth_manager()
        response = self._partial_refund([{"item_id": self.item_id, "quantity": 0}])
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=10001)

    def test_refund_after_full_refund(self):
        """已全额退款后再退款被拒."""
        self._auth_manager()
        self._partial_refund([{"item_id": self.item_id, "quantity": 3}])

        response = self._partial_refund([{"item_id": self.item_id, "quantity": 1}])
        self.assert_failed(response, status.HTTP_400_BAD_REQUEST, expected_code=60002)

    def test_partial_refund_log(self):
        """部分退款写入操作日志."""
        self._auth_manager()
        self._partial_refund([{"item_id": self.item_id, "quantity": 1}])

        logs = OperationLog.objects.filter(
            module="transaction",
            action="refund",
            target_id=str(self.tx_id),
        )
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.detail["refund_amount"], "50.00")
        self.assertEqual(log.detail["new_status"], "partial_refunded")
        self.assertEqual(
            log.detail["items"],
            [{"item_id": self.item_id, "quantity": 1}],
        )

    @patch(
        "apps.transactions.services.refund_transaction.log_operation",
        side_effect=RuntimeError("日志写入失败"),
    )
    def test_refund_rollback_when_log_fails(self, mock_log):
        """退款日志写入失败时, 退款相关数据全部回滚."""
        self._auth_manager()

        response = self._partial_refund([{"item_id": self.item_id, "quantity": 1}])

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        mock_log.assert_called_once()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 97)

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 150)

        item = TransactionItem.objects.get(pk=self.item_id)
        self.assertEqual(item.refunded_quantity, 0)

        tx = Transaction.objects.get(pk=self.tx_id)
        self.assertEqual(tx.status, "completed")
        # 退款流水必须随事务一起回滚, 只保留原消费获得流水.
        records = PointsRecord.objects.filter(transaction_id=self.tx_id)

        self.assertEqual(records.count(), 1)

        earn_record = records.get(
            record_type=PointsRecordType.EARN,
        )
        self.assertEqual(earn_record.points_delta, 150)

        self.assertFalse(
            records.filter(
                record_type=PointsRecordType.REFUND_DEDUCT,
            ).exists()
        )


class TransactionRefundRoundingTest(TransactionTestBase):
    """退款积分累计取整测试."""

    def setUp(self):
        super().setUp()
        self._auth_manager()

        # 两件商品分别为 5.01 元和 5.00 元, 总金额 10.01 元.
        self.product.price = Decimal("5.01")
        self.product.save(update_fields=["price"])

        second_product = Product.objects.create(
            store=self.store,
            name="取整测试商品",
            price=Decimal("5.00"),
            cost=Decimal("3.00"),
            stock=100,
        )
        self.second_product = second_product

        response = self.client.post(
            reverse("transaction-list"),
            {
                "payment_method": "cash",
                "member_id": self.member.pk,
                "items": [
                    {"product_id": self.product.pk, "quantity": 1},
                    {"product_id": second_product.pk, "quantity": 1},
                ],
            },
            format="json",
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)

        self.tx_id = data["id"]
        self.item_ids = [item["id"] for item in data["items"]]

        self.assertEqual(data["total_amount"], "10.01")

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 10)

    def _partial_refund(self, item_id):
        return self.client.post(
            reverse("transaction-refund", kwargs={"pk": self.tx_id}),
            {"items": [{"item_id": item_id, "quantity": 1}]},
            format="json",
        )

    def test_split_refund_points_rounding(self):
        """10.01 元交易分两次退款, 最终必须扣回全部 10 积分."""
        # 第一次退 5.01 元, 累计应扣 5 分.
        response1 = self._partial_refund(self.item_ids[0])
        self.assert_success(response1)

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 5)

        # 第二次退 5.00 元, 累计应扣 10 分, 本次再扣 5 分.
        response2 = self._partial_refund(self.item_ids[1])
        self.assert_success(response2)

        self.member.refresh_from_db()
        self.assertEqual(self.member.points, 0)

        records = PointsRecord.objects.filter(
            transaction_id=self.tx_id,
            record_type=PointsRecordType.REFUND_DEDUCT,
        ).order_by("created_at", "pk")

        self.assertEqual(records.count(), 2)

        records = list(records)
        self.assertEqual(
            [record.points_delta for record in records],
            [-5, -5],
        )
        self.assertEqual(
            [record.points_expected_delta for record in records],
            [-5, -5],
        )
        self.assertEqual(
            [(record.points_before, record.points_after) for record in records],
            [(10, 5), (5, 0)],
        )

        tx = Transaction.objects.get(pk=self.tx_id)
        self.assertEqual(tx.status, "refunded")
