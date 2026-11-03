"""商品序列化器."""

from rest_framework import serializers

from apps.products.models import Product


class ProductListSerializer(serializers.ModelSerializer):
    """商品列表/详情序列化器.

    成本价(cost)仅对有 product:edit_cost 权限的用户可见.
    """

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "barcode",
            "price",
            "cost",
            "stock",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        if request is None:
            return

        # 超级管理员和拥有 edit_cost 权限的用户能看到成本价
        if request.user.is_superuser:
            return
        perm_set = getattr(request, "perm_set", None) or set()
        if "product:edit_cost" not in perm_set:
            self.fields.pop("cost", None)


class ProductCreateSerializer(serializers.Serializer):
    """创建商品序列化器."""

    name = serializers.CharField(
        max_length=100, allow_blank=False, trim_whitespace=True, label="商品名称"
    )
    barcode = serializers.CharField(
        max_length=50, required=False, allow_blank=True, label="条码"
    )
    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, label="售价"
    )
    cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, label="成本价"
    )
    stock = serializers.IntegerField(min_value=0, default=0, label="库存")

    def validate_name(self, value):
        """同一门店内商品名称唯一."""
        store_id = self.context.get("store_id")
        if store_id and Product.objects.filter(store_id=store_id, name=value).exists():
            raise serializers.ValidationError("该门店下商品名称已存在")
        return value

    def create(self, validated_data):
        """创建商品."""
        return Product.objects.create(
            store_id=self.context["store_id"], **validated_data
        )


class ProductUpdateSerializer(serializers.Serializer):
    """编辑商品序列化器.

    名称、条码、售价所有人可改;
    成本价只有拥有 product:edit_cost 权限的人能改.
    库存只能通过专用库存调整接口修改.
    """

    name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
        label="商品名称",
    )
    barcode = serializers.CharField(
        max_length=50, required=False, allow_blank=True, label="条码"
    )
    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, label="售价"
    )
    cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, label="成本价"
    )

    def validate_name(self, value):
        """同一门店内商品名称唯一，排除自身."""
        store_id = self.context.get("store_id")
        qs = Product.objects.filter(store_id=store_id, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("该门店下商品名称已存在")
        return value

    def validate(self, attrs):
        """校验库存修改和成本价修改权限."""
        if "stock" in self.initial_data:
            raise serializers.ValidationError({"stock": ["请通过库存调整接口修改库存"]})

        if "cost" in attrs:
            request = self.context.get("request")
            if request and not request.user.is_superuser:
                perm_set = getattr(request, "perm_set", None) or set()
                if "product:edit_cost" not in perm_set:
                    raise serializers.ValidationError({"cost": ["无权限修改成本价"]})
        return attrs

    def update(self, instance, validated_data):
        """更新商品信息."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if validated_data:
            instance.save(update_fields=(*validated_data.keys(), "updated_at"))
        return instance


class ProductAdjustStockSerializer(serializers.Serializer):
    """商品库存调整序列化器."""

    quantity = serializers.IntegerField(label="调整数量, 正数入库, 负数出库")
    reason = serializers.CharField(
        max_length=200, allow_blank=False, trim_whitespace=True, label="调整原因"
    )

    def validate_quantity(self, value):
        if value == 0:
            raise serializers.ValidationError("调整数量不能为 0")
        return value
