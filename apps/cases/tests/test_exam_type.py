"""Slice 002 — ExamType, Case.exam_type, migration backfill EDA e auditoria.

Cobre R1 (enum/campo/backfill/índice) e a parte de auditoria de R4
(payload de CASE_CREATED para novos casos, sem reescrever eventos antigos).
"""

from __future__ import annotations

import importlib

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.cases.models import Case, CaseEvent, CaseStatus, ExamType

pytestmark = pytest.mark.django_db

User = get_user_model()

_MIGRATION_MODULE = "apps.cases.migrations.0014_case_exam_type"
_MIGRATION_NAME = "0014_case_exam_type"
_PREV_MIGRATION = "0013_case_priority_signals"


class TestExamTypeEnum:
    """R1 — enum com somente eda e colonoscopy."""

    def test_only_eda_and_colonoscopy_values(self) -> None:
        assert set(ExamType.values) == {"eda", "colonoscopy"}
        assert ExamType.EDA.value == "eda"
        assert ExamType.COLONOSCOPY.value == "colonoscopy"

    def test_human_labels(self) -> None:
        assert ExamType(ExamType.EDA).label == "EDA"
        assert ExamType(ExamType.COLONOSCOPY).label == "Colonoscopia"


class TestCaseExamTypeField:
    """R1/R5 — campo persistido e compatibilidade de fixtures EDA."""

    def test_new_case_defaults_to_eda_for_fixture_compat(self, case_factory, user) -> None:
        """Fixture existente (Case sem tipo) permanece EDA — default documentado."""
        case = case_factory(user)
        assert case.exam_type == ExamType.EDA

    def test_colonoscopy_case_is_persisted(self, case_factory, user) -> None:
        case = Case.objects.create(created_by=user, exam_type=ExamType.COLONOSCOPY)
        fetched = Case.objects.get(pk=case.pk)
        assert fetched.exam_type == ExamType.COLONOSCOPY

    def test_index_composite_status_exam_type_exists(self) -> None:
        index_names = [idx.name for idx in Case._meta.indexes]
        assert "cases_status_exam_type_idx" in index_names


class TestCaseCreatedAuditPayload:
    """R4 — CASE_CREATED de novos casos inclui exam_type."""

    def test_case_created_payload_includes_colonoscopy(self, user) -> None:
        case = Case.objects.create(created_by=user, exam_type=ExamType.COLONOSCOPY)
        event = CaseEvent.objects.get(case=case, event_type="CASE_CREATED")
        assert event.payload.get("exam_type") == ExamType.COLONOSCOPY

    def test_case_created_payload_includes_eda(self, user) -> None:
        case = Case.objects.create(created_by=user, exam_type=ExamType.EDA)
        event = CaseEvent.objects.get(case=case, event_type="CASE_CREATED")
        assert event.payload.get("exam_type") == ExamType.EDA


class TestBackfillFunctionDirect:
    """R1 — função de backfill força EDA em todos os casos, sem artefatos."""

    @pytest.fixture(autouse=True)
    def _registry(self) -> None:
        executor = MigrationExecutor(connection)
        targets = [
            (
                "cases",
                _MIGRATION_NAME,
            )
            if node == ("cases", _MIGRATION_NAME)
            else node
            for node in executor.loader.graph.leaf_nodes()
        ]
        self._historical_apps = executor.loader.project_state(targets).apps

    def _backfill(self) -> None:
        module = importlib.import_module(_MIGRATION_MODULE)
        module.backfill_exam_type_eda(self._historical_apps, connection.schema_editor())

    def test_backfill_sets_all_existing_cases_to_eda(self, user, case_factory, advance_to) -> None:
        """Casos em status variados (aberto, decidido, encerrado) viram EDA."""
        open_case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        denied = advance_to(case_factory(user), CaseStatus.DOCTOR_DENIED)
        cleaned = advance_to(case_factory(user), CaseStatus.CLEANED)

        # Simula divergência para provar que o backfill força EDA
        for c in (open_case, denied, cleaned):
            Case.objects.filter(pk=c.pk).update(exam_type="colonoscopy")

        self._backfill()

        for c in (open_case, denied, cleaned):
            assert Case.objects.get(pk=c.pk).exam_type == ExamType.EDA

    def test_backfill_preserves_other_fields(self, user, case_factory, advance_to) -> None:
        """Backfill não altera status/decisão/registro — sem reprocessamento."""
        case = advance_to(case_factory(user), CaseStatus.DOCTOR_DENIED)
        case.agency_record_number = "2026-0909-001"
        case.doctor_decision = "deny"
        case.save(update_fields=["agency_record_number", "doctor_decision"])
        Case.objects.filter(pk=case.pk).update(exam_type="colonoscopy")

        self._backfill()

        case = Case.objects.get(pk=case.pk)
        assert case.exam_type == ExamType.EDA
        assert case.status == CaseStatus.DOCTOR_DENIED
        assert case.doctor_decision == "deny"
        assert case.agency_record_number == "2026-0909-001"


@pytest.mark.django_db(transaction=True)
class TestMigrationForwardReal:
    """R1 — execução forward real da migration 0014 sobre casos 0013."""

    @pytest.fixture(autouse=True)
    def _migration_sandbox(self):
        executor = MigrationExecutor(connection)
        self._leaf_nodes = executor.loader.graph.leaf_nodes()
        self._targets_prev = [
            ("cases", _PREV_MIGRATION) if node == ("cases", _MIGRATION_NAME) else node for node in self._leaf_nodes
        ]
        try:
            yield
        finally:
            MigrationExecutor(connection).migrate(self._leaf_nodes)

    def test_forward_backfills_existing_cases_as_eda_preserving_fields(self, user, case_factory) -> None:
        # Usuário criado antes do migrate down (tabela accounts não é tocada)
        MigrationExecutor(connection).migrate(self._targets_prev)
        old_apps = MigrationExecutor(connection).loader.project_state(self._targets_prev).apps
        old_case_cls = old_apps.get_model("cases", "Case")
        old_case = old_case_cls.objects.create(
            created_by_id=user.pk,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="2026-HIST-001",
            extracted_text="laudo histórico EDA",
        )
        old_case_id = old_case.pk

        # Aplica 0014 (AddField + backfill + índice)
        MigrationExecutor(connection).migrate(self._leaf_nodes)

        case = Case.objects.get(pk=old_case_id)
        assert case.exam_type == ExamType.EDA
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.agency_record_number == "2026-HIST-001"
        assert case.extracted_text == "laudo histórico EDA"
        # Nenhum evento novo deve ter sido criado pelo backfill
        assert case.events.count() == 0
