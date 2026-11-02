"""操作日志记录函数。

业务视图在关键操作成功后显式调用 log_operation,记录审计日志。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.logs.models import OperationLog

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.stores.models import Store


def log_operation(
    *,
    user: User,
    module: str,
    action: str,
    target_type: str,
    target_id: str,
    store: Store | None = None,
    detail: dict[str, Any] | None = None,
) -> OperationLog:
    """记录一条操作日志。

    user: 操作人
    module: 模块,如 account、role、store
    action: 动作,如 create、update、disable
    target_type: 对象类型,如 User、Role、Store
    target_id: 对象业务标识,如工号、角色编码、门店 ID
    store: 操作发生的门店,平台管理员操作时传 None
    detail: 业务语义变更详情
    """
    return OperationLog.objects.create(
        user=user,
        store=store,
        module=module,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail or {},
    )


def get_operator_store(user: User) -> Store | None:
    """从请求上下文推断操作发生的门店。

    当前实现：从 JWT payload 的 store_id 读,由视图传入。
    这里只作为占位,实际门店上下文由视图从 request.store_id 拿。
    """
    return None
