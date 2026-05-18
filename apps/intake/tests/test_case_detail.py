"""Testes da view case_detail — detalhes e timeline — Slice 5."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()


SAMPLE_PATIENT_NAME = "Maria da Silva"


def _case_with_patient(case: Case, name: str = SAMPLE_PATIENT_NAME) -> Case:
    """Set structured_data with patient name for a case."""
    case.structured_data = {"patient": {"name": name}}
    case.save()
    return case


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


# ── Tests: case_detail GET ───────────────────────────────────────────────


@pytest.mark.django_db
class TestCaseDetailRenders:
    """GET /intake/<uuid>/ — renderização básica da página de detalhe."""

    def test_case_detail_renders(self, client) -> None:
        """GET case/<uuid>/ retorna 200 para caso do NIR logado."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="2026-0505-001",
            status=CaseStatus.NEW,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200

    def test_case_detail_shows_record_number(self, client) -> None:
        """HTML contém agency_record_number do caso."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="REG-2026-0505",
            status=CaseStatus.NEW,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        assert "REG-2026-0505" in response.content.decode()

    def test_case_detail_shows_status(self, client) -> None:
        """HTML contém o label em português do status."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="STATUS-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Aguardando médico" in content

    def test_case_detail_shows_timeline(self, client) -> None:
        """HTML contém eventos de auditoria (CaseEvent)."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="TIMELINE-001",
            status=CaseStatus.NEW,
        )
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_CREATED",
            actor=user,
            actor_type="human",
        )
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_START_PROCESSING",
            actor=user,
            actor_type="human",
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        # Deve ter o elemento timeline-event
        assert "timeline-event" in content
        # Deve conter os labels em português dos eventos
        assert "Caso criado" in content
        assert "Processamento iniciado" in content

    def test_case_detail_has_pdf_embed(self, client) -> None:
        """HTML deve conter referência ao PDF (embed/object)."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="PDF-001",
            status=CaseStatus.NEW,
            pdf_file="pdfs/2026/05/test.pdf",
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        # Deve ter um iframe ou embed para o PDF
        assert ".pdf" in content or "iframe" in content

    def test_case_detail_shows_pdf_direct_link(self, client) -> None:
        """Quando tem pdf_file, HTML deve ter link direto para abrir o PDF."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="PDF-LINK",
            status=CaseStatus.NEW,
            pdf_file="pdfs/2026/05/test.pdf",
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "pdfs/2026/05/test.pdf" in content


@pytest.mark.django_db
class TestCaseDetailAuthorization:
    """Verificações de autorização e isolamento."""

    def test_case_detail_404_other_user(self, client) -> None:
        """NIR não vê caso de outro NIR (404)."""
        client, user = _nir_client(client)
        other_user = User.objects.create_user(username="other@test.com")
        other_case = Case.objects.create(
            created_by=other_user,
            agency_record_number="OTHER-999",
            status=CaseStatus.NEW,
        )
        response = client.get(reverse("intake:case_detail", args=[other_case.case_id]))
        assert response.status_code == 404

    def test_case_detail_404_nonexistent(self, client) -> None:
        """UUID inexistente → 404."""
        client, _ = _nir_client(client)
        response = client.get(reverse("intake:case_detail", args=["00000000-0000-0000-0000-000000000001"]))
        assert response.status_code == 404

    def test_case_detail_requires_nir(self, client) -> None:
        """Usuário doctor não pode ver detalhes (redirecionado)."""
        client, _ = _doctor_client(client)
        # Cria um caso qualquer
        some_user = User.objects.create_user(username="some@test.com")
        case = Case.objects.create(
            created_by=some_user,
            agency_record_number="ANY-001",
            status=CaseStatus.NEW,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        # role_required bloqueia → 302 (ou 404 dependendo da ordem)
        assert response.status_code in (302, 404)


# ── Tests: confirm_receipt ───────────────────────────────────────────────


@pytest.mark.django_db
class TestCaseDetailResultInfo:
    """Verifica exibição da seção de resultado final na página de detalhe."""

    def test_result_shows_accepted_scheduled(self, client) -> None:
        """APPT_CONFIRMED → mostra badge Agendamento Confirmado + data + suporte + fluxo."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="RES-ACCEPT",
                status=CaseStatus.APPT_CONFIRMED,
                appointment_at=timezone.now(),
                doctor_support_flag="anesthesist",
                doctor_admission_flow="scheduled",
                appointment_instructions="Chegar 30min antes",
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" in content
        assert "Anestesista" in content  # support
        assert "Agendamento" in content  # flow
        assert "Chegar 30min antes" in content

    def test_result_shows_accepted_scheduled_no_instructions(self, client) -> None:
        """APPT_CONFIRMED sem instruções → não quebra."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="RES-ACCEPT2",
                status=CaseStatus.APPT_CONFIRMED,
                appointment_at=timezone.now(),
                doctor_support_flag="anesthesist_icu",
                doctor_admission_flow="immediate",
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" in content
        assert "Anestesista + UTI" in content
        assert "Vinda Imediata" in content

    def test_result_shows_appt_denied(self, client) -> None:
        """APPT_DENIED → mostra badge Agendamento Negado + motivo."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="RES-DENY",
                status=CaseStatus.APPT_DENIED,
                appointment_reason="Vaga indisponível",
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Negado" in content
        assert "Vaga indisponível" in content

    def test_result_shows_doctor_denied(self, client) -> None:
        """DOCTOR_DENIED → mostra badge Recusado pelo Médico + motivo."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="RES-DOCDENY",
                status=CaseStatus.DOCTOR_DENIED,
                doctor_reason="Paciente não se enquadra",
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Recusado pelo Médico" in content
        assert "Paciente não se enquadra" in content

    def test_result_shows_failed(self, client) -> None:
        """FAILED → mostra badge Falha no Processamento."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="RES-FAIL",
                status=CaseStatus.FAILED,
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Falha no Processamento" in content

    def test_result_shows_terminal_with_result(self, client) -> None:
        """WAIT_R1_CLEANUP_THUMBS → mostra badge Agendamento Confirmado."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="RES-TERM",
                status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
                appointment_at=timezone.now(),
                doctor_support_flag="none",
                doctor_admission_flow="scheduled",
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" in content

    def test_result_shows_cleaned(self, client) -> None:
        """CLEANED → mostra badge Agendamento Confirmado."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="RES-CLEAN",
                status=CaseStatus.CLEANED,
                appointment_at=timezone.now(),
                doctor_support_flag="none",
                doctor_admission_flow="scheduled",
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" in content

    def test_result_hidden_for_in_progress(self, client) -> None:
        """WAIT_DOCTOR → badges de resultado não aparecem (stepper tem "Resultado Final" como label)."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="RES-HIDE",
                status=CaseStatus.WAIT_DOCTOR,
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        # Stepper tem step "Resultado Final", então verificamos badges específicos do card
        assert "Agendamento Confirmado" not in content
        assert "Agendamento Negado" not in content
        assert "Recusado pelo Médico" not in content
        assert "Falha no Processamento" not in content


@pytest.mark.django_db
class TestCaseDetailPatientName:
    """Verifica exibição do nome do paciente na página de detalhe."""

    def test_patient_name_in_top_info(self, client) -> None:
        """Nome do paciente aparece no topo quando disponível."""
        client, user = _nir_client(client)
        case = _case_with_patient(
            Case.objects.create(
                created_by=user,
                agency_record_number="NAME-001",
                status=CaseStatus.NEW,
            )
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert SAMPLE_PATIENT_NAME in content

    def test_patient_name_fallback_text(self, client) -> None:
        """Sem nome do paciente → fallback para texto extraído."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="NAME-002",
            status=CaseStatus.NEW,
            extracted_text="Relatório médico do paciente João",
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Relatório médico do paciente João" in content

    def test_patient_name_fallback_case_id(self, client) -> None:
        """Sem nome nem texto extraído → fallback para 'Caso <id truncado>'."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="NAME-003",
            status=CaseStatus.NEW,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Caso" in content


@pytest.mark.django_db
class TestCaseDetailScopeGatedResult:
    """Verifica exibição de resultado de revisão manual para casos scope-gated."""

    def test_scope_gated_shows_manual_review_badge(self, client) -> None:
        """WAIT_R1_CLEANUP_THUMBS com decision=manual_review_required mostra badge de revisão."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="SCOPE-001",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            suggested_action={
                "decision": "manual_review_required",
                "suggestion": "manual_review_required",
                "reason_code": "non_eda_request",
                "reason_text": "Relatorio fora de escopo EDA; revisao manual obrigatoria.",
                "exam_type": "non_eda",
            },
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Revisão Manual Obrigatória" in content
        assert "Relatorio fora de escopo EDA" in content

    def test_scope_gated_unknown_shows_manual_review_badge(self, client) -> None:
        """WAIT_R1_CLEANUP_THUMBS com reason_code=unknown_exam_type mostra badge de revisão."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="SCOPE-002",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            suggested_action={
                "decision": "manual_review_required",
                "suggestion": "manual_review_required",
                "reason_code": "unknown_exam_type",
                "reason_text": "Tipo de exame nao identificado; revisao manual obrigatoria.",
                "exam_type": "unknown",
            },
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Revisão Manual Obrigatória" in content
        assert "Tipo de exame nao identificado" in content

    def test_scope_gated_has_confirm_button(self, client) -> None:
        """Scope-gated case em WAIT_R1_CLEANUP_THUMBS mostra botão Confirmar."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="SCOPE-003",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            suggested_action={
                "decision": "manual_review_required",
                "reason_code": "non_eda_request",
                "reason_text": "Fora de escopo.",
            },
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Confirmar" in content

    def test_scope_gated_can_confirm_receipt(self, client) -> None:
        """Scope-gated case: POST confirm → transita para CLEANED."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="SCOPE-004",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            suggested_action={
                "decision": "manual_review_required",
                "reason_code": "non_eda_request",
                "reason_text": "Fora de escopo.",
            },
        )
        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            follow=True,
        )
        assert response.status_code == 200
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED

    def test_scope_gated_does_not_show_accepted_badge(self, client) -> None:
        """Scope-gated case não mostra badge 'Agendamento Confirmado'."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="SCOPE-005",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            suggested_action={
                "decision": "manual_review_required",
                "reason_code": "non_eda_request",
                "reason_text": "Fora de escopo.",
            },
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" not in content


