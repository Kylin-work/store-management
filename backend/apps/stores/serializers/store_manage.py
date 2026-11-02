"""
门店管理端序列化器。

提供门店新增、编辑及详情数据序列化。
包含门店编码、名称唯一性校验。
"""

from rest_framework import serializers

from apps.stores.models import Store


class StoreManageSerializer(serializers.ModelSerializer):
    """门店管理端序列化器。"""

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
            "address",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "store_type_display",
            "created_at",
            "updated_at",
        )

        extra_kwargs = {  # noqa: RUF012
            "code": {
                "required": True,
                "allow_blank": False,
                "trim_whitespace": True,
            },
            "name": {
                "required": True,
                "allow_blank": False,
                "trim_whitespace": True,
            },
            "store_type": {
                "required": False,
            },
        }

    def validate_code(self, value):
        """门店编码唯一性校验,统一转大写。"""

        value = value.strip().upper()

        qs = Store.objects.filter(code=value)

        # 编辑时排除当前门店
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("门店编码已存在")

        return value

    def validate_name(self, value):
        """门店名称唯一性校验。"""

        value = value.strip()

        qs = Store.objects.filter(name=value)

        # 编辑时排除当前门店
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("门店名称已存在")

        return value
