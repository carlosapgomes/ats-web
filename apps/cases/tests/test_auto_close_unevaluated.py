"""Batch de encerramento de casos nao avaliados (rotina 06h) — Slice 002.

TDD: testes falham antes da implementacao do servico/command.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()

pytestmark = pytest.mark.django_db


def _lock_as(case: Case, user, minutes: int = 10) -> Case:
    """Reserva o caso como se um medico o tivesse aberto."""
    case.locked_by = user
    case.locked_at = timezone.now()
    case.locked_until = timezone.now() + timedelta(minutes=minutes)
    import uuid as _uuid

    case.lock_token = _uuid.uuid4()
    case.lock_context = "doctor_decision"
    case.lock_role = "doctor"
    case.save(
        update_fields=[
            "locked_by",
            "locked_at",
            "locked_until",
            "lock_token",
            "lock_context",
            "lock_role",
        ]
    )
    return Case.objects.get(pk=case.pk)


class TestCloseUnevaluatedBatch:
    def test_closes_wait_doctor_without_lock_as_system(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import close_unevaluated_wait_doctor_cases

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        result = close_unevaluated_wait_doctor_cases()

        assert result.closed == 1
        assert result.skipped_locked == 0
        assert result.skipped_changed == 0
        assert Case.objects.get(pk=case.pk).status == CaseStatus.CLEANED
        event = CaseEvent.objects.get(case=case, event_type="CASE_ADMINISTRATIVELY_CLOSED")
        assert event.actor is None
        assert event.actor_type == "system"
        assert event.payload["previous_status"] == "WAIT_DOCTOR"
        assert event.payload["reason_code"] == "not_evaluated_by_doctor"
        assert event.payload["active_role"] == "system"

    def test_skips_case_with_valid_lock_and_keeps_it(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import close_unevaluated_wait_doctor_cases

        doctor = User.objects.create_user(username="doctor", password="x")
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case = _lock_as(case, doctor, minutes=10)

        result = close_unevaluated_wait_doctor_cases()

        assert result.closed == 0
        assert result.skipped_locked == 1
        assert result.skipped_changed == 0
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        assert reloaded.locked_by_id == doctor.pk
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_ADMINISTRATIVELY_CLOSED").exists()

    def test_closes_case_with_expired_lock(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import close_unevaluated_wait_doctor_cases

        doctor = User.objects.create_user(username="doctor", password="x")
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case = _lock_as(case, doctor, minutes=-5)

        result = close_unevaluated_wait_doctor_cases()

        assert result.closed == 1
        assert Case.objects.get(pk=case.pk).status == CaseStatus.CLEANED

    def test_skips_case_that_changed_status_before_row_lock(self, user, case_factory, advance_to) -> None:
        """Simula decisao medica concorrente commitada antes do nosso lock."""
        from apps.cases.services import close_unevaluated_wait_doctor_cases

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        real_sfu = Case.objects.select_for_update

        def sfu_spy():
            qs = real_sfu()
            real_get = qs.get

            def get(*args, **kwargs):
                found = real_get(*args, **kwargs)
                if str(found.pk) == str(case.pk):
                    Case.objects.filter(pk=found.pk).update(status=CaseStatus.DOCTOR_DENIED, doctor_decision="deny")
                    return real_sfu().get(*args, **kwargs)
                return found

            qs.get = get
            return qs

        import django.db.models.manager as _manager

        _orig = _manager.Manager.select_for_update
        _manager.Manager.select_for_update = lambda self, *a, **k: sfu_spy()
        try:
            result = close_unevaluated_wait_doctor_cases()
        finally:
            _manager.Manager.select_for_update = _orig

        assert result.closed == 0
        assert result.skipped_changed == 1

    def test_service_error_maps_to_skipped_changed(self, user, case_factory, advance_to, monkeypatch) -> None:
        from apps.cases import services as services_mod
        from apps.cases.services import close_unevaluated_wait_doctor_cases

        advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)

        def _boom(*, case, **kwargs):
            raise ValueError("Caso já está encerrado (CLEANED).")

        monkeypatch.setattr(services_mod, "administratively_close_case", _boom)
        result = close_unevaluated_wait_doctor_cases()

        assert result.closed == 0
        assert result.skipped_changed == 1

    def test_second_run_is_idempotent(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import close_unevaluated_wait_doctor_cases

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        first = close_unevaluated_wait_doctor_cases()
        assert first.closed == 1

        before = CaseEvent.objects.filter(case=case).count()
        second = close_unevaluated_wait_doctor_cases()

        assert second.closed == 0
        assert second.skipped_locked == 0
        assert second.skipped_changed == 0
        assert CaseEvent.objects.filter(case=case).count() == before


class TestCloseUnevaluatedCommand:
    def test_dry_run_reports_without_writing(self, user, case_factory, advance_to) -> None:
        doctor = User.objects.create_user(username="doctor", password="x")
        open_case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        locked_case = _lock_as(advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR), doctor)
        events_before = CaseEvent.objects.count()

        out = StringIO()
        call_command("auto_close_unevaluated_cases", "--dry-run", stdout=out)
        report = out.getvalue()

        assert "closed" in report and "skipped_locked" in report and "skipped_changed" in report
        assert Case.objects.get(pk=open_case.pk).status == CaseStatus.WAIT_DOCTOR
        assert Case.objects.get(pk=locked_case.pk).status == CaseStatus.WAIT_DOCTOR
        assert CaseEvent.objects.count() == events_before

    def test_command_closes_and_reports(self, user, case_factory, advance_to) -> None:
        open_case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)

        out = StringIO()
        call_command("auto_close_unevaluated_cases", stdout=out)
        report = out.getvalue()

        assert "closed" in report
        assert Case.objects.get(pk=open_case.pk).status == CaseStatus.CLEANED


class TestSystemActorValidation:
    def test_user_none_requires_system_role(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        with pytest.raises(ValueError, match="system"):
            administratively_close_case(
                case=case,
                user=None,
                reason_code="not_evaluated_by_doctor",
                reason_text="Rotina 06:00.",
                active_role="manager",
            )
        assert Case.objects.get(pk=case.pk).status == CaseStatus.WAIT_DOCTOR

    def test_user_none_with_system_role_closes(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        administratively_close_case(
            case=case,
            user=None,
            reason_code="not_evaluated_by_doctor",
            reason_text="Rotina 06:00.",
            active_role="system",
        )
        assert Case.objects.get(pk=case.pk).status == CaseStatus.CLEANED
        event = CaseEvent.objects.get(case=case, event_type="CASE_ADMINISTRATIVELY_CLOSED")
        assert event.actor is None
        assert event.actor_type == "system"
