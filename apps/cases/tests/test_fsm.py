"""Testes da máquina de estados FSM do Case (17 estados)."""

from __future__ import annotations

import pytest
from django_fsm import TransitionNotAllowed

from apps.cases.models import Case, CaseStatus


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
    def test_transition_extracting_to_llm_struct_success(self, user) -> None:
        """EXTRACTING → LLM_STRUCT quando sucesso."""
        case = _advance_to(case_factory(user), CaseStatus.EXTRACTING)
        case.extraction_complete(success=True, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.LLM_STRUCT

    def test_transition_extracting_to_failed(self, user) -> None:
        """EXTRACTING → FAILED quando falha."""
        case = _advance_to(case_factory(user), CaseStatus.EXTRACTING)
        case.extraction_complete(success=False, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED


class TestFSMLlmStruct:
    def test_transition_llm_struct_to_llm_suggest(self, user) -> None:
        """LLM_STRUCT → LLM_SUGGEST."""
        case = _advance_to(case_factory(user), CaseStatus.LLM_STRUCT)
        case.llm1_complete(success=True, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.LLM_SUGGEST

    def test_transition_llm_struct_to_failed(self, user) -> None:
        """LLM_STRUCT → FAILED."""
        case = _advance_to(case_factory(user), CaseStatus.LLM_STRUCT)
        case.llm1_complete(success=False, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED


class TestFSMLlmSuggest:
    def test_transition_llm_suggest_to_r2_post_widget(self, user) -> None:
        """LLM_SUGGEST → R2_POST_WIDGET."""
        case = _advance_to(case_factory(user), CaseStatus.LLM_SUGGEST)
        case.llm2_complete(success=True, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.R2_POST_WIDGET

    def test_transition_llm_suggest_to_failed(self, user) -> None:
        """LLM_SUGGEST → FAILED."""
        case = _advance_to(case_factory(user), CaseStatus.LLM_SUGGEST)
        case.llm2_complete(success=False, user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED


class TestFSMR2PostWidgetToWaitDoctor:
    def test_transition_r2_post_widget_to_wait_doctor(self, user) -> None:
        """R2_POST_WIDGET → WAIT_DOCTOR."""
        case = _advance_to(case_factory(user), CaseStatus.R2_POST_WIDGET)
        case.ready_for_doctor(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR


class TestFSMWaitDoctor:
    def test_transition_wait_doctor_to_accepted(self, user) -> None:
        """WAIT_DOCTOR → DOCTOR_ACCEPTED."""
        case = _advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.doctor_decide(decision="accept", user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.DOCTOR_ACCEPTED

    def test_transition_wait_doctor_to_denied(self, user) -> None:
        """WAIT_DOCTOR → DOCTOR_DENIED."""
        case = _advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.doctor_decide(decision="deny", user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.DOCTOR_DENIED


class TestFSMDoctorAccepted:
    def test_transition_accepted_to_r3_post_request(self, user) -> None:
        """DOCTOR_ACCEPTED → R3_POST_REQUEST."""
        case = _advance_to(case_factory(user), CaseStatus.DOCTOR_ACCEPTED)
        case.ready_for_scheduler(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.R3_POST_REQUEST

    def test_transition_r3_to_wait_appt(self, user) -> None:
        """R3_POST_REQUEST → WAIT_APPT."""
        case = _advance_to(case_factory(user), CaseStatus.R3_POST_REQUEST)
        case.scheduler_request_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_APPT


class TestFSMWaitAppt:
    def test_transition_wait_appt_to_confirmed(self, user) -> None:
        """WAIT_APPT → APPT_CONFIRMED."""
        case = _advance_to(case_factory(user), CaseStatus.WAIT_APPT)
        case.scheduler_decide(appointment_status="confirmed", user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.APPT_CONFIRMED

    def test_transition_wait_appt_to_denied(self, user) -> None:
        """WAIT_APPT → APPT_DENIED."""
        case = _advance_to(case_factory(user), CaseStatus.WAIT_APPT)
        case.scheduler_decide(appointment_status="denied", user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.APPT_DENIED


class TestFSMClosurePaths:
    def test_transition_denied_to_wait_cleanup(self, user) -> None:
        """DOCTOR_DENIED → WAIT_R1_CLEANUP_THUMBS."""
        case = _advance_to(case_factory(user), CaseStatus.DOCTOR_DENIED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_transition_confirmed_to_wait_cleanup(self, user) -> None:
        """APPT_CONFIRMED → WAIT_R1_CLEANUP_THUMBS."""
        case = _advance_to(case_factory(user), CaseStatus.APPT_CONFIRMED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_transition_failed_to_wait_cleanup(self, user) -> None:
        """FAILED → WAIT_R1_CLEANUP_THUMBS."""
        case = _advance_to(case_factory(user), CaseStatus.FAILED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_transition_appt_denied_to_wait_cleanup(self, user) -> None:
        """APPT_DENIED → WAIT_R1_CLEANUP_THUMBS."""
        case = _advance_to(case_factory(user), CaseStatus.APPT_DENIED)
        case.final_reply_posted(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS


class TestFSMCleanup:
    def test_transition_wait_cleanup_to_running(self, user) -> None:
        """WAIT_R1_CLEANUP_THUMBS → CLEANUP_RUNNING."""
        case = _advance_to(case_factory(user), CaseStatus.WAIT_R1_CLEANUP_THUMBS)
        case.cleanup_triggered(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANUP_RUNNING

    def test_transition_running_to_cleaned(self, user) -> None:
        """CLEANUP_RUNNING → CLEANED."""
        case = _advance_to(case_factory(user), CaseStatus.CLEANUP_RUNNING)
        case.cleanup_completed(user=user)
        case.save()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED


class TestFSMInvalidTransitions:
    def test_invalid_transition_new_to_wait_doctor(self, user) -> None:
        """NEW → WAIT_DOCTOR (transição inválida) deve levantar TransitionNotAllowed."""
        case = Case.objects.create(created_by=user)
        with pytest.raises(TransitionNotAllowed):
            case.doctor_decide(decision="accept")


# ── helpers ──────────────────────────────────────────────────────────────────


def case_factory(user) -> Case:
    """Cria um caso novo."""
    return Case.objects.create(created_by=user)


def _advance_to(case: Case, target: str) -> Case:
    """Avança o caso até o estado alvo via transições válidas."""
    path = {
        CaseStatus.R1_ACK_PROCESSING: ["start_processing"],
        CaseStatus.EXTRACTING: ["start_processing", "start_extraction"],
        CaseStatus.LLM_STRUCT: ["start_processing", "start_extraction", "extraction_complete(success=True)"],
        CaseStatus.LLM_SUGGEST: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
        ],
        CaseStatus.R2_POST_WIDGET: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
        ],
        CaseStatus.WAIT_DOCTOR: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
        ],
        CaseStatus.DOCTOR_ACCEPTED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
        ],
        CaseStatus.DOCTOR_DENIED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='deny')",
        ],
        CaseStatus.R3_POST_REQUEST: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
        ],
        CaseStatus.WAIT_APPT: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
            "scheduler_request_posted",
        ],
        CaseStatus.APPT_CONFIRMED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
            "scheduler_request_posted",
            "scheduler_decide(appointment_status='confirmed')",
        ],
        CaseStatus.APPT_DENIED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
            "scheduler_request_posted",
            "scheduler_decide(appointment_status='denied')",
        ],
        CaseStatus.FAILED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=False)",
        ],
        CaseStatus.WAIT_R1_CLEANUP_THUMBS: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='deny')",
            "final_reply_posted",
        ],
        CaseStatus.CLEANUP_RUNNING: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='deny')",
            "final_reply_posted",
            "cleanup_triggered",
        ],
    }

    steps = path.get(target, [])  # type: ignore[call-overload]
    for step in steps:
        if "(" in step:
            method_name, args_str = step.split("(", 1)
            args_str = args_str.rstrip(")")
            kwargs = {}
            if "=" in args_str:
                for pair in args_str.split(","):
                    k, v = pair.split("=")
                    k = k.strip()
                    v = v.strip().strip("'")
                    if v == "True":
                        v = True
                    elif v == "False":
                        v = False
                    kwargs[k] = v
                getattr(case, method_name)(**kwargs)
            else:
                getattr(case, method_name)()
        else:
            getattr(case, step)()
        case.save()

    case = Case.objects.get(pk=case.pk)
    return case
