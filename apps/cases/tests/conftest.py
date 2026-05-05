"""Shared fixtures for cases tests."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseStatus

User = get_user_model()


@pytest.fixture
def user(db):
    """Cria um usuário ativo para testes."""
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def case_factory():
    """Retorna uma factory que cria um Case novo dado um user."""

    def _factory(user) -> Case:
        return Case.objects.create(created_by=user)

    return _factory


@pytest.fixture
def advance_to():
    """Retorna função helper que avança um Case até o estado alvo."""

    def _advance(case: Case, target: str) -> Case:
        path = {
            CaseStatus.R1_ACK_PROCESSING: ["start_processing"],
            CaseStatus.EXTRACTING: ["start_processing", "start_extraction"],
            CaseStatus.LLM_STRUCT: [
                "start_processing",
                "start_extraction",
                "extraction_complete(success=True)",
            ],
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

        return Case.objects.get(pk=case.pk)

    return _advance
