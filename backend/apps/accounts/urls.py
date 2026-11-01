"""accounts 路由。"""

from django.urls import path

from apps.accounts.views.login import LoginView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
]
