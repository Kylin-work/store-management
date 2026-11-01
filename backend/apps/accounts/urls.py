"""accounts 路由。"""

from django.urls import path

from apps.accounts.views.account import (
    AccountDetailView,
    AccountListCreateView,
    AccountStatusView,
    AccountStoreRolesView,
)
from apps.accounts.views.login import LoginView
from apps.accounts.views.me import MeView
from apps.accounts.views.role import (
    PermissionListView,
    RoleDetailView,
    RoleListCreateView,
)

urlpatterns = [
    # 认证
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    # 账号管理
    path("accounts/", AccountListCreateView.as_view(), name="account-list"),
    path(
        "accounts/<str:employee_code>/",
        AccountDetailView.as_view(),
        name="account-detail",
    ),
    path(
        "accounts/<str:employee_code>/status/",
        AccountStatusView.as_view(),
        name="account-status",
    ),
    path(
        "accounts/<str:employee_code>/store-roles/",
        AccountStoreRolesView.as_view(),
        name="account-store-roles",
    ),
    # 角色管理
    path("roles/", RoleListCreateView.as_view(), name="role-list"),
    path("roles/<str:code>/", RoleDetailView.as_view(), name="role-detail"),
    # 权限码
    path("permissions/", PermissionListView.as_view(), name="permission-list"),
]
