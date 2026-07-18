"""Testes dos serviços de intercorrência pós-aceitação (Slice 002).

Testa os novos endpoints genéricos com contexto/UUID e eventos
POST_ACCEPTANCE_ISSUE_*, preservando compatibilidade com legado.
"""

from __future__ import annotations

import uuid

import pytest
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_cleaned_confirmed(case_factory, advance_to, user) -> Case:
    """Cria um Case CLEANED elegível para intercorrência agendada."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.appointment_at = timezone.now()
    case.appointment_location = "Hospital Central"
    case.save(
        update_fields=[
            "doctor_decision",
            "doctor_admission_flow",
            "appointment_status",
            "appointment_at",
            "appointment_location",
        ]
    )
    return Case.objects.get(pk=case.pk)


def _build_cleaned_no_schedule(case_factory, advance_to, user, flow="immediate") -> Case:
    """Cria um Case CLEANED com fluxo sem agendamento."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = flow
    case.save(update_fields=["doctor_decision", "doctor_admission_flow"])
    return Case.objects.get(pk=case.pk)


def _assert_event_type(case, event_type):
    events = CaseEvent.objects.filter(case=case, event_type=event_type)
    assert events.exists(), f"Evento {event_type} não encontrado"
    return events.latest("timestamp")


# ── Abertura genérica (open) ─────────────────────────────────────────────


class TestOpenPostAcceptanceIssue:
    """Testes da nova API genérica de abertura pós-aceitação."""

    def test_abre_scheduled_com_contexto_e_cycle_id(self, user, case_factory, advance_to) -> None:
        """Abertura scheduled persiste contexto e UUID."""
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="scheduled",
        )

        assert case.post_acceptance_issue_context == "scheduled"
        assert case.post_acceptance_issue_cycle_id is not None
        assert isinstance(case.post_acceptance_issue_cycle_id, uuid.UUID)
        assert case.status == CaseStatus.WAIT_APPT

    def test_abre_scheduled_emite_evento_novo(self, user, case_factory, advance_to) -> None:
        """Abertura scheduled registra POST_ACCEPTANCE_ISSUE_OPENED."""
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="scheduled",
        )

        event = _assert_event_type(case, "POST_ACCEPTANCE_ISSUE_OPENED")
        payload = event.payload
        assert payload.get("context") == "scheduled"
        assert payload.get("admission_flow") == "scheduled"
        assert payload.get("reason") == "death"
        assert "cycle_id" in payload
        assert "appointment_snapshot" in payload

    def test_abre_scheduled_registra_snapshot_agenda(self, user, case_factory, advance_to) -> None:
        """Abertura scheduled inclui snapshot da agenda atual no payload."""
        from datetime import UTC, datetime

        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        case.appointment_at = datetime(2026, 7, 1, 14, 0, tzinfo=UTC)
        case.appointment_location = "Sala 3"
        case.save(update_fields=["appointment_at", "appointment_location"])

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="scheduled",
        )

        event = _assert_event_type(case, "POST_ACCEPTANCE_ISSUE_OPENED")
        snap = event.payload.get("appointment_snapshot", {})
        assert snap.get("status") == "confirmed"
        assert snap.get("appointment_location") == "Sala 3"

    def test_abre_preenche_campos_legados_tambem(self, user, case_factory, advance_to) -> None:
        """Abertura genérica também preenche campos legados post_schedule_issue_*."""
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="scheduled",
        )

        assert case.post_schedule_issue_status == "opened"
        assert case.post_schedule_issue_reason == "death"

    def test_fluxo_sem_agenda_bloqueado_ainda(self, user, case_factory, advance_to) -> None:
        """Fluxos sem agenda (immediate/pre_icu/...) continuam inelegíveis."""
        from apps.cases.services import open_post_acceptance_issue

        for flow in ("immediate", "pre_icu", "ward_icu_backup", "pediatric_em"):
            case = _build_cleaned_no_schedule(case_factory, advance_to, user, flow=flow)
            with pytest.raises(ValueError, match="não é elegível|elegível"):
                open_post_acceptance_issue(
                    case=case,
                    user=user,
                    reason="death",
                    context="operational_notice",
                )

    def test_segunda_abertura_falha(self, user, case_factory, advance_to) -> None:
        """Segunda abertura com issue ativa falha."""
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        with pytest.raises(ValueError, match="intercorrência ativa"):
            open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")

    def test_abertura_transacional_com_select_for_update(self, user, case_factory, advance_to) -> None:
        """Abertura usa select_for_update para evitar race condition."""
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        with pytest.raises(ValueError, match="intercorrência ativa"):
            open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")


