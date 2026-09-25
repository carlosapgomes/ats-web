"""Slice 010 — precheck não destrutivo do downgrade 4.0 (R2 / design D14).

A fronteira de rollback deste change é o **primeiro write 4.0** ou a **primeira
row de identidade nova** (design D14; spec ``procedure-neutral-analysis``:
"Primeiro write 4.0 concluído → rollback para writer 3.0 não é suportado").
Depois dela, o caminho suportado é fix-forward: nunca reativar o writer 3.0,
nunca apagar rows/artefatos e nunca reclassificar identidades novas.

Artefato 3.0, row de Ecoendoscopia/CPRE e dado legado v2 são o **baseline da
imagem anterior** (o writer 3.0 os produziu e os lê nativamente): aparecem no
relatório como contagens informativas e NUNCA bloqueiam o retorno à imagem 3.0.

Cobre:
- pré-cutover (inclusive com artefatos 3.0 e rows de Eco/CPRE) → permitido;
- row de cada uma das seis identidades novas → bloqueado;
- write 4.0 em ``structured_data``/``suggested_action``/payload de ``CaseEvent``
  → bloqueado;
- job de pipeline em voo → bloqueado;
- dado legado v2 (sinal de Eco e evento especializado) → informativo;
- a orientação fix-forward está na mensagem do caminho bloqueado;
- a checagem não altera dados e não expõe texto clínico.

O relatório é machine-readable: um único documento JSON no stdout com códigos
estáveis. O caminho bloqueado levanta ``CommandError`` (exit code 1).
"""

from __future__ import annotations

import json
from io import StringIO
from typing import Any, cast

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, ProcedureType
from apps.cases.procedures import SUPPORTED_PROCEDURE_TYPES

pytestmark = pytest.mark.django_db

COMMAND_NAME = "check_specialized_procedure_downgrade"

# Códigos estáveis do relatório (contrato machine-readable do precheck).
CODE_PIPELINE_JOB = "pipeline_job_in_flight"
CODE_NEW_IDENTITY_ROW = "new_identity_case_procedure"
CODE_V4_WRITE = "v4_artifact_write"
CODE_SPECIALIZED_ROW = "specialized_case_procedure"
CODE_V3_WRITE = "v3_artifact_write"
CODE_SPECIALIZED_EVENT = "specialized_case_event"
CODE_LEGACY_ECHO = "legacy_echo_artifact"

# Classes de fronteira deste change: bloqueiam o downgrade.
BOUNDARY_CODES = (CODE_PIPELINE_JOB, CODE_NEW_IDENTITY_ROW, CODE_V4_WRITE)

# Classes de baseline da imagem anterior (3.0): apenas informativas.
BASELINE_CODES = (CODE_SPECIALIZED_ROW, CODE_V3_WRITE, CODE_SPECIALIZED_EVENT, CODE_LEGACY_ECHO)

ALL_CODES = (*BOUNDARY_CODES, *BASELINE_CODES)

