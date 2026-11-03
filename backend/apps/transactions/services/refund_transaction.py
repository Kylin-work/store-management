"""退款业务逻辑.

支持部分退款和全额退款.
退款涉及回滚库存, 扣回积分, 更新交易状态, 写操作日志,
必须在同一事务内完成.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.logs.services.logger import log_operation
from apps.members.models import Member, PointsRecord, PointsRecordType
from apps.products.models import Product
from apps.transactions.models import Transaction, TransactionStatus
from core.codes import BizCode
from core.exceptions import BizException

# 与创建交易时的积分规则保持一致
POINTS_PER_YUAN = 1


def refund_transaction(
    *,
    transaction_id: int,
    store_id: int,
    staff,
    items: list[dict] | None = None,
) -> Transaction:
    """退款.

    transaction_id: 交易 ID
    store_id: 门店 ID, 用于数据隔离
    staff: 经办人 (仅店长)
    items: 退款明细列表, 每项形如 {"item_id": int, "quantity": int}.
           传 None 表示全额退款所有明细.
    """
    with transaction.atomic():
        # 锁定交易行, 保证同一交易的退款串行执行
        tx = (
            Transaction.objects.select_for_update()
            .filter(pk=transaction_id, store_id=store_id)
            .first()
        )
        if tx is None:
            raise BizException(
                code=BizCode.TRANSACTION_NOT_FOUND,
                message="交易不存在",
                http_status=404,
            )
        if tx.status == TransactionStatus.REFUNDED:
            raise BizException(
                code=BizCode.TRANSACTION_STATUS_INVALID,
                message="该交易已全额退款",
            )

        # 确定要退的明细
        tx_items = list(tx.items.select_related("product").order_by("id"))

        if items is None:
            refund_map = {
                item.pk: item.quantity - item.refunded_quantity
                for item in tx_items
                if item.quantity > item.refunded_quantity
            }
        else:
            refund_map = {}
            item_dict = {item.pk: item for item in tx_items}
            for req in items:
                item_id = req.get("item_id")
                qty = req.get("quantity", 0)
                if item_id not in item_dict:
                    raise BizException(
                        code=BizCode.PARAM_INVALID,
                        message=f"明细 {item_id} 不属于该交易",
                    )
                if qty <= 0:
                    raise BizException(
                        code=BizCode.PARAM_INVALID,
                        message="退款数量必须大于 0",
                    )
                item = item_dict[item_id]
                remaining = item.quantity - item.refunded_quantity
                if qty > remaining:
                    raise BizException(
                        code=BizCode.PARAM_INVALID,
                        message=f"明细 {item_id} 可退数量为 {remaining}, 请求退 {qty}",
                    )
                if item_id in refund_map:
                    raise BizException(
                        code=BizCode.PARAM_INVALID,
                        message=f"明细 {item_id} 重复提交",
                    )
                refund_map[item_id] = qty

        if not refund_map:
            raise BizException(
                code=BizCode.PARAM_INVALID,
                message="没有可退款的明细",
            )

        # 锁定商品行, 按 pk 排序避免死锁
        product_ids = sorted(
            {item.product_id for item in tx_items if item.pk in refund_map}
        )
        products = {
            p.pk: p
            for p in Product.objects.select_for_update()
            .filter(pk__in=product_ids)
            .order_by("pk")
        }

        # 执行退款: 回滚库存, 更新 refunded_quantity, 计算本次退款金额
        refund_amount = Decimal("0.00")
        for item in tx_items:
            if item.pk not in refund_map:
                continue
            qty = refund_map[item.pk]
            product = products[item.product_id]
            product.stock += qty
            product.save(update_fields=("stock", "updated_at"))
            item.refunded_quantity += qty
            item.save(update_fields=("refunded_quantity",))
            refund_amount += item.unit_price * qty

        # 扣回积分 (如果关联会员)
        points_deducted = 0
        if tx.member_id is not None and tx.total_amount > 0:
            member = Member.objects.select_for_update().get(pk=tx.member_id)

            # 查找原交易的消费获得流水.
            # 新交易通过流水计算累计应扣积分; 历史交易兼容旧算法.
            earn_record = PointsRecord.objects.filter(
                earn_transaction=tx,
                record_type=PointsRecordType.EARN,
            ).first()

            if earn_record is not None:
                # 根据所有明细的累计退款数量计算累计退款金额.
                cumulative_refund_amount = sum(
                    (item.unit_price * item.refunded_quantity for item in tx_items),
                    Decimal("0.00"),
                )

                # 累计应扣积分向下取整.
                cumulative_points_to_deduct = int(
                    cumulative_refund_amount
                    / tx.total_amount
                    * earn_record.points_delta
                )

                # 此前退款流水记录的是实际扣回积分, 而不是预期扣回积分.
                previous_refund_delta = (
                    PointsRecord.objects.filter(
                        transaction=tx,
                        record_type=PointsRecordType.REFUND_DEDUCT,
                    ).aggregate(total=Sum("points_delta"))["total"]
                    or 0
                )
                previously_deducted = -previous_refund_delta

                # 本次预期扣回 = 累计应扣 - 此前实际扣回.
                points_to_deduct = max(
                    0,
                    cumulative_points_to_deduct - previously_deducted,
                )

                points_before = member.points
                points_deducted = min(points_to_deduct, points_before)
                points_after = points_before - points_deducted

                if points_deducted > 0:
                    member.points = points_after
                    member.save(update_fields=("points", "updated_at"))

                # 预期扣回大于实际扣回时也记录流水, 保留积分不足的差额.
                if points_to_deduct > 0:
                    PointsRecord.objects.create(
                        member=member,
                        staff=staff,
                        transaction=tx,
                        record_type=PointsRecordType.REFUND_DEDUCT,
                        points_delta=-points_deducted,
                        points_expected_delta=-points_to_deduct,
                        points_before=points_before,
                        points_after=points_after,
                        reason="交易退款扣回积分",
                    )

            else:
                # 历史交易没有消费获得流水, 保留旧算法,
                # 避免将上线前已经扣回的积分重复纳入累计计算.
                total_points_earned = int(tx.total_amount * POINTS_PER_YUAN)
                points_to_deduct = int(
                    refund_amount / tx.total_amount * total_points_earned
                )
                points_deducted = min(points_to_deduct, member.points)

                if points_deducted > 0:
                    member.points -= points_deducted
                    member.save(update_fields=("points", "updated_at"))

        # 更新交易状态
        all_refunded = all(item.refunded_quantity >= item.quantity for item in tx_items)
        if all_refunded:
            tx.status = TransactionStatus.REFUNDED
        else:
            tx.status = TransactionStatus.PARTIAL_REFUNDED
        tx.save(update_fields=("status",))

        # 操作日志
        log_operation(
            user=staff,
            module="transaction",
            action="refund",
            target_type="Transaction",
            target_id=str(tx.pk),
            detail={
                "refund_amount": str(refund_amount),
                "member_id": tx.member_id,
                "points_deducted": points_deducted,
                "items": [
                    {
                        "item_id": item.pk,
                        "quantity": refund_map[item.pk],
                    }
                    for item in tx_items
                    if item.pk in refund_map
                ],
                "new_status": tx.status,
            },
        )

        return tx
