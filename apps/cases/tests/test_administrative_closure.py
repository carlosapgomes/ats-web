"""Testes de encerramento administrativo — FSM + serviço + filas operacionais.

Slice 001: encerramento administrativo auditável.
TDD obrigatório: testes falham antes da implementação.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _set_lock(case: Case, user) -> None:
    """Define um lock manual no caso."""
    case.locked_by = user
    case.locked_at = timezone.now()
    case.locked_until = timezone.now() + timedelta(minutes=10)
    case.lock_token = uuid.uuid4()
    case.lock_context = "doctor_decision"
    case.lock_role = "doctor"
    case.save(
        update_fields=[
            "locked_by",
            "locked_at",
            "locked_until",
            "lock_token",
            "lock_context",
            "lock_role",
        ]
    )


def _set_post_schedule_issue(case: Case, user) -> None:
    """Define uma intercorrência pós-agendamento ativa."""
    case.post_schedule_issue_status = "opened"
    case.post_schedule_issue_reason = "death"
    case.post_schedule_issue_opened_by = user
    case.post_schedule_issue_opened_at = timezone.now()
    case.save(
        update_fields=[
            "post_schedule_issue_status",
            "post_schedule_issue_reason",
            "post_schedule_issue_opened_by",
            "post_schedule_issue_opened_at",
        ]
    )


# ── FSM Transition Tests ────────────────────────────────────────────────


class TestAdministrativeClosureFSM:
    """Testes da transição FSM administratively_close."""

    def test_administrative_close_moves_non_cleaned_case_to_cleaned(self, user, case_factory, advance_to) -> None:
        """Encerramento administrativo move caso de LLM_SUGGEST para CLEANED."""
        case = advance_to(case_factory(user), CaseStatus.LLM_SUGGEST)
        case.administratively_close(
            user=user,
            payload={
                "reason_code": "llm_failure",
                "reason_text": "LLM retornou fora do contrato",
            },
        )
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED

    def test_administrative_close_moves_wait_doctor_to_cleaned(self, user, case_factory, advance_to) -> None:
        """Encerramento administrativo move caso de WAIT_DOCTOR para CLEANED."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.administratively_close(
            user=user,
            payload={
                "reason_code": "stuck_lock",
                "reason_text": "Caso travado com lock expirado",
            },
        )
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED

    def test_administrative_close_moves_failed_to_cleaned(self, user, case_factory, advance_to) -> None:
        """Encerramento administrativo move caso de FAILED para CLEANED."""
        case = advance_to(case_factory(user), CaseStatus.FAILED)
        case.administratively_close(
            user=user,
            payload={
                "reason_code": "processing_error",
                "reason_text": "Falha no processamento do PDF",
            },
        )
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED

    def test_administrative_close_from_cleaned_raises_error(self, user, case_factory, advance_to) -> None:
        """Transição CLEANED → CLEANED não é permitida."""
        from django_fsm import TransitionNotAllowed

        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        with pytest.raises(TransitionNotAllowed):
            case.administratively_close(user=user, payload={})
            case.save()

    def test_administrative_close_creates_audit_event(self, user, case_factory, advance_to) -> None:
        """Encerramento cria evento CASE_ADMINISTRATIVELY_CLOSED com payload."""
        case = advance_to(case_factory(user), CaseStatus.LLM_SUGGEST)
        payload = {
            "reason_code": "llm_failure",
            "reason_text": "Falha do LLM",
            "previous_status": CaseStatus.LLM_SUGGEST,
            "active_role": "manager",
        }
        case.administratively_close(user=user, payload=payload)
        case.save()

        events = CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        )
        assert events.count() == 1
        event = events.first()
        assert event is not None
        assert event.payload.get("reason_code") == "llm_failure"
        assert event.payload.get("reason_text") == "Falha do LLM"
        assert event.payload.get("previous_status") == CaseStatus.LLM_SUGGEST
        assert event.payload.get("active_role") == "manager"

    def test_administrative_close_does_not_create_cleanup_events(self, user, case_factory, advance_to) -> None:
        """Encerramento administrativo NÃO cria eventos de cleanup normal."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.administratively_close(
            user=user,
            payload={
                "reason_code": "other",
                "reason_text": "Intervenção do supervisor",
            },
        )
        case.save()

        cleanup_events = CaseEvent.objects.filter(
            case=case,
            event_type__in=["CLEANUP_TRIGGERED", "CLEANUP_COMPLETED"],
        )
        assert cleanup_events.count() == 0

        admin_events = CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        )
        assert admin_events.count() == 1


# ── Service Tests ───────────────────────────────────────────────────────


class TestAdministrativeCloseService:
    """Testes do serviço administratively_close_case."""

    def _call_service(
        self,
        case: Case,
        user,
        *,
        reason_code: str = "system_bug",
        reason_text: str = "Bug identificado pelo supervisor",
        active_role: str = "manager",
    ) -> Case:
        from apps.cases.services import administratively_close_case

        return administratively_close_case(
            case=case,
            user=user,
            reason_code=reason_code,
            reason_text=reason_text,
            active_role=active_role,
        )

    def test_service_moves_case_to_cleaned(self, user, case_factory, advance_to) -> None:
        """Serviço move caso não CLEANED para CLEANED."""
        case = advance_to(case_factory(user), CaseStatus.LLM_SUGGEST)
        case = self._call_service(case, user)
        assert case.status == CaseStatus.CLEANED

    def test_service_creates_audit_event_with_previous_status_and_reason(self, user, case_factory, advance_to) -> None:
        """Evento criado tem payload com previous_status, reason_code, reason_text, active_role."""
        case = advance_to(case_factory(user), CaseStatus.LLM_SUGGEST)
        case = self._call_service(
            case,
            user,
            reason_code="llm_failure",
            reason_text="Falha na sugestão LLM",
            active_role="admin",
        )

        events = CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        )
        assert events.count() == 1
        event = events.first()
        assert event is not None
        assert event.event_type == "CASE_ADMINISTRATIVELY_CLOSED"
        payload = event.payload
        assert payload.get("previous_status") == CaseStatus.LLM_SUGGEST
        assert payload.get("reason_code") == "llm_failure"
        assert payload.get("reason_text") == "Falha na sugestão LLM"
        assert payload.get("active_role") == "admin"

    def test_service_requires_reason_text(self, user, case_factory, advance_to) -> None:
        """Motivo vazio levanta ValueError; status não muda; evento não é criado."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        original_status = case.status

        from apps.cases.services import administratively_close_case

        with pytest.raises(ValueError, match="Motivo obrigatório"):
            administratively_close_case(
                case=case,
                user=user,
                reason_code="other",
                reason_text="   ",
                active_role="manager",
            )

        # Busca instância fresca para evitar problema com FSM protected
        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.status == original_status
        assert not CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        ).exists()

    def test_service_requires_reason_code(self, user, case_factory, advance_to) -> None:
        """reason_code vazio levanta ValueError."""
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        with pytest.raises(ValueError, match="Código de motivo obrigatório"):
            administratively_close_case(
                case=case,
                user=user,
                reason_code="",
                reason_text="Motivo qualquer",
                active_role="manager",
            )

    def test_service_rejects_invalid_reason_code(self, user, case_factory, advance_to) -> None:
        """reason_code inválido levanta ValueError."""
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        with pytest.raises(ValueError, match="Código de motivo inválido"):
            administratively_close_case(
                case=case,
                user=user,
                reason_code="invalid_code",
                reason_text="Motivo qualquer",
                active_role="manager",
            )

    def test_service_rejects_already_cleaned_case(self, user, case_factory, advance_to) -> None:
        """Caso já CLEANED não gera novo evento."""
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.CLEANED)

        with pytest.raises(ValueError, match="já está encerrado"):
            administratively_close_case(
                case=case,
                user=user,
                reason_code="other",
                reason_text="Tentativa de encerrar já encerrado",
                active_role="manager",
            )

        assert not CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        ).exists()

    def test_service_clears_lock_fields(self, user, case_factory, advance_to) -> None:
        """Lock é limpo; payload registra had_lock=True e snapshot."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        _set_lock(case, user)

        assert case.locked_by is not None
        assert case.lock_token is not None

        case = self._call_service(case, user)

        # Lock fields limpos
        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.locked_by is None
        assert fresh_case.locked_at is None
        assert fresh_case.locked_until is None
        assert fresh_case.lock_token is None
        assert fresh_case.lock_context == ""
        assert fresh_case.lock_role == ""

        # Payload registra had_lock
        event = CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        ).first()
        assert event is not None
        payload = event.payload
        assert payload.get("had_lock") is True
        assert "previous_lock" in payload

    def test_service_clears_active_post_schedule_issue(self, user, case_factory, advance_to) -> None:
        """Intercorrência ativa é limpa; snapshot registrado no payload."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_APPT)
        _set_post_schedule_issue(case, user)

        assert case.post_schedule_issue_status != ""
        assert case.post_schedule_issue_reason != ""

        case = self._call_service(case, user)
        fresh_case = Case.objects.get(pk=case.pk)

        # Issue fields limpos
        assert fresh_case.post_schedule_issue_status == ""
        assert fresh_case.post_schedule_issue_reason == ""
        assert fresh_case.post_schedule_issue_opened_by is None

        # Payload registra snapshot
        event = CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        ).first()
        assert event is not None
        payload = event.payload
        assert "post_schedule_issue_status" in payload


