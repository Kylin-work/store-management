"""项目根路由。"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.stores.urls")),
    path("api/v1/", include("apps.menus.urls")),
]