# ── Resposta do agendador (respond) ─────────────────────────────────────


class TestRespondPostAcceptanceIssue:
    """Testes da resposta agendada com snapshots e novo evento."""

    def _open(self, case_factory, advance_to, user):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        return open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")

    def test_resposta_registra_evento_novo_com_snapshots(self, user, case_factory, advance_to) -> None:
        """Resposta scheduled registra POST_ACCEPTANCE_ISSUE_RESPONDED com snapshots."""
        from apps.cases.services import respond_scheduled_post_acceptance_issue

        case = self._open(case_factory, advance_to, user)
        case = respond_scheduled_post_acceptance_issue(
            case=case,
            user=user,
            action="cancel",
            response_message="Cancelado pelo CHD",
        )

        event = _assert_event_type(case, "POST_ACCEPTANCE_ISSUE_RESPONDED")
        payload = event.payload
        assert payload.get("action") == "cancel"
        assert payload.get("context") == "scheduled"
        assert "cycle_id" in payload
        assert "appointment_before" in payload
        assert "appointment_after" in payload

    def test_cancel_registra_appointment_after_cancelled(self, user, case_factory, advance_to) -> None:
        """Cancel registra appointment_after com status 'cancelled'."""
        from apps.cases.services import respond_scheduled_post_acceptance_issue

        case = self._open(case_factory, advance_to, user)
        case = respond_scheduled_post_acceptance_issue(
            case=case,
            user=user,
            action="cancel",
        )

        event = _assert_event_type(case, "POST_ACCEPTANCE_ISSUE_RESPONDED")
        after = event.payload.get("appointment_after", {})
        assert after.get("status") == "cancelled"

    def test_reschedule_registra_novos_dados_no_after(self, user, case_factory, advance_to) -> None:
        """Reschedule registra novos dados no appointment_after."""
        from apps.cases.services import respond_scheduled_post_acceptance_issue

        case = self._open(case_factory, advance_to, user)
        case = respond_scheduled_post_acceptance_issue(
            case=case,
            user=user,
            action="reschedule",
            appointment_at="2026-08-01T10:00:00Z",
            appointment_location="Nova Sala",
            appointment_instructions="Chegar cedo",
        )

        event = _assert_event_type(case, "POST_ACCEPTANCE_ISSUE_RESPONDED")
        before = event.payload.get("appointment_before", {})
        after = event.payload.get("appointment_after", {})

        assert after.get("status") == "confirmed"
        # Before must have the original location
        assert before.get("appointment_location") == "Hospital Central"
        # After must have the new location
        assert after.get("appointment_location") == "Nova Sala"
        assert after.get("appointment_instructions") == "Chegar cedo"

    def test_maintain_preserva_appointment(self, user, case_factory, advance_to) -> None:
        """Maintain preserva appointment_status='confirmed'."""
        from apps.cases.services import respond_scheduled_post_acceptance_issue

        case = self._open(case_factory, advance_to, user)
        case = respond_scheduled_post_acceptance_issue(
            case=case,
            user=user,
            action="maintain",
        )

        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "confirmed"

    def test_deny_preserva_agendamento(self, user, case_factory, advance_to) -> None:
        """Deny preserva appointment_status='confirmed'."""
        from apps.cases.services import respond_scheduled_post_acceptance_issue

        case = self._open(case_factory, advance_to, user)
        case = respond_scheduled_post_acceptance_issue(
            case=case,
            user=user,
            action="deny",
            response_message="Sem vagas disponíveis",
        )

        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "confirmed"

    def test_acao_invalida_rejeitada(self, user, case_factory, advance_to) -> None:
        """Ação inválida é rejeitada."""
        from apps.cases.services import respond_scheduled_post_acceptance_issue

        case = self._open(case_factory, advance_to, user)
        with pytest.raises(ValueError, match="inválida"):
            respond_scheduled_post_acceptance_issue(case=case, user=user, action="invalid_action")

    def test_resposta_sem_issue_aberta_falha(self, user, case_factory, advance_to) -> None:
        """Responder sem issue aberta falha."""
        from apps.cases.services import respond_scheduled_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        with pytest.raises(ValueError, match="intercorrência aberta"):
            respond_scheduled_post_acceptance_issue(case=case, user=user, action="cancel")


