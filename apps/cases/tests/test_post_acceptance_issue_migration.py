"""Testes da migration 0012 — backfill de intercorrências legadas ativas.

Cobre tanto a função backfill produtiva (importada via importlib) quanto
a execução forward real da migration com MigrationExecutor.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.cases.models import Case, CaseStatus

pytestmark = pytest.mark.django_db

User = get_user_model()


# ── Helpers ─────────────────────────────────────────────────────────────


def _create_case_data(user, case_factory, advance_to, status: str) -> Case:
    """Cria caso CLEANED/scheduled/confirmed com status de issue definido."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])
    Case.objects.filter(pk=case.pk).update(
        post_schedule_issue_status=status,
        post_schedule_issue_reason="death",
    )
    return Case.objects.get(pk=case.pk)


# ═════════════════════════════════════════════════════════════════════════
# Testes da função produtiva (backfill via importlib)
# ═════════════════════════════════════════════════════════════════════════


class TestBackfillFunctionDirect:
    """Testes diretos da função backfill_active_post_acceptance_issues.

    Utilizam registry histórico do MigrationExecutor no estado 0012,
    que inclui os AddField mas não o RunPython executado. Isto garante
    que o model usado pelo backfill reflita o schema pós-AddField,
    como ocorre durante a execução real da migration.
    """

    @pytest.fixture(autouse=True)
    def _registry(self):
        """Obtém registry histórico do estado 0012 (com campos novos, sem backfill)."""
        executor = MigrationExecutor(connection)
        targets = [
            ("cases", "0012_post_acceptance_issue_fields")
            if node == ("cases", "0012_post_acceptance_issue_fields")
            else node
            for node in executor.loader.graph.leaf_nodes()
        ]
        self._historical_apps = executor.loader.project_state(targets).apps

    def test_opened_receives_context_and_unique_uuid(self, user, case_factory, advance_to):
        """Issue opened recebe contexto 'scheduled' e UUID único."""
        import importlib

        backfill = importlib.import_module(
            "apps.cases.migrations.0012_post_acceptance_issue_fields"
        ).backfill_active_post_acceptance_issues

        c1 = _create_case_data(user, case_factory, advance_to, "opened")
        c2 = _create_case_data(user, case_factory, advance_to, "opened")

        # Executa com registry histórico (schema não tem os campos novos)
        backfill(self._historical_apps, connection.schema_editor())

        c1 = Case.objects.get(pk=c1.pk)
        c2 = Case.objects.get(pk=c2.pk)

        assert c1.post_acceptance_issue_context == "scheduled"
        assert c1.post_acceptance_issue_cycle_id is not None
        assert isinstance(c1.post_acceptance_issue_cycle_id, uuid.UUID)
        assert c2.post_acceptance_issue_context == "scheduled"
        assert c2.post_acceptance_issue_cycle_id is not None
        assert c1.post_acceptance_issue_cycle_id != c2.post_acceptance_issue_cycle_id, "UUIDs devem ser distintos"

    def test_responded_receives_context_and_uuid(self, user, case_factory, advance_to):
        """Issue responded também recebe contexto/UUID."""
        import importlib

        backfill = importlib.import_module(
            "apps.cases.migrations.0012_post_acceptance_issue_fields"
        ).backfill_active_post_acceptance_issues

        case = _create_case_data(user, case_factory, advance_to, "responded")
        backfill(self._historical_apps, connection.schema_editor())

        c = Case.objects.get(pk=case.pk)
        assert c.post_acceptance_issue_context == "scheduled"
        assert c.post_acceptance_issue_cycle_id is not None

    def test_no_active_issue_stays_default(self, user, case_factory, advance_to):
        """Casos sem issue ativa permanecem com valores vazios/nulos."""
        import importlib

        backfill = importlib.import_module(
            "apps.cases.migrations.0012_post_acceptance_issue_fields"
        ).backfill_active_post_acceptance_issues

        case = _create_case_data(user, case_factory, advance_to, "")
        # Garantir que não tem status ativo
        Case.objects.filter(pk=case.pk).update(post_schedule_issue_status="")

        backfill(self._historical_apps, connection.schema_editor())

        c = Case.objects.get(pk=case.pk)
        assert c.post_acceptance_issue_context == ""
        assert c.post_acceptance_issue_cycle_id is None

    def test_many_cases_in_same_batch_have_unique_uuids(self, user, case_factory, advance_to):
        """Múltiplos casos no mesmo lote recebem UUIDs distintos."""
        import importlib

        backfill = importlib.import_module(
            "apps.cases.migrations.0012_post_acceptance_issue_fields"
        ).backfill_active_post_acceptance_issues

        pks = []
        for _ in range(10):
            case = _create_case_data(user, case_factory, advance_to, "opened")
            pks.append(case.pk)

        backfill(self._historical_apps, connection.schema_editor())

        uuids_set: set[uuid.UUID] = set()
        for pk in pks:
            c = Case.objects.get(pk=pk)
            assert c.post_acceptance_issue_context == "scheduled"
            assert c.post_acceptance_issue_cycle_id is not None
            uuids_set.add(c.post_acceptance_issue_cycle_id)

        assert len(uuids_set) == 10, f"Esperados 10 UUIDs únicos, obtidos {len(uuids_set)}"

    def test_existing_context_not_overwritten(self, user, case_factory, advance_to):
        """Valores já preenchidos não são sobrescritos no backfill direto."""
        existing_cycle_id = uuid.uuid4()

        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        case.save(update_fields=["doctor_decision", "doctor_admission_flow", "appointment_status"])
        Case.objects.filter(pk=case.pk).update(
            post_schedule_issue_status="opened",
            post_schedule_issue_reason="death",
            post_acceptance_issue_context="scheduled",
            post_acceptance_issue_cycle_id=existing_cycle_id,
        )

        import importlib

        backfill = importlib.import_module(
            "apps.cases.migrations.0012_post_acceptance_issue_fields"
        ).backfill_active_post_acceptance_issues

        backfill(self._historical_apps, connection.schema_editor())

        c = Case.objects.get(pk=case.pk)
        assert c.post_acceptance_issue_context == "scheduled"
        assert c.post_acceptance_issue_cycle_id == existing_cycle_id, "UUID existente não deve ser sobrescrito"


