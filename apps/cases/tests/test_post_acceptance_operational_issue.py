"""Testes dos serviços de intercorrência operacional pós-aceitação (Slice 003).

Cobre:
- Elegibilidade dos 4 fluxos sem agenda (R1)
- Três novos motivos + validação de mensagem (R2)
- Abertura mantém CLEANED e agenda intacta (R3)
- Query durável própria (R4)
- Sem duplicidade com notice inicial (R5)
- ACK atômico e idempotente (R7)
- Múltiplos ciclos (R8)
- Scheduled/admin/dashboard sem regressão (R10)
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cases.admission import OPERATIONAL_NOTICE_FLOWS
from apps.cases.models import Case, CaseEvent, CaseStatus

pytestmark = pytest.mark.django_db


# ── Helpers ─────────────────────────────────────────────────────────────


def _build_cleaned_operational(case_factory, advance_to, user, flow="immediate") -> Case:
    """Cria um Case CLEANED elegível para intercorrência operacional.

    O advance_to usa o caminho scheduled/confirmed por padrão, então
    sobrescrevemos doctor_admission_flow após chegar a CLEANED.
    """
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = flow
    case.save(update_fields=["doctor_decision", "doctor_admission_flow"])
    return Case.objects.get(pk=case.pk)


def _assert_event_type(case, event_type):
    events = CaseEvent.objects.filter(case=case, event_type=event_type)
    assert events.exists(), f"Evento {event_type} nao encontrado"
    return events.latest("timestamp")


def _assert_event_not_exists(case, event_type):
    assert not CaseEvent.objects.filter(case=case, event_type=event_type).exists(), (
        f"Evento {event_type} nao deveria existir"
    )


# ── R1: Elegibilidade dos 4 fluxos ─────────────────────────────────────


class TestOperationalEligibility:
    """R1: Elegibilidade apenas para os 4 fluxos sem agenda."""

    @pytest.mark.parametrize("flow", OPERATIONAL_NOTICE_FLOWS)
    def test_quatro_fluxos_elegiveis(self, user, case_factory, advance_to, flow):
        from apps.cases.services import (
            is_post_acceptance_issue_eligible,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow=flow)
        assert is_post_acceptance_issue_eligible(case, context="operational_notice")

    def test_scheduled_nao_elegivel_operational(self, user, case_factory, advance_to):
        from apps.cases.services import (
            is_post_acceptance_issue_eligible,
        )

        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])
        case = Case.objects.get(pk=case.pk)

        assert not is_post_acceptance_issue_eligible(case, context="operational_notice")

    def test_denied_nao_elegivel(self, user, case_factory, advance_to):
        from apps.cases.services import (
            is_post_acceptance_issue_eligible,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)
        case.doctor_decision = "deny"
        case.save(update_fields=["doctor_decision"])
        case = Case.objects.get(pk=case.pk)

        assert not is_post_acceptance_issue_eligible(case, context="operational_notice")

    def test_not_cleaned_nao_elegivel(self, user, case_factory, advance_to):
        from apps.cases.services import (
            is_post_acceptance_issue_eligible,
        )

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "immediate"
        case.save(update_fields=["doctor_decision", "doctor_admission_flow"])

        assert not is_post_acceptance_issue_eligible(case, context="operational_notice")

    def test_issue_ativa_bloqueia(self, user, case_factory, advance_to):
        from apps.cases.services import (
            is_post_acceptance_issue_eligible,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)

        # Primeira abertura
        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        assert not is_post_acceptance_issue_eligible(case, context="operational_notice")

    def test_ineligibility_reason_operational(self, user, case_factory, advance_to):
        from apps.cases.services import (
            get_post_acceptance_issue_ineligibility_reason,
        )

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "immediate"
        case.save(update_fields=["doctor_decision", "doctor_admission_flow"])

        reason = get_post_acceptance_issue_ineligibility_reason(case, context="operational_notice")
        assert "CLEANED" in reason


# ── R2: Novos motivos ──────────────────────────────────────────────────


class TestNewReasons:
    """R2: Tres novos motivos com validacao de mensagem."""

    def test_patient_absconded_existe(self):
        from apps.cases.services import (
            POST_SCHEDULE_ISSUE_REASONS,
            get_post_schedule_issue_reason_label,
        )

        assert "patient_absconded" in POST_SCHEDULE_ISSUE_REASONS
        assert "evadiu" in get_post_schedule_issue_reason_label("patient_absconded").lower()

    def test_accepted_elsewhere_existe(self):
        from apps.cases.services import (
            POST_SCHEDULE_ISSUE_REASONS,
            get_post_schedule_issue_reason_label,
        )

        assert "accepted_elsewhere" in POST_SCHEDULE_ISSUE_REASONS
        assert "unidade mais" in get_post_schedule_issue_reason_label("accepted_elsewhere").lower()

    def test_origin_cancelled_existe(self):
        from apps.cases.services import (
            POST_SCHEDULE_ISSUE_REASONS,
            get_post_schedule_issue_reason_label,
        )

        assert "origin_cancelled" in POST_SCHEDULE_ISSUE_REASONS
        assert "cancelada" in get_post_schedule_issue_reason_label("origin_cancelled").lower()

    def test_accepted_elsewhere_exige_mensagem(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)

        with pytest.raises(ValueError, match="Mensagem.*obrigat.ria"):
            open_post_acceptance_issue(
                case=case,
                user=user,
                reason="accepted_elsewhere",
                message="",
                context="operational_notice",
            )

    def test_patient_absconded_exige_mensagem(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)

        with pytest.raises(ValueError, match="Mensagem.*obrigat.ria"):
            open_post_acceptance_issue(
                case=case,
                user=user,
                reason="patient_absconded",
                message="",
                context="operational_notice",
            )

    def test_origin_cancelled_exige_mensagem(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)

        with pytest.raises(ValueError, match="Mensagem.*obrigat.ria"):
            open_post_acceptance_issue(
                case=case,
                user=user,
                reason="origin_cancelled",
                message="",
                context="operational_notice",
            )

    def test_death_continua_sem_mensagem_obrigatoria(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        assert case.post_schedule_issue_status == "opened"


# ── R3: Abertura mantem CLEANED e agenda intacta ──────────────────────


class TestOperationalOpen:
    """R3: Abertura operacional mantem status e agenda."""

    @pytest.mark.parametrize("flow", OPERATIONAL_NOTICE_FLOWS)
    def test_abre_mantem_cleaned(self, user, case_factory, advance_to, flow):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user, flow=flow)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )

        assert case.status == CaseStatus.CLEANED
        assert case.post_acceptance_issue_context == "operational_notice"
        assert case.post_acceptance_issue_cycle_id is not None

    @pytest.mark.parametrize("flow", OPERATIONAL_NOTICE_FLOWS)
    def test_abre_nao_altera_appointment(self, user, case_factory, advance_to, flow):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user, flow=flow)
        # Snapshot antes
        appt_status_before = case.appointment_status
        appt_at_before = case.appointment_at
        appt_location_before = case.appointment_location
        appt_instructions_before = case.appointment_instructions

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="patient_absconded",
            message="Paciente evadiu-se da unidade",
            context="operational_notice",
        )

        assert case.appointment_status == appt_status_before
        assert case.appointment_at == appt_at_before
        assert case.appointment_location == appt_location_before
        assert case.appointment_instructions == appt_instructions_before

    def test_abre_emite_evento_com_contexto_e_cycle(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="accepted_elsewhere",
            message="Transferido para Hospital B",
            context="operational_notice",
        )

        event = _assert_event_type(case, "POST_ACCEPTANCE_ISSUE_OPENED")
        payload = event.payload
        assert payload.get("context") == "operational_notice"
        assert payload.get("admission_flow") == "immediate"
        assert payload.get("reason") == "accepted_elsewhere"
        assert payload.get("message") == "Transferido para Hospital B"
        assert "cycle_id" in payload
        assert isinstance(uuid.UUID(payload["cycle_id"]), uuid.UUID)

    def test_abre_preenche_storage_ativo(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="origin_cancelled",
            message="Demanda cancelada pela origem",
            context="operational_notice",
        )

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == "opened"
        assert case.post_schedule_issue_reason == "origin_cancelled"
        assert case.post_schedule_issue_message == "Demanda cancelada pela origem"
        assert case.post_schedule_issue_opened_by == user
        assert case.post_schedule_issue_opened_at is not None

    def test_abre_contexto_invalido_bloqueia(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)

        with pytest.raises(ValueError, match="Contexto inv.lido"):
            open_post_acceptance_issue(
                case=case,
                user=user,
                reason="death",
                context="invalid_context",
            )

    def test_nao_emite_case_administratively_closed(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)
        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )

        _assert_event_not_exists(case, "CASE_ADMINISTRATIVELY_CLOSED")


# ── R4: Query propria e duraivel ───────────────────────────────────────


class TestOperationalIssueQuery:
    """R4: Query helper para issues operacionais abertas."""

    def test_query_retorna_issue_aberta(self, user, case_factory, advance_to):
        from apps.cases.services import (
            open_post_acceptance_issue,
            unacknowledged_operational_issue_qs,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)
        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )

        qs = unacknowledged_operational_issue_qs()
        assert qs.filter(pk=case.pk).exists()

    def test_query_nao_retorna_scheduled(self, user, case_factory, advance_to):
        from apps.cases.services import (
            open_post_acceptance_issue,
            unacknowledged_operational_issue_qs,
        )

        # Scheduled issue - should NOT be in operational query
        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])
        case = Case.objects.get(pk=case.pk)

        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="scheduled",
        )

        qs = unacknowledged_operational_issue_qs()
        assert not qs.filter(pk=case.pk).exists()

    def test_query_nao_retorna_apos_ack(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
            unacknowledged_operational_issue_qs,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)
        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        qs = unacknowledged_operational_issue_qs()
        assert not qs.filter(pk=case.pk).exists()


# ── R5: Sem duplicidade com notice inicial ─────────────────────────────


class TestNoDuplication:
    """R5: Issue operacional substitui notice inicial na fila."""

    def test_notice_inicial_qs_exclui_issue_operacional_ativa(self, user, case_factory, advance_to):
        from apps.cases.services import (
            open_post_acceptance_issue,
            unacknowledged_operational_notice_qs,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="immediate")
        # Este caso terá evento ADMISSION_FLOW_OPERATIONAL_NOTICE do advancer
        # e também terá uma issue operacional

        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )

        qs = unacknowledged_operational_notice_qs()
        assert not qs.filter(pk=case.pk).exists(), "notice inicial nao deve aparecer quando ha issue operacional ativa"

    def test_apos_ack_operational_notice_inicial_nao_reaparece(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
            unacknowledged_operational_notice_qs,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="immediate")

        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        # Depois do ACK da issue operacional, o notice inicial
        # tambem esta satisfeito e nao deve reaparecer
        qs = unacknowledged_operational_notice_qs()
        assert not qs.filter(pk=case.pk).exists(), "notice inicial nao deve reaparecer apos ACK da issue operacional"

    def test_issue_ack_satisfies_real_pending_initial_notice(self, user, case_factory, advance_to):
        """C1: notice inicial REAL pendente → issue → ACK → zero pendencias."""
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
            unacknowledged_operational_notice_qs,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="immediate")
        CaseEvent.objects.create(
            case=case,
            actor=user,
            actor_type="human",
            event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        # 1. Antes da issue: notice inicial pendente aparece
        qs_before = unacknowledged_operational_notice_qs()
        assert qs_before.filter(pk=case.pk).exists(), "notice inicial deve aparecer antes da issue"

        # 2. Abre issue operacional
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="patient_absconded",
            message="Paciente evadiu-se",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        # 3. Com issue ativa: somente a issue
        qs_during = unacknowledged_operational_notice_qs()
        assert not qs_during.filter(pk=case.pk).exists(), (
            "notice inicial nao deve aparecer quando ha issue operacional ativa"
        )

        # 4. ACK da issue
        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        # 5. Apos ACK: ambos ausentes — este e o teste que falhava antes da correcao
        qs_after = unacknowledged_operational_notice_qs()
        assert not qs_after.filter(pk=case.pk).exists(), (
            "BUG: notice inicial fantasma reapareceu apos ACK da issue operacional"
        )

        # 6. Evento inicial permanece no historico
        assert CaseEvent.objects.filter(case=case, event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE").exists(), (
            "evento historico nao deve ser apagado"
        )

    def test_already_acked_notice_does_not_block_new_issue(self, user, case_factory, advance_to):
        """C1: notice inicial ja confirmado → nova issue continua visivel."""
        from apps.cases.services import (
            is_post_acceptance_issue_eligible,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="pre_icu")
        # Marca o notice inicial como ja confirmado
        CaseEvent.objects.create(
            case=case,
            actor=user,
            actor_type="human",
            event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE",
            timestamp=timezone.now() - timedelta(days=1),
        )
        CaseEvent.objects.create(
            case=case,
            actor=user,
            actor_type="human",
            event_type="SCHEDULER_OPERATIONAL_NOTICE_ACK",
            timestamp=timezone.now(),
        )
        case = Case.objects.get(pk=case.pk)

        # Nova issue deve ser possivel apesar do ACK historico
        assert is_post_acceptance_issue_eligible(case, context="operational_notice")

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="origin_cancelled",
            message="Cancelado pela origem",
            context="operational_notice",
        )
        assert case.post_schedule_issue_status == "opened"

    def test_second_cycle_visible_after_ack(self, user, case_factory, advance_to):
        """C1: segundo ciclo depois do ACK → issue reaparece com UUID novo."""
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
            unacknowledged_operational_issue_qs,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="pediatric_em")

        # Ciclo 1: abre e fecha
        case = open_post_acceptance_issue(case=case, user=user, reason="death", context="operational_notice")
        case = Case.objects.get(pk=case.pk)
        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        # Ciclo 2: nova abertura
        case = Case.objects.get(pk=case.pk)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="accepted_elsewhere",
            message="Transferido",
            context="operational_notice",
        )

        # Deve aparecer na query de issues abertas
        qs = unacknowledged_operational_issue_qs()
        assert qs.filter(pk=case.pk).exists(), "segundo ciclo deve aparecer na fila"
        assert case.post_acceptance_issue_cycle_id is not None


# ── R7: ACK atomico e idempotente ─────────────────────────────────────


class TestOperationalAck:
    """R7: ACK operatorio atomico e idempotente."""

    def test_ack_cria_evento(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        event = _assert_event_type(case, "POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED")
        payload = event.payload
        assert payload.get("context") == "operational_notice"
        assert "cycle_id" in payload
        assert payload.get("admission_flow") == "immediate"

    def test_ack_mantem_cleaned_e_agenda(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)
        # Snapshot
        appt_status_before = case.appointment_status
        appt_at_before = case.appointment_at

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        acknowledge_operational_post_acceptance_issue(case=case, user=user)
        case = Case.objects.get(pk=case.pk)

        assert case.status == CaseStatus.CLEANED
        assert case.appointment_status == appt_status_before
        assert case.appointment_at == appt_at_before

    def test_ack_limpa_storage_ativo(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        acknowledge_operational_post_acceptance_issue(case=case, user=user)
        case = Case.objects.get(pk=case.pk)

        assert case.post_schedule_issue_status == ""
        assert case.post_schedule_issue_reason == ""
        assert case.post_schedule_issue_message == ""
        assert case.post_acceptance_issue_context == ""
        assert case.post_acceptance_issue_cycle_id is None

    def test_ack_repetido_nao_duplica(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        # Segundo ACK deve falhar sem corromper
        with pytest.raises(ValueError, match="intercorr.ncia"):
            acknowledge_operational_post_acceptance_issue(case=case, user=user)

        # Verifica que so existe um evento ACK
        ack_events = CaseEvent.objects.filter(
            case=case,
            event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED",
        )
        assert ack_events.count() == 1

    def test_ack_sem_issue_aberta_falha(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)

        with pytest.raises(ValueError, match="intercorr.ncia"):
            acknowledge_operational_post_acceptance_issue(case=case, user=user)

    def test_ack_scheduled_nao_funciona_em_operational(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_scheduled_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        with pytest.raises(ValueError):
            acknowledge_scheduled_post_acceptance_issue(case=case, user=user)


# ── R8: Multiplos ciclos ───────────────────────────────────────────────


class TestMultipleCycles:
    """R8: Multiplos ciclos com UUIDs diferentes."""

    def test_ciclo_2_apos_ack_funciona(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="pre_icu")

        # Primeiro ciclo
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        cycle_1 = case.post_acceptance_issue_cycle_id
        assert cycle_1 is not None

        case = Case.objects.get(pk=case.pk)
        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        # Segundo ciclo
        case = Case.objects.get(pk=case.pk)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="accepted_elsewhere",
            message="Transferido para Hospital C",
            context="operational_notice",
        )
        cycle_2 = case.post_acceptance_issue_cycle_id
        assert cycle_2 is not None
        assert cycle_2 != cycle_1

    def test_ciclo_2_tem_uuid_proprio_nos_eventos(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="ward_icu_backup")

        # Ciclo 1
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)
        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        # Ciclo 2
        case = Case.objects.get(pk=case.pk)
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="patient_absconded",
            message="Evadiu-se da unidade",
            context="operational_notice",
        )

        events = CaseEvent.objects.filter(
            case=case,
            event_type="POST_ACCEPTANCE_ISSUE_OPENED",
        ).order_by("timestamp")

        assert events.count() == 2
        cycle_ids = [e.payload.get("cycle_id") for e in events]
        assert cycle_ids[0] != cycle_ids[1]


# ── R10: Sem regressao scheduled/dashboard ─────────────────────────────


class TestNoRegression:
    """R10: Scheduled e admin continuam funcionando."""

    def test_scheduled_continua_funcionando(self, user, case_factory, advance_to):
        from apps.cases.services import (
            open_post_acceptance_issue,
            respond_scheduled_post_acceptance_issue,
        )

        # Scheduled case
        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        case.appointment_at = timezone.now()
        case.save(
            update_fields=[
                "doctor_decision",
                "doctor_admission_flow",
                "appointment_status",
                "appointment_at",
            ]
        )
        case = Case.objects.get(pk=case.pk)

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="other",
            message="Teste scheduled",
            context="scheduled",
        )
        assert case.status == CaseStatus.WAIT_APPT

        case = respond_scheduled_post_acceptance_issue(
            case=case,
            user=user,
            action="maintain",
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_administrative_close_captura_contexto_operational(self, user, case_factory, advance_to):
        from apps.cases.services import (
            administratively_close_case,
        )

        # Caso em WAIT_DOCTOR elegivel para encerramento administrativo
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.post_schedule_issue_status = "opened"
        case.post_acceptance_issue_context = "operational_notice"
        case.post_acceptance_issue_cycle_id = uuid.uuid4()
        case.save(
            update_fields=[
                "post_schedule_issue_status",
                "post_acceptance_issue_context",
                "post_acceptance_issue_cycle_id",
            ]
        )

        case = administratively_close_case(
            case=case,
            user=user,
            reason_code="other",
            reason_text="Teste com contexto operacional",
            active_role="manager",
        )

        assert case.status == CaseStatus.CLEANED
        assert case.post_acceptance_issue_context == ""
        assert case.post_acceptance_issue_cycle_id is None

        event = _assert_event_type(case, "CASE_ADMINISTRATIVELY_CLOSED")
        assert event.payload.get("post_acceptance_issue_context") == "operational_notice"


# ── C5: Todos os 6 campos appointment_* imutaveis ────────────────────


class TestAllAppointmentFieldsImmutable:
    """C5: Cobertura completa dos 6 campos appointment_* na abertura e ACK."""

    APPOINTMENT_FIELDS = [
        "appointment_status",
        "appointment_at",
        "appointment_location",
        "appointment_instructions",
        "appointment_reason",
        "appointment_decided_at",
    ]

    def test_all_six_fields_unchanged_after_open(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="immediate")
        sentinel_dt = timezone.now()

        # Preenche valores sentinela
        Case.objects.filter(pk=case.pk).update(
            appointment_status="confirmed",
            appointment_at=sentinel_dt,
            appointment_location="Hospital Sentinela",
            appointment_instructions="Jejum 8h",
            appointment_reason="Motivo sentinela",
            appointment_decided_at=sentinel_dt,
        )
        case = Case.objects.get(pk=case.pk)

        # Snapshot antes
        snap_before = {f: getattr(case, f) for f in self.APPOINTMENT_FIELDS}

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="patient_absconded",
            message="Evadiu-se",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        snap_after = {f: getattr(case, f) for f in self.APPOINTMENT_FIELDS}
        assert snap_after == snap_before, f"Campos appointment_* mudaram: before={snap_before}, after={snap_after}"
        assert case.status == CaseStatus.CLEANED

    def test_all_six_fields_unchanged_after_ack_service(self, user, case_factory, advance_to):
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="pre_icu")
        sentinel_dt = timezone.now()

        Case.objects.filter(pk=case.pk).update(
            appointment_status="confirmed",
            appointment_at=sentinel_dt,
            appointment_location="UTI Sentinela",
            appointment_instructions="Preparo especial",
            appointment_reason="Razao sentinela",
            appointment_decided_at=sentinel_dt,
        )
        case = Case.objects.get(pk=case.pk)

        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        snap_before_ack = {f: getattr(case, f) for f in self.APPOINTMENT_FIELDS}

        acknowledge_operational_post_acceptance_issue(case=case, user=user)
        case = Case.objects.get(pk=case.pk)

        snap_after_ack = {f: getattr(case, f) for f in self.APPOINTMENT_FIELDS}
        assert snap_after_ack == snap_before_ack, (
            f"Campos appointment_* mudaram apos ACK: before={snap_before_ack}, after={snap_after_ack}"
        )
        assert case.status == CaseStatus.CLEANED


# ── C6: System notices com payload flow/cycle ─────────────────────────


class TestSystemNoticesOperational:
    """C6: System notices operacionais auditaveis pelo payload."""

    def test_opened_notice_includes_flow_in_body(self, user, case_factory, advance_to):
        """C6: OPENED notice inclui fluxo de admissao no corpo."""
        from apps.cases.services import (
            create_system_communication_notice_for_event,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="ward_icu_backup")
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="accepted_elsewhere",
            message="Transferido",
            context="operational_notice",
        )

        event = case.events.filter(event_type="POST_ACCEPTANCE_ISSUE_OPENED").first()
        assert event is not None
        cycle_id_val = event.payload.get("cycle_id", "")

        msg = create_system_communication_notice_for_event(event)
        assert msg is not None
        assert msg.message_type == "system"
        # F1: assert exato de fluxo, contexto e ciclo
        assert "Fluxo: Vinda para enfermaria (para retaguarda em UTI)" in msg.body
        assert "Modo: apenas para ciência" in msg.body
        assert f"Ciclo: {cycle_id_val}" in msg.body

    def test_opened_notice_stable_after_storage_cleared(self, user, case_factory, advance_to):
        """F1: Body da notice nao muda apos limpar storage ativo."""
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            create_system_communication_notice_for_event,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="pediatric_em")
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="patient_absconded",
            message="Evadiu-se",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        event = case.events.filter(event_type="POST_ACCEPTANCE_ISSUE_OPENED").first()
        assert event is not None
        cycle_id_val = event.payload.get("cycle_id", "")

        msg_before = create_system_communication_notice_for_event(event)
        assert msg_before is not None
        body_before = msg_before.body
        # F1: assert exato
        assert "Compartilhar" in body_before
        assert "Modo: apenas para ciência" in body_before
        assert f"Ciclo: {cycle_id_val}" in body_before

        # Limpa storage ativo
        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        # Mensagem historica nao muda
        msg_after = create_system_communication_notice_for_event(event)
        assert msg_after is not None
        assert msg_after.body == body_before

    def test_ack_notice_includes_flow_and_context_and_cycle(self, user, case_factory, advance_to):
        """F1: ACK notice inclui fluxo, contexto e ciclo exatos."""
        from apps.cases.services import (
            acknowledge_operational_post_acceptance_issue,
            create_system_communication_notice_for_event,
            open_post_acceptance_issue,
        )

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="immediate")
        case = open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )
        case = Case.objects.get(pk=case.pk)

        acknowledge_operational_post_acceptance_issue(case=case, user=user)

        ack_event = case.events.filter(event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED").first()
        assert ack_event is not None
        cycle_id_val = ack_event.payload.get("cycle_id", "")

        msg = create_system_communication_notice_for_event(ack_event)
        assert msg is not None
        # F1: asserts exatos
        assert "Fluxo: Vinda Imediata" in msg.body
        assert "Modo: apenas para ciência" in msg.body
        assert f"Ciclo: {cycle_id_val}" in msg.body

    def test_opened_notice_does_not_create_user_notification(self, user, case_factory, advance_to):
        """C6: System notice nao cria UserNotification."""
        from apps.accounts.models import UserNotification
        from apps.cases.services import open_post_acceptance_issue

        # Conta notificacoes antes
        before = UserNotification.objects.count()

        case = _build_cleaned_operational(case_factory, advance_to, user, flow="immediate")
        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )

        after = UserNotification.objects.count()
        assert after == before, f"System notice criou UserNotification: before={before}, after={after}"


# ── Concorrencia ────────────────────────────────────────────────────────


class TestConcurrency:
    """Testes de concorrencia e idempotencia."""

    def test_abre_duas_vezes_segunda_falha(self, user, case_factory, advance_to):
        from apps.cases.services import open_post_acceptance_issue

        case = _build_cleaned_operational(case_factory, advance_to, user)
        open_post_acceptance_issue(
            case=case,
            user=user,
            reason="death",
            context="operational_notice",
        )

        case = Case.objects.get(pk=case.pk)
        with pytest.raises(ValueError, match="intercorr.ncia"):
            open_post_acceptance_issue(
                case=case,
                user=user,
                reason="death",
                context="operational_notice",
            )
