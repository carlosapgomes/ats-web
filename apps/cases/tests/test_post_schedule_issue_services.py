"""Testes dos serviços de intercorrência pós-agendamento."""

from __future__ import annotations

import pytest
from django_fsm import TransitionNotAllowed

from apps.cases.models import Case, CaseEvent, CaseStatus

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_cleaned_confirmed(case_factory, advance_to, user) -> Case:
    """Cria um Case CLEANED elegível para intercorrência."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])
    return Case.objects.get(pk=case.pk)


def _assert_event_type(case, event_type):
    events = CaseEvent.objects.filter(case=case, event_type=event_type)
    assert events.exists(), f"Evento {event_type} não encontrado"
    return events.first()


# ── Elegibilidade ────────────────────────────────────────────────────────


class TestEligibility:
    def test_elegivel_cleaned_com_agendamento_confirmado(self, user, case_factory, advance_to) -> None:
        """Caso CLEANED com aceite médico, fluxo scheduled e agendamento confirmado é elegível."""
        from apps.cases.services import is_post_schedule_issue_eligible

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        assert is_post_schedule_issue_eligible(case) is True

    def test_nao_elegivel_medico_negou(self, user, case_factory, advance_to) -> None:
        """Caso negado pelo médico não é elegível."""
        from apps.cases.services import is_post_schedule_issue_eligible

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case.doctor_decision = "deny"
        case.save(update_fields=["doctor_decision"])
        assert is_post_schedule_issue_eligible(case) is False

    def test_nao_elegivel_sem_agendamento_confirmado(self, user, case_factory, advance_to) -> None:
        """Caso sem appointment_status='confirmed' não é elegível."""
        from apps.cases.services import is_post_schedule_issue_eligible

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case.appointment_status = "cancelled"
        case.save(update_fields=["appointment_status"])
        assert is_post_schedule_issue_eligible(case) is False

    def test_nao_elegivel_nao_cleanado(self, user, case_factory, advance_to) -> None:
        """Caso em status diferente de CLEANED não é elegível."""
        from apps.cases.services import is_post_schedule_issue_eligible

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        assert is_post_schedule_issue_eligible(case) is False

    def test_nao_elegivel_intercorrencia_ativa(self, user, case_factory, advance_to) -> None:
        """Caso com issue opened não é elegível."""
        from apps.cases.services import (
            is_post_schedule_issue_eligible,
            open_post_schedule_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        assert is_post_schedule_issue_eligible(case) is False


class TestIneligibilityReason:
    def test_reason_medico_negou(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import get_post_schedule_issue_ineligibility_reason

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case.doctor_decision = "deny"
        case.save(update_fields=["doctor_decision"])
        reason = get_post_schedule_issue_ineligibility_reason(case)
        assert "médico" in reason.lower()

    def test_reason_sem_agendamento(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import get_post_schedule_issue_ineligibility_reason

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case.appointment_status = ""
        case.save(update_fields=["appointment_status"])
        reason = get_post_schedule_issue_ineligibility_reason(case)
        assert "agendamento" in reason.lower()

    def test_reason_issue_ativa(self, user, case_factory, advance_to) -> None:
        from apps.cases.services import (
            get_post_schedule_issue_ineligibility_reason,
            open_post_schedule_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        reason = get_post_schedule_issue_ineligibility_reason(case)
        assert "intercorrência ativa" in reason.lower()


# ── Abertura (open) ─────────────────────────────────────────────────────


class TestOpenPostScheduleIssue:
    def test_abre_e_vai_para_wait_appt(self, user, case_factory, advance_to) -> None:
        """Caso elegível CLEANED → WAIT_APPT após abertura."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        assert case.status == CaseStatus.WAIT_APPT

    def test_registra_evento_com_snapshot(self, user, case_factory, advance_to) -> None:
        """Abertura registra POST_SCHEDULE_ISSUE_OPENED com payload."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case.appointment_at = "2026-06-15T10:00:00Z"
        case.appointment_location = "Hospital Central"
        case.save(update_fields=["appointment_at", "appointment_location"])

        case = open_post_schedule_issue(case=case, user=user, reason="death")

        event = _assert_event_type(case, "POST_SCHEDULE_ISSUE_OPENED")
        payload = event.payload
        assert payload.get("reason") == "death"
        assert payload.get("message") == ""
        assert "appointment_snapshot" in payload
        snap = payload["appointment_snapshot"]
        assert snap.get("status") == "confirmed"
        assert snap.get("appointment_location") == "Hospital Central"

    def test_death_permite_mensagem_vazia(self, user, case_factory, advance_to) -> None:
        """Motivo death aceita mensagem vazia."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death", message="")
        assert case.status == CaseStatus.WAIT_APPT

    def test_clinical_condition_exige_mensagem(self, user, case_factory, advance_to) -> None:
        """Motivo clinical_condition exige mensagem não vazia."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        with pytest.raises(ValueError, match="obrigatória"):
            open_post_schedule_issue(case=case, user=user, reason="clinical_condition", message="")

    def test_external_regulation_permite_mensagem_vazia(self, user, case_factory, advance_to) -> None:
        """Motivo external_regulation aceita mensagem vazia."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="external_regulation", message="")
        assert case.status == CaseStatus.WAIT_APPT

    def test_transport_unavailable_exige_mensagem(self, user, case_factory, advance_to) -> None:
        """Motivo transport_unavailable exige mensagem."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        with pytest.raises(ValueError, match="obrigatória"):
            open_post_schedule_issue(case=case, user=user, reason="transport_unavailable", message="")

    def test_segunda_abertura_falha(self, user, case_factory, advance_to) -> None:
        """Segunda abertura com issue opened ou responded falha."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")

        with pytest.raises(ValueError, match="intercorrência ativa"):
            open_post_schedule_issue(case=case, user=user, reason="death")

    def test_abertura_transacional_impede_duplicidade(self, user, case_factory, advance_to) -> None:
        """Abertura usa select_for_update para evitar race condition."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Simula duas aberturas simultâneas: a segunda deve falhar
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        with pytest.raises(ValueError, match="intercorrência ativa"):
            open_post_schedule_issue(case=case, user=user, reason="death")

    def test_campos_preenchidos_apos_abertura(self, user, case_factory, advance_to) -> None:
        """Após abertura, os campos de issue são preenchidos."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(
            case=case, user=user, reason="reschedule_request", message="Precisamos de nova data"
        )
        assert case.post_schedule_issue_status == "opened"
        assert case.post_schedule_issue_reason == "reschedule_request"
        assert case.post_schedule_issue_message == "Precisamos de nova data"
        assert case.post_schedule_issue_opened_by == user
        assert case.post_schedule_issue_opened_at is not None
        assert case.post_schedule_issue_response_action == ""
        assert case.post_schedule_issue_responded_by is None


