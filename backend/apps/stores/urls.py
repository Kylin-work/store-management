"""stores 路由."""

from django.urls import path

from apps.stores.views.store import StoreOptionListView
from apps.stores.views.store_manage import (
    StoreManageDetailView,
    StoreManageListCreateView,
    StoreManageStatusView,
)

urlpatterns = [
    # 公开：登录页选门店
    path("stores/", StoreOptionListView.as_view(), name="store-list"),
    # 管理端：平台管理员
    path(
        "stores/manage/", StoreManageListCreateView.as_view(), name="store-manage-list"
    ),
    path(
        "stores/manage/<int:pk>/",
        StoreManageDetailView.as_view(),
        name="store-manage-detail",
    ),
    path(
        "stores/manage/<int:pk>/status/",
        StoreManageStatusView.as_view(),
        name="store-manage-status",
    ),
]
