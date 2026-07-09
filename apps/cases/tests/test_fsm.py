"""Testes da máquina de estados FSM do Case (17 estados)."""

from __future__ import annotations

import pytest
from django_fsm import TransitionNotAllowed

from apps.cases.models import Case, CaseEvent, CaseStatus


class TestFSMNewToR1Ack:
    def test_transition_new_to_r1_ack(self, user) -> None:
        """NEW → R1_ACK_PROCESSING deve ser permitido."""
        case = Case.objects.create(created_by=user)
        case.start_processing(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.R1_ACK_PROCESSING


class TestFSMR1AckToExtracting:
    def test_transition_r1_ack_to_extracting(self, user) -> None:
        """R1_ACK_PROCESSING → EXTRACTING deve ser permitido."""
        case = Case.objects.create(created_by=user)
        case.start_processing(user=user)
        case.save()
        case.start_extraction(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.EXTRACTING


class TestFSMExtracting:
    def test_transition_extracting_to_llm_struct_success(self, user, case_factory, advance_to) -> None:
        """EXTRACTING → LLM_STRUCT quando sucesso."""
        case = advance_to(case_factory(user), CaseStatus.EXTRACTING)
        case.extraction_complete(success=True, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.LLM_STRUCT

    def test_transition_extracting_to_failed(self, user, case_factory, advance_to) -> None:
        """EXTRACTING → FAILED quando falha."""
        case = advance_to(case_factory(user), CaseStatus.EXTRACTING)
        case.extraction_complete(success=False, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED


class TestFSMLlmStruct:
    def test_transition_llm_struct_to_llm_suggest(self, user, case_factory, advance_to) -> None:
        """LLM_STRUCT → LLM_SUGGEST."""
        case = advance_to(case_factory(user), CaseStatus.LLM_STRUCT)
        case.llm1_complete(success=True, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.LLM_SUGGEST

    def test_transition_llm_struct_to_failed(self, user, case_factory, advance_to) -> None:
        """LLM_STRUCT → FAILED."""
        case = advance_to(case_factory(user), CaseStatus.LLM_STRUCT)
        case.llm1_complete(success=False, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED

    def test_scope_gate_bypass_transition(self, user, case_factory, advance_to) -> None:
        """Scope-gated case: LLM_STRUCT → WAIT_R1_CLEANUP_THUMBS directly."""
        case = advance_to(case_factory(user), CaseStatus.LLM_STRUCT)
        case.scope_gate_bypass(reason_code="non_eda_request")
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        events = CaseEvent.objects.filter(case=case)
        event_types = [e.event_type for e in events]
        assert "SCOPE_GATE_BYPASS" in event_types
        assert "LLM2_OK" not in event_types


class TestFSMLlmSuggest:
    def test_transition_llm_suggest_to_r2_post_widget(self, user, case_factory, advance_to) -> None:
        """LLM_SUGGEST → R2_POST_WIDGET."""
        case = advance_to(case_factory(user), CaseStatus.LLM_SUGGEST)
        case.llm2_complete(success=True, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.R2_POST_WIDGET

    def test_transition_llm_suggest_to_failed(self, user, case_factory, advance_to) -> None:
        """LLM_SUGGEST → FAILED."""
        case = advance_to(case_factory(user), CaseStatus.LLM_SUGGEST)
        case.llm2_complete(success=False, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED


class TestFSMR2PostWidgetToWaitDoctor:
    def test_transition_r2_post_widget_to_wait_doctor(self, user, case_factory, advance_to) -> None:
        """R2_POST_WIDGET → WAIT_DOCTOR."""
        case = advance_to(case_factory(user), CaseStatus.R2_POST_WIDGET)
        case.ready_for_doctor(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR


class TestFSMWaitDoctor:
    def test_transition_wait_doctor_to_accepted(self, user, case_factory, advance_to) -> None:
        """WAIT_DOCTOR → DOCTOR_ACCEPTED."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.doctor_decide(decision="accept", user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.DOCTOR_ACCEPTED

    def test_transition_wait_doctor_to_denied(self, user, case_factory, advance_to) -> None:
        """WAIT_DOCTOR → DOCTOR_DENIED."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.doctor_decide(decision="deny", user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.DOCTOR_DENIED


class TestFSMDoctorAccepted:
    def test_transition_accepted_to_r3_post_request(self, user, case_factory, advance_to) -> None:
        """DOCTOR_ACCEPTED → R3_POST_REQUEST."""
        case = advance_to(case_factory(user), CaseStatus.DOCTOR_ACCEPTED)
        case.ready_for_scheduler(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.R3_POST_REQUEST

    def test_transition_r3_to_wait_appt(self, user, case_factory, advance_to) -> None:
        """R3_POST_REQUEST → WAIT_APPT."""
        case = advance_to(case_factory(user), CaseStatus.R3_POST_REQUEST)
        case.scheduler_request_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_APPT


class TestFSMWaitAppt:
    def test_transition_wait_appt_to_confirmed(self, user, case_factory, advance_to) -> None:
        """WAIT_APPT → APPT_CONFIRMED."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_APPT)
        case.scheduler_decide(appointment_status="confirmed", user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.APPT_CONFIRMED

    def test_transition_wait_appt_to_denied(self, user, case_factory, advance_to) -> None:
        """WAIT_APPT → APPT_DENIED."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_APPT)
        case.scheduler_decide(appointment_status="denied", user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.APPT_DENIED


class TestFSMClosurePaths:
    def test_transition_denied_to_wait_cleanup(self, user, case_factory, advance_to) -> None:
        """DOCTOR_DENIED → WAIT_R1_CLEANUP_THUMBS."""
        case = advance_to(case_factory(user), CaseStatus.DOCTOR_DENIED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_final_reply_posted_sets_timestamp(self, user, case_factory, advance_to) -> None:
        """final_reply_posted() registra timestamp para métricas/auditoria."""
        case = advance_to(case_factory(user), CaseStatus.DOCTOR_DENIED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.final_reply_posted_at is not None

    def test_transition_confirmed_to_wait_cleanup(self, user, case_factory, advance_to) -> None:
        """APPT_CONFIRMED → WAIT_R1_CLEANUP_THUMBS."""
        case = advance_to(case_factory(user), CaseStatus.APPT_CONFIRMED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_transition_failed_to_wait_cleanup(self, user, case_factory, advance_to) -> None:
        """FAILED → WAIT_R1_CLEANUP_THUMBS."""
        case = advance_to(case_factory(user), CaseStatus.FAILED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_transition_appt_denied_to_wait_cleanup(self, user, case_factory, advance_to) -> None:
        """APPT_DENIED → WAIT_R1_CLEANUP_THUMBS."""
        case = advance_to(case_factory(user), CaseStatus.APPT_DENIED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS


class TestFSMCleanup:
    def test_transition_wait_cleanup_to_running(self, user, case_factory, advance_to) -> None:
        """WAIT_R1_CLEANUP_THUMBS → CLEANUP_RUNNING."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_R1_CLEANUP_THUMBS)
        case.cleanup_triggered(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANUP_RUNNING

    def test_cleanup_triggered_sets_timestamp(self, user, case_factory, advance_to) -> None:
        """cleanup_triggered() registra timestamp do início do cleanup."""
        case = advance_to(case_factory(user), CaseStatus.WAIT_R1_CLEANUP_THUMBS)
        case.cleanup_triggered(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.cleanup_triggered_at is not None

    def test_transition_running_to_cleaned(self, user, case_factory, advance_to) -> None:
        """CLEANUP_RUNNING → CLEANED."""
        case = advance_to(case_factory(user), CaseStatus.CLEANUP_RUNNING)
        case.cleanup_completed(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED

    def test_cleanup_completed_sets_timestamp(self, user, case_factory, advance_to) -> None:
        """cleanup_completed() registra timestamp usado pelo ciclo total."""
        case = advance_to(case_factory(user), CaseStatus.CLEANUP_RUNNING)
        case.cleanup_completed(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.cleanup_completed_at is not None


class TestFSMInvalidTransitions:
    def test_invalid_transition_new_to_wait_doctor(self, user) -> None:
        """NEW → WAIT_DOCTOR (transição inválida) deve levantar TransitionNotAllowed."""
        case = Case.objects.create(created_by=user)
        with pytest.raises(TransitionNotAllowed):
            case.doctor_decide(decision="accept")