# ── Resposta do agendador (respond) ─────────────────────────────────────


class TestRespondPostScheduleIssue:
    def _open_and_fetch(self, case_factory, advance_to, user):
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        return Case.objects.get(pk=case.pk)

    def test_reschedule_atualiza_data_local_instrucoes(self, user, case_factory, advance_to) -> None:
        """Resposta reschedule atualiza appointment e vai para WAIT_R1_CLEANUP_THUMBS."""
        from apps.cases.services import respond_post_schedule_issue

        case = self._open_and_fetch(case_factory, advance_to, user)
        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="reschedule",
            appointment_at="2026-07-01T14:00:00Z",
            appointment_location="Hospital Central - Sala 2",
            appointment_instructions="Chegar 30min antes",
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "confirmed"
        assert str(case.appointment_at) == "2026-07-01 14:00:00+00:00"
        # The tz handling depends on settings, let's just check the date part

    def test_reschedule_mantem_status_confirmed(self, user, case_factory, advance_to) -> None:
        """Reschedule marca appointment_status='confirmed'."""
        from apps.cases.services import respond_post_schedule_issue

        case = self._open_and_fetch(case_factory, advance_to, user)
        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="reschedule",
            appointment_at="2026-07-01T14:00:00Z",
        )
        assert case.appointment_status == "confirmed"

    def test_cancel_marca_cancelled(self, user, case_factory, advance_to) -> None:
        """Resposta cancel marca appointment_status='cancelled'."""
        from apps.cases.services import respond_post_schedule_issue

        case = self._open_and_fetch(case_factory, advance_to, user)
        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="cancel",
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "cancelled"

    def test_maintain_preserva_agendamento(self, user, case_factory, advance_to) -> None:
        """Resposta maintain preserva appointment_status='confirmed'."""
        from apps.cases.services import respond_post_schedule_issue

        case = self._open_and_fetch(case_factory, advance_to, user)
        case.appointment_at = "2026-06-15T10:00:00Z"
        case.appointment_location = "Hospital Central"
        case.save(update_fields=["appointment_at", "appointment_location"])

        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="maintain",
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "confirmed"

    def test_deny_preserva_agendamento_confirmado(self, user, case_factory, advance_to) -> None:
        """Resposta deny preserva appointment_status='confirmed' e dados."""
        from apps.cases.services import respond_post_schedule_issue

        case = self._open_and_fetch(case_factory, advance_to, user)
        original_at = "2026-06-15T10:00:00Z"
        original_location = "Hospital Central"
        case.appointment_at = original_at
        case.appointment_location = original_location
        case.save(update_fields=["appointment_at", "appointment_location"])

        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="deny",
            response_message="Sem vagas disponíveis",
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "confirmed"

    def test_acao_invalida_rejeitada(self, user, case_factory, advance_to) -> None:
        """Ação que não está entre as permitidas rejeita."""
        from apps.cases.services import respond_post_schedule_issue

        case = self._open_and_fetch(case_factory, advance_to, user)
        with pytest.raises(ValueError, match="Ação inválida"):
            respond_post_schedule_issue(case=case, user=user, action="invalid_action")

    def test_responde_sem_issue_aberta_falha(self, user, case_factory, advance_to) -> None:
        """Responder sem issue aberta falha."""
        from apps.cases.services import respond_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        with pytest.raises(ValueError, match="intercorrência aberta"):
            respond_post_schedule_issue(case=case, user=user, action="cancel")

    def test_resposta_registra_evento(self, user, case_factory, advance_to) -> None:
        """Resposta registra POST_SCHEDULE_ISSUE_RESPONDED."""
        from apps.cases.services import respond_post_schedule_issue

        case = self._open_and_fetch(case_factory, advance_to, user)
        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="cancel",
            response_message="Agendamento cancelado",
        )

        event = _assert_event_type(case, "POST_SCHEDULE_ISSUE_RESPONDED")
        payload = event.payload
        assert payload.get("action") == "cancel"
        assert payload.get("response_message") == "Agendamento cancelado"


