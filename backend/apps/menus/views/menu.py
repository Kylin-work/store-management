"""菜单视图。"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.menus.models import Menu
from apps.menus.serializers.menu import MenuTreeSerializer
from core.responses import success


def _build_menu_tree(menus, perm_set, is_superuser):
    """按权限过滤并组装菜单树。

    menus: 已按 sort 排序的全部启用菜单
    perm_set: 当前用户权限码集合,超级管理员传 None
    is_superuser: 是否超级管理员
    """
    # 按 parent_id 分组
    children_map: dict[int | None, list[Menu]] = {}
    for menu in menus:
        children_map.setdefault(menu.parent_id, []).append(menu)

    def _filter_and_build(parent_id):
        result = []
        for menu in children_map.get(parent_id, []):
            # 权限过滤：超级管理员全放行；无权限码的菜单放行；有权限码需在集合内
            if (
                not is_superuser
                and menu.permission_code
                and menu.permission_code not in perm_set
            ):
                continue

            # 递归处理子菜单
            filtered_children = _filter_and_build(menu.id)

            # 父菜单有子菜单配置但全部被过滤,且父菜单自身无路由,则剔除
            has_children_configured = bool(children_map.get(menu.id))
            if has_children_configured and not filtered_children and not menu.path:
                continue

            menu._filtered_children = filtered_children
            result.append(menu)
        return result

    return _filter_and_build(None)


class MenuListView(APIView):
    """当前用户可见菜单树。"""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """返回按权限过滤后的菜单树。"""
        menus = list(Menu.objects.filter(is_active=True).order_by("sort", "id"))

        if request.user.is_superuser:
            tree = _build_menu_tree(menus, perm_set=set(), is_superuser=True)
        else:
            perm_set = getattr(request, "perm_set", None) or set()
            tree = _build_menu_tree(menus, perm_set=perm_set, is_superuser=False)

        serializer = MenuTreeSerializer(tree, many=True)
        return success(data=serializer.data)
