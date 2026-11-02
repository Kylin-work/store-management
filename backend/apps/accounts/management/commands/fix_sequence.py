"""修复工号序列.

createsuperuser 手动指定工号时会绕过序列, 导致后续创建普通用户工号冲突.
此命令把序列推到当前数据库中最大工号的值, 保证后续自动生成不冲突.
"""

from django.core.management.base import BaseCommand

from apps.accounts.models import Sequence, User


class Command(BaseCommand):
    help = "把工号序列推到当前最大工号的值"

    def handle(self, *args, **options):
        # 找当前最大工号
        max_code = (
            User.objects.filter(employee_code__isnull=False)
            .exclude(employee_code="")
            .order_by("-employee_code")
            .values_list("employee_code", flat=True)
            .first()
        )

        if max_code is None:
            self.stdout.write(self.style.WARNING("没有用户, 序列保持 0"))
            return

        try:
            max_value = int(max_code)
        except (TypeError, ValueError):
            self.stdout.write(
                self.style.ERROR(f"最大工号 {max_code} 不是纯数字, 无法解析")
            )
            return

        seq = Sequence.objects.filter(name="employee_code").first()
        if seq is None:
            Sequence.objects.create(name="employee_code", current_value=max_value)
        else:
            if max_value > seq.current_value:
                seq.current_value = max_value
                seq.save(update_fields=["current_value"])

        self.stdout.write(
            self.style.SUCCESS(
                f"序列已推到 {max_value}, 下一个工号 {max_value + 1:08d}"
            )
        )