# ── Operational Queue Tests ─────────────────────────────────────────────


class TestAdministrativeClosureQueueEffects:
    """Testes que o caso encerrado sai das filas operacionais."""

    def test_administratively_closed_case_leaves_nir_list(self, user, case_factory, advance_to) -> None:
        """Caso encerrado não aparece em intake:my_cases (exclui CLEANED)."""
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        administratively_close_case(
            case=case,
            user=user,
            reason_code="system_bug",
            reason_text="Bug no processamento",
            active_role="manager",
        )

        # Verifica que o caso não aparece na queryset do NIR
        nir_qs = Case.objects.exclude(status=CaseStatus.CLEANED)
        assert nir_qs.filter(pk=case.pk).count() == 0

    def test_administratively_closed_case_removed_from_wait_doctor(self, user, case_factory, advance_to) -> None:
        """Caso originalmente WAIT_DOCTOR não aparece na fila médica após encerramento."""
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        administratively_close_case(
            case=case,
            user=user,
            reason_code="stuck_lock",
            reason_text="Lock expirado",
            active_role="manager",
        )

        doctor_queue = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR)
        assert doctor_queue.filter(pk=case.pk).count() == 0

    def test_administratively_closed_case_removed_from_wait_appt(self, user, case_factory, advance_to) -> None:
        """Caso originalmente WAIT_APPT não aparece na fila scheduler após encerramento."""
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_APPT)
        administratively_close_case(
            case=case,
            user=user,
            reason_code="duplicate_reprocess",
            reason_text="Duplicado",
            active_role="admin",
        )

        scheduler_queue = Case.objects.filter(status=CaseStatus.WAIT_APPT)
        assert scheduler_queue.filter(pk=case.pk).count() == 0

    def test_administratively_closed_case_appears_in_audit(self, user, case_factory, advance_to) -> None:
        """Caso encerrado ainda é acessível via auditoria (dashboard detail)."""
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        administratively_close_case(
            case=case,
            user=user,
            reason_code="system_bug",
            reason_text="Bug",
            active_role="manager",
        )

        # Ainda existe no banco
        assert Case.objects.filter(pk=case.pk).exists()
        # Evento de auditoria existe
        assert CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        ).exists()


