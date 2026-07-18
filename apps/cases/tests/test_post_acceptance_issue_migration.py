"""Testes da migration 0012 — backfill de intercorrências legadas ativas.

Testa a função backfill_active_post_acceptance_issues importada via
importlib da migration 0012, com o registry histórico correto.
"""

from __future__ import annotations

import importlib
import uuid
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseStatus

pytestmark = pytest.mark.django_db

User = get_user_model()


def _get_backfill_fn():
    """Importa a função de backfill da migration 0012 via importlib."""
    mod = importlib.import_module("apps.cases.migrations.0012_post_acceptance_issue_fields")
    return mod.backfill_active_post_acceptance_issues


def _create_backfill_data(pks: list[int], status: str) -> None:
    """Cria casos com issue legada ativa via update (evita FSM)."""
    Case.objects.filter(pk__in=pks).update(
        post_schedule_issue_status=status,
        post_schedule_issue_reason="death",
    )


class TestMigrationBackfill:
    """Testes da função backfill da migration 0012."""

    def test_opened_receives_context_and_unique_uuid(self, user, case_factory, advance_to) -> None:
        """Issue opened recebe contexto 'scheduled' e UUID único."""
        backfill = _get_backfill_fn()

        case1 = advance_to(case_factory(user), CaseStatus.CLEANED)
        case1.doctor_decision = "accept"
        case1.doctor_admission_flow = "scheduled"
        case1.appointment_status = "confirmed"
        case1.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])

        case2 = advance_to(case_factory(user), CaseStatus.CLEANED)
        case2.doctor_decision = "accept"
        case2.doctor_admission_flow = "scheduled"
        case2.appointment_status = "confirmed"
        case2.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])

        _create_backfill_data([case1.pk, case2.pk], "opened")

        from django.apps import apps as django_apps

        backfill(django_apps, MagicMock())

        c1 = Case.objects.get(pk=case1.pk)
        c2 = Case.objects.get(pk=case2.pk)

        assert c1.post_acceptance_issue_context == "scheduled"
        assert c1.post_acceptance_issue_cycle_id is not None
        assert isinstance(c1.post_acceptance_issue_cycle_id, uuid.UUID)

        assert c2.post_acceptance_issue_context == "scheduled"
        assert c2.post_acceptance_issue_cycle_id is not None

        assert c1.post_acceptance_issue_cycle_id != c2.post_acceptance_issue_cycle_id, "UUIDs devem ser distintos"

    def test_responded_receives_context_and_uuid(self, user, case_factory, advance_to) -> None:
        """Issue responded também recebe contexto/UUID."""
        backfill = _get_backfill_fn()

        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])
        _create_backfill_data([case.pk], "responded")

        from django.apps import apps as django_apps

        backfill(django_apps, MagicMock())

        c = Case.objects.get(pk=case.pk)
        assert c.post_acceptance_issue_context == "scheduled"
        assert c.post_acceptance_issue_cycle_id is not None

    def test_no_active_issue_stays_default(self, user, case_factory, advance_to) -> None:
        """Casos sem issue ativa permanecem com valores vazios/nulos."""
        backfill = _get_backfill_fn()

        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])
        # post_schedule_issue_status permanece "" (default)

        from django.apps import apps as django_apps

        backfill(django_apps, MagicMock())

        c = Case.objects.get(pk=case.pk)
        assert c.post_acceptance_issue_context == ""
        assert c.post_acceptance_issue_cycle_id is None

    def test_many_cases_in_same_batch_have_unique_uuids(self, user, case_factory, advance_to) -> None:
        """Múltiplos casos no mesmo lote recebem UUIDs distintos."""
        backfill = _get_backfill_fn()

        pks = []
        for i in range(10):
            case = advance_to(case_factory(user), CaseStatus.CLEANED)
            case.doctor_decision = "accept"
            case.doctor_admission_flow = "scheduled"
            case.appointment_status = "confirmed"
            case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])
            pks.append(case.pk)

        _create_backfill_data(pks, "opened")

        from django.apps import apps as django_apps

        backfill(django_apps, MagicMock())

        uuids_set = set()
        for pk in pks:
            c = Case.objects.get(pk=pk)
            assert c.post_acceptance_issue_context == "scheduled"
            assert c.post_acceptance_issue_cycle_id is not None
            uuids_set.add(c.post_acceptance_issue_cycle_id)

        assert len(uuids_set) == 10, f"Esperados 10 UUIDs únicos, obtidos {len(uuids_set)}"

    def test_existing_context_not_overwritten(self, user, case_factory, advance_to) -> None:
        """Valores já preenchidos não são sobrescritos."""
        backfill = _get_backfill_fn()

        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])

        existing_cycle_id = uuid.uuid4()
        Case.objects.filter(pk=case.pk).update(
            post_schedule_issue_status="opened",
            post_schedule_issue_reason="death",
            post_acceptance_issue_context="scheduled",
            post_acceptance_issue_cycle_id=existing_cycle_id,
        )

        from django.apps import apps as django_apps

        backfill(django_apps, MagicMock())

        c = Case.objects.get(pk=case.pk)
        assert c.post_acceptance_issue_context == "scheduled"
        assert c.post_acceptance_issue_cycle_id == existing_cycle_id, "UUID existente não deve ser sobrescrito"
