"""Slice 009 — precheck não destrutivo do downgrade especializado (R4).

Cobre:
- pré-cutover sem nenhum write 3.0 e sem artefato especializado → permitido
  (exit 0);
- baseline EDA/Colonoscopia (rows + artefato 2.0 legado) → permitido;
- pós-cutover → bloqueado (exit não zero) por classe de artefato: job de
  pipeline 3.0 em voo, row ``CaseProcedure`` especializada, ``CaseEvent``
  especializado, artefato derivado do sinal legado de Ecoendoscopia e write
  3.0 persistido (``structured_data``/``suggested_action``);
- a checagem não altera dados e não expõe texto clínico.

O relatório é machine-readable: um único documento JSON no stdout, com os
códigos estáveis assertados abaixo. O caminho bloqueado levanta
``CommandError`` (exit code 1).
"""

from __future__ import annotations

import json
from io import StringIO
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, ProcedureType

pytestmark = pytest.mark.django_db

User = get_user_model()

COMMAND_NAME = "check_specialized_procedure_downgrade"

# Códigos estáveis do relatório (contrato machine-readable do precheck).
CODE_PIPELINE_JOB = "pipeline_job_in_flight"
CODE_SPECIALIZED_ROW = "specialized_case_procedure"
CODE_SPECIALIZED_EVENT = "specialized_case_event"
CODE_LEGACY_ECHO = "legacy_echo_artifact"
CODE_V3_WRITE = "v3_artifact_write"

ALL_CODES = (
    CODE_PIPELINE_JOB,
    CODE_SPECIALIZED_ROW,
    CODE_SPECIALIZED_EVENT,
    CODE_LEGACY_ECHO,
    CODE_V3_WRITE,
)

# Texto clínico usado para provar que o relatório não vaza conteúdo do PDF.
CLINICAL_TEXT = "PACIENTE JOAO DA SILVA — LAUDO CONFIDENCIAL"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_case(user: Any, *, status: str = CaseStatus.WAIT_DOCTOR) -> Case:
    return Case.objects.create(created_by=user, agency_record_number="12345", status=status)


def _run_any_command() -> tuple[str, dict[str, Any], CommandError | None]:
    """Executa o precheck e devolve (stdout bruto, relatório, erro).

    O erro é ``None`` quando o gate passa (exit 0) e o ``CommandError`` do
    caminho bloqueado (exit 1) quando a fronteira foi cruzada.
    """
    stdout = StringIO()
    error: CommandError | None = None
    try:
        call_command(COMMAND_NAME, stdout=stdout)
    except CommandError as exc:
        error = exc
    raw = stdout.getvalue()
    return raw, json.loads(raw), error


def _run_command() -> tuple[str, dict[str, Any]]:
    """Executa o precheck permitido (exit 0) e devolve (stdout bruto, relatório)."""
    raw, report, error = _run_any_command()
    assert error is None, f"precheck bloqueou inesperadamente (exit 1): {error}"
    return raw, report


def _run_blocked_command() -> tuple[str, dict[str, Any], CommandError]:
    """Executa o precheck bloqueado: exige exit code não zero + relatório JSON."""
    raw, report, error = _run_any_command()
    assert error is not None, "precheck deveria ter bloqueado (exit 1)"
    return raw, report, error


def _check_by_code(report: dict[str, Any], code: str) -> dict[str, Any]:
    matches = [check for check in report["checks"] if check["code"] == code]
    assert len(matches) == 1, f"código ausente ou duplicado no relatório: {code}"
    return cast(dict[str, Any], matches[0])


# ── Dado legado v2: informativo, nunca bloqueio ──────────────────────────────
#
# R1–R3: ``status``/exit code refletem SOMENTE a fronteira do primeiro write
# 3.0. Sinal de Eco da era 2.0 (``priority_signals``/``CaseEvent``) é dado
# legado: aparece no campo ``old_image_return_available`` e na nota do relatório,
# mas não bloqueia o gate de cutover.


def _legacy_echo_case(user: Any) -> Case:
    case = _make_case(user, status=CaseStatus.CLEANED)
    case.priority_signals = [{"code": "echoendoscopy", "category": "special_procedure", "detail": "EUS", "version": 1}]
    case.save(update_fields=["priority_signals"])
    return case


