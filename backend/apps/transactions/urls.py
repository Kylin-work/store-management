"""transactions 路由."""

from django.urls import path

from apps.transactions.views.transaction import (
    TransactionDetailView,
    TransactionListCreateView,
    TransactionRefundView,
)

urlpatterns = [
    path(
        "transactions/",
        TransactionListCreateView.as_view(),
        name="transaction-list",
    ),
    path(
        "transactions/<int:pk>/",
        TransactionDetailView.as_view(),
        name="transaction-detail",
    ),
    path(
        "transactions/<int:pk>/refund/",
        TransactionRefundView.as_view(),
        name="transaction-refund",
    ),
]
