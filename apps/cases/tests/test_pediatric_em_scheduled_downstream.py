"""Testes downstream do lifecycle pediátrico agendado (Slice 002).

Cobre:
- R1: intercorrência de novo caso `pediatric_appt` usa contexto `scheduled`
      e reabre `WAIT_APPT`;
- R2: legado `pediatric_em` permanece `operational_notice` com campos
      `appointment_*` imutáveis;
- R3: `closed_case_detail` do NIR usa contexto `scheduled` para o novo código;
- R4: histórico CHD inclui `pediatric_appt` e exclui `pediatric_em` sem agenda;
- R5: dashboard aponta agendador e consolida métrica sem dupla contagem.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus
from tests.shared_case_fixtures import attach_procedure_projection

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _cleaned_flow(case_factory, advance_to, user, *, flow, appointment_status=None):
    """Cria um Case CLEANED aceito com o fluxo de admissão escolhido."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = flow
    if appointment_status:
        case.appointment_status = appointment_status
        case.appointment_at = timezone.now()
        case.appointment_location = "Hospital Central"
    case.save()
    return Case.objects.get(pk=case.pk)


def _latest_event(case: Case, event_type: str) -> CaseEvent:
    events = CaseEvent.objects.filter(case=case, event_type=event_type)
    assert events.exists(), f"Evento {event_type} não encontrado"
    return events.latest("timestamp")


def _nir_client(client):
    """Cria usuário NIR logado com papel ativo."""
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Role

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(username="nir_downstream", password="testpass")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return user


# ── R1: novo caso pediátrico agendado ───────────────────────────────────


class TestPediatricApptScheduledEligibility:
    """R1 — `pediatric_appt` confirmado/CLEANED é eligible no contexto scheduled."""

    def test_pediatric_appt_confirmed_eligible_scheduled_not_operational(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import (
            get_post_acceptance_issue_ineligibility_reason,
            is_post_acceptance_issue_eligible,
        )

        case = _cleaned_flow(
            case_factory,
            advance_to,
            user,
            flow="pediatric_appt",
            appointment_status="confirmed",
        )

        assert is_post_acceptance_issue_eligible(case, context="scheduled") is True
        assert is_post_acceptance_issue_eligible(case, context="operational_notice") is False
        reason = get_post_acceptance_issue_ineligibility_reason(case, context="scheduled")
        assert reason != "Fluxo de admissão não é agendado."

    def test_open_pediatric_appt_scheduled_transitions_to_wait_appt(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import open_post_acceptance_issue

        case = _cleaned_flow(
            case_factory,
            advance_to,
            user,
            flow="pediatric_appt",
            appointment_status="confirmed",
        )

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="scheduled",
        )

        assert case.status == CaseStatus.WAIT_APPT
        assert case.post_acceptance_issue_context == "scheduled"
        event = _latest_event(case, "POST_ACCEPTANCE_ISSUE_OPENED")
        payload = event.payload
        assert payload.get("context") == "scheduled"
        assert payload.get("admission_flow") == "pediatric_appt"
        assert payload.get("appointment_snapshot", {}).get("status") == "confirmed"


# ── R2: legado pediátrico operacional ────────────────────────────────────


class TestLegacyPediatricEmOperational:
    """R2 — `pediatric_em` histórico permanece operational_notice imutável."""

    def test_pediatric_em_scheduled_ineligible_operational_eligible(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import (
            get_post_acceptance_issue_ineligibility_reason,
            is_post_acceptance_issue_eligible,
        )

        case = _cleaned_flow(case_factory, advance_to, user, flow="pediatric_em")

        assert is_post_acceptance_issue_eligible(case, context="scheduled") is False
        assert is_post_acceptance_issue_eligible(case, context="operational_notice") is True
        assert (
            get_post_acceptance_issue_ineligibility_reason(case, context="scheduled")
            == "Fluxo de admissão não é agendado."
        )

    def test_pediatric_em_open_ack_keeps_cleaned_and_appointment_immutable(
        self, user, case_factory, advance_to
    ) -> None:
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _cleaned_flow(case_factory, advance_to, user, flow="pediatric_em")
        before = {
            "appointment_status": case.appointment_status,
            "appointment_at": case.appointment_at,
            "appointment_location": case.appointment_location,
            "appointment_instructions": case.appointment_instructions,
        }

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            message="Óbito do paciente.",
            context="operational_notice",
        )
        assert case.status == CaseStatus.CLEANED
        assert case.post_acceptance_issue_context == "operational_notice"

        case = acknowledge_operational_post_acceptance_issue(case=case, user=user)
        refreshed = Case.objects.get(pk=case.pk)
        assert refreshed.status == CaseStatus.CLEANED
        assert refreshed.appointment_status == before["appointment_status"]
        assert refreshed.appointment_at == before["appointment_at"]
        assert refreshed.appointment_location == before["appointment_location"]
        assert refreshed.appointment_instructions == before["appointment_instructions"]


# ── R4: histórico CHD ────────────────────────────────────────────────────


class TestSchedulerHistoryIncludesPediatricAppt:
    """R4 — histórico CHD inclui novo agendado e exclui legado operacional."""

    def test_is_scheduler_historical_case_accepts_pediatric_appt(self, user) -> None:
        from apps.scheduler.views import _is_scheduler_historical_case

        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="pediatric_appt",
            appointment_status="confirmed",
        )
        assert _is_scheduler_historical_case(case) is True

    def test_historical_queryset_includes_new_and_excludes_legacy(self, user) -> None:
        from apps.scheduler.views import _scheduler_historical_queryset

        Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="pediatric_appt",
            appointment_status="confirmed",
            agency_record_number="NEW-PED-001",
        )
        Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="pediatric_em",
            agency_record_number="LEGACY-PED-002",
        )
        Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="denied",
            agency_record_number="SCHED-DENIED-003",
        )

        ids = set(_scheduler_historical_queryset().values_list("agency_record_number", flat=True))
        assert "NEW-PED-001" in ids
        assert "SCHED-DENIED-003" in ids
        assert "LEGACY-PED-002" not in ids

    def test_historical_search_page_finds_pediatric_appt_case(self, client, user) -> None:
        from apps.accounts.models import Role

        scheduler = user
        scheduler.username = "sched_downstream"
        scheduler.save()
        role, _ = Role.objects.get_or_create(name="scheduler")
        scheduler.roles.add(role)
        client.force_login(scheduler)
        session = client.session
        session["active_role"] = "scheduler"
        session.save()

        attach_procedure_projection(
            Case.objects.create(
                created_by=user,
                status=CaseStatus.CLEANED,
                doctor_decision="accept",
                doctor_admission_flow="pediatric_appt",
                appointment_status="confirmed",
                agency_record_number="HIST-PED-APPT",
                structured_data={"patient": {"name": "Criança Agendada"}},
            ),
            declared=("eda",),
            detected=("eda",),
            approved=("eda",),
        )

        response = client.get("/scheduler/historical/?q=HIST-PED-APPT")
        assert response.status_code == 200
        content = response.content.decode()
        # Card de resultado (não apenas o valor do input): nome do paciente
        # do caso só aparece na lista de resultados do template.
        assert "Criança Agendada" in content
        assert "1 caso" in content


