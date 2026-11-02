"""
统一响应封装。

成功：{ "code": 0, "message": "ok", "data": ... }
错误：{ "code": 10001, "message": "无权操作", "data": null }
"""

from rest_framework import status
from rest_framework.response import Response

from core.codes import BizCode


def success(
    data=None, message: str = "ok", http_status: int = status.HTTP_200_OK
) -> Response:
    """成功响应。默认 HTTP 200,创建类接口可传 201。"""
    return Response(
        {
            "code": BizCode.OK,
            "message": message,
            "data": data,
        },
        status=http_status,
    )


def error(
    code: int,
    message: str,
    data=None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    """错误响应。业务码与 HTTP 状态码分开传入,默认 HTTP 400。"""
    return Response(
        {
            "code": code,
            "message": message,
            "data": data,
        },
        status=http_status,
    )
