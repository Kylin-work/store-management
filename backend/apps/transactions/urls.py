"""transactions 路由."""

from django.urls import path

from apps.transactions.views.transaction import (
    TransactionDetailView,
    TransactionListCreateView,
    TransactionRefundView,
)

urlpatterns = [
    path("", TransactionListCreateView.as_view(), name="transaction-list"),
    path("<int:pk>/", TransactionDetailView.as_view(), name="transaction-detail"),
    path(
        "<int:pk>/refund/", TransactionRefundView.as_view(), name="transaction-refund"
    ),
]
