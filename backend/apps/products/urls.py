"""products 路由."""

from django.urls import path

from apps.products.views.product import (
    ProductAdjustStockView,
    ProductDetailView,
    ProductListCreateView,
)

urlpatterns = [
    path("", ProductListCreateView.as_view(), name="product-list"),
    path("<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path(
        "<int:pk>/stock/", ProductAdjustStockView.as_view(), name="product-adjust-stock"
    ),
]
