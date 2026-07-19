"""Testes verticais NIR para intercorrência operacional (Slice 003 Cobertura).

T1: busca histórica NIR (search, structured_data, detalhes, inelegibilidade)
T2: validação individual dos 3 novos motivos via view
     + asserts exatos de copy, badge, appointment fields, permissions.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.cases.models import Case, CaseEvent, CaseStatus

pytestmark = pytest.mark.django_db


# ── Fixtures ────────────────────────────────────────────────────────────────


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


# ── Helpers ─────────────────────────────────────────────────────────────────


def _cleaned(**kwargs):
    """Cria caso CLEANED aceito. Aceita kwargs para sobrescrever defaults."""
    defaults = {
        "status": CaseStatus.CLEANED,
        "doctor_decision": "accept",
        "doctor_admission_flow": "immediate",
        "agency_record_number": "REG-001",
    }
    defaults.update(kwargs)
    return Case.objects.create(**defaults)


def _cleaned_with_patient(created_by, flow="pre_icu", record="REG-SENTINELA-003"):
    """Caso CLEANED com structured_data rico para busca NIR."""
    case = _cleaned(
        created_by=created_by,
        doctor_admission_flow=flow,
        agency_record_number=record,
        structured_data={
            "patient": {"name": "Paciente Sentinela"},
            "origin_context": {
                "hospital": "Hospital Origem Sentinela",
                "unit": "Unidade Sentinela",
            },
        },
    )
    return Case.objects.get(pk=case.pk)


# ── T1: Busca histórica NIR ─────────────────────────────────────────────────


class TestNirSearchOperational:
    """T1: busca histórica NIR para casos operacionais CLEANED."""

    def test_search_by_record_finds_case(self, nir_client, nir_user):
        """T1.1: NIR pesquisa por registro e encontra caso operacional CLEANED."""
        _cleaned_with_patient(nir_user, flow="pre_icu", record="REG-SENTINELA-003")

        response = nir_client.get(reverse("intake:closed_cases_search"), {"q": "REG-SENTINELA-003"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Paciente Sentinela" in content
        assert "REG-SENTINELA-003" in content

    def test_search_by_patient_name_finds_case(self, nir_client, nir_user):
        """T1.2: NIR pesquisa por nome do paciente e encontra o caso."""
        _cleaned_with_patient(nir_user, flow="pediatric_em", record="REG-T1-002")

        response = nir_client.get(reverse("intake:closed_cases_search"), {"q": "Sentinela"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Paciente Sentinela" in content
        assert "REG-T1-002" in content

    def test_result_shows_details_link(self, nir_client, nir_user):
        """T1.3: resultado mostra link de acesso a Detalhes."""
        _cleaned_with_patient(nir_user, flow="immediate", record="REG-T1-003")
        response = nir_client.get(reverse("intake:closed_cases_search"), {"q": "REG-T1-003"})
        content = response.content.decode()
        assert 'href="/cases/closed-cases/' in content

    def test_eligible_case_does_not_show_ineligibility(self, nir_client, nir_user):
        """T1.4: caso elegível operacional não exibe mensagem de inelegibilidade."""
        _cleaned_with_patient(nir_user, flow="ward_icu_backup", record="REG-T1-004")
        response = nir_client.get(reverse("intake:closed_cases_search"), {"q": "REG-T1-004"})
        content = response.content.decode()
        assert "Paciente Sentinela" in content
        assert "não é elegível" not in content and "inelegível" not in content.lower()

    def test_non_nir_does_not_mutate_on_search(self, scheduler_client, nir_user):
        """H2: não-NIR acessa busca e recebe 302 sem mutar caso."""
        case = _cleaned_with_patient(nir_user, flow="immediate", record="REG-T1-005")
        response = scheduler_client.get(reverse("intake:closed_cases_search"), {"q": "REG-T1-005"})
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""
        assert case.status == CaseStatus.CLEANED
        assert not CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_OPENED").exists()


# ── T2: Validação individual dos 3 novos motivos ────────────────────────────


class TestThreeReasonsValidation:
    """T2: testes parametrizados para os 3 novos motivos operacionais."""

    REASONS = [
        ("patient_absconded", "evadiu-se da unidade de origem"),
        ("accepted_elsewhere", "unidade mais próxima da residência"),
        ("origin_cancelled", "cancelada pela unidade de origem"),
    ]

    @pytest.mark.parametrize("reason,label_fragment", REASONS)
    def test_empty_message_re_renders_with_error(self, nir_client, nir_user, reason, label_fragment):
        """T2: POST sem mensagem retorna 200 com erro 'Mensagem é obrigatória'."""
        case = _cleaned(created_by=nir_user)
        response = nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": reason, "message": ""},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Mensagem é obrigatória" in content

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""
        assert not CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_OPENED").exists()

    @pytest.mark.parametrize("reason,label_fragment", REASONS)
    def test_valid_post_persists(self, nir_client, nir_user, reason, label_fragment):
        """T2: POST válido para cada motivo → status 'opened' e evento criado."""
        case = _cleaned(created_by=nir_user)
        response = nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": reason, "message": f"Motivo: {label_fragment}"},
            follow=True,
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == "opened"
        assert case.post_acceptance_issue_context == "operational_notice"
        assert case.post_schedule_issue_reason == reason
        assert CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_OPENED").exists()


# ── Preservados (F2): Detalhe histórico NIR ─────────────────────────────────


class TestNirClosedDetailOperational:
    """Detalhe histórico NIR com formulário operacional."""

    def test_detail_shows_form_with_new_reasons(self, nir_client, nir_user):
        case = _cleaned(created_by=nir_user)
        response = nir_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "evadiu-se" in content
        assert "unidade mais próxima" in content
        assert "cancelada pela unidade de origem" in content

    def test_post_success_shows_exact_accented_copy(self, nir_client, nir_user):
        case = _cleaned(created_by=nir_user, doctor_admission_flow="ward_icu_backup")
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
        case = _cleaned(created_by=nir_user)
        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "accepted_elsewhere", "message": "Transferido para Hospital X"},
            follow=True,
        )
        response = nir_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        content = response.content.decode()
        assert "Aguardando ciência do CHD" in content

    def test_all_six_appointment_fields_unchanged_after_post(self, nir_client, nir_user):
        case = _cleaned(created_by=nir_user, doctor_admission_flow="pediatric_em")
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
        case = _cleaned(created_by=nir_user)
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
        case = _cleaned(created_by=nir_user)
        response = scheduler_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 302

    def test_form_validation_shows_error_for_empty_message(self, nir_client, nir_user):
        case = _cleaned(created_by=nir_user)
        response = nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "patient_absconded", "message": ""},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Mensagem é obrigatória" in content

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""