# ── R5: dashboard ────────────────────────────────────────────────────────


class TestDashboardNextStepAndMetric:
    """R5 — próximo responsável e métrica funcional consolidada."""

    def test_next_step_wait_appt_pediatric_appt_points_to_scheduler(self, user) -> None:
        from apps.dashboard.views import _compute_next_step

        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            doctor_admission_flow="pediatric_appt",
        )
        result = _compute_next_step(case)
        assert result is not None
        assert result[0] == "Pendente: agendador"

    def test_admission_flow_metric_consolidates_legacy_and_new(self, user) -> None:
        from apps.cases.services import local_day_bounds
        from apps.dashboard.views import _compute_admission_flow

        start, _end = local_day_bounds()
        Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="pediatric_em",
            agency_record_number="PED-EM-001",
            created_at=start + timedelta(minutes=1),
        )
        Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="pediatric_appt",
            agency_record_number="PED-APPT-002",
            created_at=start + timedelta(minutes=2),
        )
        Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            agency_record_number="IMM-003",
            created_at=start + timedelta(minutes=3),
        )

        result = _compute_admission_flow()
        assert result["pediatric_em"] == 2
        assert result["immediate"] == 1
        assert result["scheduled"] == 0
        assert result["pre_icu"] == 0
        assert result["ward_icu_backup"] == 0


# ── R3: detalhe histórico NIR ────────────────────────────────────────────


class TestNirClosedDetailScheduledContext:
    """R3 — `closed_case_detail` usa contexto scheduled para o novo código."""

    def test_get_shows_intercurrence_form_for_pediatric_appt(self, client, case_factory, advance_to) -> None:
        user = _nir_client(client)
        case = _cleaned_flow(
            case_factory,
            advance_to,
            user,
            flow="pediatric_appt",
            appointment_status="confirmed",
        )

        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência Pós-Aceitação" in content
        assert "Registrar intercorrência" in content
        assert "não é elegível para intercorrência operacional" not in content

    def test_post_opens_scheduled_issue_for_pediatric_appt(self, client, case_factory, advance_to) -> None:
        user = _nir_client(client)
        case = _cleaned_flow(
            case_factory,
            advance_to,
            user,
            flow="pediatric_appt",
            appointment_status="confirmed",
        )

        response = client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "death", "message": "Paciente evoluiu a óbito."},
        )
        assert response.status_code == 302
        refreshed = Case.objects.get(pk=case.pk)
        assert refreshed.status == CaseStatus.WAIT_APPT
        assert refreshed.post_acceptance_issue_context == "scheduled"
        assert refreshed.post_schedule_issue_status == "opened"
