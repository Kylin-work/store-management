"""项目根路由."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.stores.urls")),
    path("api/v1/", include("apps.menus.urls")),
    path("api/v1/", include("apps.logs.urls")),
    path("api/v1/", include("apps.members.urls")),
    path("api/v1/", include("apps.products.urls")),
    path("api/v1/", include("apps.transactions.urls")),
    path("api/v1/", include("apps.dashboard.urls")),
]