# As seis identidades novas deste change (a imagem anterior só conhece
# eda/colonoscopy/echoendoscopy/cpre). Ordem canônica do catálogo.
NEW_IDENTITY_TYPES = (
    ProcedureType.EDA_GASTROSTOMY,
    ProcedureType.EDA_CAPSULE,
    ProcedureType.EDA_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
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


def _write_schema_artifact(case: Case, version: str) -> None:
    """Persiste o marcador de schema gravável (3.0/4.0) em ``structured_data``."""
    case.structured_data = {"schema_version": version, "requested_procedures": []}
    case.save(update_fields=["structured_data"])


# ── As seis identidades novas ────────────────────────────────────────────────


class TestNewIdentityUniverse:
    def test_new_identities_are_exactly_the_catalog_minus_the_previous_image(self) -> None:
        previous_image = {
            ProcedureType.EDA,
            ProcedureType.COLONOSCOPY,
            ProcedureType.ECHOENDOSCOPY,
            ProcedureType.CPRE,
        }

        assert set(SUPPORTED_PROCEDURE_TYPES) - previous_image == set(NEW_IDENTITY_TYPES)


# ── Pré-cutover: permitido, inclusive com baseline 3.0 ───────────────────────


class TestPreCutoverAllowed:
    def test_empty_database_is_allowed(self, user) -> None:
        _raw, report = _run_command()

        assert report["status"] == "allowed"
        assert report["blocking_checks"] == []
        assert report["old_image_return_available"] is True
        assert report["notes"] == []
        assert [check["code"] for check in report["checks"]] == list(ALL_CODES)
        assert all(check["count"] == 0 for check in report["checks"])

    def test_eda_colonoscopy_2_0_baseline_is_allowed(self, user) -> None:
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

    def test_3_0_baseline_with_echo_and_cpre_rows_does_not_block(self, user) -> None:
        # Núcleo de R2/design D14: o writer 3.0 (imagem anterior) produziu e lê
        # esses dados nativamente — reverter a imagem é seguro enquanto nenhum
        # write 4.0 / row de identidade nova existir.
        case = _make_case(user)
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.ECHOENDOSCOPY, declared_by_nir=True)
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.CPRE, declared_by_nir=True)
        _write_schema_artifact(case, "3.0")
        case.suggested_action = {"schema_version": "3.0", "procedure_recommendations": []}
        case.save(update_fields=["suggested_action"])
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_PROCEDURES_DETECTED",
            actor_type="system",
            payload={"schema_version": "3.0", "detected_procedures": ["echoendoscopy", "cpre"]},
        )

        _raw, report = _run_command()

        assert report["status"] == "allowed"
        assert report["blocking_checks"] == []
        assert report["old_image_return_available"] is True
        assert _check_by_code(report, CODE_V3_WRITE)["count"] == 1
        assert _check_by_code(report, CODE_SPECIALIZED_ROW)["count"] == 1
        assert _check_by_code(report, CODE_SPECIALIZED_EVENT)["count"] == 1
        assert any("imagem anterior" in note for note in report["notes"])
        assert any(CODE_V3_WRITE in note for note in report["notes"])


# ── Baseline v2: informativo, nunca bloqueio ─────────────────────────────────


class TestLegacyV2BaselineIsInformational:
    def _legacy_echo_case(self, user: Any) -> Case:
        case = _make_case(user, status=CaseStatus.CLEANED)
        case.priority_signals = [
            {"code": "echoendoscopy", "category": "special_procedure", "detail": "EUS", "version": 1}
        ]
        case.save(update_fields=["priority_signals"])
        return case

    def test_legacy_echo_signal_does_not_block(self, user) -> None:
        case = self._legacy_echo_case(user)

        _raw, report = _run_command()

        assert report["status"] == "allowed"
        assert report["blocking_checks"] == []
        check = _check_by_code(report, CODE_LEGACY_ECHO)
        assert check["count"] == 1
        assert str(case.case_id) in check["samples"]


# ── Fronteira do primeiro write 4.0: bloqueado ───────────────────────────────


