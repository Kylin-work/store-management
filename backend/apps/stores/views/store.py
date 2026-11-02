"""
门店视图.

提供公开门店选项接口,供登录页面选择门店.
仅返回启用状态的门店及必要的展示字段.
"""

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.stores.models import Store
from apps.stores.serializers.store import StoreOptionSerializer
from core.responses import success


class StoreOptionListView(APIView):
    """公开门店选项列表."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request):
        """获取启用中的门店列表."""

        stores = (
            Store.objects.filter(is_active=True)
            .only(
                "id",
                "code",
                "name",
                "store_type",
            )
            .order_by("code")
        )

        serializer = StoreOptionSerializer(
            stores,
            many=True,
        )

        return success(data=serializer.data)
