"""members 路由。"""

from django.urls import path

from apps.members.views.member import (
    MemberChangeLevelView,
    MemberDetailView,
    MemberListCreateView,
    MemberRechargeView,
)

urlpatterns = [
    path("members/", MemberListCreateView.as_view(), name="member-list"),
    path("members/<int:pk>/", MemberDetailView.as_view(), name="member-detail"),
    path(
        "members/<int:pk>/recharge/",
        MemberRechargeView.as_view(),
        name="member-recharge",
    ),
    path(
        "members/<int:pk>/level/",
        MemberChangeLevelView.as_view(),
        name="member-change-level",
    ),
]
