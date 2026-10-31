# Agendamento diario 06:00 America/Bahia (rotina 06h) — Slice 003.
#
# TDD: testes falham antes do seed/helper existirem.

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from django_q.models import Schedule

pytestmark = pytest.mark.django_db


def test_daily_0600_helper_picks_same_day_before_0600() -> None:
    from apps.cases.services import next_daily_0600

    bahia = ZoneInfo("America/Bahia")
    now = datetime(2026, 11, 3, 4, 30, tzinfo=bahia)
    assert next_daily_0600(now) == datetime(2026, 11, 3, 6, 0, tzinfo=bahia)


def test_daily_0600_helper_picks_next_day_after_0600() -> None:
    from apps.cases.services import next_daily_0600

    bahia = ZoneInfo("America/Bahia")
    now = datetime(2026, 11, 3, 9, 15, tzinfo=bahia)
    assert next_daily_0600(now) == datetime(2026, 11, 4, 6, 0, tzinfo=bahia)


def test_ensure_creates_daily_llm_schedule_at_0600_bahia() -> None:
    from apps.cases.services import (
        AUTO_CLOSE_SCHEDULE_CLUSTER,
        AUTO_CLOSE_SCHEDULE_FUNC,
        AUTO_CLOSE_SCHEDULE_NAME,
        ensure_auto_close_schedule,
    )

    before = timezone.now()
    schedule = ensure_auto_close_schedule()

    assert schedule.name == AUTO_CLOSE_SCHEDULE_NAME
    assert schedule.func == AUTO_CLOSE_SCHEDULE_FUNC
    assert schedule.schedule_type == Schedule.DAILY
    assert schedule.cluster == AUTO_CLOSE_SCHEDULE_CLUSTER
    assert schedule.repeats == -1
    local_run = timezone.localtime(schedule.next_run)
    assert (local_run.hour, local_run.minute) == (6, 0)
    assert schedule.next_run > before
    assert schedule.next_run <= before + timedelta(days=1, minutes=1)


def test_ensure_is_idempotent() -> None:
    from apps.cases.services import AUTO_CLOSE_SCHEDULE_NAME, ensure_auto_close_schedule

    ensure_auto_close_schedule()
    ensure_auto_close_schedule()

    assert Schedule.objects.filter(name=AUTO_CLOSE_SCHEDULE_NAME).count() == 1


def test_schedule_func_resolves_to_batch_service() -> None:
    from django.utils.module_loading import import_string

    from apps.cases.services import AUTO_CLOSE_SCHEDULE_FUNC, ensure_auto_close_schedule

    schedule = ensure_auto_close_schedule()
    assert schedule.func == AUTO_CLOSE_SCHEDULE_FUNC
    assert import_string(schedule.func).__name__ == "close_unevaluated_wait_doctor_cases"
