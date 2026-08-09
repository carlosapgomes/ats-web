"""Slice 011-C — Migration 0016: precheck fail-closed e cutover físico.

Cobre R1 (precheck aborta ANTES de remover coluna/índice com erro explícito que
identifica o caso), R2 (remoção preservadora: somente o índice composto
``cases_status_exam_type_idx`` e o field ``Case.exam_type`` saem; casos, rows,
eventos — incluindo payload legado de ``CASE_CREATED`` com ``exam_type`` —,
JSON, decisões e agenda permanecem) e R8 (introspecção prova a ausência da
coluna/índice após o forward).

O sandbox usa ``transaction.atomic`` + ``set_rollback`` (e não o padrão
flush do ``TransactionTestCase``): migrate down/up, dados e registros de
``django_migrations`` são desfeitos ao final de cada teste, mantendo o banco
de teste sempre no schema leaf e sem acumular colunas dropped do PostgreSQL.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.cases.models import Case, CaseEvent, CaseStatus

pytestmark = pytest.mark.django_db

User = get_user_model()

_PREV_MIGRATION = "0015_caseprocedure"
_TARGET_MIGRATION = "0016_remove_case_exam_type"


def _column_exists(table: str, column: str) -> bool:
    with connection.cursor() as cursor:
        fields = connection.introspection.get_table_description(cursor, table)
    return any(f.name == column for f in fields)


def _index_exists(table: str, name: str) -> bool:
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return name in constraints


@pytest.mark.django_db(transaction=True)
class TestMigration0016Cutover:
    """Sandbox MigrationExecutor: schema 0015 → 0016 com rollback total."""

    @pytest.fixture(autouse=True)
    def _migration_sandbox(self):
        executor = MigrationExecutor(connection)
        self._leaf_nodes = executor.loader.graph.leaf_nodes()
        self._targets_prev = [
            ("cases", _PREV_MIGRATION) if node[0] == "cases" and node[1] >= _PREV_MIGRATION else node
            for node in self._leaf_nodes
        ]
        with transaction.atomic():
            yield
            # DDL e dados (incl. django_migrations) são desfeitos aqui —
            # o banco permanece no schema leaf entre testes.
            transaction.set_rollback(True)

    def _migrate_to_prev(self) -> None:
        """Desaplica a 0016, deixando o banco no schema 0015 (coluna viva)."""
        MigrationExecutor(connection).migrate(self._targets_prev)

    def _migrate_to_leaf(self) -> None:
        """Aplica a 0016 (precheck + RemoveIndex + RemoveField)."""
        with connection.cursor() as cursor:
            # O container de teste cria FKs como DEFERRABLE INITIALLY
            # DEFERRED (artefato de ambiente, nenhuma migration define isso):
            # INSERTs históricos no mesmo atomic deixam triggers pendentes
            # que bloqueiam o DROP COLUMN do RemoveField. Dispara/limpa as
            # checagens de constraint antes do DDL.
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _prev_apps(self):
        """Project state 0015: models históricos com a coluna ``exam_type``."""
        return MigrationExecutor(connection).loader.project_state(self._targets_prev).apps

    # ── R1 — precheck fail-closed aborta antes de qualquer mudança de schema ──

    def test_precheck_aborts_case_without_rows_keeping_column(self, django_user_model) -> None:
        """Caso sem rows CaseProcedure aborta; coluna e índice permanecem."""
        user = django_user_model.objects.create_user(username="mig0016-a@test.com")
        self._migrate_to_prev()
        old_case_cls = self._prev_apps().get_model("cases", "Case")
        bad_case = old_case_cls.objects.create(created_by_id=user.pk)
        bad_id = bad_case.pk

        with pytest.raises(RuntimeError, match=str(bad_id)):
            self._migrate_to_leaf()
        # Introspecção: a falha ocorreu ANTES do RemoveIndex/RemoveField.
        assert _column_exists("cases_case", "exam_type")
        assert _index_exists("cases_case", "cases_status_exam_type_idx")

    def test_precheck_aborts_on_invalid_procedure_type(self, django_user_model) -> None:
        """Row com tipo fora de eda|colonoscopy aborta identificando o tipo."""
        user = django_user_model.objects.create_user(username="mig0016-b@test.com")
        self._migrate_to_prev()
        old_apps = self._prev_apps()
        old_case_cls = old_apps.get_model("cases", "Case")
        old_proc_cls = old_apps.get_model("cases", "CaseProcedure")
        bad_case = old_case_cls.objects.create(created_by_id=user.pk)
        old_proc_cls.objects.create(
            case_id=bad_case.pk,
            procedure_type="gastroscopy",
            declared_by_nir=True,
        )

        with pytest.raises(RuntimeError, match="gastroscopy"):
            self._migrate_to_leaf()
        assert _column_exists("cases_case", "exam_type")

    def test_precheck_aborts_without_declared_row(self, django_user_model) -> None:
        """Caso cuja única row não é declarada pelo NIR aborta (fail-closed)."""
        user = django_user_model.objects.create_user(username="mig0016-c@test.com")
        self._migrate_to_prev()
        old_apps = self._prev_apps()
        old_case_cls = old_apps.get_model("cases", "Case")
        old_proc_cls = old_apps.get_model("cases", "CaseProcedure")
        bad_case = old_case_cls.objects.create(created_by_id=user.pk)
        old_proc_cls.objects.create(
            case_id=bad_case.pk,
            procedure_type="eda",
            declared_by_nir=False,
        )

        with pytest.raises(RuntimeError, match=str(bad_case.pk)):
            self._migrate_to_leaf()
        assert _column_exists("cases_case", "exam_type")

    # ── R2 — forward preservador: remove só coluna/índice, preserva o resto ──

    def test_forward_valid_state_removes_column_and_index_preserving_data(self, django_user_model) -> None:
        """Estado válido (1 caso com 1 row, 1 caso com 2 rows) migra; dados/eventos preservados."""
        user = django_user_model.objects.create_user(username="mig0016-d@test.com")
        self._migrate_to_prev()
        old_apps = self._prev_apps()
        old_case_cls = old_apps.get_model("cases", "Case")
        old_proc_cls = old_apps.get_model("cases", "CaseProcedure")
        old_event_cls = old_apps.get_model("cases", "CaseEvent")

        # Caso A: 1 row declarada (eda) + decisão/agenda/JSON + evento legado.
        case_a = old_case_cls.objects.create(
            created_by_id=user.pk,
            status=CaseStatus.WAIT_DOCTOR,
            doctor_decision="accept",
            appointment_status="confirmed",
            structured_data={"patient": {"name": "Paciente A"}},
        )
        old_proc_cls.objects.create(case_id=case_a.pk, procedure_type="eda", declared_by_nir=True)
        old_event_cls.objects.create(
            case_id=case_a.pk,
            event_type="CASE_CREATED",
            actor_type="human",
            actor_id=user.pk,
            payload={"status": "NEW", "exam_type": "eda"},
        )

        # Caso B: 2 rows declaradas (eda + colonoscopy) — combinado.
        case_b = old_case_cls.objects.create(created_by_id=user.pk, status=CaseStatus.NEW)
        old_proc_cls.objects.create(case_id=case_b.pk, procedure_type="eda", declared_by_nir=True)
        old_proc_cls.objects.create(case_id=case_b.pk, procedure_type="colonoscopy", declared_by_nir=True)

        self._migrate_to_leaf()

        # Introspecção: coluna e índice compostos REMOVIDOS.
        assert not _column_exists("cases_case", "exam_type")
        assert not _index_exists("cases_case", "cases_status_exam_type_idx")
        # Índices dimensionais do Slice 001 permanecem.
        assert _index_exists("cases_caseprocedure", "proc_declared_idx")
        assert _index_exists("cases_caseprocedure", "proc_detection_idx")
        assert _index_exists("cases_caseprocedure", "proc_disposition_idx")

        # Preservação: caso A (status, decisão, agenda, JSON, row, evento legado).
        a = Case.objects.get(pk=case_a.pk)
        assert a.status == CaseStatus.WAIT_DOCTOR
        assert a.doctor_decision == "accept"
        assert a.appointment_status == "confirmed"
        assert a.structured_data == {"patient": {"name": "Paciente A"}}
        assert set(a.procedures.values_list("procedure_type", flat=True)) == {"eda"}
        legacy_event = CaseEvent.objects.get(case=a, event_type="CASE_CREATED")
        assert legacy_event.payload == {"status": "NEW", "exam_type": "eda"}

        # Preservação: caso B (duas rows, nenhum evento criado pela migration).
        b = Case.objects.get(pk=case_b.pk)
        assert set(b.procedures.values_list("procedure_type", flat=True)) == {"eda", "colonoscopy"}
        assert b.events.count() == 0

    def test_forward_marks_migration_applied(self, django_user_model) -> None:
        """Após o forward, 0016 está aplicada e o sandbox restaura sem erro."""
        user = django_user_model.objects.create_user(username="mig0016-e@test.com")
        self._migrate_to_prev()
        old_apps = self._prev_apps()
        old_case_cls = old_apps.get_model("cases", "Case")
        old_proc_cls = old_apps.get_model("cases", "CaseProcedure")
        ok_case = old_case_cls.objects.create(created_by_id=user.pk)
        old_proc_cls.objects.create(case_id=ok_case.pk, procedure_type="eda", declared_by_nir=True)

        self._migrate_to_leaf()

        executor = MigrationExecutor(connection)
        applied = set(executor.loader.applied_migrations)
        assert ("cases", _TARGET_MIGRATION) in applied
