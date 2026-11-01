"""
门店选项序列化器。

仅返回前端门店选择所需的最小字段，
不暴露门店地址、联系方式等非必要信息。
"""

from rest_framework import serializers

from apps.stores.models import Store


class StoreOptionSerializer(serializers.ModelSerializer):
    """门店选项序列化器。"""

    store_type_display = serializers.CharField(
        source="get_store_type_display",
        read_only=True,
        label="门店类型名称",
    )

    class Meta:
        model = Store
        fields = (
            "id",
            "code",
            "name",
            "store_type",
            "store_type_display",
        )
        read_only_fields = fields