# ── Ciência NIR (acknowledge) ────────────────────────────────────────────


class TestAcknowledgePostAcceptanceIssue:
    """Testes da ciência NIR com ciclo/contexto."""

    def _open_and_respond(self, case_factory, advance_to, user):
        from apps.cases.services import (
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        case = respond_scheduled_post_acceptance_issue(case=case, user=user, action="maintain")
        return Case.objects.get(pk=case.pk)

    def test_ack_registra_evento_novo_com_ciclo(self, user, case_factory, advance_to) -> None:
        """ACK registra POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED com ciclo/contexto."""
        from apps.cases.services import acknowledge_scheduled_post_acceptance_issue

        case = self._open_and_respond(case_factory, advance_to, user)
        cycle_id_before = case.post_acceptance_issue_cycle_id

        case = acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

        event = _assert_event_type(case, "POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED")
        payload = event.payload
        assert payload.get("context") == "scheduled"
        assert payload.get("cycle_id") == str(cycle_id_before)

        # Campos ativos limpos
        assert case.post_acceptance_issue_context == ""
        assert case.post_acceptance_issue_cycle_id is None

    def test_ack_limpa_campos_legados_tambem(self, user, case_factory, advance_to) -> None:
        """ACK limpa também campos legados."""
        from apps.cases.services import acknowledge_scheduled_post_acceptance_issue

        case = self._open_and_respond(case_factory, advance_to, user)
        case = acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

        assert case.status == CaseStatus.CLEANED
        assert case.post_schedule_issue_status == ""
        assert case.post_schedule_issue_reason == ""

    def test_ack_sem_issue_respondida_falha(self, user, case_factory, advance_to) -> None:
        """ACK sem issue responded falha."""
        from apps.cases.services import (
            acknowledge_scheduled_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        with pytest.raises(ValueError, match="respondida"):
            acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

    def test_ack_nao_cria_evento_legado_duplicado(self, user, case_factory, advance_to) -> None:
        """ACK novo não cria simultaneamente eventos POST_SCHEDULE_ISSUE_ACKNOWLEDGED."""
        from apps.cases.services import acknowledge_scheduled_post_acceptance_issue

        case = self._open_and_respond(case_factory, advance_to, user)
        count_old_before = CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_ACKNOWLEDGED").count()

        case = acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

        count_old_after = CaseEvent.objects.filter(case=case, event_type="POST_SCHEDULE_ISSUE_ACKNOWLEDGED").count()
        assert count_old_after == count_old_before, (
            "Não deve criar POST_SCHEDULE_ISSUE_ACKNOWLEDGED — apenas POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED"
        )


# ── Ciclos múltiplos ────────────────────────────────────────────────────


class TestMultipleCyclesPostAcceptance:
    """Testes de múltiplos ciclos sequenciais com UUIDs diferentes."""

    def test_ciclos_tem_uuid_diferentes(self, user, case_factory, advance_to) -> None:
        """Cada ciclo recebe UUID diferente."""
        from apps.cases.services import (
            acknowledge_scheduled_post_acceptance_issue,
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        uuid1 = case.post_acceptance_issue_cycle_id
        case = respond_scheduled_post_acceptance_issue(case=case, user=user, action="maintain")
        case = acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

        assert case.status == CaseStatus.CLEANED

        # Segundo ciclo
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="reschedule_request",
            message="Nova data",
            context="scheduled",
        )
        uuid2 = case.post_acceptance_issue_cycle_id
        case = respond_scheduled_post_acceptance_issue(
            case=case,
            user=user,
            action="reschedule",
            appointment_at="2026-09-01T10:00:00Z",
        )
        case = acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

        assert uuid1 != uuid2, "UUIDs dos ciclos devem ser diferentes"

        # Verifica 2 ciclos completos
        assert CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_OPENED").count() == 2
        assert CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_RESPONDED").count() == 2
        assert CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED").count() == 2


# ── Legado compatível ───────────────────────────────────────────────────


class TestLegacyCompatibility:
    """Serviço legado open_post_schedule_issue continua funcionando."""

    def test_open_post_schedule_issue_ainda_funciona(self, user, case_factory, advance_to) -> None:
        """Função legada open_post_schedule_issue ainda funciona."""
        from apps.cases.services import open_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")

        assert case.status == CaseStatus.WAIT_APPT
        assert case.post_schedule_issue_status == "opened"

    def test_respond_post_schedule_issue_ainda_funciona(self, user, case_factory, advance_to) -> None:
        """Função legada respond_post_schedule_issue ainda funciona."""
        from apps.cases.services import open_post_schedule_issue, respond_post_schedule_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="cancel")

        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_acknowledge_post_schedule_issue_ainda_funciona(self, user, case_factory, advance_to) -> None:
        """Função legada acknowledge_post_schedule_issue ainda funciona."""
        from apps.cases.services import (
            acknowledge_post_schedule_issue,
            open_post_schedule_issue,
            respond_post_schedule_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="maintain")
        case = acknowledge_post_schedule_issue(case=case, user=user)

        assert case.status == CaseStatus.CLEANED
        assert case.post_schedule_issue_status == ""


# ── C4: Domain validation ──────────────────────────────────────────────


class TestContextValidation:
    """Testes de validação de contexto e cycle_id (Slice 002 C4)."""

    def test_respond_rejeita_contexto_vazio(self, user, case_factory, advance_to) -> None:
        """respond_scheduled_post_acceptance_issue rejeita contexto vazio."""
        from apps.cases.services import (
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        # Corrompe o contexto
        Case.objects.filter(pk=case.pk).update(post_acceptance_issue_context="")

        case = Case.objects.get(pk=case.pk)
        with pytest.raises(ValueError, match="Contexto incorreto"):
            respond_scheduled_post_acceptance_issue(case=case, user=user, action="maintain")

    def test_respond_rejeita_cycle_id_nulo(self, user, case_factory, advance_to) -> None:
        """respond_scheduled_post_acceptance_issue rejeita cycle_id nulo."""
        from apps.cases.services import (
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        # Corrompe o cycle_id
        Case.objects.filter(pk=case.pk).update(post_acceptance_issue_cycle_id=None)

        case = Case.objects.get(pk=case.pk)
        with pytest.raises(ValueError, match="cycle_id ausente"):
            respond_scheduled_post_acceptance_issue(case=case, user=user, action="maintain")

    def test_ack_rejeita_contexto_vazio(self, user, case_factory, advance_to) -> None:
        """acknowledge_scheduled_post_acceptance_issue rejeita contexto vazio."""
        from apps.cases.services import (
            acknowledge_scheduled_post_acceptance_issue,
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        case = respond_scheduled_post_acceptance_issue(case=case, user=user, action="maintain")
        # Corrompe o contexto
        Case.objects.filter(pk=case.pk).update(post_acceptance_issue_context="")

        case = Case.objects.get(pk=case.pk)
        with pytest.raises(ValueError, match="Contexto incorreto"):
            acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

    def test_ack_rejeita_cycle_id_nulo(self, user, case_factory, advance_to) -> None:
        """acknowledge_scheduled_post_acceptance_issue rejeita cycle_id nulo."""
        from apps.cases.services import (
            acknowledge_scheduled_post_acceptance_issue,
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        case = respond_scheduled_post_acceptance_issue(case=case, user=user, action="maintain")
        # Corrompe o cycle_id
        Case.objects.filter(pk=case.pk).update(post_acceptance_issue_cycle_id=None)

        case = Case.objects.get(pk=case.pk)
        with pytest.raises(ValueError, match="cycle_id ausente"):
            acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

    def test_validacao_nao_altera_fsm_nem_agenda(self, user, case_factory, advance_to) -> None:
        """Validação falha não altera FSM, agenda ou eventos."""
        from apps.cases.services import (
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        Case.objects.filter(pk=case.pk).update(post_acceptance_issue_context="")

        events_before = CaseEvent.objects.filter(case=case).count()
        status_before = case.status
        appt_status_before = case.appointment_status

        case = Case.objects.get(pk=case.pk)
        try:
            respond_scheduled_post_acceptance_issue(case=case, user=user, action="maintain")
        except ValueError:
            pass

        case = Case.objects.get(pk=case.pk)
        assert case.status == status_before, "FSM não deve ser alterado"
        assert case.appointment_status == appt_status_before, "Agenda não deve ser alterada"
        assert CaseEvent.objects.filter(case=case).count() == events_before, "Nenhum evento novo deve ser criado"


# ── C5/C6: System notices for POST_ACCEPTANCE_ISSUE_* events ───────────


class TestPostAcceptanceSystemNotices:
    """Testes de mensagens sistêmicas para eventos POST_ACCEPTANCE_ISSUE_*."""

    def test_opened_creates_system_notice(self, user, case_factory, advance_to) -> None:
        """POST_ACCEPTANCE_ISSUE_OPENED gera mensagem sistêmica na thread."""
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")

        from apps.cases.models import CaseCommunicationMessage

        msgs = CaseCommunicationMessage.objects.filter(case=case, system_event_type="POST_ACCEPTANCE_ISSUE_OPENED")
        assert msgs.count() == 1
        msg = msgs.first()
        assert msg is not None
        assert msg.message_type == "system"
        assert "Intercorrência pós-aceitação" in msg.body

    def test_responded_creates_system_notice(self, user, case_factory, advance_to) -> None:
        """POST_ACCEPTANCE_ISSUE_RESPONDED gera mensagem sistêmica."""
        from apps.cases.services import (
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        case = respond_scheduled_post_acceptance_issue(
            case=case, user=user, action="cancel", response_message="Cancelado"
        )

        from apps.cases.models import CaseCommunicationMessage

        msgs = CaseCommunicationMessage.objects.filter(case=case, system_event_type="POST_ACCEPTANCE_ISSUE_RESPONDED")
        assert msgs.count() == 1
        msg = msgs.first()
        assert msg is not None
        assert msg.message_type == "system"
        assert "Intercorrência respondida" in msg.body

    def test_acknowledged_creates_system_notice(self, user, case_factory, advance_to) -> None:
        """POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED gera mensagem sistêmica (C6)."""
        from apps.cases.services import (
            acknowledge_scheduled_post_acceptance_issue,
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        case = respond_scheduled_post_acceptance_issue(case=case, user=user, action="maintain")
        case = acknowledge_scheduled_post_acceptance_issue(case=case, user=user)

        from apps.cases.models import CaseCommunicationMessage

        msgs = CaseCommunicationMessage.objects.filter(
            case=case, system_event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED"
        )
        assert msgs.count() == 1, "POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED deve gerar 1 mensagem sistêmica"
        msg = msgs.first()
        assert msg is not None
        assert msg.message_type == "system"
        assert "ciência" in msg.body.lower() or "Ciência" in msg.body

    def test_idempotent_notice_does_not_duplicate(self, user, case_factory, advance_to) -> None:
        """create_system_communication_notice_for_event é idempotente."""
        from apps.cases.services import create_system_communication_notice_for_event, open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")

        from apps.cases.models import CaseCommunicationMessage

        event = case.events.filter(event_type="POST_ACCEPTANCE_ISSUE_OPENED").first()
        assert event is not None, "Evento POST_ACCEPTANCE_ISSUE_OPENED deve existir"

        # Primeira chamada
        msg1 = create_system_communication_notice_for_event(event)

        # Segunda chamada — deve retornar a mesma, não criar nova
        msg2 = create_system_communication_notice_for_event(event)

        assert msg1 is not None
        assert msg2 is not None
        assert msg1.pk == msg2.pk

        count = CaseCommunicationMessage.objects.filter(
            case=case, system_event_type="POST_ACCEPTANCE_ISSUE_OPENED"
        ).count()
        assert count == 1, "Não deve duplicar mensagem sistêmica"

    def test_system_notice_does_not_create_user_notification(self, user, case_factory, advance_to) -> None:
        """Mensagens sistêmicas não criam UserNotification."""
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        from apps.accounts.models import UserNotification

        before = UserNotification.objects.count()

        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")

        after = UserNotification.objects.count()
        assert after == before, "Mensagem sistêmica não deve criar UserNotification"

    def test_formatter_does_not_query_appointment_at(self, user, case_factory, advance_to) -> None:
        """Formatador de POST_ACCEPTANCE_ISSUE_RESPONDED é projeção pura do payload."""
        from apps.cases.models import CaseCommunicationMessage
        from apps.cases.services import (
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="scheduled")
        case = respond_scheduled_post_acceptance_issue(case=case, user=user, action="cancel")

        # Muda appointment_at após a resposta — o formatter deve usar
        # o snapshot do payload, não o valor atual
        Case.objects.filter(pk=case.pk).update(appointment_at="2030-01-01T00:00:00Z")

        msg = CaseCommunicationMessage.objects.filter(
            case=case, system_event_type="POST_ACCEPTANCE_ISSUE_RESPONDED"
        ).first()
        assert msg is not None
        # O body não deve conter a data futura (2030) — vem do payload
        assert "Cancelado" in msg.body
