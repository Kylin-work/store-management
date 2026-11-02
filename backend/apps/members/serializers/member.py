"""会员序列化器."""

from decimal import Decimal

from rest_framework import serializers

from apps.members.models import Member, MemberLevel


class MemberListSerializer(serializers.ModelSerializer):
    """会员列表/详情序列化器."""

    level_display = serializers.CharField(
        source="get_level_display", read_only=True, label="等级名称"
    )

    class Meta:
        model = Member
        fields = (
            "id",
            "name",
            "phone",
            "balance",
            "points",
            "level",
            "level_display",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class MemberCreateSerializer(serializers.Serializer):
    """创建会员序列化器."""

    name = serializers.CharField(
        max_length=50, allow_blank=False, trim_whitespace=True, label="姓名"
    )
    phone = serializers.CharField(
        max_length=20, allow_blank=False, trim_whitespace=True, label="手机号"
    )

    def validate_phone(self, value):
        """同一门店内手机号唯一,由视图传入 store_id 后校验."""
        store_id = self.context.get("store_id")
        if store_id and Member.objects.filter(store_id=store_id, phone=value).exists():
            raise serializers.ValidationError("该门店下手机号已存在")
        return value

    def create(self, validated_data):
        """创建会员,余额、积分、等级用默认值."""
        return Member.objects.create(
            store_id=self.context["store_id"], **validated_data
        )


class MemberUpdateSerializer(serializers.Serializer):
    """编辑会员序列化器.仅允许改姓名和手机号."""

    name = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
        label="姓名",
    )
    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
        label="手机号",
    )

    def validate_phone(self, value):
        """同一门店内手机号唯一,排除自身."""
        store_id = self.context.get("store_id")
        qs = Member.objects.filter(store_id=store_id, phone=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("该门店下手机号已存在")
        return value

    def update(self, instance, validated_data):
        """更新会员信息."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if validated_data:
            instance.save(update_fields=(*validated_data.keys(), "updated_at"))
        return instance


class MemberRechargeSerializer(serializers.Serializer):
    """会员充值入参序列化器."""

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("50000.00"),
        label="充值金额",
    )


class MemberChangeLevelSerializer(serializers.Serializer):
    """会员等级调整序列化器."""

    level = serializers.ChoiceField(choices=MemberLevel.choices, label="等级")


class MemberAdjustPointsSerializer(serializers.Serializer):
    """会员积分调整序列化器."""

    points = serializers.IntegerField(label="调整数量, 正数增加, 负数减少")
    reason = serializers.CharField(
        max_length=200, allow_blank=False, trim_whitespace=True, label="调整原因"
    )

    def validate_points(self, value):
        if value == 0:
            raise serializers.ValidationError("调整数量不能为 0")
        return value
