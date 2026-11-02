"""角色管理序列化器。"""

from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Permission, Role


class PermissionItemSerializer(serializers.ModelSerializer):
    """权限码项。"""

    class Meta:
        model = Permission
        fields = ("id", "code", "name", "module", "is_active")
        read_only_fields = fields


class RoleListSerializer(serializers.ModelSerializer):
    """角色列表序列化器。"""

    permissions = PermissionItemSerializer(
        many=True,
        read_only=True,
        label="权限码",
    )
    user_count = serializers.IntegerField(
        read_only=True,
        label="关联用户数",
    )

    class Meta:
        model = Role
        fields = (
            "id",
            "code",
            "name",
            "is_system",
            "is_active",
            "permissions",
            "user_count",
        )
        read_only_fields = fields


class BaseRoleSerializer(serializers.Serializer):
    """角色序列化器基础类。"""

    @staticmethod
    def validate_permission_code_list(value):
        """校验权限码是否存在且启用,并去重。"""
        permission_codes = list(dict.fromkeys(value))

        if not permission_codes:
            return []

        existing_codes = set(
            Permission.objects.filter(
                code__in=permission_codes,
                is_active=True,
            ).values_list("code", flat=True)
        )

        missing_codes = set(permission_codes) - existing_codes

        if missing_codes:
            raise serializers.ValidationError(
                f"权限码不存在或已停用：{sorted(missing_codes)}"
            )

        return permission_codes

    @staticmethod
    def set_permissions(role, permission_codes):
        """全量替换角色权限。"""
        permissions = Permission.objects.filter(
            code__in=permission_codes,
        )
        role.permissions.set(permissions)


class RoleCreateSerializer(BaseRoleSerializer):
    """创建角色序列化器。"""

    code = serializers.CharField(
        max_length=50,
        allow_blank=False,
        trim_whitespace=True,
        label="角色编码",
    )
    name = serializers.CharField(
        max_length=50,
        allow_blank=False,
        trim_whitespace=True,
        label="角色名称",
    )
    permission_codes = serializers.ListField(
        child=serializers.CharField(
            max_length=100,
            allow_blank=False,
            trim_whitespace=True,
        ),
        allow_empty=True,
        default=list,
        label="权限码列表",
    )

    def validate_code(self, value):
        """角色编码统一小写并校验唯一性。"""
        value = value.strip().lower()

        if Role.objects.filter(code=value).exists():
            raise serializers.ValidationError("角色编码已存在")

        return value

    def validate_name(self, value):
        """角色名称唯一性校验。"""
        value = value.strip()

        if Role.objects.filter(name=value).exists():
            raise serializers.ValidationError("角色名称已存在")

        return value

    def validate_permission_codes(self, value):
        """校验权限码。"""
        return self.validate_permission_code_list(value)

    @transaction.atomic
    def create(self, validated_data):
        """创建角色并分配权限。"""
        permission_codes = validated_data.pop("permission_codes", [])

        role = Role.objects.create(**validated_data)

        self.set_permissions(role, permission_codes)

        return role


class RoleUpdateSerializer(BaseRoleSerializer):
    """编辑角色序列化器。"""

    name = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
        label="角色名称",
    )
    is_active = serializers.BooleanField(
        required=False,
        label="是否启用",
    )
    permission_codes = serializers.ListField(
        child=serializers.CharField(
            max_length=100,
            allow_blank=False,
            trim_whitespace=True,
        ),
        required=False,
        allow_empty=True,
        label="权限码列表",
    )

    def validate_name(self, value):
        """角色名称唯一性校验。"""
        value = value.strip()

        queryset = Role.objects.filter(name=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("角色名称已存在")

        return value

    def validate_permission_codes(self, value):
        """校验权限码。"""
        return self.validate_permission_code_list(value)

    @transaction.atomic
    def update(self, instance, validated_data):
        """更新角色,权限码全量替换。"""
        permission_codes = validated_data.pop("permission_codes", None)

        update_fields = []

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            update_fields.append(attr)

        if update_fields:
            instance.save(update_fields=update_fields)

        if permission_codes is not None:
            self.set_permissions(instance, permission_codes)

        return instance
