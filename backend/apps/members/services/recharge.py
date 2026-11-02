"""会员充值业务逻辑.

充值涉及改余额、写充值记录、写操作日志,必须在同一事务内完成.
"""

from decimal import Decimal

from django.db import transaction

from apps.logs.services.logger import log_operation
from apps.members.models import Member, RechargeRecord
from core.codes import BizCode
from core.exceptions import BizException

# 单笔充值金额上限,防止误操作
MAX_RECHARGE_AMOUNT = Decimal("50000.00")
MIN_RECHARGE_AMOUNT = Decimal("0.01")


def recharge_member(
    *,
    member_id: int,
    amount: Decimal,
    staff,
    store_id: int,
) -> RechargeRecord:
    """为会员充值.

    member_id: 会员 ID
    amount: 充值金额,必须为正数,且不超过单笔上限
    staff: 经办人(User 实例)
    store_id: 门店 ID,用于校验会员归属和数据隔离
    """
    if amount < MIN_RECHARGE_AMOUNT:
        raise BizException(
            code=BizCode.PARAM_INVALID,
            message=f"充值金额不能小于 {MIN_RECHARGE_AMOUNT}",
        )
    if amount > MAX_RECHARGE_AMOUNT:
        raise BizException(
            code=BizCode.PARAM_INVALID,
            message=f"单笔充值金额不能超过 {MAX_RECHARGE_AMOUNT}",
        )

    with transaction.atomic():
        # 锁定会员行,防止并发充值导致余额覆盖
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
                message="会员已停用,不能充值",
            )

        balance_before = member.balance
        member.balance = member.balance + amount
        member.save(update_fields=("balance", "updated_at"))

        record = RechargeRecord.objects.create(
            member=member,
            staff=staff,
            amount=amount,
            balance_before=balance_before,
            balance_after=member.balance,
        )

        log_operation(
            user=staff,
            module="member",
            action="recharge",
            target_type="Member",
            target_id=str(member.pk),
            detail={
                "amount": str(amount),
                "balance_before": str(balance_before),
                "balance_after": str(member.balance),
            },
        )

        return record
