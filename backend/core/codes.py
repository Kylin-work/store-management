"""
业务码常量.

与 HTTP 状态码分离：HTTP 状态码表达"请求是否成功",
业务码表达"业务层面的具体结果",前端根据业务码做提示.

约定：
- 0 表示成功
- 1xxxx 通用错误
- 2xxxx 账号/认证相关
- 3xxxx 门店相关
- 4xxxx 会员相关
- 5xxxx 商品相关
- 6xxxx 交易相关
"""


class BizCode:
    """业务码命名空间,集中管理避免魔法数字散落."""

    OK = 0  # 成功

    # --- 通用错误 ---
    PARAM_INVALID = 10001  # 参数校验失败
    PERMISSION_DENIED = 10002  # 无权限
    NOT_FOUND = 10003  # 资源不存在
    SERVER_ERROR = 10004  # 服务端异常

    # --- 账号/认证 ---
    LOGIN_FAILED = 20001  # 工号或密码错误
    ACCOUNT_DISABLED = 20002  # 账号已停用
    STORE_NOT_ASSIGNED = 20003  # 未分配所选门店

    # --- 门店 ---
    STORE_NOT_FOUND = 30001  # 门店不存在
    STORE_DISABLED = 30002  # 门店已停用

    # --- 会员 ---
    MEMBER_NOT_FOUND = 40001  # 会员不存在
    MEMBER_BALANCE_INSUFFICIENT = 40002  # 余额不足
    MEMBER_CROSS_STORE = 40003  # 跨门店操作会员

    # --- 商品 ---
    PRODUCT_NOT_FOUND = 50001  # 商品不存在
    PRODUCT_STOCK_INSUFFICIENT = 50002  # 库存不足

    # --- 交易 ---
    TRANSACTION_NOT_FOUND = 60001  # 交易不存在
    TRANSACTION_STATUS_INVALID = 60002  # 交易状态不允许该操作
