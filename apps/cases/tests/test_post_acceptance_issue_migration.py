"""Testes de migration e backfill para campos post_acceptance_issue_*.

Slice 002: migration 0012 adiciona post_acceptance_issue_context e
post_acceptance_issue_cycle_id com backfill de intercorrências legadas ativas.
"""

from __future__ import annotations

import pytest

from apps.cases.models import Case, CaseStatus

pytestmark = pytest.mark.django_db


def _refetch(case: Case) -> Case:
    """Re-fetch a case from DB, avoiding django-fsm refresh_from_db issues."""
    return Case.objects.get(pk=case.pk)


class TestMigrationFields:
    """Testes de existência dos campos e backfill da migration."""

    def test_fields_exist_on_model(self) -> None:
        """Campos post_acceptance_issue_context e post_acceptance_issue_cycle_id existem."""
        assert hasattr(Case, "post_acceptance_issue_context"), (
            "Campo post_acceptance_issue_context não existe no modelo"
        )
        assert hasattr(Case, "post_acceptance_issue_cycle_id"), (
            "Campo post_acceptance_issue_cycle_id não existe no modelo"
        )

    def test_defaults_are_correct(self, user, case_factory) -> None:
        """Casos novos iniciam com valores default."""
        case = case_factory(user)
        assert case.post_acceptance_issue_context == ""
        assert case.post_acceptance_issue_cycle_id is None

    def test_backfill_opened_legacy_issue(self, user, case_factory, advance_to) -> None:
        """Issue legada opened recebe contexto 'scheduled' e UUID único."""
        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        # Set via update para evitar FSM protected field
        Case.objects.filter(pk=case.pk).update(
            post_schedule_issue_status="opened",
            post_schedule_issue_reason="death",
        )
        # Executar backfill manual
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cases_case
                   SET post_acceptance_issue_context = 'scheduled',
                       post_acceptance_issue_cycle_id = gen_random_uuid()
                   WHERE post_schedule_issue_status IN ('opened', 'responded')
                     AND post_acceptance_issue_context = ''"""
            )

        case = _refetch(case)
        assert case.post_acceptance_issue_context == "scheduled", (
            f"Contexto deve ser 'scheduled' após backfill, mas é '{case.post_acceptance_issue_context}'"
        )
        assert case.post_acceptance_issue_cycle_id is not None, "cycle_id deve ser preenchido após backfill"

    def test_backfill_responded_legacy_issue(self, user, case_factory, advance_to) -> None:
        """Issue legada responded também recebe contexto/UUID."""
        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        Case.objects.filter(pk=case.pk).update(
            post_schedule_issue_status="responded",
            post_schedule_issue_reason="death",
            post_schedule_issue_response_action="cancel",
        )

        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cases_case
                   SET post_acceptance_issue_context = 'scheduled',
                       post_acceptance_issue_cycle_id = gen_random_uuid()
                   WHERE post_schedule_issue_status IN ('opened', 'responded')
                     AND post_acceptance_issue_context = ''"""
            )

        case = _refetch(case)
        assert case.post_acceptance_issue_context == "scheduled"
        assert case.post_acceptance_issue_cycle_id is not None

    def test_no_issue_active_stays_default(self, user, case_factory, advance_to) -> None:
        """Casos sem issue ativa permanecem com valores vazios/nulos."""
        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        Case.objects.filter(pk=case.pk).update(post_schedule_issue_status="")

        case = _refetch(case)
        assert case.post_acceptance_issue_context == ""
        assert case.post_acceptance_issue_cycle_id is None

    def test_each_case_gets_unique_cycle_id(self, user, case_factory, advance_to) -> None:
        """Cada caso com issue ativa recebe UUID diferente."""
        case1 = advance_to(case_factory(user), CaseStatus.CLEANED)
        case1.doctor_decision = "accept"
        case1.doctor_admission_flow = "scheduled"
        case1.appointment_status = "confirmed"
        Case.objects.filter(pk=case1.pk).update(
            post_schedule_issue_status="opened",
            post_schedule_issue_reason="death",
        )

        case2 = advance_to(case_factory(user), CaseStatus.CLEANED)
        case2.doctor_decision = "accept"
        case2.doctor_admission_flow = "scheduled"
        case2.appointment_status = "confirmed"
        Case.objects.filter(pk=case2.pk).update(
            post_schedule_issue_status="responded",
            post_schedule_issue_reason="death",
            post_schedule_issue_response_action="maintain",
        )

        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cases_case
                   SET post_acceptance_issue_context = 'scheduled',
                       post_acceptance_issue_cycle_id = gen_random_uuid()
                   WHERE post_schedule_issue_status IN ('opened', 'responded')
                     AND post_acceptance_issue_context = ''"""
            )

        case1 = _refetch(case1)
        case2 = _refetch(case2)

        assert case1.post_acceptance_issue_cycle_id is not None
        assert case2.post_acceptance_issue_cycle_id is not None
        assert case1.post_acceptance_issue_cycle_id != case2.post_acceptance_issue_cycle_id, (
            "UUIDs devem ser diferentes entre casos"
        )
