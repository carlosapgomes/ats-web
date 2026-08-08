"""Shared pytest fixtures for cases, users, and FSM advancement across apps.

These fixtures were consolidated from duplicated definitions in
apps/cases/tests/conftest.py, apps/intake/tests/conftest.py, and
apps/scheduler/tests/conftest.py.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseProcedure, CaseStatus, DoctorDisposition

User = get_user_model()


# ── Helpers explícitos de projeção (Slice 009-B/R5) ──────────────────────
# Helpers de função (não fixtures) para criar rows CaseProcedure explícitas
# em call sites de teste. NÃO leem ``case.exam_type``, NÃO inferem por status
# e NÃO usam signal/autouse: o conjunto é fornecido pelo teste no call site.
# Necessário porque universos/ações CHD exigem ao menos uma row aprovada.


def approved_set_for_exam_type(exam_type: object) -> tuple[str, ...]:
    """Mapeia a intenção declarada de exam_type num conjunto aprovado.

    Usada pelo FACTORY (não pelo helper de rows) para derivar o conjunto
    explícito a partir do seu próprio parâmetro local — nunca lendo
    ``case.exam_type``. ``eda_colonoscopy`` ⇒ ambos; singulares ⇒ o próprio;
    valor ausente/não-str ⇒ ``("eda",)`` (default fail-closed), acomodando o
    ``dict.get()`` de factories com valores heterogêneos.
    """
    if not isinstance(exam_type, str):
        return ("eda",)
    if exam_type == "eda_colonoscopy":
        return ("eda", "colonoscopy")
    if exam_type in {"eda", "colonoscopy"}:
        return (exam_type,)
    return ("eda",)


def attach_approved_procedures(case: Case, *, approved: tuple[str, ...]) -> Case:
    """Cria rows ``CaseProcedure`` aprovadas explícitas no call site.

    Helper explícito: recebe o conjunto aprovado e cria uma row aprovada por
    tipo (declarada pelo NIR). NÃO lê ``case.exam_type``, NÃO infere por
    status e NÃO usa signal/autouse (Slice 009-B/R5). Casos em estados CHD
    (WAIT_APPT/notices/issues/processados/histórico) precisam de ao menos
    uma row aprovada para aparecer no universo operacional do agendador.
    """
    for procedure_type in approved:
        CaseProcedure.objects.create(
            case=case,
            procedure_type=procedure_type,
            declared_by_nir=True,
            doctor_disposition=DoctorDisposition.APPROVED,
        )
    return case


@pytest.fixture
def user(db: None) -> User:  # type: ignore[valid-type]
    """Cria um usuário ativo para testes."""
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def case_factory() -> Callable[..., Case]:
    """Retorna uma factory que cria um Case novo dado um user."""

    def _factory(user_param: Any) -> Case:
        return Case.objects.create(created_by=user_param)

    return _factory


@pytest.fixture
def advance_to() -> Callable[..., Case]:
    """Retorna função helper que avança um Case até o estado alvo."""

    def _advance(case: Case, target: CaseStatus) -> Case:
        path: dict[CaseStatus, list[str]] = {
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
            CaseStatus.CLEANED: [
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
                "final_reply_posted",
                "cleanup_triggered",
                "cleanup_completed",
            ],
        }

        steps: list[str] = path.get(target, [])
        for step in steps:
            if "(" in step:
                method_name, args_str = step.split("(", 1)
                args_str = args_str.rstrip(")")
                kwargs = {}
                if "=" in args_str:
                    for pair in args_str.split(","):
                        k, v = pair.split("=")
                        k = k.strip()
                        v_val: str | bool = v.strip().strip("'")
                        if v_val == "True":
                            v_val = True
                        elif v_val == "False":
                            v_val = False
                        kwargs[k] = v_val
                    getattr(case, method_name)(**kwargs)
                else:
                    getattr(case, method_name)()
            else:
                getattr(case, step)()
            case.save()

        return Case.objects.get(pk=case.pk)

    return _advance
