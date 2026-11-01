"""accounts 路由。"""

from django.urls import path

from apps.accounts.views.login import LoginView
from apps.accounts.views.me import MeView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
]
