"""账号管理序列化器。"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import Role, User, UserStoreRole
from apps.stores.models import Store


class StoreRoleItemSerializer(serializers.Serializer):
    """创建账号时的门店角色项。"""

    store_id = serializers.IntegerField(min_value=1, label="门店ID")
    role_code = serializers.CharField(
        max_length=50,
        allow_blank=False,
        trim_whitespace=True,
        label="角色编码",
    )


class AccountListSerializer(serializers.ModelSerializer):
    """账号列表序列化器。"""

    store_roles = serializers.SerializerMethodField(label="门店角色")

    class Meta:
        model = User
        fields = (
            "employee_code",
            "phone",
            "real_name",
            "is_active",
            "is_superuser",
            "date_joined",
            "store_roles",
        )
        read_only_fields = fields

    def get_store_roles(self, obj):
        """返回账号的全部门店角色。"""
        return [
            {
                "store_id": item.store_id,
                "store_name": item.store.name,
                "role_code": item.role.code,
                "role_name": item.role.name,
            }
            for item in obj.store_roles.select_related("store", "role").all()
        ]


class AccountCreateSerializer(serializers.Serializer):
    """创建账号序列化器。"""

    phone = serializers.CharField(
        max_length=11,
        allow_blank=False,
        label="手机号",
    )
    real_name = serializers.CharField(
        max_length=50,
        allow_blank=False,
        label="姓名",
    )
    password = serializers.CharField(
        max_length=128,
        write_only=True,
        allow_blank=False,
        trim_whitespace=False,
        label="初始密码",
    )
    store_roles = StoreRoleItemSerializer(
        many=True,
        allow_empty=False,
        label="门店角色",
    )

    def validate_phone(self, value):
        """手机号唯一性校验。"""
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("手机号已存在")
        return value

    def validate_password(self, value):
        """校验初始密码。"""
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def validate_store_roles(self, value):
        """校验门店和角色是否有效,以及门店是否重复。"""
        if not value:
            raise serializers.ValidationError("至少分配一个门店角色")

        store_ids = [item["store_id"] for item in value]

        # 同一账号在同一门店只能分配一个角色
        if len(store_ids) != len(set(store_ids)):
            raise serializers.ValidationError("同一门店只能分配一个角色")

        # 校验门店
        existing_store_ids = set(
            Store.objects.filter(
                pk__in=store_ids,
                is_active=True,
            ).values_list("pk", flat=True)
        )

        missing_store_ids = set(store_ids) - existing_store_ids
        if missing_store_ids:
            raise serializers.ValidationError(
                f"门店不存在或已停用：{sorted(missing_store_ids)}"
            )

        # 校验角色,并缓存角色对象,避免 create 时逐条查询
        role_codes = {item["role_code"] for item in value}
        roles = Role.objects.filter(
            code__in=role_codes,
            is_active=True,
        )

        self._roles_by_code = {role.code: role for role in roles}

        missing_role_codes = role_codes - set(self._roles_by_code)
        if missing_role_codes:
            raise serializers.ValidationError(
                f"角色不存在或已停用：{sorted(missing_role_codes)}"
            )

        return value

    def create(self, validated_data):
        """创建账号并分配门店角色。"""
        store_roles = validated_data.pop("store_roles")
        password = validated_data.pop("password")

        user = User.objects.create_user(
            employee_code=None,
            password=password,
            **validated_data,
        )

        UserStoreRole.objects.bulk_create(
            [
                UserStoreRole(
                    user=user,
                    store_id=item["store_id"],
                    role=self._roles_by_code[item["role_code"]],
                )
                for item in store_roles
            ]
        )

        return user


class AccountUpdateSerializer(serializers.Serializer):
    """编辑账号序列化器。"""

    phone = serializers.CharField(
        max_length=11,
        required=False,
        allow_blank=False,
        label="手机号",
    )
    real_name = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=False,
        label="姓名",
    )
    password = serializers.CharField(
        max_length=128,
        required=False,
        write_only=True,
        allow_blank=False,
        trim_whitespace=False,
        label="新密码",
    )

    def validate_phone(self, value):
        """手机号唯一性校验,排除当前账号。"""
        queryset = User.objects.filter(phone=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("手机号已存在")

        return value

    def validate_password(self, value):
        """校验新密码。"""
        try:
            validate_password(value, user=self.instance)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

        return value

    def update(self, instance, validated_data):
        """更新账号信息。"""
        update_fields = []

        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            update_fields.append(attr)

        if password is not None:
            instance.set_password(password)
            update_fields.append("password")

        if update_fields:
            instance.save(update_fields=update_fields)

        return instance
