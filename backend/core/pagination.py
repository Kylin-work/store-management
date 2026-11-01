"""
自定义分页器。

输出结构统一为：
{
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20
}
"""

from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 20  # 默认每页 20 条
    page_size_query_param = "page_size"  # 允许前端用 ?page_size=50 覆盖
    max_page_size = 100  # 单页上限，防止一次拉太多

    def get_paginated_response(self, data):
        """重写分页响应结构，字段名与前端约定一致。"""
        return Response(
            OrderedDict(
                [
                    ("items", data),  # 当前页数据
                    ("total", self.page.paginator.count),  # 总条数
                    ("page", self.page.number),  # 当前页码
                    ("page_size", self.get_page_size(self.request)),  # 实际每页条数
                ]
            )
        )
