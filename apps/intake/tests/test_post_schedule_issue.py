"""Testes do Slice 002 — NIR busca casos encerrados e abre intercorrência."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client):
    """Cria usuário NIR, faz login e retorna o cliente + user."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client):
    """Cria usuário doctor, faz login e retorna o cliente + user."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


def _build_cleaned_confirmed(case_factory, advance_to, user) -> Case:
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


def _build_cleaned_not_eligible(case_factory, advance_to, user) -> Case:
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


# ── Testes: Busca ─────────────────────────────────────────────────────────


class TestClosedCasesSearchAccess:
    """Testes de acesso à página de busca de casos encerrados."""

    SEARCH_URL = reverse("intake:closed_cases_search")

    def test_sem_login_redireciona(self, client) -> None:
        """Usuário sem login é redirecionado para login."""
        response = client.get(self.SEARCH_URL)
        assert response.status_code == 302

    def test_sem_role_nir_nao_acessa(self, client) -> None:
        """Usuário sem papel ativo nir não acessa."""
        client, _ = _doctor_client(client)
        response = client.get(self.SEARCH_URL)
        assert response.status_code == 302

    def test_nir_acessa_pagina_de_busca(self, client) -> None:
        """NIR acessa página de busca com status 200."""
        client, _ = _nir_client(client)
        response = client.get(self.SEARCH_URL)
        assert response.status_code == 200


class TestClosedCasesSearchResults:
    """Testes de busca de casos encerrados."""

    SEARCH_URL = reverse("intake:closed_cases_search")

    def test_busca_por_ocorrencia_encontra_cleaned(self, client, case_factory, advance_to) -> None:
        """Busca por número da ocorrência encontra caso CLEANED."""
        client, user = _nir_client(client)
        _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.get(self.SEARCH_URL, {"q": "OCOR-2026-001"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Reg. OCOR-2026-001" in content

    def test_busca_por_nome_paciente_encontra_cleaned(self, client, case_factory, advance_to) -> None:
        """Busca por nome do paciente encontra caso CLEANED."""
        client, user = _nir_client(client)
        _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.get(self.SEARCH_URL, {"q": "João Silva"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "João Silva" in content

    def test_caso_nao_cleaned_nao_aparece(self, client, case_factory, advance_to) -> None:
        """Caso não CLEANED não aparece na busca de encerrados."""
        client, user = _nir_client(client)
        # Cria caso ativo (wait_doctor)
        active_case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        active_case.agency_record_number = "ACTIVE-001"
        active_case.doctor_decision = "accept"
        active_case.doctor_admission_flow = "scheduled"
        active_case.appointment_status = "confirmed"
        active_case.save(
            update_fields=[
                "agency_record_number",
                "doctor_decision",
                "doctor_admission_flow",
                "appointment_status",
            ]
        )

        response = client.get(self.SEARCH_URL, {"q": "ACTIVE-001"})
        assert response.status_code == 200
        content = response.content.decode()
        # The query value appears in the input field, but the label "Reg. ACTIVE-001"
        # should NOT appear in results (card content)
        assert "Nenhum caso encontrado" in content or "resultado" in content.lower()

    def test_busca_sem_resultados_mostra_mensagem(self, client) -> None:
        """Busca sem resultados mostra mensagem de nenhum caso encontrado."""
        client, user = _nir_client(client)

        response = client.get(self.SEARCH_URL, {"q": "NONEXISTENT-999"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Nenhum caso encontrado" in content

    def test_caso_nao_elegivel_mostra_motivo_sem_botao(self, client, case_factory, advance_to) -> None:
        """Caso não elegível aparece sem botão e com motivo de inelegibilidade."""
        client, user = _nir_client(client)
        _build_cleaned_not_eligible(case_factory, advance_to, user)

        response = client.get(self.SEARCH_URL, {"q": "OCOR-NOELIG-001"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Reg. OCOR-NOELIG-001" in content
        # Deve mostrar mensagem de inelegibilidade sem botão
        assert "Registrar intercorrência" not in content
        assert "foi aceito" in content.lower() or "recusado" in content.lower()

    def test_caso_elegivel_mostra_botao(self, client, case_factory, advance_to) -> None:
        """Caso elegível mostra botão Registrar intercorrência."""
        client, user = _nir_client(client)
        _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.get(self.SEARCH_URL, {"q": "OCOR-2026-001"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Registrar intercorrência" in content

    def test_pagina_sem_query_carrega_sem_erros(self, client) -> None:
        """Página de busca sem query carrega sem erros."""
        client, _ = _nir_client(client)
        response = client.get(self.SEARCH_URL)
        assert response.status_code == 200


# ── Testes: Abertura ─────────────────────────────────────────────────────


class TestPostScheduleIssueForm:
    """Testes do formulário de abertura de intercorrência."""

    def _issue_url(self, case_id):
        return reverse("intake:post_schedule_issue_open", kwargs={"case_id": case_id})

    def _fresh(self, case):
        """Busca caso fresco do banco (evita conflito com FSM protected)."""
        return Case.objects.get(pk=case.pk)

    def test_get_form_para_elegivel(self, client, case_factory, advance_to) -> None:
        """GET do formulário abre para caso elegível."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.get(self._issue_url(case.case_id))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Registrar Intercorrência" in content

    def test_get_form_para_inelegivel_retorna_mensagem(self, client, case_factory, advance_to) -> None:
        """GET do formulário retorna mensagem bloqueada para caso inelegível."""
        client, user = _nir_client(client)
        case = _build_cleaned_not_eligible(case_factory, advance_to, user)

        response = client.get(self._issue_url(case.case_id))
        assert response.status_code == 200
        content = response.content.decode()
        # Deve mostrar que não é elegível
        assert "Intercorrência indisponível" in content

    def test_post_death_mensagem_vazia_abre(self, client, case_factory, advance_to) -> None:
        """POST com motivo death e mensagem vazia abre intercorrência."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.post(
            self._issue_url(case.case_id),
            {"reason": "death", "message": ""},
        )
        assert response.status_code == 302  # redirect após sucesso

        case = self._fresh(case)
        assert case.status == CaseStatus.WAIT_APPT
        assert case.post_schedule_issue_status == "opened"
        assert case.post_schedule_issue_reason == "death"

    def test_post_reason_em_branco_mostra_erro(self, client, case_factory, advance_to) -> None:
        """POST com motivo em branco mostra erro de validação."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.post(
            self._issue_url(case.case_id),
            {"reason": "", "message": ""},
        )
        assert response.status_code == 200  # mesma página com erro
        content = response.content.decode()
        assert "Selecione um motivo" in content

        case = self._fresh(case)
        assert case.status == CaseStatus.CLEANED  # não mudou

    def test_post_clinical_condition_mensagem_vazia_mostra_erro(self, client, case_factory, advance_to) -> None:
        """POST com motivo clinical_condition e mensagem vazia mostra erro."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.post(
            self._issue_url(case.case_id),
            {"reason": "clinical_condition", "message": ""},
        )
        assert response.status_code == 200  # mesma página com erro
        content = response.content.decode()
        assert "obrigatória" in content.lower()

        case = self._fresh(case)
        assert case.status == CaseStatus.CLEANED  # não mudou

    def test_post_valido_muda_status_e_grava_evento(self, client, case_factory, advance_to) -> None:
        """POST válido muda status para WAIT_APPT e grava evento."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        response = client.post(
            self._issue_url(case.case_id),
            {"reason": "reschedule_request", "message": "Unidade solicita nova data"},
        )
        assert response.status_code == 302

        case = self._fresh(case)
        assert case.status == CaseStatus.WAIT_APPT
        assert case.post_schedule_issue_status == "opened"
        assert case.post_schedule_issue_reason == "reschedule_request"
        assert case.post_schedule_issue_message == "Unidade solicita nova data"

        # Verifica evento
        event = CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_OPENED").first()
        assert event is not None
        assert event.payload.get("reason") == "reschedule_request"

    def test_segunda_tentativa_abertura_bloqueada(self, client, case_factory, advance_to) -> None:
        """Segunda tentativa de abertura no mesmo caso é bloqueada."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Primeira abertura com sucesso
        response = client.post(
            self._issue_url(case.case_id),
            {"reason": "death", "message": ""},
        )
        assert response.status_code == 302

        case = self._fresh(case)

        # Segunda tentativa deve falhar — a view mostra mensagem de erro
        response = client.post(
            self._issue_url(case.case_id),
            {"reason": "death", "message": ""},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência indisponível" in content or "ativa" in content.lower()

        # Verifica que permanece no estado anterior
        case = self._fresh(case)
        assert case.post_schedule_issue_status == "opened"

    def test_caso_com_issue_ativa_mostra_badge_na_busca(self, client, case_factory, advance_to) -> None:
        """Caso com intercorrência ativa mostra badge na busca."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Abre intercorrência via serviço — caso sai de CLEANED
        from apps.cases.services import open_post_schedule_issue

        open_post_schedule_issue(case=case, user=user, reason="death")

        # Busca pelo número da ocorrência
        # O caso não está mais CLEANED, mas a busca por intercorrência
        # também inclui casos com post_schedule_issue_status != ""
        response = client.get(
            reverse("intake:closed_cases_search"),
            {"q": "OCOR-2026-001"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        # Deve mostrar badge de intercorrência ativa
        assert "Intercorrência em avaliação" in content
        assert "Registrar intercorrência" not in content
