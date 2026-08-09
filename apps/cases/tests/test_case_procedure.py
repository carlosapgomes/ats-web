"""Slice 001 — CaseProcedure: projeção normalizada, índices D1, backfill D3.

Cobre:
- R1: enum e modelo mínimos; unique constraint (case, procedure_type); os três
      índices dimensionais D1 existem na Meta.
- R2: backfill fecha a tabela D3 nos 18 estados (com/sem marcador downstream
      nos cinco condicionais), mapeamento fechado de doctor_disposition,
      preservação de campos/eventos e reversão determinística.
- R3: serviço único de declaração (conjunto ordenado, evento enxuto e
      atomicidade).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.cases.models import (
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)
from apps.cases.procedures import (
    format_procedure_selection,
    get_approved_procedure_types,
    get_declared_procedure_types,
    get_detected_procedure_types,
    set_declared_procedures,
)

pytestmark = pytest.mark.django_db

User = get_user_model()

_PENDING_STATUSES = (
    CaseStatus.NEW,
    CaseStatus.R1_ACK_PROCESSING,
    CaseStatus.EXTRACTING,
    CaseStatus.LLM_STRUCT,
)
_DETECTED_STATUSES = (
    CaseStatus.LLM_SUGGEST,
    CaseStatus.R2_POST_WIDGET,
    CaseStatus.WAIT_DOCTOR,
    CaseStatus.DOCTOR_DENIED,
    CaseStatus.DOCTOR_ACCEPTED,
    CaseStatus.R3_POST_REQUEST,
    CaseStatus.WAIT_APPT,
    CaseStatus.APPT_CONFIRMED,
    CaseStatus.APPT_DENIED,
)
_CONDITIONAL_STATUSES = (
    CaseStatus.FAILED,
    CaseStatus.R1_FINAL_REPLY_POSTED,
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    CaseStatus.CLEANUP_RUNNING,
    CaseStatus.CLEANED,
)


class TestProcedureEnums:
    """R1 — enums mínimos sem CPRE/procedure engine genérica."""

    def test_procedure_type_values(self) -> None:
        assert set(ProcedureType.values) == {"eda", "colonoscopy"}
        assert ProcedureType.EDA.label == "EDA"
        assert ProcedureType.COLONOSCOPY.label == "Colonoscopia"

    def test_detection_status_values(self) -> None:
        assert set(DetectionStatus.values) == {"pending", "detected", "not_detected"}

    def test_doctor_disposition_values(self) -> None:
        assert set(DoctorDisposition.values) == {"pending", "approved", "denied"}


class TestCaseProcedureModel:
    """R1 — constraint única e índices dimensionais D1."""

    def test_unique_constraint_blocks_duplicate_procedure(self, user, case_factory) -> None:
        case = case_factory(user)
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA)

    def test_same_procedure_different_case_allowed(self, user, case_factory) -> None:
        case_a = case_factory(user)
        case_b = case_factory(user)
        CaseProcedure.objects.create(case=case_a, procedure_type=ProcedureType.EDA)
        # constraint é (case, procedure_type) — outro caso aceita a mesma row
        CaseProcedure.objects.create(case=case_b, procedure_type=ProcedureType.EDA)

    def test_d1_indexes_present(self) -> None:
        index_names = {idx.name: tuple(idx.fields) for idx in CaseProcedure._meta.indexes}
        assert (
            "procedure_type",
            "declared_by_nir",
            "case",
        ) in index_names.values()
        assert ("procedure_type", "detection_status", "case") in index_names.values()
        assert ("procedure_type", "doctor_disposition", "case") in index_names.values()

    def test_related_name_and_defaults(self, user, case_factory) -> None:
        case = case_factory(user)
        row = CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.COLONOSCOPY)
        assert case.procedures.count() == 1
        assert row.declared_by_nir is False
        assert row.detection_status == DetectionStatus.PENDING
        assert row.doctor_disposition == DoctorDisposition.PENDING


@pytest.mark.django_db(transaction=True)
class TestBackfillD3Table:
    """R2 — backfill fecha a tabela D3 nos 18 estados sem inferir/reprocessar.

    Sandbox de schema (Slice 011-C0): migra o banco down até 0014 — estado
    histórico em que ``Case.exam_type`` sempre existe — cria/inspeciona os
    casos pelos modelos históricos e aplica/reverte a 0015 via
    MigrationExecutor (backfill/reverse reais, nunca o leaf). O rollback
    total do atomic desfaz DDL e ``django_migrations``: o banco de teste
    permanece no schema leaf entre testes, com ou sem a coluna no leaf
    (independência do cutover 011-C).
    """

    _MIGRATION_0014 = "0014_case_exam_type"
    _MIGRATION_0015 = "0015_caseprocedure"
    _TARGETS_0014 = [("cases", _MIGRATION_0014)]
    _TARGETS_0015 = [("cases", _MIGRATION_0015)]

    @pytest.fixture(autouse=True)
    def _schema_sandbox(self) -> Iterator[None]:
        """Sandbox: schema 0014 no setup; rollback total no teardown."""
        executor = MigrationExecutor(connection)
        # Estado histórico 0014: modelos com a coluna (criação/leitura de
        # casos — nunca o ORM do leaf). Targets parciais: o plan de migrate
        # cobre apenas o app ``cases``; os demais apps permanecem no leaf.
        self._apps = executor.loader.project_state(self._TARGETS_0014).apps
        with transaction.atomic():
            # Hygiene de isolamento (o flush entre testes já limpa; mantido
            # por fidelidade aos testes originais — a tabela existe no leaf).
            CaseProcedure.objects.all().delete()
            self._immediate_constraints()
            # Down até 0014: reverse da 0015 (reverse do backfill + drop da
            # tabela). Após o cutover, o reverse da 0016 re-adiciona a coluna
            # (precheck com reverse noop). O rollback no teardown desfaz tudo.
            MigrationExecutor(connection).migrate(self._TARGETS_0014)
            yield
            transaction.set_rollback(True)

    @staticmethod
    def _immediate_constraints() -> None:
        """Dispara checagens deferidas antes de DDL (o container cria FKs
        DEFERRABLE INITIALLY DEFERRED — artefato de ambiente)."""
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def _backfill(self) -> None:
        """Aplica a 0015: cria a tabela e roda o backfill sobre os casos 0014."""
        self._immediate_constraints()
        MigrationExecutor(connection).migrate(self._TARGETS_0015)

    def _reverse(self) -> None:
        """Reverte a 0015: reverse do backfill + remoção da tabela."""
        self._immediate_constraints()
        MigrationExecutor(connection).migrate(self._TARGETS_0014)

    def _make_case(
        self,
        user,
        status: str,
        record: str,
        doctor_decision: str = "",
        appointment_status: str = "",
        doctor_reason: str = "",
        events: tuple[str, ...] = (),
    ) -> Any:
        """Cria caso pelo modelo histórico 0014 (a coluna existe nesse estado)."""
        historical_case: Any = self._apps.get_model("cases", "Case")
        historical_case_event: Any = self._apps.get_model("cases", "CaseEvent")
        historical_user: Any = self._apps.get_model("accounts", "User")
        # FKs históricas validam a CLASSE do modelo: resolve o mesmo row no
        # registry 0014 (classes dos modelos históricos combinam entre si).
        owner = historical_user.objects.get(pk=user.pk)
        case = historical_case.objects.create(
            created_by=owner,
            status=status,
            agency_record_number=record,
            doctor_decision=doctor_decision,
            appointment_status=appointment_status,
            doctor_reason=doctor_reason,
        )
        for event_type in events:
            historical_case_event.objects.create(case=case, event_type=event_type, actor=owner, actor_type="system")
        return case

    def test_covers_all_18_statuses_and_conditional_markers(self, user) -> None:
        """Representante de cada linha D3; condicionais com e sem marcador."""
        created: dict[tuple[str, str], Case] = {}
        seq = 0
        for status in _PENDING_STATUSES:
            seq += 1
            created[(str(status), "none")] = self._make_case(user, status, f"P-{seq:03d}")
        for status in _DETECTED_STATUSES:
            seq += 1
            created[(str(status), "none")] = self._make_case(user, status, f"D-{seq:03d}")
        for status in _CONDITIONAL_STATUSES:
            seq += 1
            created[(str(status), "none")] = self._make_case(user, status, f"C-{seq:03d}")
            seq += 1
            created[(str(status), "marker")] = self._make_case(user, status, f"C-{seq:03d}", doctor_decision="accept")
        # LLM1_OK isolado NÃO é marcador downstream inequívoco
        seq += 1
        created[("CLEANED", "llm1_only")] = self._make_case(user, "CLEANED", f"C-{seq:03d}", events=("LLM1_OK",))

        self._backfill()

        for status in _PENDING_STATUSES:
            row = CaseProcedure.objects.get(case_id=created[(str(status), "none")].pk)
            assert row.detection_status == DetectionStatus.PENDING
            assert row.declared_by_nir is True
            assert row.doctor_disposition == DoctorDisposition.PENDING
        for status in _DETECTED_STATUSES:
            row = CaseProcedure.objects.get(case_id=created[(str(status), "none")].pk)
            assert row.detection_status == DetectionStatus.DETECTED
        for status in _CONDITIONAL_STATUSES:
            without = CaseProcedure.objects.get(case_id=created[(str(status), "none")].pk)
            assert without.detection_status == DetectionStatus.PENDING
            with_marker = CaseProcedure.objects.get(case_id=created[(str(status), "marker")].pk)
            assert with_marker.detection_status == DetectionStatus.DETECTED
        llm1_only = CaseProcedure.objects.get(case_id=created[("CLEANED", "llm1_only")].pk)
        assert llm1_only.detection_status == DetectionStatus.PENDING

    def test_appointment_status_and_events_are_downstream_markers(self, user) -> None:
        by_appt = self._make_case(user, "CLEANED", "M-APPT", appointment_status="confirmed")
        by_event = self._make_case(user, "FAILED", "M-EVENT", events=("CASE_READY_FOR_SCHEDULER",))
        self._backfill()
        assert CaseProcedure.objects.get(case_id=by_appt.pk).detection_status == DetectionStatus.DETECTED
        assert CaseProcedure.objects.get(case_id=by_event.pk).detection_status == DetectionStatus.DETECTED

    def test_doctor_disposition_closed_table(self, user) -> None:
        accepted = self._make_case(user, "DOCTOR_ACCEPTED", "DIS-ACC", doctor_decision="accept", doctor_reason="sobra")
        denied = self._make_case(user, "DOCTOR_DENIED", "DIS-DEN", doctor_decision="deny", doctor_reason="motivo exato")
        pending = self._make_case(user, "WAIT_DOCTOR", "DIS-PEN")
        self._backfill()
        assert CaseProcedure.objects.get(case_id=accepted.pk).doctor_disposition == DoctorDisposition.APPROVED
        assert CaseProcedure.objects.get(case_id=accepted.pk).doctor_reason == ""
        assert CaseProcedure.objects.get(case_id=denied.pk).doctor_disposition == DoctorDisposition.DENIED
        assert CaseProcedure.objects.get(case_id=denied.pk).doctor_reason == "motivo exato"
        assert CaseProcedure.objects.get(case_id=pending.pk).doctor_disposition == DoctorDisposition.PENDING
        assert CaseProcedure.objects.get(case_id=pending.pk).doctor_reason == ""

    def test_backfill_preserves_fields_and_events(self, user) -> None:
        historical_case: Any = self._apps.get_model("cases", "Case")
        historical_user: Any = self._apps.get_model("accounts", "User")
        owner = historical_user.objects.get(pk=user.pk)
        case = historical_case.objects.create(
            created_by=owner,
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="recusa",
            agency_record_number="PRES-001",
        )
        events_before = case.events.count()
        self._backfill()
        reloaded = historical_case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.DOCTOR_DENIED
        assert reloaded.doctor_reason == "recusa"
        row = CaseProcedure.objects.get(case_id=case.pk)
        assert row.procedure_type == ProcedureType.EDA
        assert row.declared_by_nir is True
        # Nenhum evento novo: backfill não reprocessa nem audita
        assert case.events.count() == events_before

    def test_forward_and_reverse_are_deterministic(self, user) -> None:
        case = self._make_case(user, "NEW", "REV-001")
        self._backfill()
        assert CaseProcedure.objects.filter(case_id=case.pk).count() == 1
        self._reverse()
        # Reversão determinística: o estado 0014 não conhece a tabela — o
        # reverse do backfill apagou as rows e o CreateModel foi revertido.
        assert "CaseProcedure" not in {m.__name__ for m in self._apps.get_models()}
        # Re-forward determinístico: o backfill recria exatamente 1 row (sem
        # duplicação), provando que o reverse removeu as rows anteriores.
        self._backfill()
        assert CaseProcedure.objects.filter(case_id=case.pk).count() == 1
        assert Case.objects.get(pk=case.pk).status == CaseStatus.NEW


class TestDeclaredProjectionService:
    """R3 — serviço único de declaração: conjunto, evento e atomicidade."""

    def test_combined_creates_exactly_two_declared_rows(self, user, case_factory) -> None:
        case = case_factory(user)
        set_declared_procedures(case=case, procedure_types=["colonoscopy", "eda"], actor=user)
        rows = list(CaseProcedure.objects.filter(case=case).order_by("procedure_type"))
        assert len(rows) == 2
        assert {r.procedure_type for r in rows} == {"eda", "colonoscopy"}
        assert all(r.declared_by_nir for r in rows)

    def test_single_selection_unmarks_other_row(self, user, case_factory) -> None:
        case = case_factory(user)
        set_declared_procedures(case=case, procedure_types=["eda", "colonoscopy"], actor=user)
        set_declared_procedures(case=case, procedure_types=["colonoscopy"], actor=user)
        reloaded = Case.objects.get(pk=case.pk)
        assert CaseProcedure.objects.get(case=reloaded, procedure_type="eda").declared_by_nir is False
        assert CaseProcedure.objects.get(case=reloaded, procedure_type="colonoscopy").declared_by_nir is True

    def test_invalid_or_empty_selection_creates_nothing(self, user, case_factory) -> None:
        case = case_factory(user)
        with pytest.raises(ValueError):
            set_declared_procedures(case=case, procedure_types=[], actor=user)
        with pytest.raises(ValueError):
            set_declared_procedures(case=case, procedure_types=["cpre"], actor=user)
        assert CaseProcedure.objects.filter(case=case).count() == 0

    def test_event_contains_ordered_set_without_clinical_text(self, user, case_factory) -> None:
        case = case_factory(user)
        set_declared_procedures(case=case, procedure_types=["colonoscopy", "eda"], actor=user)
        event = CaseEvent.objects.get(case=case, event_type="CASE_PROCEDURES_DECLARED")
        assert event.payload["procedures"] == ["eda", "colonoscopy"]
        assert "text" not in event.payload
        assert event.actor_id == user.pk

    def test_failure_rolls_back_projection(self, user, case_factory) -> None:
        case = case_factory(user)
        with mock.patch("apps.cases.procedures._sync_declared_rows", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                set_declared_procedures(case=case, procedure_types=["eda"], actor=user)
        assert CaseProcedure.objects.filter(case=case).count() == 0

    def test_get_declared_and_format_helpers(self, user, case_factory) -> None:
        case = case_factory(user)
        # Slice 010 (R3): caso sem rows projetiona vazio (sem inferência).
        assert get_declared_procedure_types(case) == ()
        set_declared_procedures(case=case, procedure_types=["colonoscopy"], actor=user)
        assert get_declared_procedure_types(case) == ("colonoscopy",)
        assert format_procedure_selection(["eda"]) == "EDA"
        assert format_procedure_selection(["colonoscopy"]) == "Colonoscopia"
        assert format_procedure_selection(["colonoscopy", "eda"]) == "EDA + Colonoscopia"

    def test_getters_fail_closed_without_bridge(self, user, case_factory) -> None:
        """Slice 010 (R3) — getters sempre retornam apenas rows normalizadas.

        Rows como fonte única: um caso sem rows devolve ``()`` em todas as
        três dimensões, sem o fallback global ``doctor_decision=accept`` no
        aprovado.
        """
        case = case_factory(user)  # sem rows
        # Slice 010 (R3): os getters são ALWAYS fail-closed — caso sem rows
        # ⇒ () em todas as três dimensões (fonte única: rows).
        assert get_declared_procedure_types(case) == ()
        assert get_detected_procedure_types(case) == ()
        assert get_approved_procedure_types(case) == ()
        assert get_declared_procedure_types(case) == ()
        assert get_detected_procedure_types(case) == ()
        assert get_approved_procedure_types(case) == ()
        # Aprovado tampouco é inferido de ``doctor_decision=accept``, mesmo
        # com doctor_decision=accept (fallback global removido).
        case.doctor_decision = "accept"
        case.save(update_fields=["doctor_decision"])
        assert get_approved_procedure_types(case) == ()
        assert get_approved_procedure_types(case) == ()


class TestProcedureGettersReturnOnlyRows:
    """Slice 010 (R3) — getters retornam apenas rows normalizadas.

    Prova que nenhum getter depende de qualquer campo do ``Case`` além das
    rows: um caso sem rows projeta ``()`` em todas as dimensões, mesmo com
    ``doctor_decision=accept`` preenchido (fallback global removido).
    """

    def test_case_without_rows_is_empty_in_all_dimensions(self, user, case_factory) -> None:
        case = case_factory(user)  # sem rows
        assert get_declared_procedure_types(case) == ()
        assert get_detected_procedure_types(case) == ()
        assert get_approved_procedure_types(case) == ()

    def test_case_without_rows_empty_even_with_doctor_accept(self, user) -> None:
        """Sem rows, ``doctor_decision="accept"`` não recria o aprovado."""
        case = Case.objects.create(
            created_by=user,
            doctor_decision="accept",
        )
        assert get_declared_procedure_types(case) == ()
        assert get_detected_procedure_types(case) == ()
        assert get_approved_procedure_types(case) == ()

    def test_declared_rows_returned_without_bridge(self, user, case_factory) -> None:
        case = case_factory(user)
        set_declared_procedures(case=case, procedure_types=["colonoscopy", "eda"], actor=user)
        case = Case.objects.get(pk=case.pk)
        assert get_declared_procedure_types(case) == ("eda", "colonoscopy")
        # Detecção ainda pendente: detected vazio (não herda a declaração).
        assert get_detected_procedure_types(case) == ()
        assert get_approved_procedure_types(case) == ()

    def test_detected_and_approved_rows_drive_their_own_getters(self, user, case_factory) -> None:
        """Fluxo canônico só com rows: cada dimensão reflete exclusivamente as
        próprias rows, sem qualquer dependência de campo do ``Case``."""
        case = case_factory(user)
        set_declared_procedures(case=case, procedure_types=["eda"], actor=user)
        CaseProcedure.objects.create(
            case=case,
            procedure_type="colonoscopy",
            detection_status=DetectionStatus.DETECTED,
            doctor_disposition=DoctorDisposition.APPROVED,
        )
        case = Case.objects.get(pk=case.pk)
        assert get_declared_procedure_types(case) == ("eda",)
        assert get_detected_procedure_types(case) == ("colonoscopy",)
        assert get_approved_procedure_types(case) == ("colonoscopy",)
