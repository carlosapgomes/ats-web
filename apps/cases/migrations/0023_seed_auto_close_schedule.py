# Seed idempotente do agendamento diário 06:00 (rotina 06h, Slice 003).

from django.db import migrations


def seed_auto_close_schedule(apps, schema_editor):  # type: ignore[no-untyped-def]
    from apps.cases.services import ensure_auto_close_schedule

    ensure_auto_close_schedule()


def unseed_auto_close_schedule(apps, schema_editor):  # type: ignore[no-untyped-def]
    from django_q.models import Schedule

    from apps.cases.services import AUTO_CLOSE_SCHEDULE_NAME

    Schedule.objects.filter(name=AUTO_CLOSE_SCHEDULE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0022_case_patient_identity"),
        # O seed grava em django_q_schedule: sem esta dependência, um banco
        # novo roda cases.0023 antes de django_q.0001 e o migrate quebra
        # (relation "django_q_schedule" does not exist).
        ("django_q", "0016_schedule_intended_date_kwarg"),
    ]

    operations = [
        migrations.RunPython(seed_auto_close_schedule, unseed_auto_close_schedule),
    ]