# ── FSM Integration Tests ───────────────────────────────────────────────


class TestAdministrativeClosureFSMIntegration:
    """Testes integrados FSM + serviço para múltiplos estados."""

    @pytest.mark.parametrize(
        "target_status",
        [
            CaseStatus.NEW,
            CaseStatus.R1_ACK_PROCESSING,
            CaseStatus.EXTRACTING,
            CaseStatus.LLM_STRUCT,
            CaseStatus.LLM_SUGGEST,
            CaseStatus.R2_POST_WIDGET,
            CaseStatus.WAIT_DOCTOR,
            CaseStatus.DOCTOR_ACCEPTED,
            CaseStatus.DOCTOR_DENIED,
            CaseStatus.R3_POST_REQUEST,
            CaseStatus.WAIT_APPT,
            CaseStatus.APPT_CONFIRMED,
            CaseStatus.APPT_DENIED,
            CaseStatus.FAILED,
            CaseStatus.R1_FINAL_REPLY_POSTED,
            CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            CaseStatus.CLEANUP_RUNNING,
        ],
    )
    def test_administrative_close_from_all_non_cleaned_states(
        self, user, case_factory, advance_to, target_status
    ) -> None:
        """Encerramento administrativo funciona de qualquer estado não CLEANED."""
        from apps.cases.services import administratively_close_case

        # Se for CLEANED, o serviço rejeita — testado separadamente
        if target_status == CaseStatus.CLEANED:
            return

        case = advance_to(case_factory(user), target_status)
        administratively_close_case(
            case=case,
            user=user,
            reason_code="processing_error",
            reason_text=f"Encerrado de {target_status}",
            active_role="manager",
        )
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED
