"""dashboard 路由."""

from django.urls import path

from apps.dashboard.views.overview import (
    DashboardSummaryView,
    DashboardTopMembersView,
    DashboardTopProductsView,
    DashboardTransactionTrendView,
)

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path(
        "top-products/",
        DashboardTopProductsView.as_view(),
        name="dashboard-top-products",
    ),
    path(
        "top-members/", DashboardTopMembersView.as_view(), name="dashboard-top-members"
    ),
    path(
        "transaction-trend/",
        DashboardTransactionTrendView.as_view(),
        name="dashboard-transaction-trend",
    ),
]
