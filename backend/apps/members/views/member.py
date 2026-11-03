"""会员管理视图."""

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.logs.services.logger import log_operation
from apps.members.models import Member, PointsRecord, PointsRecordType
from apps.members.serializers.member import (
    MemberAdjustPointsSerializer,
    MemberChangeLevelSerializer,
    MemberCreateSerializer,
    MemberListSerializer,
    MemberRechargeSerializer,
    MemberUpdateSerializer,
)
from apps.members.services.recharge import recharge_member
from core.codes import BizCode
from core.exceptions import BizException
from core.pagination import StandardPagination
from core.permissions import HasPerm
from core.responses import success

# ---------------------------------------------------------------------------
# 权限类
# ---------------------------------------------------------------------------


class CanListMember(HasPerm):
    """会员列表及详情权限."""

    required_perm = "member:list"


class CanCreateMember(HasPerm):
    """创建会员权限."""

    required_perm = "member:create"


class CanUpdateMember(HasPerm):
    """编辑会员权限."""

    required_perm = "member:update"


class CanRechargeMember(HasPerm):
    """会员充值权限."""

    required_perm = "member:recharge"


class CanChangeLevel(HasPerm):
    """会员等级调整权限(仅店长)."""

    required_perm = "member:change_level"


class CanAdjustPoints(HasPerm):
    """会员积分调整权限(仅店长)."""

    required_perm = "member:adjust_points"


# ---------------------------------------------------------------------------
# 公共方法
# ---------------------------------------------------------------------------


def _get_member(pk: int, store_id: int, *, for_update: bool = False) -> Member:
    """按主键和门店获取会员, 不存在时抛业务异常."""
    queryset = Member.objects.filter(pk=pk, store_id=store_id)
    if for_update:
        queryset = queryset.select_for_update()
    member = queryset.first()
    if member is None:
        raise BizException(
            code=BizCode.MEMBER_NOT_FOUND,
            message="会员不存在",
            http_status=status.HTTP_404_NOT_FOUND,
        )
    return member


def _get_store_id(request) -> int:
    """从请求上下文获取当前门店 ID."""
    store_id = getattr(request, "store_id", None)
    if store_id is None:
        raise BizException(
            code=BizCode.PERMISSION_DENIED,
            message="当前账号未绑定门店",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return store_id


# ---------------------------------------------------------------------------
# 会员列表与创建
# ---------------------------------------------------------------------------


class MemberListCreateView(APIView):
    """会员列表与创建."""

    def get_permissions(self):
        permission_class = (
            CanListMember if self.request.method == "GET" else CanCreateMember
        )
        return [IsAuthenticated(), permission_class()]

    def get(self, request):
        store_id = _get_store_id(request)
        queryset = Member.objects.filter(store_id=store_id).order_by("-created_at")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = MemberListSerializer(page, many=True)
        return success(
            data={
                "items": serializer.data,
                "total": paginator.page.paginator.count,
                "page": paginator.page.number,
                "page_size": paginator.get_page_size(request),
            }
        )

    @transaction.atomic
    def post(self, request):
        store_id = _get_store_id(request)
        serializer = MemberCreateSerializer(
            data=request.data, context={"store_id": store_id}
        )
        serializer.is_valid(raise_exception=True)
        member = serializer.save()
        log_operation(
            user=request.user,
            module="member",
            action="create",
            target_type="Member",
            target_id=str(member.pk),
            detail={"name": member.name, "phone": member.phone},
        )
        return success(
            data=MemberListSerializer(member).data, http_status=status.HTTP_201_CREATED
        )


# ---------------------------------------------------------------------------
# 会员详情与编辑
# ---------------------------------------------------------------------------


class MemberDetailView(APIView):
    """会员详情与编辑."""

    def get_permissions(self):
        permission_class = (
            CanListMember if self.request.method == "GET" else CanUpdateMember
        )
        return [IsAuthenticated(), permission_class()]

    def get(self, request, pk):
        store_id = _get_store_id(request)
        member = _get_member(pk, store_id)
        return success(data=MemberListSerializer(member).data)

    @transaction.atomic
    def patch(self, request, pk):
        store_id = _get_store_id(request)
        member = _get_member(pk, store_id, for_update=True)
        serializer = MemberUpdateSerializer(
            member, data=request.data, partial=True, context={"store_id": store_id}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_operation(
            user=request.user,
            module="member",
            action="update",
            target_type="Member",
            target_id=str(member.pk),
            detail={"changed_fields": list(serializer.validated_data.keys())},
        )
        return success(data=MemberListSerializer(member).data)


# ---------------------------------------------------------------------------
# 会员充值
# ---------------------------------------------------------------------------


class MemberRechargeView(APIView):
    """会员充值."""

    permission_classes = (IsAuthenticated, CanRechargeMember)

    def post(self, request, pk):
        store_id = _get_store_id(request)
        serializer = MemberRechargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = recharge_member(
            member_id=pk,
            amount=serializer.validated_data["amount"],
            staff=request.user,
            store_id=store_id,
        )
        member = Member.objects.get(pk=pk)
        return success(
            data={
                "recharge_record_id": record.pk,
                "amount": str(record.amount),
                "balance_before": str(record.balance_before),
                "balance_after": str(record.balance_after),
                "member": MemberListSerializer(member).data,
            }
        )


# ---------------------------------------------------------------------------
# 会员等级调整
# ---------------------------------------------------------------------------


class MemberChangeLevelView(APIView):
    """会员等级调整, 仅店长."""

    permission_classes = (IsAuthenticated, CanChangeLevel)

    @transaction.atomic
    def patch(self, request, pk):
        store_id = _get_store_id(request)
        member = _get_member(pk, store_id, for_update=True)
        serializer = MemberChangeLevelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_level = member.level
        member.level = serializer.validated_data["level"]
        member.save(update_fields=("level", "updated_at"))
        log_operation(
            user=request.user,
            module="member",
            action="change_level",
            target_type="Member",
            target_id=str(member.pk),
            detail={"old_level": old_level, "new_level": member.level},
        )
        return success(data=MemberListSerializer(member).data)


# ---------------------------------------------------------------------------
# 会员积分调整
# ---------------------------------------------------------------------------


class MemberAdjustPointsView(APIView):
    """会员积分调整, 仅店长."""

    permission_classes = (IsAuthenticated, CanAdjustPoints)

    @transaction.atomic
    def patch(self, request, pk):
        store_id = _get_store_id(request)
        member = _get_member(pk, store_id, for_update=True)
        serializer = MemberAdjustPointsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        points_delta = serializer.validated_data["points"]
        reason = serializer.validated_data["reason"]

        points_before = member.points
        new_points = points_before + points_delta

        if new_points < 0:
            raise BizException(
                code=BizCode.PARAM_INVALID,
                message=f"积分不足, 当前积分 {points_before}, 调整后不能为负",
            )

        member.points = new_points
        member.save(update_fields=("points", "updated_at"))

        # 会员积分余额与积分流水必须在同一事务内.
        PointsRecord.objects.create(
            member=member,
            staff=request.user,
            record_type=PointsRecordType.ADJUST,
            points_delta=points_delta,
            points_expected_delta=points_delta,
            points_before=points_before,
            points_after=new_points,
            reason=reason,
        )

        log_operation(
            user=request.user,
            module="member",
            action="adjust_points",
            target_type="Member",
            target_id=str(member.pk),
            detail={
                "points_before": points_before,
                "points_after": new_points,
                "reason": reason,
            },
        )

        return success(data=MemberListSerializer(member).data)
