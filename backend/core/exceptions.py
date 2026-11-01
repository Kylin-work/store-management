"""
自定义业务异常 + 全局异常处理器。

所有从视图抛出的异常，最终都会被 custom_exception_handler 转成
统一响应结构：{ "code": ..., "message": ..., "data": ... }
"""

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from core.codes import BizCode


class BizException(APIException):
    """业务异常基类。视图里主动抛这个，比 return error() 更干净。"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "业务异常"
    default_code = "biz_error"

    def __init__(self, code: int, message: str, http_status: int | None = None):
        self.biz_code = code
        self.biz_message = message
        if http_status is not None:
            self.status_code = http_status
        super().__init__(detail=message)


def custom_exception_handler(exc, context):
    """DRF 全局异常处理器。先交给 DRF 默认处理，再对结果做统一包装。"""

    # 业务异常：直接按我们的结构返回
    if isinstance(exc, BizException):
        return Response(
            {
                "code": exc.biz_code,
                "message": exc.biz_message,
                "data": None,
            },
            status=exc.status_code,
        )

    # 交给 DRF 默认处理器，拿到标准 Response 或 None
    response = drf_exception_handler(exc, context)

    if response is None:
        # 未被 DRF 识别的异常（如数据库错误、代码 bug），返回 500
        return Response(
            {
                "code": BizCode.SERVER_ERROR,
                "message": "服务端异常",
                "data": None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 根据异常类型映射业务码
    if isinstance(exc, ValidationError):
        code = BizCode.PARAM_INVALID
    elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        code = BizCode.LOGIN_FAILED
    elif isinstance(exc, PermissionDenied):
        code = BizCode.PERMISSION_DENIED
    elif isinstance(exc, NotFound):
        code = BizCode.NOT_FOUND
    else:
        code = BizCode.SERVER_ERROR

    # DRF 的 ValidationError.detail 可能是 dict（字段级错误），保留在 data 里
    data = exc.detail if isinstance(exc, ValidationError) else None

    # message 取 detail 的字符串形式；dict 时给通用提示
    if isinstance(exc.detail, dict):
        message = "参数校验失败"
    elif isinstance(exc.detail, list):
        message = str(exc.detail[0]) if exc.detail else "请求失败"
    else:
        message = str(exc.detail)

    return Response(
        {
            "code": code,
            "message": message,
            "data": data,
        },
        status=response.status_code,
    )
