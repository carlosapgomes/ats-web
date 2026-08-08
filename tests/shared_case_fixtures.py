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

from apps.cases.models import (
    Case,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
)

User = get_user_model()


# ── Helper explícito de projeção (Slice 009-B/R5) ────────────────────────
# Helper de função (não fixture) para criar rows CaseProcedure a partir de
# conjuntos EXPLÍCITOS no call site. NÃO lê ``case.exam_type``, NÃO recebe
# ``bridge_exam_type``/``exam_type``, NÃO infere por ``Case.status``,
# ``doctor_decision``, admission flow ou appointment status, e NÃO usa
# signal/autouse/criação implícita global. Valor ausente/inválido nunca
# inventa EDA — o teste declara as três dimensões.

_VALID_PROCEDURE_TYPES: tuple[str, ...] = ("eda", "colonoscopy")
_PROCEDURE_ORDER: dict[str, int] = {"eda": 0, "colonoscopy": 1}


def attach_procedure_projection(
    case: Case,
    *,
    declared: tuple[str, ...],
    detected: tuple[str, ...],
    approved: tuple[str, ...],
    denied: tuple[str, ...] = (),
    reasons: dict[str, str] | None = None,
) -> Case:
    """Cria rows ``CaseProcedure`` a partir das três dimensões explícitas.

    Contrato (R5/Slice 009-B):
    - rows vêm somente da união dos conjuntos explícitos;
    - ``declared_by_nir`` deriva somente de ``declared``;
    - ``detection_status='detected'`` deriva somente de ``detected`` (demais
      ficam ``pending``);
    - ``doctor_disposition`` deriva somente de ``approved``/``denied``;
    - ``approved`` e ``denied`` não podem se sobrepor;
    - tipos inválidos ou combinações incoerentes falham claramente;
    - aprovação de procedimento NÃO detectado exige razão explícita em
      ``reasons`` (inclusão médica justificada);
    - toda negação exige razão explícita em ``reasons`` (contrato de domínio).
    """
    declared_set = set(declared)
    detected_set = set(detected)
    approved_set = set(approved)
    denied_set = set(denied)

    for label, subset in (
        ("declared", declared_set),
        ("detected", detected_set),
        ("approved", approved_set),
        ("denied", denied_set),
    ):
        invalid = subset - set(_VALID_PROCEDURE_TYPES)
        if invalid:
            raise ValueError(f"procedure_type inválido em {label}: {sorted(invalid)}")

    if approved_set & denied_set:
        raise ValueError("approved e denied não podem se sobrepor")

    reasons = reasons or {}
    for procedure_type in sorted(approved_set - detected_set, key=lambda t: _PROCEDURE_ORDER[t]):
        if not reasons.get(procedure_type, "").strip():
            raise ValueError(f"aprovação de '{procedure_type}' sem detecção exige razão de inclusão explícita")
    for procedure_type in sorted(denied_set, key=lambda t: _PROCEDURE_ORDER[t]):
        if not reasons.get(procedure_type, "").strip():
            raise ValueError(f"negação de '{procedure_type}' exige razão explícita")

    for procedure_type in sorted(
        declared_set | detected_set | approved_set | denied_set, key=lambda t: _PROCEDURE_ORDER[t]
    ):
        CaseProcedure.objects.create(
            case=case,
            procedure_type=procedure_type,
            declared_by_nir=procedure_type in declared_set,
            detection_status=(DetectionStatus.DETECTED if procedure_type in detected_set else DetectionStatus.PENDING),
            doctor_disposition=(
                DoctorDisposition.APPROVED
                if procedure_type in approved_set
                else DoctorDisposition.DENIED
                if procedure_type in denied_set
                else DoctorDisposition.PENDING
            ),
            doctor_reason=reasons.get(procedure_type, ""),
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
