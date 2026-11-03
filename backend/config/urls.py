"""项目根路由."""

from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # 认证、账号、角色与权限
    path("api/v1/", include("apps.accounts.urls")),
    # 业务模块
    path("api/v1/stores/", include("apps.stores.urls")),
    path("api/v1/menus/", include("apps.menus.urls")),
    path("api/v1/operation-logs/", include("apps.logs.urls")),
    path("api/v1/members/", include("apps.members.urls")),
    path("api/v1/products/", include("apps.products.urls")),
    path("api/v1/transactions/", include("apps.transactions.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    # API 文档
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
