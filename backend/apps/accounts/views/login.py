"""
登录视图:
调用 LoginSerializer 完成身份认证和门店权限校验,
签发 JWT(包含用户、门店及角色上下文),返回统一响应.
"""

from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers.login import LoginSerializer
from core.responses import success


class LoginView(APIView):
    """用户登录接口"""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    # 登录频率限制：按 IP 限流,速率在 settings.REST_FRAMEWORK.DEFAULT_THROTTLE_RATES 配置
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"

    def post(self, request):
        # 1. 验证登录信息(身份认证 + 门店关联校验)
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        user = data["user"]
        store_id = data["store_id"]
        role_code = data["role_code"]

        # 2. 签发 JWT
        refresh = RefreshToken.for_user(user)

        # 添加业务身份上下文,后续认证类从 payload 读取
        refresh["employee_code"] = user.employee_code
        refresh["store_id"] = store_id
        refresh["role_code"] = role_code
        refresh["is_superuser"] = user.is_superuser

        # 3. 返回登录结果
        return success(
            data={
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "employee_code": user.employee_code,
                    "real_name": user.real_name,
                    "is_superuser": user.is_superuser,
                    "store_id": store_id,
                    "role_code": role_code,
                },
            }
        )
