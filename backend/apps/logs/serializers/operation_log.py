"""操作日志序列化器。"""

from rest_framework import serializers

from apps.logs.models import OperationLog


class OperationLogSerializer(serializers.ModelSerializer):
    """操作日志列表序列化器。"""

    user_employee_code = serializers.CharField(
        source="user.employee_code", read_only=True, label="操作人工号"
    )
    user_real_name = serializers.CharField(
        source="user.real_name", read_only=True, label="操作人姓名"
    )
    store_name = serializers.CharField(
        source="store.name", read_only=True, default=None, label="门店名称"
    )

    class Meta:
        model = OperationLog
        fields = (
            "id",
            "user_employee_code",
            "user_real_name",
            "store_name",
            "module",
            "action",
            "target_type",
            "target_id",
            "detail",
            "created_at",
        )
        read_only_fields = fields