# ═════════════════════════════════════════════════════════════════════════
# Testes da migration forward real 0011→0012 com MigrationExecutor
# ═════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db(transaction=True)
class TestMigrationForwardReal:
    @pytest.fixture(autouse=True)
    def _migration_sandbox(self):
        """Salva leaf nodes originais e restaura schema após o teste."""
        executor = MigrationExecutor(connection)
        self._leaf_nodes = executor.loader.graph.leaf_nodes()
        # Substitui cases.0012 por cases.0011 nos leaf nodes
        self._targets_0011 = [
            ("cases", "0011_dashboard_case_search_indexes")
            if node == ("cases", "0012_post_acceptance_issue_fields")
            else node
            for node in self._leaf_nodes
        ]
        try:
            yield
        finally:
            # Restaura ao estado leaf original
            MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _migrate_to_0011(self):
        """Desaplica cases 0012, deixando o banco no schema 0011."""
        MigrationExecutor(connection).migrate(self._targets_0011)

    def _migrate_to_0012(self):
        """Aplica cases 0012 (AddField + RunPython backfill)."""
        MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _get_0011_state(self):
        """Retorna apps do project state 0011 (sem os campos novos)."""
        return MigrationExecutor(connection).loader.project_state(self._targets_0011).apps

    # ── Cenários ──────────────────────────────────────────────────────

    def test_forward_opened_and_responded_receive_context_and_uuid(self, user):
        """Migration forward popula contexto e UUID para issues ativas."""
        self._migrate_to_0011()
        old_apps = self._get_0011_state()
        old_case_cls = old_apps.get_model("cases", "Case")

        # Cria casos via model histórico (schema 0011, sem campos novos)
        c1 = old_case_cls.objects.create(
            created_by_id=user.pk,
            post_schedule_issue_status="opened",
            post_schedule_issue_reason="death",
        )
        c2 = old_case_cls.objects.create(
            created_by_id=user.pk,
            post_schedule_issue_status="responded",
            post_schedule_issue_reason="transport_unavailable",
        )

        self._migrate_to_0012()

        c1_real = Case.objects.get(pk=c1.pk)
        c2_real = Case.objects.get(pk=c2.pk)

        assert c1_real.post_acceptance_issue_context == "scheduled"
        assert c1_real.post_acceptance_issue_cycle_id is not None
        assert isinstance(c1_real.post_acceptance_issue_cycle_id, uuid.UUID)

        assert c2_real.post_acceptance_issue_context == "scheduled"
        assert c2_real.post_acceptance_issue_cycle_id is not None
        assert c2_real.post_acceptance_issue_cycle_id != c1_real.post_acceptance_issue_cycle_id, (
            "UUIDs devem ser distintos"
        )

    def test_forward_unique_uuids_in_same_batch(self, user):
        """Vários casos no mesmo lote recebem UUIDs distintos na migration."""
        self._migrate_to_0011()
        old_apps = self._get_0011_state()
        old_case_cls = old_apps.get_model("cases", "Case")

        pks = []
        for _ in range(10):
            c = old_case_cls.objects.create(
                created_by_id=user.pk,
                post_schedule_issue_status="opened",
                post_schedule_issue_reason="death",
            )
            pks.append(c.pk)

        self._migrate_to_0012()

        uuids_set: set[uuid.UUID] = set()
        for pk in pks:
            c = Case.objects.get(pk=pk)
            assert c.post_acceptance_issue_context == "scheduled"
            assert c.post_acceptance_issue_cycle_id is not None
            uuids_set.add(c.post_acceptance_issue_cycle_id)

        assert len(uuids_set) == 10, f"Esperados 10 UUIDs únicos, obtidos {len(uuids_set)}"

    def test_forward_no_active_issue_stays_default(self, user):
        """Caso sem issue ativa permanece com campos default após migration."""
        self._migrate_to_0011()
        old_apps = self._get_0011_state()
        old_case_cls = old_apps.get_model("cases", "Case")

        c = old_case_cls.objects.create(
            created_by_id=user.pk,
            post_schedule_issue_status="",  # sem issue ativa
        )

        self._migrate_to_0012()

        c_real = Case.objects.get(pk=c.pk)
        assert c_real.post_acceptance_issue_context == ""
        assert c_real.post_acceptance_issue_cycle_id is None

    def test_forward_preserves_legacy_data(self, user):
        """Dados legados (post_schedule_issue_*) são preservados."""
        self._migrate_to_0011()
        old_apps = self._get_0011_state()
        old_case_cls = old_apps.get_model("cases", "Case")

        c = old_case_cls.objects.create(
            created_by_id=user.pk,
            post_schedule_issue_status="opened",
            post_schedule_issue_reason="death",
            post_schedule_issue_opened_by_id=user.pk,
        )

        self._migrate_to_0012()

        c_real = Case.objects.get(pk=c.pk)
        assert c_real.post_schedule_issue_status == "opened"
        assert c_real.post_schedule_issue_reason == "death"
        assert c_real.post_schedule_issue_opened_by_id == user.pk

    def test_forward_migration_completes_cleanly(self):
        """Após executar a migration forward, 0012 está aplicada e sem erros."""
        self._migrate_to_0011()
        self._migrate_to_0012()

        # Verifica que 0012 está aplicada
        executor = MigrationExecutor(connection)
        applied = set(executor.loader.applied_migrations)
        assert ("cases", "0012_post_acceptance_issue_fields") in applied, (
            "0012 deve estar aplicada após migration forward"
        )