class TestLegacyV2DataIsInformational:
    def test_legacy_v2_signal_without_3_0_write_is_allowed(self, user) -> None:
        case = _legacy_echo_case(user)

        _raw, report = _run_command()

        assert report["status"] == "allowed"
        assert report["blocking_checks"] == []
        assert report["old_image_return_available"] is False
        check = _check_by_code(report, CODE_LEGACY_ECHO)
        assert check["count"] == 1
        assert str(case.case_id) in check["samples"]
        assert any(CODE_LEGACY_ECHO in note and "4.3" in note for note in report["notes"])

    def test_legacy_v2_event_without_3_0_write_is_allowed(self, user) -> None:
        # Premissa atualizada (precheck legado vs fronteira): ``CaseEvent``
        # referenciando procedimento especializado é dado legado — informativo,
        # não bloqueia o cutover.
        case = _make_case(user)
        CaseEvent.objects.create(
            case=case,
            event_type="DOCTOR_PROCEDURE_SET_CHANGED",
            actor_type="human",
            payload={"detected": ["eda"], "approved": ["cpre"], "reason_present": True},
        )

        _raw, report = _run_command()

        assert report["status"] == "allowed"
        assert report["blocking_checks"] == []
        assert report["old_image_return_available"] is False
        assert _check_by_code(report, CODE_SPECIALIZED_EVENT)["count"] == 1

    def test_boundary_write_with_legacy_data_blocks_on_boundary_only(self, user) -> None:
        _legacy_echo_case(user)
        case = _make_case(user)
        case.structured_data = {"schema_version": "3.0", "requested_procedures": []}
        case.save(update_fields=["structured_data"])

        _raw, report, error = _run_blocked_command()

        assert error.returncode == 1
        assert report["status"] == "blocked"
        assert report["blocking_checks"] == [CODE_V3_WRITE]
        assert report["old_image_return_available"] is False
        assert CODE_LEGACY_ECHO not in str(error)
        assert CODE_SPECIALIZED_EVENT not in str(error)


# ── Pré-cutover: permitido ───────────────────────────────────────────────────


class TestPreCutoverAllowed:
    def test_empty_database_is_allowed(self, user) -> None:
        _raw, report = _run_command()

        assert report["status"] == "allowed"
        assert report["blocking_checks"] == []
        assert report["old_image_return_available"] is True
        assert report["notes"] == []
        assert [check["code"] for check in report["checks"]] == list(ALL_CODES)
        assert all(check["count"] == 0 for check in report["checks"])

    def test_eda_colonoscopy_baseline_without_3_0_is_allowed(self, user) -> None:
        case = _make_case(user)
        for procedure_type in (ProcedureType.EDA, ProcedureType.COLONOSCOPY):
            CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)
        case.structured_data = {"schema_version": "2.0", "requested_procedures": [{"procedure_type": "eda"}]}
        case.suggested_action = {"schema_version": "2.0", "procedure_recommendations": []}
        case.save(update_fields=["structured_data", "suggested_action"])
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_PROCEDURES_DETECTED",
            actor_type="system",
            payload={"schema_version": "2.0", "detected_procedures": ["eda"]},
        )

        _raw, report = _run_command()

        assert report["status"] == "allowed"
        assert report["blocking_checks"] == []
        assert report["old_image_return_available"] is True


# ── Pós-cutover: bloqueado por classe de fronteira ───────────────────────────


