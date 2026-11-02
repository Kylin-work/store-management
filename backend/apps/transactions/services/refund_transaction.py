"""退款业务逻辑.

退款涉及回滚库存, 扣回积分, 改交易状态, 写操作日志,
必须在同一事务内完成.
"""

from django.db import transaction

from apps.logs.services.logger import log_operation
from apps.members.models import Member
from apps.products.models import Product
from apps.transactions.models import Transaction, TransactionStatus
from core.codes import BizCode
from core.exceptions import BizException

# 与创建交易时的积分规则保持一致
POINTS_PER_YUAN = 1


def refund_transaction(*, transaction_id: int, store_id: int, staff) -> Transaction:
    """全额退款.

    transaction_id: 交易 ID
    store_id: 门店 ID, 用于数据隔离
    staff: 经办人 (仅店长)
    """
    with transaction.atomic():
        # 锁定交易行
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
                message="该交易已退款",
            )

        # 回滚库存: 锁定商品行, 按 pk 排序避免死锁
        items = list(tx.items.select_related("product").order_by("product_id"))
        product_ids = sorted({item.product_id for item in items})

        products = {
            p.pk: p
            for p in Product.objects.select_for_update()
            .filter(pk__in=product_ids)
            .order_by("pk")
        }

        for item in items:
            product = products[item.product_id]
            product.stock += item.quantity
            product.save(update_fields=("stock", "updated_at"))

        # 扣回积分 (如果关联会员)
        points_deducted = 0
        if tx.member_id is not None:
            member = Member.objects.select_for_update().get(pk=tx.member_id)
            points_to_deduct = int(tx.total_amount * POINTS_PER_YUAN)
            # 不扣成负数
            points_deducted = min(points_to_deduct, member.points)
            if points_deducted > 0:
                member.points -= points_deducted
                member.save(update_fields=("points", "updated_at"))

        # 改交易状态
        tx.status = TransactionStatus.REFUNDED
        tx.save(update_fields=("status",))

        # 操作日志
        log_operation(
            user=staff,
            module="transaction",
            action="refund",
            target_type="Transaction",
            target_id=str(tx.pk),
            detail={
                "total_amount": str(tx.total_amount),
                "member_id": tx.member_id,
                "points_deducted": points_deducted,
                "items": [
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                    }
                    for item in items
                ],
            },
        )

        return tx

