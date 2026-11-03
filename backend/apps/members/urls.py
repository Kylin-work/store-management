"""members 路由."""

from django.urls import path

from apps.members.views.member import (
    MemberAdjustPointsView,
    MemberChangeLevelView,
    MemberDetailView,
    MemberListCreateView,
    MemberRechargeView,
)

urlpatterns = [
    path("", MemberListCreateView.as_view(), name="member-list"),
    path("<int:pk>/", MemberDetailView.as_view(), name="member-detail"),
    path("<int:pk>/recharge/", MemberRechargeView.as_view(), name="member-recharge"),
    path(
        "<int:pk>/level/", MemberChangeLevelView.as_view(), name="member-change-level"
    ),
    path(
        "<int:pk>/points/",
        MemberAdjustPointsView.as_view(),
        name="member-adjust-points",
    ),
]
