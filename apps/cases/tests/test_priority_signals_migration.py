"""Testes da migration 0013 — backfill de priority_signals para casos abertos.

Cobre a função backfill produtiva (importada via importlib) e a execução
forward real da migration com MigrationExecutor, de forma equivalente a
test_post_acceptance_issue_migration.py.
"""

from __future__ import annotations

import importlib

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.cases.models import Case, CaseStatus
from apps.cases.priority_signals import resolve_priority_signals

pytestmark = pytest.mark.django_db

User = get_user_model()

_MIGRATION_MODULE = "apps.cases.migrations.0013_case_priority_signals"
_MIGRATION_NAME = "0013_case_priority_signals"


def _structured_pediatric_fb() -> dict[str, object]:
    """structured_data com pediatria (idade 10) + corpo estranho (flag)."""
    return {
        "patient": {"name": "Paciente", "age": 10, "sex": "F"},
        "eda": {
            "indication_category": "other",
            "is_pediatric": True,
            "foreign_body_suspected": False,
            "requested_procedure": {"name": "EDA", "subtype": "standard"},
        },
        "preop_screening": {"rulebook_signals": {"eda_subtype": "standard"}},
    }


def _build_open_case(user, case_factory, advance_to) -> Case:
    """Cria caso WAIT_DOCTOR com structured_data/extracted_text para backfill."""
    case: Case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
    case.structured_data = _structured_pediatric_fb()
    case.extracted_text = "Paciente com corpo estranho em esôfago."
    case.save()
    return case


class TestBackfillFunctionDirect:
    """Testes diretos da função backfill_priority_signals.

    Utilizam registry histórico do MigrationExecutor no estado 0013
    (campo presente, RunPython não executado) e executam a função
    backfill produtiva via importlib sobre o mesmo banco.
    """

    @pytest.fixture(autouse=True)
    def _registry(self) -> None:
        executor = MigrationExecutor(connection)
        targets = [
            ("cases", _MIGRATION_NAME) if node == ("cases", _MIGRATION_NAME) else node
            for node in executor.loader.graph.leaf_nodes()
        ]
        self._historical_apps = executor.loader.project_state(targets).apps

    def _backfill(self) -> None:
        module = importlib.import_module(_MIGRATION_MODULE)
        module.backfill_priority_signals(self._historical_apps, connection.schema_editor())

    def test_open_case_receives_signals(self, user, case_factory, advance_to) -> None:
        case = _build_open_case(user, case_factory, advance_to)
        assert case.priority_signals == []
        self._backfill()
        case = Case.objects.get(pk=case.pk)
        codes = [s["code"] for s in case.priority_signals]
        assert codes == ["foreign_body", "pediatric"]

    def test_cleaned_case_remains_empty(self, user, case_factory, advance_to) -> None:
        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.structured_data = _structured_pediatric_fb()
        case.extracted_text = "Paciente com corpo estranho em esôfago."
        case.save()
        self._backfill()
        case = Case.objects.get(pk=case.pk)
        assert case.priority_signals == []

    def test_existing_list_not_overwritten(self, user, case_factory, advance_to) -> None:
        case = _build_open_case(user, case_factory, advance_to)
        existing = [{"code": "gastrostomy", "category": "special_procedure", "detail": "", "version": 1}]
        Case.objects.filter(pk=case.pk).update(priority_signals=existing)
        self._backfill()
        case = Case.objects.get(pk=case.pk)
        assert case.priority_signals == existing

    def test_status_and_decision_preserved(self, user, case_factory, advance_to) -> None:
        case = _build_open_case(user, case_factory, advance_to)
        case.doctor_decision = "accept"
        case.save(update_fields=["doctor_decision"])
        self._backfill()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == "accept"
        assert [s["code"] for s in case.priority_signals] == ["foreign_body", "pediatric"]

    def test_rerun_is_idempotent(self, user, case_factory, advance_to) -> None:
        case = _build_open_case(user, case_factory, advance_to)
        self._backfill()
        first = Case.objects.get(pk=case.pk).priority_signals
        self._backfill()
        second = Case.objects.get(pk=case.pk).priority_signals
        assert first == second
        assert [s["code"] for s in second] == ["foreign_body", "pediatric"]

    def test_case_without_structured_data_stays_empty(self, user, case_factory, advance_to) -> None:
        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case.extracted_text = "Paciente com corpo estranho."
        case.save()
        self._backfill()
        case = Case.objects.get(pk=case.pk)
        assert case.priority_signals == []