class TestFirstFourZeroWriteBoundary:
    def test_v4_structured_data_write_blocks(self, user) -> None:
        case = _make_case(user)
        _write_schema_artifact(case, "4.0")

        _raw, report, error = _run_blocked_command()

        assert error.returncode == 1
        assert report["status"] == "blocked"
        assert report["blocking_checks"] == [CODE_V4_WRITE]
        assert report["old_image_return_available"] is False
        check = _check_by_code(report, CODE_V4_WRITE)
        assert check["count"] == 1
        assert str(case.case_id) in check["samples"]

    def test_v4_suggested_action_write_blocks(self, user) -> None:
        case = _make_case(user)
        case.suggested_action = {"schema_version": "4.0", "procedure_recommendations": []}
        case.save(update_fields=["suggested_action"])

        _raw, report, _error = _run_blocked_command()

        assert report["blocking_checks"] == [CODE_V4_WRITE]
        assert _check_by_code(report, CODE_V4_WRITE)["count"] == 1

    def test_v4_event_marker_blocks(self, user) -> None:
        case = _make_case(user)
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_PROCEDURES_DETECTED",
            actor_type="system",
            payload={"schema_version": "4.0", "detected_procedures": ["eda"]},
        )

        _raw, report, _error = _run_blocked_command()

        assert report["blocking_checks"] == [CODE_V4_WRITE]
        assert _check_by_code(report, CODE_V4_WRITE)["count"] == 1

    @pytest.mark.parametrize("procedure_type", NEW_IDENTITY_TYPES)
    def test_each_new_identity_row_blocks(self, user, procedure_type: str) -> None:
        case = _make_case(user)
        CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)

        _raw, report, _error = _run_blocked_command()

        assert report["status"] == "blocked"
        assert report["blocking_checks"] == [CODE_NEW_IDENTITY_ROW]
        check = _check_by_code(report, CODE_NEW_IDENTITY_ROW)
        assert check["count"] == 1
        assert str(case.case_id) in check["samples"]

    def test_pipeline_job_in_flight_blocks(self, user) -> None:
        case = _make_case(user, status=CaseStatus.LLM_SUGGEST)

        _raw, report, _error = _run_blocked_command()

        assert report["blocking_checks"] == [CODE_PIPELINE_JOB]
        check = _check_by_code(report, CODE_PIPELINE_JOB)
        assert check["count"] == 1
        assert str(case.case_id) in check["samples"]

    def test_3_0_baseline_does_not_soften_the_boundary(self, user) -> None:
        baseline = _make_case(user)
        _write_schema_artifact(baseline, "3.0")
        CaseProcedure.objects.create(case=baseline, procedure_type=ProcedureType.CPRE, declared_by_nir=True)
        case = _make_case(user)
        _write_schema_artifact(case, "4.0")

        _raw, report, _error = _run_blocked_command()

        assert report["blocking_checks"] == [CODE_V4_WRITE]
        assert _check_by_code(report, CODE_SPECIALIZED_ROW)["count"] == 1
        assert _check_by_code(report, CODE_V3_WRITE)["count"] == 1

    def test_every_boundary_class_is_reported_together(self, user) -> None:
        in_flight = _make_case(user, status=CaseStatus.LLM_STRUCT)
        new_identity = _make_case(user)
        CaseProcedure.objects.create(case=new_identity, procedure_type=ProcedureType.EDA_CAPSULE)
        v4 = _make_case(user)
        _write_schema_artifact(v4, "4.0")

        _raw, report, _error = _run_blocked_command()

        assert sorted(report["blocking_checks"]) == sorted(BOUNDARY_CODES)
        for code in BOUNDARY_CODES:
            assert _check_by_code(report, code)["count"] == 1
        assert str(in_flight.case_id) in _check_by_code(report, CODE_PIPELINE_JOB)["samples"]
        assert str(new_identity.case_id) in _check_by_code(report, CODE_NEW_IDENTITY_ROW)["samples"]
        assert str(v4.case_id) in _check_by_code(report, CODE_V4_WRITE)["samples"]


# ── Orientação fix-forward ───────────────────────────────────────────────────


class TestFixForwardGuidance:
    def test_blocked_message_orients_fix_forward_without_data_loss(self, user) -> None:
        case = _make_case(user)
        _write_schema_artifact(case, "4.0")

        _raw, _report, error = _run_blocked_command()

        message = str(error)
        assert CODE_V4_WRITE in message
        assert "primeiro write 4.0" in message
        assert "corrigir para frente" in message
        assert "writer 3.0" in message
        assert "apagar" in message
        assert "reclassificar" in message


# ── Não destrutividade e sigilo ──────────────────────────────────────────────


class TestNonDestructive:
    def test_check_does_not_change_data_or_leak_clinical_text(self, user) -> None:
        case = _make_case(user)
        case.extracted_text = CLINICAL_TEXT
        case.structured_data = {"schema_version": "4.0", "requested_procedures": []}
        case.save(update_fields=["extracted_text", "structured_data"])
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA_GASTROSTOMY, declared_by_nir=True)
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_PROCEDURES_DETECTED",
            actor_type="system",
            payload={"schema_version": "4.0", "detected_procedures": ["eda_gastrostomy"]},
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
