"""预置工号序列行。

Sequence(name='employee_code') 必须在使用前存在,
这样 User.save() 里可以省去"不存在则创建"的并发不安全分支。
"""

from django.db import migrations


def seed_sequence(apps, schema_editor):
    """创建工号序列行,若已存在则跳过。"""
    Sequence = apps.get_model("accounts", "Sequence")
    Sequence.objects.get_or_create(name="employee_code", defaults={"current_value": 0})


def remove_sequence(apps, schema_editor):
    """回滚时删除该序列行。"""
    Sequence = apps.get_model("accounts", "Sequence")
    Sequence.objects.filter(name="employee_code").delete()


class Migration(migrations.Migration):
    dependencies = (("accounts", "0001_initial"),)

    operations = (migrations.RunPython(seed_sequence, remove_sequence),)
