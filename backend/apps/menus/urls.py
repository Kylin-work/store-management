"""menus 路由。"""

from django.urls import path

from apps.menus.views.menu import MenuListView

urlpatterns = [
    path("menus/", MenuListView.as_view(), name="menu-list"),
]
