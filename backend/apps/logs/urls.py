"""logs 路由."""

from django.urls import path

from apps.logs.views.operation_log import OperationLogListView

urlpatterns = [
    path("operation-logs/", OperationLogListView.as_view(), name="operation-log-list"),
]