@pytest.mark.django_db(transaction=True)
class TestMigrationForwardReal:
    """Execução forward real 0012 → 0013 com MigrationExecutor."""

    @pytest.fixture(autouse=True)
    def _migration_sandbox(self):
        """Salva leaf nodes originais e restaura schema após o teste."""
        executor = MigrationExecutor(connection)
        self._leaf_nodes = executor.loader.graph.leaf_nodes()
        self._targets_0012 = [
            ("cases", "0012_post_acceptance_issue_fields") if node == ("cases", _MIGRATION_NAME) else node
            for node in self._leaf_nodes
        ]
        try:
            yield
        finally:
            MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _migrate_to_0012(self) -> None:
        """Desaplica cases 0013, deixando o banco no schema 0012."""
        MigrationExecutor(connection).migrate(self._targets_0012)

    def _migrate_to_0013(self) -> None:
        """Aplica cases 0013 (AddField + RunPython backfill)."""
        MigrationExecutor(connection).migrate(self._leaf_nodes)

    def _get_0012_state(self):
        return MigrationExecutor(connection).loader.project_state(self._targets_0012).apps

    def _create_0012_case(self, old_apps, user, *, status: str, structured_data, extracted_text):
        old_case_cls = old_apps.get_model("cases", "Case")
        return old_case_cls.objects.create(
            created_by_id=user.pk,
            status=status,
            structured_data=structured_data,
            extracted_text=extracted_text,
        )

    def test_forward_open_case_receives_signals(self, user) -> None:
        self._migrate_to_0012()
        old_apps = self._get_0012_state()
        c = self._create_0012_case(
            old_apps,
            user,
            status="WAIT_DOCTOR",
            structured_data=_structured_pediatric_fb(),
            extracted_text="Paciente com corpo estranho em esôfago.",
        )
        self._migrate_to_0013()
        c_real = Case.objects.get(pk=c.pk)
        codes = [s["code"] for s in c_real.priority_signals]
        assert codes == ["foreign_body", "pediatric"]

    def test_forward_cleaned_remains_empty(self, user) -> None:
        self._migrate_to_0012()
        old_apps = self._get_0012_state()
        c = self._create_0012_case(
            old_apps,
            user,
            status="CLEANED",
            structured_data=_structured_pediatric_fb(),
            extracted_text="Paciente com corpo estranho em esôfago.",
        )
        self._migrate_to_0013()
        c_real = Case.objects.get(pk=c.pk)
        assert c_real.priority_signals == []

    def test_forward_preserves_status_and_decision(self, user) -> None:
        self._migrate_to_0012()
        old_apps = self._get_0012_state()
        old_case_cls = old_apps.get_model("cases", "Case")
        c = old_case_cls.objects.create(
            created_by_id=user.pk,
            status="WAIT_DOCTOR",
            doctor_decision="accept",
            structured_data=_structured_pediatric_fb(),
            extracted_text="Paciente com corpo estranho em esôfago.",
        )
        self._migrate_to_0013()
        c_real = Case.objects.get(pk=c.pk)
        assert c_real.status == CaseStatus.WAIT_DOCTOR
        assert c_real.doctor_decision == "accept"
        assert [s["code"] for s in c_real.priority_signals] == ["foreign_body", "pediatric"]

    def test_forward_migration_completes_cleanly(self) -> None:
        self._migrate_to_0012()
        self._migrate_to_0013()
        executor = MigrationExecutor(connection)
        applied = set(executor.loader.applied_migrations)
        assert ("cases", _MIGRATION_NAME) in applied

    def test_snapshot_equivalence_with_runtime_resolver(self) -> None:
        """O snapshot v1 da migration é equivalente ao resolvedor runtime nos seis códigos."""
        module = importlib.import_module(_MIGRATION_MODULE)
        snapshot = module._snapshot_resolve_priority_signals

        base = _structured_pediatric_fb()
        scenarios: list[tuple[dict[str, object], str]] = [
            # pediatria (idade 10)
            (base, ""),
            # corpo estranho textual positivo
            ({"patient": {"age": 30}}, "Suspeita de corpo estranho em esôfago."),
            # corpo estranho textual negado
            ({"patient": {"age": 30}}, "Sem corpo estranho."),
            # ingestão cáustica com tempo
            ({"patient": {"age": 30}}, "Paciente ingeriu soda cáustica há 3 semanas."),
            # ecoendoscopia termo completo
            ({"patient": {"age": 30}}, "Solicito ecoendoscopia."),
            # EUS contextual
            ({"patient": {"age": 30}}, "Solicito EUS para avaliar lesão."),
            # dilatação esofágica
            ({"patient": {"age": 30}}, "Dilatação esofágica indicada."),
            # dilatação genérica NÃO sinaliza
            ({"patient": {"age": 30}}, "Solicito dilatação."),
            # gastrostomia com contexto
            ({"patient": {"age": 30}}, "Solicito gastrostomia."),
            # gastrostomia histórica NÃO sinaliza
            ({"patient": {"age": 30}}, "Paciente com gastrostomia prévia."),
            # EUS isolado NÃO sinaliza
            ({"patient": {"age": 30}}, "EUS"),
        ]

        for overrides, text in scenarios:
            structured = {
                "patient": {"name": "X", "age": 30, "sex": "M"},
                "eda": {
                    "indication_category": "other",
                    "is_pediatric": False,
                    "foreign_body_suspected": False,
                    "requested_procedure": {"name": "EDA", "subtype": "standard"},
                },
                "preop_screening": {"rulebook_signals": {"eda_subtype": "standard"}},
            }
            structured.update(overrides)
            runtime_codes = [s["code"] for s in resolve_priority_signals(structured_data=structured, source_text=text)]
            snapshot_codes = [s["code"] for s in snapshot(structured_data=structured, source_text=text)]
            assert snapshot_codes == runtime_codes, f"Equivalência falhou para {structured!r} / {text!r}"

        # corpo estranho via subtipo estruturado
        subtype_payload = {
            "patient": {"name": "X", "age": 30, "sex": "M"},
            "eda": {
                "indication_category": "foreign_body",
                "is_pediatric": False,
                "foreign_body_suspected": True,
                "requested_procedure": {"name": "EDA", "subtype": "foreign_body"},
            },
            "preop_screening": {"rulebook_signals": {"eda_subtype": "foreign_body"}},
        }
        runtime_codes = [s["code"] for s in resolve_priority_signals(structured_data=subtype_payload, source_text="")]
        snapshot_codes = [s["code"] for s in snapshot(structured_data=subtype_payload, source_text="")]
        assert snapshot_codes == runtime_codes == ["foreign_body"]
