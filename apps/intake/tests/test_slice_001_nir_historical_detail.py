"""Testes do Slice 001 — NIR histórico: cards → detalhe → intercorrência.

RED phase: all tests should fail before implementation.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Role
from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client: Any) -> tuple[Any, Any]:
    """Cria usuário NIR, faz login e retorna o cliente + user."""
    user = User.objects.create_user(username="nir@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client: Any) -> tuple[Any, Any]:
    """Cria usuário doctor, faz login e retorna o cliente + user."""
    user = User.objects.create_user(username="doc@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


def _build_cleaned_confirmed(case_factory: Any, advance_to: Any, user: Any) -> Case:
    """Cria um Case CLEANED elegível para intercorrência."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.agency_record_number = "OCOR-2026-001"
    case.structured_data = {
        "patient": {"name": "João Silva", "age": 45, "sex": "M"},
        "eda": {"indication_category": "HDA"},
    }
    case.save(
        update_fields=[
            "doctor_decision",
            "doctor_admission_flow",
            "appointment_status",
            "agency_record_number",
            "structured_data",
        ]
    )
    return Case.objects.get(pk=case.pk)


def _build_cleaned_not_eligible(case_factory: Any, advance_to: Any, user: Any) -> Case:
    """Cria um Case CLEANED mas não elegível (médico negou)."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "deny"
    case.agency_record_number = "OCOR-NOELIG-001"
    case.structured_data = {
        "patient": {"name": "Maria Souza", "age": 60, "sex": "F"},
    }
    case.save(
        update_fields=[
            "doctor_decision",
            "agency_record_number",
            "structured_data",
        ]
    )
    return Case.objects.get(pk=case.pk)


def _build_operational_case(case_factory: Any, advance_to: Any, user: Any) -> Case:
    """Cria um caso operacional comum (WAIT_DOCTOR), não CLEANED."""
    case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
    case.agency_record_number = "OCOR-OP-001"
    case.structured_data = {
        "patient": {"name": "Carlos Pereira", "age": 50, "sex": "M"},
    }
    case.save(update_fields=["agency_record_number", "structured_data"])
    return Case.objects.get(pk=case.pk)


# ── Test R1: Busca com cards e Detalhes ─────────────────────────────────


class TestClosedCasesSearchCards:
    """R1: A busca de encerrados deve mostrar cards com botão Detalhes."""

    SEARCH_URL = reverse("intake:closed_cases_search")

    def test_closed_cases_search_renders_cards_with_details_link(
        self, client: Any, case_factory: Any, advance_to: Any
    ) -> None:
        """Busca encontra caso CLEANED; resposta contém 'Detalhes'; link aponta
        para closed_case_detail; não contém botão primário direto 'Registrar
        intercorrência' no card."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.get(self.SEARCH_URL, {"q": "OCOR-2026"})
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Deve conter link de Detalhes
        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        assert "Detalhes" in content
        assert detail_url in content

        # Não deve conter botão direto "Registrar intercorrência"
        register_url = reverse("intake:post_schedule_issue_open", kwargs={"case_id": case.case_id})
        assert register_url not in content


# ── Test R2: Detalhe histórico NIR ───────────────────────────────────────