@pytest.mark.django_db
class TestConfirmReceipt:
    """POST /intake/<uuid>/confirm/ — confirmação de recebimento."""

    def test_confirm_receipt_transitions_to_cleaned(self, client) -> None:
        """POST confirm quando WAIT_R1_CLEANUP_THUMBS → transita para CLEANED."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="CONFIRM-001",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )
        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            follow=True,
        )
        assert response.status_code == 200
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED

    def test_confirm_receipt_creates_events(self, client) -> None:
        """Confirmar recebimento deve gerar CLEANUP_TRIGGERED e CLEANUP_COMPLETED."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="CONFIRM-EVENTS",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )
        client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            follow=True,
        )
        events = CaseEvent.objects.filter(case=case)
        event_types = set(e.event_type for e in events)
        assert "CLEANUP_TRIGGERED" in event_types
        assert "CLEANUP_COMPLETED" in event_types

    def test_confirm_receipt_only_when_waiting(self, client) -> None:
        """POST confirm em status != WAIT_R1_CLEANUP_THUMBS → sem efeito."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="NO-CONFIRM",
            status=CaseStatus.NEW,
        )
        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            follow=True,
        )
        assert response.status_code == 200  # redireciona de volta
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.NEW  # Não mudou

    def test_confirm_receipt_shows_button(self, client) -> None:
        """WAIT_R1_CLEANUP_THUMBS → botão 'Confirmar Recebimento' aparece."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="SHOW-BTN",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Confirmar" in content

    def test_confirm_receipt_hides_button(self, client) -> None:
        """Status != WAIT_R1_CLEANUP_THUMBS → botão não aparece."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="HIDE-BTN",
            status=CaseStatus.NEW,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Confirmar" not in content

    def test_confirm_receipt_requires_nir(self, client) -> None:
        """Doctor não pode confirmar recebimento."""
        client, user = _doctor_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="DOC-CONFIRM",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )
        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
        )
        assert response.status_code in (302, 404)


@pytest.mark.django_db
class TestCaseDetailStepper:
    """Verifica que o stepper de progresso aparece com os estados corretos."""

    def test_stepper_is_present(self, client) -> None:
        """HTML deve conter o elemento steps-bar."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="STEP-001",
            status=CaseStatus.NEW,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        assert "steps-bar" in response.content.decode()

    def test_stepper_new_has_upload_current(self, client) -> None:
        """NEW → primeiro step marcado como 'current'."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="STEP-002",
            status=CaseStatus.NEW,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "current" in content

    def test_stepper_wait_doctor_shows_done_and_current(self, client) -> None:
        """WAIT_DOCTOR → upload + extração done, avaliação current."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="STEP-003",
            status=CaseStatus.WAIT_DOCTOR,
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        # Deve ter steps marcados como done
        assert "done" in content
        # Deve ter step marcado como current
        assert "current" in content


# ── Prior case lookup card tests ────────────────────────────────────────


@pytest.mark.django_db
class TestCaseDetailPriorCaseLookup:
    """Tests for PRIOR_CASE_LOOKUP card in case detail view."""

    def test_prior_case_card_appears_with_prior_case_lookup_event(self, client) -> None:
        """Card 'Caso Anterior' aparece quando há evento PRIOR_CASE_LOOKUP."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="PRIOR-EVT",
            status=CaseStatus.NEW,
        )
        CaseEvent.objects.create(
            case=case,
            event_type="PRIOR_CASE_LOOKUP",
            actor=user,
            actor_type="system",
            payload={
                "prior_case_id": "abc-123",
                "decision": "doctor_denied",
                "prior_denial_count_7d": 1,
            },
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Caso Anterior" in content
        assert "Triagem Negada" in content

    def test_prior_case_card_hidden_without_event(self, client) -> None:
        """Card não aparece quando não há evento PRIOR_CASE_LOOKUP."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="NO-PRIOR",
            status=CaseStatus.NEW,
        )
        # Create a different event, not PRIOR_CASE_LOOKUP
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_CREATED",
            actor=user,
            actor_type="system",
        )
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Caso Anterior" not in content