class TestPostCutoverBlocked:
    def test_pipeline_job_in_flight_blocks(self, user) -> None:
        case = _make_case(user, status=CaseStatus.LLM_STRUCT)

        _raw, report, error = _run_blocked_command()

        assert error.returncode == 1
        assert report["status"] == "blocked"
        assert report["blocking_checks"] == [CODE_PIPELINE_JOB]
        check = _check_by_code(report, CODE_PIPELINE_JOB)
        assert check["count"] == 1
        assert str(case.case_id) in check["samples"]

    @pytest.mark.parametrize("procedure_type", [ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE])
    def test_specialized_case_procedure_blocks(self, user, procedure_type: str) -> None:
        case = _make_case(user)
        CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)

        _raw, report, _error = _run_blocked_command()

        assert report["status"] == "blocked"
        assert report["blocking_checks"] == [CODE_SPECIALIZED_ROW]
        check = _check_by_code(report, CODE_SPECIALIZED_ROW)
        assert check["count"] == 1
        assert str(case.case_id) in check["samples"]

    # ``test_specialized_case_event_blocks`` virou
    # ``TestLegacyV2DataIsInformational.test_legacy_v2_event_without_3_0_write_is_allowed``:
    # o evento especializado é dado legado (premissa do precheck legado vs
    # fronteira), não bloqueio de cutover.

    def test_v3_structured_data_write_blocks(self, user) -> None:
        case = _make_case(user)
        case.structured_data = {"schema_version": "3.0", "requested_procedures": [{"procedure_type": "eda"}]}
        case.save(update_fields=["structured_data"])

        _raw, report, _error = _run_blocked_command()

        assert report["blocking_checks"] == [CODE_V3_WRITE]
        # Fronteira cruzada ⇒ o retorno à imagem anterior (Seção 4.3 do runbook)
        # está fechado, mesmo sem dado legado v2.
        assert report["old_image_return_available"] is False
        check = _check_by_code(report, CODE_V3_WRITE)
        assert check["count"] == 1
        assert str(case.case_id) in check["samples"]

    def test_v3_suggested_action_write_blocks(self, user) -> None:
        case = _make_case(user)
        case.suggested_action = {"schema_version": "3.0", "procedure_recommendations": []}
        case.save(update_fields=["suggested_action"])

        _raw, report, _error = _run_blocked_command()

        assert report["blocking_checks"] == [CODE_V3_WRITE]
        assert _check_by_code(report, CODE_V3_WRITE)["count"] == 1

    # ``test_legacy_echo_artifact_blocks`` virou
    # ``TestLegacyV2DataIsInformational.test_legacy_v2_signal_without_3_0_write_is_allowed``:
    # o artefato derivado do sinal legado de Eco é dado legado, não bloqueio.

    def test_every_found_class_is_reported_together(self, user) -> None:
        # Premissa ajustada (R1/R2 do Slice 001): classes legadas
        # (legacy_echo_artifact/specialized_case_event) saíram da expectativa de
        # bloqueio — o fixture cobre agora a junção de classes de fronteira.
        case = _make_case(user)
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.ECHOENDOSCOPY)
        case.structured_data = {"schema_version": "3.0", "requested_procedures": []}
        case.save(update_fields=["structured_data"])

        _raw, report, _error = _run_blocked_command()

        assert sorted(report["blocking_checks"]) == sorted([CODE_SPECIALIZED_ROW, CODE_V3_WRITE])
        assert _check_by_code(report, CODE_SPECIALIZED_ROW)["count"] == 1
        assert _check_by_code(report, CODE_V3_WRITE)["count"] == 1


# ── Não destrutividade e sigilo ──────────────────────────────────────────────


class TestNonDestructive:
    def test_check_does_not_change_data_or_leak_clinical_text(self, user) -> None:
        case = _make_case(user)
        case.extracted_text = CLINICAL_TEXT
        case.structured_data = {"schema_version": "3.0", "requested_procedures": []}
        case.save(update_fields=["extracted_text", "structured_data"])
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.CPRE, declared_by_nir=True)
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_PROCEDURES_DETECTED",
            actor_type="system",
            payload={"schema_version": "3.0", "detected_procedures": ["cpre"]},
        )
        before = (
            CaseProcedure.objects.count(),
            CaseEvent.objects.count(),
            Case.objects.get(pk=case.pk).structured_data,
        )

        raw, report, _error = _run_blocked_command()

        after = (
            CaseProcedure.objects.count(),
            CaseEvent.objects.count(),
            Case.objects.get(pk=case.pk).structured_data,
        )
        assert before == after
        assert CLINICAL_TEXT not in raw
        assert CLINICAL_TEXT not in json.dumps(report)
        assert report["status"] == "blocked"