class TestClosedCaseDetailAccess:
    """R2: Acesso ao detalhe histórico NIR."""

    def test_closed_case_detail_requires_nir_role(self, client: Any, case_factory: Any, advance_to: Any) -> None:
        """Usuário sem papel ativo nir não acessa o detalhe histórico."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})

        # Desloga NIR e loga como doctor
        client, _ = _doctor_client(client)
        response = client.get(detail_url)
        assert response.status_code in (302, 403)

    def test_closed_case_detail_renders_cleaned_case_context(
        self, client: Any, case_factory: Any, advance_to: Any
    ) -> None:
        """NIR abre detalhe de caso CLEANED; vê paciente/ocorrência/status;
        vê timeline ou eventos principais; vê thread de comunicação."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        response = client.get(detail_url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Vê nome do paciente
        assert "João Silva" in content
        # Vê ocorrência
        assert "OCOR-2026-001" in content
        # Vê status
        assert "Concluído" in content or "CLEANED" in content
        # Vê timeline (eventos do caso)
        events = case.events.all()
        if events:
            first_event = events[0]
            # O label do evento deve estar no HTML
            from apps.intake.views import EVENT_LABELS

            label = EVENT_LABELS.get(first_event.event_type, first_event.event_type)
            assert label in content

    def test_closed_case_detail_blocks_non_historical_operational_case(
        self, client: Any, case_factory: Any, advance_to: Any
    ) -> None:
        """Caso operacional comum não deve ser aberto pela rota histórica."""
        client, user = _nir_client(client)
        case = _build_operational_case(case_factory, advance_to, user)

        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        response = client.get(detail_url)
        assert response.status_code == 404

    def test_closed_case_detail_does_not_acquire_lock(self, client: Any, case_factory: Any, advance_to: Any) -> None:
        """O detalhe histórico não adquire lock no caso."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        response = client.get(detail_url)
        assert response.status_code == 200

        # Recarregar o caso do banco e verificar que não há lock
        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.locked_by is None
        assert fresh_case.lock_token is None


# ── Test R3: PDF histórico ──────────────────────────────────────────────


class TestClosedCasePdf:
    """R3: Servir PDF de caso encerrado para NIR."""

    def test_closed_case_pdf_serves_cleaned_pdf_for_nir(self, client: Any, case_factory: Any, advance_to: Any) -> None:
        """NIR pode ver PDF de caso CLEANED pela rota histórica."""
        from django.core.files.base import ContentFile

        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Adicionar PDF ao caso
        case.pdf_file.save("test.pdf", ContentFile(b"%PDF-1.4 mock pdf content"))
        case.save(update_fields=["pdf_file"])

        pdf_url = reverse("intake:closed_case_pdf", kwargs={"case_id": case.case_id})
        response = client.get(pdf_url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"


# ── Test R4: Intercorrência dentro do detalhe ───────────────────────────


class TestIntercurrenceInsideDetail:
    """R4: Dentro do detalhe histórico, NIR abre intercorrência."""

    def test_closed_case_detail_shows_post_schedule_issue_form_when_eligible(
        self, client: Any, case_factory: Any, advance_to: Any
    ) -> None:
        """Caso elegível exibe formulário de intercorrência no detalhe."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        response = client.get(detail_url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Deve conter formulário de intercorrência
        assert "Registrar intercorrência" in content
        assert "Motivo" in content

    def test_closed_case_detail_shows_ineligibility_reason_when_not_eligible(
        self, client: Any, case_factory: Any, advance_to: Any
    ) -> None:
        """Caso não elegível exibe motivo claro."""
        client, user = _nir_client(client)
        case = _build_cleaned_not_eligible(case_factory, advance_to, user)

        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        response = client.get(detail_url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Deve conter motivo de inelegibilidade
        assert "Intercorrência indisponível" in content or "não" in content.lower()

    def test_nir_opens_post_schedule_issue_from_detail(self, client: Any, case_factory: Any, advance_to: Any) -> None:
        """POST válido via detalhe abre intercorrência; caso vai para WAIT_APPT."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        response = client.post(
            detail_url,
            {
                "reason": "death",
                "message": "Paciente faleceu antes do procedimento.",
            },
        )
        # Deve redirecionar (302) após sucesso
        assert response.status_code == 302

        # Recarregar o caso
        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.status == CaseStatus.WAIT_APPT
        assert fresh_case.post_schedule_issue_status == "opened"

        # Deve ter evento POST_SCHEDULE_ISSUE_OPENED
        assert CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_OPENED").exists()

    def test_second_active_issue_is_blocked_from_detail(self, client: Any, case_factory: Any, advance_to: Any) -> None:
        """Se já houver intercorrência ativa, detalhe não permite abrir outra."""
        from apps.cases.services import open_post_schedule_issue

        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Abrir primeira intercorrência
        open_post_schedule_issue(case=case, user=user, reason="death", message="Primeira intercorrência.")

        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        response = client.get(detail_url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Deve mostrar mensagem de inelegibilidade, não formulário
        assert "Intercorrência indisponível" in content or "Já existe" in content


# ── Test R5: Comunicação no detalhe ──────────────────────────────────────


class TestCommunicationInDetail:
    """R5: Detalhe histórico mostra thread de comunicação."""

    def test_closed_case_detail_shows_communication_thread(
        self, client: Any, case_factory: Any, advance_to: Any
    ) -> None:
        """Detalhe histórico exibe mensagens de comunicação existentes."""
        from apps.cases.models import CaseCommunicationMessage

        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Criar uma mensagem de comunicação
        CaseCommunicationMessage.objects.create(
            case=case,
            author=user,
            author_role="nir",
            body="Mensagem de teste para o histórico.",
        )

        detail_url = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        response = client.get(detail_url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        assert "Mensagem de teste para o histórico" in content


# ── Test R6: Redirect de notificação NIR ─────────────────────────────────


class TestNirNotificationRedirect:
    """R6: Notificação NIR para caso CLEANED redireciona para detalhe histórico."""

    def test_nir_notification_for_cleaned_case_redirects_to_closed_case_detail(
        self, client: Any, case_factory: Any, advance_to: Any
    ) -> None:
        """resolve_notification_redirect_url com active_role='nir' e
        status=CLEANED retorna intake:closed_case_detail."""
        from apps.accounts.services import resolve_notification_redirect_url

        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        url = resolve_notification_redirect_url(case=case, user=user, active_role="nir")
        expected = reverse("intake:closed_case_detail", kwargs={"case_id": case.case_id})
        assert url == expected
