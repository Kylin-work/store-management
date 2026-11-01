"""stores 路由。"""

from django.urls import path

from apps.stores.views.store import StoreOptionListView

urlpatterns = [
    path("stores/", StoreOptionListView.as_view(), name="store-list"),
]
