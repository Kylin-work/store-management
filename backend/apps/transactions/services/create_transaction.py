"""创建交易业务逻辑.

创建交易涉及扣库存、算积分、写交易记录、写明细、写操作日志,
必须在同一事务内完成.
"""

from decimal import Decimal

from django.db import transaction

from apps.logs.services.logger import log_operation
from apps.members.models import (
    Member,
    PointsRecord,
    PointsRecordType,
)
from apps.products.models import Product
from apps.transactions.models import (
    Transaction,
    TransactionItem,
    TransactionStatus,
)
from core.codes import BizCode
from core.exceptions import BizException

# 积分规则: 消费 1 元得 1 积分, 向下取整
POINTS_PER_YUAN = 1


def create_transaction(
    *,
    store_id: int,
    staff,
    items: list[dict],
    payment_method: str,
    member_id: int | None = None,
) -> Transaction:
    """创建交易.

    store_id: 门店 ID
    staff: 经办店员
    items: 商品明细列表, 每项形如 {"product_id": int, "quantity": int}
    payment_method: 支付方式
    member_id: 会员 ID, 散客交易传 None
    """
    if not items:
        raise BizException(
            code=BizCode.PARAM_INVALID,
            message="交易明细不能为空",
        )

    with transaction.atomic():
        # 锁定会员 (如果有关联)
        member = None
        if member_id is not None:
            member = (
                Member.objects.select_for_update()
                .filter(pk=member_id, store_id=store_id)
                .first()
            )
            if member is None:
                raise BizException(
                    code=BizCode.MEMBER_NOT_FOUND,
                    message="会员不存在或不属于当前门店",
                    http_status=404,
                )
            if not member.is_active:
                raise BizException(
                    code=BizCode.PARAM_INVALID,
                    message="会员已停用",
                )

        # 按商品 ID 汇总数量 (同一商品出现多次时合并)
        quantity_map: dict[int, int] = {}
        for item in items:
            product_id = item["product_id"]
            quantity = item["quantity"]
            if quantity <= 0:
                raise BizException(
                    code=BizCode.PARAM_INVALID,
                    message=f"商品 {product_id} 数量必须大于 0",
                )
            quantity_map[product_id] = quantity_map.get(product_id, 0) + quantity

        # 锁定商品行, 按 ID 排序避免死锁
        product_ids = sorted(quantity_map.keys())
        products = {
            p.pk: p
            for p in Product.objects.select_for_update()
            .filter(pk__in=product_ids, store_id=store_id)
            .order_by("pk")
        }

        # 校验商品存在, 启用, 库存充足
        transaction_items = []
        total_amount = Decimal("0.00")

        for product_id in product_ids:
            product = products.get(product_id)
            if product is None:
                raise BizException(
                    code=BizCode.PRODUCT_NOT_FOUND,
                    message=f"商品 {product_id} 不存在或不属于当前门店",
                    http_status=404,
                )
            if not product.is_active:
                raise BizException(
                    code=BizCode.PARAM_INVALID,
                    message=f"商品 {product.name} 已停用",
                )

            quantity = quantity_map[product_id]
            if product.stock < quantity:
                raise BizException(
                    code=BizCode.PRODUCT_STOCK_INSUFFICIENT,
                    message=f"商品 {product.name} 库存不足, 当前库存 {product.stock}",
                )

            subtotal = product.price * quantity
            total_amount += subtotal

            transaction_items.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "unit_price": product.price,
                    "subtotal": subtotal,
                }
            )

        # 创建交易
        tx = Transaction.objects.create(
            store_id=store_id,
            member=member,
            staff=staff,
            total_amount=total_amount,
            paid_amount=total_amount,
            payment_method=payment_method,
            status=TransactionStatus.COMPLETED,
        )

        # 创建明细, 扣库存
        for item in transaction_items:
            TransactionItem.objects.create(
                transaction=tx,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                subtotal=item["subtotal"],
            )
            product = item["product"]
            product.stock -= item["quantity"]
            product.save(update_fields=("stock", "updated_at"))

        # 会员积分及积分流水
        points_earned = 0
        if member is not None:
            points_earned = int(total_amount * POINTS_PER_YUAN)
            if points_earned > 0:
                points_before = member.points
                member.points += points_earned
                member.save(update_fields=("points", "updated_at"))

                PointsRecord.objects.create(
                    member=member,
                    staff=staff,
                    transaction=tx,
                    earn_transaction=tx,
                    record_type=PointsRecordType.EARN,
                    points_delta=points_earned,
                    points_expected_delta=points_earned,
                    points_before=points_before,
                    points_after=member.points,
                    reason="交易消费获得积分",
                )

        # 操作日志
        log_operation(
            user=staff,
            module="transaction",
            action="create",
            target_type="Transaction",
            target_id=str(tx.pk),
            detail={
                "total_amount": str(total_amount),
                "payment_method": payment_method,
                "member_id": member.pk if member else None,
                "points_earned": points_earned,
                "items": [
                    {
                        "product_id": item["product"].pk,
                        "quantity": item["quantity"],
                        "subtotal": str(item["subtotal"]),
                    }
                    for item in transaction_items
                ],
            },
        )

        return tx
