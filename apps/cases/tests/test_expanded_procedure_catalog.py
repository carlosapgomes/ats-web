"""Cutover 4.0 (R1/R2) — catálogo ampliado, matriz fechada e migration de schema.

Cobre:
- R1: ``ProcedureType``/``PROCEDURE_CATALOG`` contêm exatamente as dez
  identidades canônicas (código, label, ordem), ``max_length=32`` comporta o
  maior código e a migration ``0021`` é somente de schema (choices/max_length),
  sem nenhuma operação de dados/backfill;
- R2: a matriz aceita qualquer singleton canônico e somente ``{eda,
  colonoscopy}``; ``selection_key`` é total e devolve o sentinela reservado para
  conjuntos fora da matriz; ``SELECTION_KEYS``/``procedure_types_for_selection``
  são públicas; o intake deriva a validação de seleção do catálogo mantendo os
  gates de flag; os profilles clínicos resolvem as dez identidades e falham
  fechado no caminho de writer.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from django.db.migrations import AlterField, SeparateDatabaseAndState
from django.db.migrations.operations.special import RunPython, RunSQL

from apps.cases.models import CaseProcedure, ProcedureType

pytestmark = pytest.mark.django_db

# Ordem canônica única do design D1/D2 (a mesma do proposal/ADR-0010).
EXPECTED_CATALOG: tuple[tuple[str, str], ...] = (
    ("eda", "EDA"),
    ("eda_gastrostomy", "EDA + Gastrostomia (GTT)"),
    ("eda_capsule", "EDA + Cápsula"),
    ("eda_dilation", "EDA + Dilatação"),
    ("colonoscopy", "Colonoscopia"),
    ("rectosigmoidoscopy", "Retossigmoidoscopia"),
    ("rectosigmoidoscopy_dilation", "Retossigmoidoscopia + Dilatação"),
    ("rectosigmoidoscopy_argon", "Retossigmoidoscopia + Argônio"),
    ("echoendoscopy", "Ecoendoscopia"),
    ("cpre", "CPRE"),
)
EXPECTED_CODES: tuple[str, ...] = tuple(code for code, _ in EXPECTED_CATALOG)
EXPECTED_PROFILE_KEY_BY_CODE: dict[str, str] = {
    "eda": "eda",
    "eda_gastrostomy": "eda",
    "eda_capsule": "eda",
    "eda_dilation": "eda",
    "colonoscopy": "colonoscopy",
    "rectosigmoidoscopy": "colonoscopy",
    "rectosigmoidoscopy_dilation": "colonoscopy",
    "rectosigmoidoscopy_argon": "colonoscopy",
    "echoendoscopy": "echoendoscopy",
    "cpre": "cpre",
}

_MIGRATION_MODULE = "apps.cases.migrations.0021_alter_caseprocedure_procedure_type_catalog_expanded"


def _operations() -> list[Any]:
    module = importlib.import_module(_MIGRATION_MODULE)
    return list(module.Migration.operations)


# ── R1: enum, catálogo e migration ──────────────────────────────────────────


class TestProcedureTypeEnum:
    def test_enum_has_exactly_ten_codes_in_canonical_order(self) -> None:
        assert [str(value) for value, _ in ProcedureType.choices] == list(EXPECTED_CODES)

    def test_labels_match_the_canonical_catalog(self) -> None:
        assert [(str(value), label) for value, label in ProcedureType.choices] == list(EXPECTED_CATALOG)

    def test_max_length_fits_the_longest_code(self) -> None:
        field = CaseProcedure._meta.get_field("procedure_type")
        longest = max(len(code) for code in EXPECTED_CODES)
        assert longest == 27  # rectosigmoidoscopy_dilation
        assert field.max_length == 32
        assert field.max_length >= longest

    def test_model_choices_match_the_enum(self) -> None:
        field = CaseProcedure._meta.get_field("procedure_type")
        assert field.choices == list(ProcedureType.choices)


class TestProcedureCatalog:
    def test_catalog_codes_and_labels_are_exact_and_ordered(self) -> None:
        from apps.cases.procedures import PROCEDURE_CATALOG

        assert [(definition.code, definition.label) for definition in PROCEDURE_CATALOG] == list(EXPECTED_CATALOG)

    def test_supported_types_and_labels_derive_from_the_catalog(self) -> None:
        from apps.cases.procedures import PROCEDURE_CATALOG, PROCEDURE_LABELS, SUPPORTED_PROCEDURE_TYPES

        assert SUPPORTED_PROCEDURE_TYPES == EXPECTED_CODES
        assert tuple(PROCEDURE_LABELS[definition.code] for definition in PROCEDURE_CATALOG) == tuple(
            label for _, label in EXPECTED_CATALOG
        )

    def test_family_and_profile_key_resolve_every_identity(self) -> None:
        from apps.cases.procedures import PROCEDURE_CATALOG

        assert {
            definition.code: definition.profile_key for definition in PROCEDURE_CATALOG
        } == EXPECTED_PROFILE_KEY_BY_CODE
        families = {definition.code: definition.family for definition in PROCEDURE_CATALOG}
        assert families["eda_dilation"] == "eda"
        assert families["rectosigmoidoscopy_argon"] == "colonoscopy"
        assert families["cpre"] == "specialized"


class TestMigration0021IsAlterFieldOnly:
    """R1 — a migration altera apenas schema; nunca executa dados."""

    def test_single_alter_field_operation(self) -> None:
        operations = _operations()
        assert len(operations) == 1
        operation = operations[0]
        assert isinstance(operation, AlterField)
        assert operation.model_name == "caseprocedure"
        assert operation.name == "procedure_type"

    def test_no_data_operations(self) -> None:
        for operation in _operations():
            assert not isinstance(operation, RunPython)
            assert not isinstance(operation, RunSQL)
            assert not isinstance(operation, SeparateDatabaseAndState)

    def test_declares_ten_choices_and_expanded_max_length(self) -> None:
        field = _operations()[0].field
        assert field.max_length == 32
        assert [choice[0] for choice in field.choices] == list(EXPECTED_CODES)

    def test_source_has_no_backfill_calls(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        source = (
            repo_root / "apps" / "cases" / "migrations" / "0021_alter_caseprocedure_procedure_type_catalog_expanded.py"
        ).read_text(encoding="utf-8")
        assert "RunPython" not in source
        assert "RunSQL" not in source


# ── R2: matriz fechada, selection keys e fail-closed ────────────────────────


class TestClosedMatrix:
    def test_allowed_sets_are_singletons_plus_exact_pair(self) -> None:
        from apps.cases.procedures import ALLOWED_PROCEDURE_SETS, PAIRED_APPOINTMENT_SET

        assert PAIRED_APPOINTMENT_SET == frozenset({"eda", "colonoscopy"})
        assert ALLOWED_PROCEDURE_SETS == frozenset(
            {frozenset({code}) for code in EXPECTED_CODES} | {PAIRED_APPOINTMENT_SET}
        )

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_every_singleton_is_authorizable(self, code: str) -> None:
        from apps.cases.procedures import normalize_procedure_selection

        assert normalize_procedure_selection([code]) == (code,)

    @pytest.mark.parametrize(
        "selection",
        [
            ["eda", "colonoscopy", "cpre"],
            ["eda_gastrostomy", "eda_dilation"],
            ["rectosigmoidoscopy_dilation", "colonoscopy"],
            ["echoendoscopy", "cpre"],
        ],
    )
    def test_other_pairs_fail_closed(self, selection: list[str]) -> None:
        from apps.cases.procedures import normalize_procedure_selection

        with pytest.raises(ValueError):
            normalize_procedure_selection(selection)

    def test_unknown_code_fails_closed(self) -> None:
        from apps.cases.procedures import normalize_procedure_selection

        with pytest.raises(ValueError):
            normalize_procedure_selection(["eda_gastrostomy_x"])


class TestSelectionKeyIsTotal:
    def test_pair_equality_returns_combined_key(self) -> None:
        from apps.cases.procedures import selection_key

        assert selection_key(("eda", "colonoscopy")) == "eda_colonoscopy"
        assert selection_key(("colonoscopy", "eda")) == "eda_colonoscopy"

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_singleton_returns_its_own_code(self, code: str) -> None:
        from apps.cases.procedures import selection_key

        assert selection_key((code,)) == code

    def test_empty_set_returns_empty_string(self) -> None:
        from apps.cases.procedures import selection_key

        assert selection_key(()) == ""

    def test_off_matrix_set_returns_reserved_sentinel(self) -> None:
        from apps.cases.procedures import selection_key

        assert selection_key(("cpre", "echoendoscopy")) == "invalid"
        assert selection_key(("eda_gastrostomy", "eda_capsule")) == "invalid"
        assert selection_key(("not_a_procedure",)) == "invalid"

    def test_never_raises_for_tolerant_readers(self) -> None:
        from apps.cases.procedures import selection_key

        assert selection_key(("eda", "eda")) == "invalid"
        assert selection_key(("",)) == "invalid"


class TestSelectionKeysAPI:
    def test_selection_keys_are_ten_atomic_codes_plus_combined_key(self) -> None:
        from apps.cases.procedures import SELECTION_KEYS

        assert SELECTION_KEYS == (*EXPECTED_CODES, "eda_colonoscopy")

    def test_conversion_of_atomic_key_and_combined_key(self) -> None:
        from apps.cases.procedures import procedure_types_for_selection

        assert procedure_types_for_selection("eda_gastrostomy") == ("eda_gastrostomy",)
        assert procedure_types_for_selection("eda_colonoscopy") == ("eda", "colonoscopy")

    @pytest.mark.parametrize("selection_key_value", ["EDA", "Colonoscopia", "eda_cpre", "colono", ""])
    def test_unknown_key_raises_instead_of_guessing(self, selection_key_value: str) -> None:
        from apps.cases.procedures import procedure_types_for_selection

        with pytest.raises(ValueError):
            procedure_types_for_selection(selection_key_value)


class TestIntakeSelectionDerivation:
    def test_declared_selection_values_derive_from_catalog(self) -> None:
        from apps.cases.procedures import SELECTION_KEYS
        from apps.intake.services import _DECLARED_SELECTION_VALUES

        assert _DECLARED_SELECTION_VALUES == frozenset(SELECTION_KEYS)

    @pytest.mark.parametrize("code", EXPECTED_CODES)
    def test_validate_exam_type_accepts_every_canonical_key(self, code: str) -> None:
        from apps.intake.services import validate_exam_type

        assert validate_exam_type(code) == code

    def test_validate_exam_type_error_lists_catalog_labels(self) -> None:
        from apps.intake.services import validate_exam_type

        with pytest.raises(ValueError) as excinfo:
            validate_exam_type("EDA")
        message = str(excinfo.value)
        assert "Selecione o tipo de exame" in message
        assert "Retossigmoidoscopia" in message
        assert "EDA + Gastrostomia (GTT)" in message

    def test_rollout_flags_still_gate_new_case_creation(self) -> None:
        from apps.intake.services import ensure_exam_type_allowed

        # Colonoscopia/EDA + Colonoscopia continuam atrás da flag de intake;
        # EDA permanece sempre permitido.
        assert ensure_exam_type_allowed("eda") == "eda"
        with pytest.raises(ValueError):
            ensure_exam_type_allowed("eda_colonoscopy")


class TestExamProfilesResolveEveryIdentity:
    @pytest.mark.parametrize("code,profile_key", list(EXPECTED_PROFILE_KEY_BY_CODE.items()))
    def test_profile_resolution_by_family(self, code: str, profile_key: str) -> None:
        from apps.cases.exam_profiles import get_exam_profile

        assert get_exam_profile(code).exam_type == profile_key

    def test_writer_resolution_fails_closed_for_unknown_code(self) -> None:
        from apps.cases.exam_profiles import require_exam_profile

        with pytest.raises(ValueError):
            require_exam_profile("eda_gastrostomy_x")

    def test_legacy_reader_keeps_eda_fallback(self) -> None:
        from apps.cases.exam_profiles import get_exam_profile

        assert get_exam_profile("legacy_unknown_type").exam_type == "eda"
        assert get_exam_profile(None).exam_type == "eda"
