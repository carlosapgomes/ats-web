"""Testes verticais NIR para intercorrência operacional (Slice 003 F2).

Asserts exatos: copy, badge, appointment fields, permissions, validation.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.cases.models import Case, CaseStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def nir_user(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(username="nir_test", password="testpass")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


@pytest.fixture
def nir_client(client, nir_user):
    client.login(username="nir_test", password="testpass")
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client


@pytest.fixture
def scheduler_user(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(username="sched_test", password="testpass")
    role, _ = Role.objects.get_or_create(name="scheduler")
    user.roles.add(role)
    return user


@pytest.fixture
def scheduler_client(client, scheduler_user):
    client.login(username="sched_test", password="testpass")
    session = client.session
    session["active_role"] = "scheduler"
    session.save()
    return client


def _create_cleaned_operational_case(nir_user, flow="immediate"):
    case = Case.objects.create(
        created_by=nir_user,
        status=CaseStatus.CLEANED,
        doctor_decision="accept",
        doctor_admission_flow=flow,
        agency_record_number="REG-001",
    )
    return Case.objects.get(pk=case.pk)


class TestNirClosedDetailOperational:
    """F2: Detalhe histórico NIR com formulário operacional."""

    def test_detail_shows_form_with_new_reasons(self, nir_client, nir_user):
        case = _create_cleaned_operational_case(nir_user, flow="immediate")
        response = nir_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "evadiu-se" in content
        assert "unidade mais próxima" in content
        assert "cancelada pela unidade de origem" in content

    def test_post_success_shows_exact_accented_copy(self, nir_client, nir_user):
        """F2: POST bem-sucedido exibe copy exata com acentos."""
        case = _create_cleaned_operational_case(nir_user, flow="ward_icu_backup")
        response = nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "patient_absconded", "message": "Paciente evadiu-se da unidade de origem"},
            follow=True,
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência registrada com sucesso." in content
        assert "receberá um aviso para confirmar ciência" in content

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == "opened"
        assert case.post_acceptance_issue_context == "operational_notice"
        assert case.status == CaseStatus.CLEANED

    def test_awaiting_chd_science_shown_after_open(self, nir_client, nir_user):
        """F2: Após abertura, HTML contém exatamente 'Aguardando ciência do CHD'."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")
        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "accepted_elsewhere", "message": "Transferido para Hospital X"},
            follow=True,
        )
        response = nir_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        content = response.content.decode()
        assert "Aguardando ciência do CHD" in content

    def test_all_six_appointment_fields_unchanged_after_post(self, nir_client, nir_user):
        """F2: Todos os 6 campos appointment_* imutáveis via POST NIR."""
        case = _create_cleaned_operational_case(nir_user, flow="pediatric_em")
        sentinel_dt = timezone.now()

        Case.objects.filter(pk=case.pk).update(
            appointment_status="confirmed",
            appointment_at=sentinel_dt,
            appointment_location="Hospital Sentinela",
            appointment_instructions="Jejum 8h",
            appointment_reason="Motivo sentinela",
            appointment_decided_at=sentinel_dt,
        )
        case = Case.objects.get(pk=case.pk)

        snap_before = {
            "appointment_status": case.appointment_status,
            "appointment_at": case.appointment_at,
            "appointment_location": case.appointment_location,
            "appointment_instructions": case.appointment_instructions,
            "appointment_reason": case.appointment_reason,
            "appointment_decided_at": case.appointment_decided_at,
        }

        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "origin_cancelled", "message": "Cancelado pela origem"},
            follow=True,
        )

        case = Case.objects.get(pk=case.pk)
        snap_after = {
            "appointment_status": case.appointment_status,
            "appointment_at": case.appointment_at,
            "appointment_location": case.appointment_location,
            "appointment_instructions": case.appointment_instructions,
            "appointment_reason": case.appointment_reason,
            "appointment_decided_at": case.appointment_decided_at,
        }
        assert snap_after == snap_before, f"Campos mudaram: before={snap_before}, after={snap_after}"

    def test_denied_case_blocked(self, nir_client, nir_user):
        case = _create_cleaned_operational_case(nir_user, flow="immediate")
        case.doctor_decision = "deny"
        case.save(update_fields=["doctor_decision"])
        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "patient_absconded", "message": "..."},
            follow=True,
        )
        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""

    def test_not_cleaned_case_blocked(self, nir_client, nir_user):
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
        )
        response = nir_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 404

    def test_non_nir_blocked_exact_redirect(self, scheduler_client, nir_user):
        """F2: Scheduler bloqueado com status específico (não range)."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")
        response = scheduler_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        # Decorator @role_required("nir") redireciona sem mutation
        assert response.status_code == 302

    def test_form_validation_shows_error_for_empty_message(self, nir_client, nir_user):
        """F2: POST sem mensagem re-renderiza com erro visível."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")
        response = nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "patient_absconded", "message": ""},
        )
        # Não redireciona — re-renderiza com erro
        assert response.status_code == 200
        content = response.content.decode()
        assert "obrigat" in content.lower()

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""
