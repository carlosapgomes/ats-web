"""Slice 001 (R4) — migration 0020 de choices é AlterField puro e reversível.

Cobre:
- inspeção estática: a migration contém exatamente o ``AlterField`` de
  ``ProcedureFollowUp.non_performance_reason`` e NENHUMA operação de dados ou
  de remoção (``RunPython``/``RunSQL``/``RemoveField``/``RemoveConstraint``/
  ``DeleteModel``/``SeparateDatabaseAndState``) — nenhum backfill;
- choices finais reconhecem as eras legada e atual (26 códigos);
- ida/volta ``0019 → 0020 → 0019 → 0020`` com ``MigrationExecutor``: rows
  legadas permanecem byte a byte inalteradas a cada passo.
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
from django.db.models.fields import Field

from apps.cases.models import (
    CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES,
    CaseEvent,
    CaseFollowUp,
    ProcedureFollowUp,
)

pytestmark = pytest.mark.django_db

User = get_user_model()

_MIGRATION_MODULE = "apps.cases.migrations.0020_alter_procedurefollowup_non_performance_reason"
_PREVIOUS_MIGRATION = "0019_alter_caseprocedure_procedure_type"
_DESTRUCTIVE_OPERATIONS = (RunPython, RunSQL, SeparateDatabaseAndState)
_REMOVAL_OPERATION_NAMES = {"RemoveField", "RemoveConstraint", "DeleteModel"}


def _operations() -> list[Any]:
    module = importlib.import_module(_MIGRATION_MODULE)
    return list(module.Migration.operations)


class TestMigrationIsAlterFieldOnly:
    """R4 — a migration altera apenas metadados de choices; nunca executa dados."""

    def test_single_alter_field_operation(self) -> None:
        operations = _operations()
        assert len(operations) == 1
        operation = operations[0]
        assert isinstance(operation, AlterField)
        assert operation.model_name == "procedurefollowup"
        assert operation.name == "non_performance_reason"

    def test_no_data_or_destructive_operations(self) -> None:
        for operation in _operations():
            assert not isinstance(operation, _DESTRUCTIVE_OPERATIONS)
            assert type(operation).__name__ not in _REMOVAL_OPERATION_NAMES

    def test_remocao_de_coluna_ou_constraint_ausente(self) -> None:
        for operation in _operations():
            assert type(operation).__name__ not in _REMOVAL_OPERATION_NAMES

    def test_field_metadata_preservado(self) -> None:
        field = _operations()[0].field
        assert isinstance(field, Field)
        assert field.max_length == 30
        assert field.blank is True

    def test_choices_reconhecem_eras_legada_e_atual(self) -> None:
        choices = {value for value, _label in _operations()[0].field.choices}
        assert choices == set(CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES) | {
            "absenteeism",
            "resource_shortage",
        }
        assert len(choices) == 26


class TestShuttleMigrationPreservesLegacyRows:
    """R4 — ``0019 → 0020 → 0019 → 0020`` preserva rows legadas.

    Executa fora do bloco atômico do pytest: a leaf atual inclui a migration
    ``0021`` (choices/``max_length`` do catálogo ampliado) e o PostgreSQL recusa
    ``ALTER COLUMN`` numa tabela com eventos de trigger pendentes do próprio
    teste.
    """

    pytestmark = pytest.mark.django_db(transaction=True)

    @pytest.fixture(autouse=True)
    def _migration_sandbox(self):
        executor = MigrationExecutor(connection)
        self._leaf_nodes = executor.loader.graph.leaf_nodes()
        self._targets_0019 = [
            ("cases", _PREVIOUS_MIGRATION) if node[0] == "cases" and node[1] > _PREVIOUS_MIGRATION else node
            for node in self._leaf_nodes
        ]
        try:
            yield
        finally:
            MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _migrate_to_0019(self) -> None:
        MigrationExecutor(connection).migrate(self._targets_0019)

    def _migrate_to_0020(self) -> None:
        MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _state_0019(self):
        return MigrationExecutor(connection).loader.project_state(self._targets_0019).apps

    def _seed_legacy_rows(self, user) -> dict[str, Any]:
        """Cria follow-up legado (absenteeism e resource_shortage+submotivo) no schema 0019."""
        old_apps = self._state_0019()
        old_case = old_apps.get_model("cases", "Case")
        old_case_procedure = old_apps.get_model("cases", "CaseProcedure")
        old_follow_up = old_apps.get_model("cases", "CaseFollowUp")
        old_procedure_follow_up = old_apps.get_model("cases", "ProcedureFollowUp")
        old_event = old_apps.get_model("cases", "CaseEvent")

        case = old_case.objects.create(
            created_by_id=user.pk,
            agency_record_number="MIG-0020",
            status="WAIT_DOCTOR",
        )
        eda = old_case_procedure.objects.create(
            case_id=case.pk,
            procedure_type="eda",
            doctor_disposition="approved",
        )
        colon = old_case_procedure.objects.create(
            case_id=case.pk,
            procedure_type="colonoscopy",
            doctor_disposition="approved",
        )
        follow_up = old_follow_up.objects.create(case_id=case.pk, version=1, patient_admitted=True)
        absent = old_procedure_follow_up.objects.create(
            follow_up_id=follow_up.pk,
            procedure_id=eda.pk,
            performed=False,
            non_performance_reason="absenteeism",
        )
        shortage = old_procedure_follow_up.objects.create(
            follow_up_id=follow_up.pk,
            procedure_id=colon.pk,
            performed=False,
            non_performance_reason="resource_shortage",
            resource_shortage_detail="emergency_occupied",
        )
        event = old_event.objects.create(
            case_id=case.pk,
            actor_type="human",
            event_type="FOLLOWUP_RECORDED",
            payload={
                "version": 1,
                "patient_admitted": True,
                "outcomes": [
                    {"procedure_id": eda.pk, "performed": False, "non_performance_reason": "absenteeism"},
                    {
                        "procedure_id": colon.pk,
                        "performed": False,
                        "non_performance_reason": "resource_shortage",
                        "resource_shortage_detail": "emergency_occupied",
                    },
                ],
            },
        )
        return {
            "case_id": case.pk,
            "follow_up_id": follow_up.pk,
            "absent_id": absent.pk,
            "shortage_id": shortage.pk,
            "event_id": event.pk,
        }

    def _assert_legacy_rows_untouched(self, ids: dict[str, Any]) -> None:
        follow_up = CaseFollowUp.objects.get(pk=ids["follow_up_id"])
        assert follow_up.version == 1
        assert follow_up.patient_admitted is True

        absent = ProcedureFollowUp.objects.get(pk=ids["absent_id"])
        assert absent.performed is False
        assert absent.non_performance_reason == "absenteeism"
        assert absent.resource_shortage_detail == ""
        assert absent.other_reason == ""

        shortage = ProcedureFollowUp.objects.get(pk=ids["shortage_id"])
        assert shortage.performed is False
        assert shortage.non_performance_reason == "resource_shortage"
        assert shortage.resource_shortage_detail == "emergency_occupied"

        event = CaseEvent.objects.get(pk=ids["event_id"])
        assert event.payload["outcomes"][1]["non_performance_reason"] == "resource_shortage"
        assert event.payload["outcomes"][1]["resource_shortage_detail"] == "emergency_occupied"

    def test_shuttle_0019_0020_0019_0020_preserves_rows(self, user) -> None:
        self._migrate_to_0019()
        ids = self._seed_legacy_rows(user)
        self._assert_legacy_rows_untouched(ids)

        self._migrate_to_0020()
        self._assert_legacy_rows_untouched(ids)

        self._migrate_to_0019()
        self._assert_legacy_rows_untouched(ids)

        self._migrate_to_0020()
        self._assert_legacy_rows_untouched(ids)

    def test_shuttle_nao_altera_contagem_de_rows(self, user) -> None:
        self._migrate_to_0019()
        ids = self._seed_legacy_rows(user)

        self._migrate_to_0020()
        self._migrate_to_0019()
        self._migrate_to_0020()

        assert ProcedureFollowUp.objects.filter(pk=ids["shortage_id"]).count() == 1
        assert CaseFollowUp.objects.filter(case_id=ids["case_id"]).count() == 1
        assert CaseEvent.objects.filter(pk=ids["event_id"]).count() == 1

    def test_estado_final_aceita_26_codigos(self) -> None:
        self._migrate_to_0019()
        self._migrate_to_0020()
        choices = {value for value, _label in _operations()[0].field.choices}
        assert len(choices) == 26
