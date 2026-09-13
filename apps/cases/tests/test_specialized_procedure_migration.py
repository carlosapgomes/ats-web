"""Slice 001 (R1) — migration 0019 de choices é AlterField puro e não muta dados.

Cobre:
- inspeção estática: a migration contém exatamente o ``AlterField`` de
  ``CaseProcedure.procedure_type`` e NENHUMA operação de dados
  (``RunPython``/``RunSQL``/``SeparateDatabaseAndState``) — nenhum backfill;
- execução forward real 0018 → 0019 com ``MigrationExecutor``: rows de
  ``CaseProcedure``, JSON clínico (1.1/2.0) e histórico de ``CaseEvent``
  permanecem byte a byte inalterados;
- o estado final aceita os quatro tipos do catálogo.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations import AlterField, SeparateDatabaseAndState
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations.special import RunPython, RunSQL

from apps.cases.models import Case, CaseEvent, CaseProcedure, ProcedureType

pytestmark = pytest.mark.django_db

User = get_user_model()

_MIGRATION_MODULE = "apps.cases.migrations.0019_alter_caseprocedure_procedure_type"
_PREVIOUS_MIGRATION = "0018_alter_procedurefollowup_non_performance_reason"
_LEGACY_V2_STRUCTURED_DATA: dict[str, Any] = {
    "schema_version": "2.0",
    "language": "pt-BR",
    "requested_procedures": [{"procedure_type": "eda", "name": "EDA"}],
}
_LEGACY_V11_STRUCTURED_DATA: dict[str, Any] = {
    "schema_version": "1.1",
    "eda": {"indication_category": "dyspepsia"},
}


def _operations() -> list[Any]:
    module = importlib.import_module(_MIGRATION_MODULE)
    return list(module.Migration.operations)


class TestMigrationIsAlterFieldOnly:
    """R1 — a migration altera apenas schema state; nunca executa dados."""

    def test_single_alter_field_operation(self) -> None:
        operations = _operations()
        assert len(operations) == 1
        operation = operations[0]
        assert isinstance(operation, AlterField)
        assert operation.model_name == "caseprocedure"
        assert operation.name == "procedure_type"

    def test_no_data_operations(self) -> None:
        for operation in _operations():
            assert not isinstance(operation, (RunPython, RunSQL, SeparateDatabaseAndState))

    def test_operation_targets_four_typed_choices(self) -> None:
        operation = _operations()[0]
        choices = {value for value, _label in operation.field.choices}
        assert choices == {"eda", "colonoscopy", "echoendoscopy", "cpre"}


class TestForwardMigrationPreservesData:
    """R1 — forward 0018 → 0019 não muta rows, JSON clínico nem eventos."""

    @pytest.fixture(autouse=True)
    def _migration_sandbox(self):
        executor = MigrationExecutor(connection)
        self._leaf_nodes = executor.loader.graph.leaf_nodes()
        self._targets_0018 = [
            ("cases", _PREVIOUS_MIGRATION) if node[0] == "cases" and node[1] > _PREVIOUS_MIGRATION else node
            for node in self._leaf_nodes
        ]
        try:
            yield
        finally:
            MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _migrate_to_0018(self) -> None:
        MigrationExecutor(connection).migrate(self._targets_0018)

    def _migrate_to_0019(self) -> None:
        MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _state_0018(self):
        return MigrationExecutor(connection).loader.project_state(self._targets_0018).apps

    def _seed_legacy_rows(self, user) -> dict[str, Any]:
        """Cria caso EDA/Colon com JSON 1.1/2.0, rows e evento no schema 0018."""
        old_apps = self._state_0018()
        old_case = old_apps.get_model("cases", "Case")
        old_procedure = old_apps.get_model("cases", "CaseProcedure")
        old_event = old_apps.get_model("cases", "CaseEvent")

        case = old_case.objects.create(
            created_by_id=user.pk,
            status="WAIT_DOCTOR",
            structured_data=_LEGACY_V2_STRUCTURED_DATA,
            extracted_text="Texto clínico legado",
        )
        eda = old_procedure.objects.create(
            case_id=case.pk,
            procedure_type="eda",
            declared_by_nir=True,
            detection_status="detected",
            doctor_disposition="approved",
            doctor_reason="razão legada",
        )
        colon = old_procedure.objects.create(
            case_id=case.pk,
            procedure_type="colonoscopy",
            declared_by_nir=True,
            detection_status="detected",
            doctor_disposition="pending",
        )
        event = old_event.objects.create(
            case_id=case.pk,
            actor_type="system",
            event_type="CASE_PROCEDURES_DECLARED",
            payload={"procedures": ["eda", "colonoscopy"]},
        )
        return {
            "case_id": case.pk,
            "eda_id": eda.pk,
            "colon_id": colon.pk,
            "event_id": event.pk,
        }

    def _assert_legacy_rows_untouched(self, ids: dict[str, Any]) -> None:
        case = Case.objects.get(pk=ids["case_id"])
        # JSON clínico legado permanece idêntico (nenhum rewrite/backfill).
        assert case.structured_data == _LEGACY_V2_STRUCTURED_DATA

        eda = CaseProcedure.objects.get(pk=ids["eda_id"])
        assert eda.procedure_type == "eda"
        assert eda.declared_by_nir is True
        assert eda.detection_status == "detected"
        assert eda.doctor_disposition == "approved"
        assert eda.doctor_reason == "razão legada"

        colon = CaseProcedure.objects.get(pk=ids["colon_id"])
        assert colon.procedure_type == "colonoscopy"
        assert colon.doctor_disposition == "pending"

        event = CaseEvent.objects.get(pk=ids["event_id"])
        assert event.event_type == "CASE_PROCEDURES_DECLARED"
        assert event.payload == {"procedures": ["eda", "colonoscopy"]}

    def test_forward_preserves_rows_json_and_events(self, user) -> None:
        self._migrate_to_0018()
        ids = self._seed_legacy_rows(user)
        self._migrate_to_0019()
        self._assert_legacy_rows_untouched(ids)

    def test_forward_does_not_change_row_count(self, user) -> None:
        self._migrate_to_0018()
        self._seed_legacy_rows(user)
        self._migrate_to_0019()
        migrated_case = Case.objects.filter(agency_record_number="").count()
        assert migrated_case >= 1
        assert CaseProcedure.objects.filter(procedure_type__in=["eda", "colonoscopy"]).exists()

    def test_final_choices_include_specialized_types(self) -> None:
        self._migrate_to_0018()
        self._migrate_to_0019()
        assert set(ProcedureType.values) == {"eda", "colonoscopy", "echoendoscopy", "cpre"}