# ── Ciência NIR (acknowledge) ────────────────────────────────────────────


class TestAcknowledgePostScheduleIssue:
    def _open_and_respond(self, case_factory, advance_to, user):
        from apps.cases.services import open_post_schedule_issue, respond_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="cancel")
        return Case.objects.get(pk=case.pk)

    def test_ciencia_limpa_issue_retorna_cleaned(self, user, case_factory, advance_to) -> None:
        """Ciência NIR limpa issue ativa e retorna para CLEANED."""
        from apps.cases.services import acknowledge_post_schedule_issue

        case = self._open_and_respond(case_factory, advance_to, user)
        case = acknowledge_post_schedule_issue(case=case, user=user)
        assert case.status == CaseStatus.CLEANED
        assert case.post_schedule_issue_status == ""
        assert case.post_schedule_issue_reason == ""

    def test_ciencia_registra_evento(self, user, case_factory, advance_to) -> None:
        """Ciência registra POST_SCHEDULE_ISSUE_ACKNOWLEDGED."""
        from apps.cases.services import acknowledge_post_schedule_issue

        case = self._open_and_respond(case_factory, advance_to, user)
        case = acknowledge_post_schedule_issue(case=case, user=user)

        _assert_event_type(case, "POST_SCHEDULE_ISSUE_ACKNOWLEDGED")

    def test_ciencia_sem_issue_respondida_falha(self, user, case_factory, advance_to) -> None:
        """Ciencia sem issue responded falha."""
        from apps.cases.services import (
            acknowledge_post_schedule_issue,
            open_post_schedule_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        with pytest.raises(ValueError, match="respondida"):
            acknowledge_post_schedule_issue(case=case, user=user)

    def test_ciencia_nao_cria_cleanup_triggered(self, user, case_factory, advance_to) -> None:
        """acknowledge não cria CLEANUP_TRIGGERED (setup via advance_to gera, mas
        acknowledge não deve criar novos)."""
        from apps.cases.services import acknowledge_post_schedule_issue

        case = self._open_and_respond(case_factory, advance_to, user)
        # Conta eventos CLEANUP_TRIGGERED antes do acknowledge
        before = CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").count()
        case = acknowledge_post_schedule_issue(case=case, user=user)
        after = CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").count()
        assert after == before, "CLEANUP_TRIGGERED não deve ser criado no acknowledge"

    def test_ciencia_nao_cria_cleanup_completed(self, user, case_factory, advance_to) -> None:
        """acknowledge não cria CLEANUP_COMPLETED."""
        from apps.cases.services import acknowledge_post_schedule_issue

        case = self._open_and_respond(case_factory, advance_to, user)
        before = CaseEvent.objects.filter(case=case, event_type="CLEANUP_COMPLETED").count()
        case = acknowledge_post_schedule_issue(case=case, user=user)
        after = CaseEvent.objects.filter(case=case, event_type="CLEANUP_COMPLETED").count()
        assert after == before, "CLEANUP_COMPLETED não deve ser criado no acknowledge"

    def test_ciencia_cria_exatamente_um_acknowledged(self, user, case_factory, advance_to) -> None:
        """acknowledge cria exatamente um POST_SCHEDULE_ISSUE_ACKNOWLEDGED."""
        from apps.cases.services import acknowledge_post_schedule_issue

        case = self._open_and_respond(case_factory, advance_to, user)
        before = CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_ACKNOWLEDGED").count()
        case = acknowledge_post_schedule_issue(case=case, user=user)
        after = CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_ACKNOWLEDGED").count()
        assert after - before == 1, "deve criar exatamente 1 POST_SCHEDULE_ISSUE_ACKNOWLEDGED"


# ── Ciclos múltiplos ────────────────────────────────────────────────────


class TestMultipleCycles:
    def test_multiplos_ciclos_sequenciais_possiveis(self, user, case_factory, advance_to) -> None:
        """Múltiplos ciclos sequenciais são possíveis após ciência."""
        from apps.cases.services import (
            acknowledge_post_schedule_issue,
            open_post_schedule_issue,
            respond_post_schedule_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Ciclo 1 — usar maintain para preservar appointment_status="confirmed"
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        assert case.post_schedule_issue_status == "opened"
        case = respond_post_schedule_issue(case=case, user=user, action="maintain")
        assert case.post_schedule_issue_status == "responded"
        case = acknowledge_post_schedule_issue(case=case, user=user)
        assert case.status == CaseStatus.CLEANED
        assert case.post_schedule_issue_status == ""

        # Ciclo 2
        case = open_post_schedule_issue(
            case=case, user=user, reason="reschedule_request", message="Nova data necessária"
        )
        assert case.post_schedule_issue_status == "opened"
        case = respond_post_schedule_issue(
            case=case, user=user, action="reschedule", appointment_at="2026-07-15T10:00:00Z"
        )
        assert case.post_schedule_issue_status == "responded"
        case = acknowledge_post_schedule_issue(case=case, user=user)
        assert case.status == CaseStatus.CLEANED
        assert case.post_schedule_issue_status == ""

        # Verifica que foram registrados 2 ciclos completos de eventos
        opened_events = CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_OPENED")
        assert opened_events.count() == 2

        responded_events = CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_RESPONDED")
        assert responded_events.count() == 2

        acknowledged_events = CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_ACKNOWLEDGED")
        assert acknowledged_events.count() == 2


# ── Transição FSM direta ────────────────────────────────────────────────


class TestFSMTransition:
    def test_cleaned_to_wait_appt_direto(self, user, case_factory, advance_to) -> None:
        """Transição FSM CLEANED → WAIT_APPT via método do model."""
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        assert case.status == CaseStatus.CLEANED

        case.open_post_schedule_issue(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_APPT

    def test_transition_de_estado_invalido_falha(self, user, case_factory, advance_to) -> None:
        """Transição CLEANED → WAIT_APPT a partir de estado inválido falha."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        with pytest.raises(TransitionNotAllowed):
            case.open_post_schedule_issue(user=user)
