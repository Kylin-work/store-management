"""菜单接口测试."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, User, UserStoreRole
from apps.menus.models import Menu
from apps.stores.models import Store


class MenuTestBase(APITestCase):
    """菜单测试基类."""

    def setUp(self):
        throttle_patcher = patch(
            "rest_framework.throttling.ScopedRateThrottle.get_rate",
            return_value=None,
        )
        throttle_patcher.start()
        self.addCleanup(throttle_patcher.stop)

        self.url = reverse("menu-list")
        Menu.objects.all().delete()

        # 门店
        self.store = Store.objects.create(
            code="S001", name="测试门店A", store_type="direct"
        )

        # 权限码
        self.perm_member_list = Permission.objects.create(
            code="member:list", name="会员列表", module="member"
        )
        self.perm_account_list = Permission.objects.create(
            code="account:list", name="账号列表", module="account"
        )
        self.perm_dashboard = Permission.objects.create(
            code="dashboard:view", name="数据看板", module="dashboard"
        )

        # 菜单：三个有权限码的 + 一个无权限码的 + 一个停用的
        self.menu_member = Menu.objects.create(
            code="member_manage",
            name="会员管理",
            path="/members",
            permission_code="member:list",
            sort=10,
        )
        self.menu_account = Menu.objects.create(
            code="account_manage",
            name="账号管理",
            path="/accounts",
            permission_code="account:list",
            sort=90,
        )
        self.menu_dashboard = Menu.objects.create(
            code="dashboard_view",
            name="数据看板",
            path="/dashboard",
            permission_code="dashboard:view",
            sort=40,
        )
        self.menu_public = Menu.objects.create(
            code="public_home",
            name="首页",
            path="/home",
            permission_code="",
            sort=0,
        )
        self.menu_disabled = Menu.objects.create(
            code="disabled_menu",
            name="停用菜单",
            path="/disabled",
            permission_code="",
            sort=999,
            is_active=False,
        )

        # 角色：店长拥有 member:list 和 account:list
        self.role = Role.objects.create(code="store_manager", name="店长")
        self.role.permissions.set([self.perm_member_list, self.perm_account_list])

        # 无权限角色
        self.empty_role = Role.objects.create(code="staff", name="店员")

        # 用户
        self.superuser = User.objects.create_superuser(
            employee_code=None,
            password="Admin@123456",
            phone="13900000001",
            real_name="超级管理员",
        )

        self.manager = User.objects.create_user(
            employee_code=None,
            password="Manager@123456",
            phone="13800000001",
            real_name="店长",
        )
        UserStoreRole.objects.create(
            user=self.manager, store=self.store, role=self.role
        )

        self.staff = User.objects.create_user(
            employee_code=None,
            password="Staff@123456",
            phone="13800000002",
            real_name="店员",
        )
        UserStoreRole.objects.create(
            user=self.staff, store=self.store, role=self.empty_role
        )

    def _make_token(self, user, store_id=None, role_code=None):
        refresh = RefreshToken.for_user(user)
        refresh["store_id"] = store_id
        refresh["role_code"] = role_code
        return str(refresh.access_token)

    def _auth_superuser(self):
        token = self._make_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _auth_manager(self):
        token = self._make_token(
            self.manager, store_id=self.store.pk, role_code=self.role.code
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _auth_staff(self):
        token = self._make_token(
            self.staff, store_id=self.store.pk, role_code=self.empty_role.code
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _get_menus(self):
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            msg=f"接口响应异常：{response.data}",
        )
        self.assertEqual(response.data["code"], 0)
        return response.data["data"]

    def _menu_codes(self, data):
        return {item["code"] for item in data}


class MenuSuccessTest(MenuTestBase):
    """菜单接口成功场景."""

    def test_superuser_sees_all_active_menus(self):
        """超级管理员看到全部启用菜单(含无权限码的),停用的不出现."""
        self._auth_superuser()
        data = self._get_menus()

        codes = self._menu_codes(data)
        self.assertIn("member_manage", codes)
        self.assertIn("account_manage", codes)
        self.assertIn("dashboard_view", codes)
        self.assertIn("public_home", codes)
        self.assertNotIn("disabled_menu", codes)

    def test_manager_sees_menus_by_permissions(self):
        """店长只看到有权限的菜单 + 无权限码的菜单."""
        self._auth_manager()
        data = self._get_menus()

        codes = self._menu_codes(data)
        self.assertIn("member_manage", codes)  # 有 member:list
        self.assertIn("account_manage", codes)  # 有 account:list
        self.assertIn("public_home", codes)  # 无权限码,所有人可见
        self.assertNotIn("dashboard_view", codes)  # 无 dashboard:view
        self.assertNotIn("disabled_menu", codes)

    def test_staff_sees_only_public_menus(self):
        """无权限用户只看到无权限码的菜单."""
        self._auth_staff()
        data = self._get_menus()

        codes = self._menu_codes(data)
        self.assertIn("public_home", codes)
        self.assertNotIn("member_manage", codes)
        self.assertNotIn("account_manage", codes)
        self.assertNotIn("dashboard_view", codes)

    def test_menu_sorted_by_sort(self):
        """菜单按 sort 升序返回."""
        self._auth_superuser()
        data = self._get_menus()

        sorts = [item["sort"] for item in data]
        self.assertEqual(sorts, sorted(sorts))

    def test_parent_without_permission_hides_authorized_child(self):
        """父菜单无权限时,即使子菜单有权限也不返回."""
        parent = Menu.objects.create(
            code="parent_menu",
            name="父菜单",
            path="",
            permission_code="dashboard:view",
            sort=200,
        )
        Menu.objects.create(
            code="child_menu",
            name="子菜单",
            path="/child",
            permission_code="member:list",
            parent=parent,
            sort=10,
        )

        self._auth_manager()
        data = self._get_menus()

        codes = self._menu_codes(data)
        self.assertNotIn("parent_menu", codes)
        self.assertNotIn("child_menu", codes)

    def test_parent_without_path_is_hidden_when_all_children_filtered(self):
        """无路由父菜单的子菜单全部被过滤时,父菜单也不返回."""
        parent = Menu.objects.create(
            code="empty_parent",
            name="空父菜单",
            path="",
            permission_code="",
            sort=200,
        )
        Menu.objects.create(
            code="hidden_child",
            name="无权限子菜单",
            path="/hidden",
            permission_code="dashboard:view",
            parent=parent,
            sort=10,
        )

        self._auth_manager()
        data = self._get_menus()

        self.assertNotIn("empty_parent", self._menu_codes(data))


class MenuFailTest(MenuTestBase):
    """菜单接口失败场景."""

    def test_anonymous_cannot_access(self):
        """未登录返回 401."""
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class MenuPermissionChangeTest(MenuTestBase):
    """权限变更后菜单实时变化."""

    def test_remove_permission_hides_menu(self):
        """摘掉权限码后,对应菜单立即消失."""
        self._auth_manager()
        data = self._get_menus()
        self.assertIn("member_manage", self._menu_codes(data))

        # 摘掉 member:list
        self.role.permissions.remove(self.perm_member_list)

        data = self._get_menus()
        self.assertNotIn("member_manage", self._menu_codes(data))

    def test_add_permission_shows_menu(self):
        """分配权限码后,对应菜单立即出现."""
        self._auth_manager()
        data = self._get_menus()
        self.assertNotIn("dashboard_view", self._menu_codes(data))

        # 分配 dashboard:view
        self.role.permissions.add(self.perm_dashboard)

        data = self._get_menus()
        self.assertIn("dashboard_view", self._menu_codes(data))
