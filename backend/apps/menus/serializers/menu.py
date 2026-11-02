"""菜单序列化器。"""

from rest_framework import serializers

from apps.menus.models import Menu


class MenuTreeSerializer(serializers.ModelSerializer):
    """菜单树序列化器,递归输出子菜单。"""

    children = serializers.SerializerMethodField(label="子菜单")

    class Meta:
        model = Menu
        fields = ("code", "name", "path", "permission_code", "sort", "children")
        read_only_fields = fields

    def get_children(self, obj):
        """递归序列化子菜单.子菜单已在视图中按权限过滤."""
        children = getattr(obj, "_filtered_children", None)
        if children is None:
            children = obj.children.filter(is_active=True)
        return MenuTreeSerializer(children, many=True, context=self.context).data
