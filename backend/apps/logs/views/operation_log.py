"""操作日志查询视图。"""

from datetime import datetime

from core.codes import BizCode
from core.exceptions import BizException
from core.pagination import StandardPagination
from core.responses import success
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.logs.models import OperationLog
from apps.logs.serializers.operation_log import OperationLogSerializer
from apps.stores.permissions.store import IsSuperUser


def _parse_datetime(value: str, field_name: str) -> datetime:
    """解析 ISO 8601 时间字符串,失败时抛业务异常。"""
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise BizException(
            code=BizCode.PARAM_INVALID,
            message=f"{field_name} 格式错误,应为 ISO 8601",
        ) from exc


class OperationLogListView(APIView):
    """操作日志列表,平台管理员专属。"""

    permission_classes = (IsAuthenticated, IsSuperUser)

    def get(self, request):
        """查询操作日志,支持按模块、动作、操作人、时间范围筛选。"""
        queryset = OperationLog.objects.select_related("user", "store").order_by(
            "-created_at"
        )

        # 筛选：模块
        module = request.query_params.get("module")
        if module:
            queryset = queryset.filter(module=module)

        # 筛选：动作
        action = request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # 筛选：操作人工号
        user_employee_code = request.query_params.get("user_employee_code")
        if user_employee_code:
            queryset = queryset.filter(user__employee_code=user_employee_code)

        # 筛选：时间范围
        start_time = request.query_params.get("start_time")
        if start_time:
            queryset = queryset.filter(
                created_at__gte=_parse_datetime(start_time, "start_time")
            )

        end_time = request.query_params.get("end_time")
        if end_time:
            queryset = queryset.filter(
                created_at__lte=_parse_datetime(end_time, "end_time")
            )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = OperationLogSerializer(page, many=True)

        return success(
            data={
                "items": serializer.data,
                "total": paginator.page.paginator.count,
                "page": paginator.page.number,
                "page_size": paginator.get_page_size(request),
            }
        )
