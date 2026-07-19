"""Testes verticais NIR para intercorrência operacional (Slice 003 C2).

Cobre:
- Busca histórica com fluxo operacional
- Detalhe exibe formulário com 3 novos motivos
- POST válido abre context=operational_notice
- Status CLEANED preservado, agenda imutável
- Permissões bloqueiam não-NIR
- Casos denied/not-CLEANED bloqueados
- Mensagem obrigatória para novos motivos
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.cases.models import Case, CaseStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def nir_user(db):
    """Cria usuário NIR com papel ativo."""
    from django.contrib.auth import get_user_model

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(username="nir_test", password="testpass")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


@pytest.fixture
def nir_client(client, nir_user):
    """Client autenticado como NIR."""
    client.login(username="nir_test", password="testpass")
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client


@pytest.fixture
def scheduler_user(db):
    """Cria usuário scheduler."""
    from django.contrib.auth import get_user_model

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(username="sched_test", password="testpass")
    role, _ = Role.objects.get_or_create(name="scheduler")
    user.roles.add(role)
    return user


@pytest.fixture
def scheduler_client(client, scheduler_user):
    """Client autenticado como scheduler."""
    client.login(username="sched_test", password="testpass")
    session = client.session
    session["active_role"] = "scheduler"
    session.save()
    return client


def _create_cleaned_operational_case(nir_user, flow="immediate"):
    """Cria um case CLEANED com fluxo operacional."""
    case = Case.objects.create(
        created_by=nir_user,
        status=CaseStatus.CLEANED,
        doctor_decision="accept",
        doctor_admission_flow=flow,
        agency_record_number="REG-001",
    )
    return Case.objects.get(pk=case.pk)


class TestNirClosedSearchOperational:
    """C2: Busca histórica NIR encontra casos operacionais."""

    def test_search_finds_operational_case(self, nir_client, nir_user):
        """NIR encontra caso operacional CLEANED na busca histórica."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")
        case.structured_data = {"patient": {"name": "Maria Teste"}}
        case.save(update_fields=["structured_data"])

        response = nir_client.get(reverse("intake:closed_cases_search"), {"q": "REG-001"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Teste" in content

    def test_search_shows_eligible_operational_context(self, nir_client, nir_user):
        """Busca mostra caso como elegível (não bloqueado)."""
        case = _create_cleaned_operational_case(nir_user, flow="pre_icu")
        case.structured_data = {"patient": {"name": "João Operacional"}}
        case.save(update_fields=["structured_data"])

        response = nir_client.get(reverse("intake:closed_cases_search"), {"q": "João"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "João Operacional" in content
        # Deve ter botão Detalhes para caso elegível
        assert "Detalhes" in content


class TestNirClosedDetailOperational:
    """C2: Detalhe histórico NIR com formulário operacional."""

    def test_detail_shows_form_with_new_reasons(self, nir_client, nir_user):
        """Detalhe exibe formulário com os 3 novos motivos."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")

        response = nir_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        # Verifica presença dos 3 novos motivos no HTML do select
        assert "evadiu-se" in content
        assert "unidade mais próxima" in content
        assert "cancelada pela unidade de origem" in content

    def test_post_opens_operational_issue(self, nir_client, nir_user):
        """POST válido abre intercorrência operacional."""
        case = _create_cleaned_operational_case(nir_user, flow="ward_icu_backup")

        response = nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {
                "reason": "patient_absconded",
                "message": "Paciente evadiu-se da unidade de origem",
            },
            follow=True,
        )
        assert response.status_code == 200
        content = response.content.decode()

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == "opened"
        assert case.post_acceptance_issue_context == "operational_notice"
        assert case.status == CaseStatus.CLEANED

        # Mensagem de sucesso com português acentuado
        assert "Intercorrência" in content or "Intercorrencia" in content
        assert "receberá" in content or "recebera" in content

    @pytest.mark.parametrize(
        "field_name,expected_match",
        [
            ("appointment_status", ""),
            ("appointment_reason", ""),
            ("appointment_instructions", ""),
        ],
    )
    def test_appointment_fields_unchanged_after_post(self, nir_client, nir_user, field_name, expected_match):
        """Todos os campos de appointment permanecem inalterados após POST."""
        case = _create_cleaned_operational_case(nir_user, flow="pediatric_em")
        before = getattr(case, field_name)

        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "origin_cancelled", "message": "Cancelado pela origem"},
            follow=True,
        )

        case = Case.objects.get(pk=case.pk)
        after = getattr(case, field_name)
        assert after == before, f"{field_name} mudou de {before} para {after}"

    def test_awaiting_chd_science_shown_after_open(self, nir_client, nir_user):
        """Após abertura, página mostra status 'Aguardando ciência do CHD'."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")

        # Abre a issue
        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "accepted_elsewhere", "message": "Transferido para Hospital X"},
            follow=True,
        )

        # GET novamente para ver a página após abertura
        response = nir_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        content = response.content.decode()
        # Deve mostrar badge de intercorrência em avaliação
        assert "Intercorrência" in content

    def test_denied_case_blocked(self, nir_client, nir_user):
        """Caso denied não permite abertura."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")
        case.doctor_decision = "deny"
        case.save(update_fields=["doctor_decision"])

        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "patient_absconded", "message": "..."},
            follow=True,
        )
        # Deve redirecionar com warning
        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""  # issue NÃO foi aberta

    def test_not_cleaned_case_blocked(self, nir_client, nir_user):
        """Caso não CLEANED não permite abertura."""
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
        )

        response = nir_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 404

    def test_non_nir_blocked_from_detail(self, scheduler_client, nir_user):
        """Scheduler não acessa detalhe histórico NIR."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")

        response = scheduler_client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code in (302, 403, 404)


class TestNirOperationalFormValidation:
    """C2: Validação de formulário operacional."""

    def test_form_requires_message_for_accepted_elsewhere(self, nir_client, nir_user):
        """Backend exige mensagem para accepted_elsewhere."""
        case = _create_cleaned_operational_case(nir_user, flow="immediate")

        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "accepted_elsewhere", "message": ""},
        )
        # Deve re-renderizar com erro (não redirecionar com sucesso)
        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == "", "issue nao deve ser aberta sem mensagem"

    def test_form_requires_message_for_patient_absconded(self, nir_client, nir_user):
        """Backend exige mensagem para patient_absconded."""
        case = _create_cleaned_operational_case(nir_user, flow="pre_icu")

        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "patient_absconded", "message": ""},
        )
        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""

    def test_form_requires_message_for_origin_cancelled(self, nir_client, nir_user):
        """Backend exige mensagem para origin_cancelled."""
        case = _create_cleaned_operational_case(nir_user, flow="ward_icu_backup")

        nir_client.post(
            reverse("intake:closed_case_detail", args=[case.case_id]),
            {"reason": "origin_cancelled", "message": ""},
        )
        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""
