"""Slice 001 — CaseProcedure: projeção normalizada, índices D1, backfill D3.

Cobre:
- R1: enum e modelo mínimos; unique constraint (case, procedure_type); os três
      índices dimensionais D1 existem na Meta.
- R2: backfill fecha a tabela D3 nos 18 estados (com/sem marcador downstream
      nos cinco condicionais), mapeamento fechado de doctor_disposition,
      preservação de campos/eventos e reversão determinística.
- R3: serviço único de declaração (conjunto ordenado, ponte transitória,
      evento enxuto e atomicidade).
"""

from __future__ import annotations

import importlib
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ExamType,
    ProcedureType,
)
from apps.cases.procedures import (
    format_procedure_selection,
    get_declared_procedure_types,
    set_declared_procedures,
)

pytestmark = pytest.mark.django_db

User = get_user_model()

_MIGRATION_MODULE = "apps.cases.migrations.0015_caseprocedure"

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


class TestBackfillD3Table:
    """R2 — backfill fecha a tabela D3 nos 18 estados sem inferir/reprocessar."""

    @pytest.fixture(autouse=True)
    def _historical_apps(self) -> None:
        executor = MigrationExecutor(connection)
        self._apps = executor.loader.project_state(executor.loader.graph.leaf_nodes()).apps

    def _backfill(self) -> None:
        module = importlib.import_module(_MIGRATION_MODULE)
        module.backfill_case_procedures(self._apps, connection.schema_editor())

    def _reverse(self) -> None:
        module = importlib.import_module(_MIGRATION_MODULE)
        module.reverse_backfill_case_procedures(self._apps, connection.schema_editor())

    def _make_case(
        self,
        user,
        status: str,
        record: str,
        doctor_decision: str = "",
        appointment_status: str = "",
        doctor_reason: str = "",
        events: tuple[str, ...] = (),
    ) -> Case:
        case = Case.objects.create(
            created_by=user,
            exam_type=ExamType.EDA,
            status=status,
            agency_record_number=record,
            doctor_decision=doctor_decision,
            appointment_status=appointment_status,
            doctor_reason=doctor_reason,
        )
        for event_type in events:
            CaseEvent.objects.create(case=case, event_type=event_type, actor=user, actor_type="system")
        return case

    def test_covers_all_18_statuses_and_conditional_markers(self, user) -> None:
        """Representante de cada linha D3; condicionais com e sem marcador."""
        CaseProcedure.objects.all().delete()
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
            row = CaseProcedure.objects.get(case=created[(str(status), "none")])
            assert row.detection_status == DetectionStatus.PENDING
            assert row.declared_by_nir is True
            assert row.doctor_disposition == DoctorDisposition.PENDING
        for status in _DETECTED_STATUSES:
            row = CaseProcedure.objects.get(case=created[(str(status), "none")])
            assert row.detection_status == DetectionStatus.DETECTED
        for status in _CONDITIONAL_STATUSES:
            without = CaseProcedure.objects.get(case=created[(str(status), "none")])
            assert without.detection_status == DetectionStatus.PENDING
            with_marker = CaseProcedure.objects.get(case=created[(str(status), "marker")])
            assert with_marker.detection_status == DetectionStatus.DETECTED
        llm1_only = CaseProcedure.objects.get(case=created[("CLEANED", "llm1_only")])
        assert llm1_only.detection_status == DetectionStatus.PENDING

    def test_appointment_status_and_events_are_downstream_markers(self, user) -> None:
        CaseProcedure.objects.all().delete()
        by_appt = self._make_case(user, "CLEANED", "M-APPT", appointment_status="confirmed")
        by_event = self._make_case(user, "FAILED", "M-EVENT", events=("CASE_READY_FOR_SCHEDULER",))
        self._backfill()
        assert CaseProcedure.objects.get(case=by_appt).detection_status == DetectionStatus.DETECTED
        assert CaseProcedure.objects.get(case=by_event).detection_status == DetectionStatus.DETECTED

    def test_doctor_disposition_closed_table(self, user) -> None:
        CaseProcedure.objects.all().delete()
        accepted = self._make_case(user, "DOCTOR_ACCEPTED", "DIS-ACC", doctor_decision="accept", doctor_reason="sobra")
        denied = self._make_case(user, "DOCTOR_DENIED", "DIS-DEN", doctor_decision="deny", doctor_reason="motivo exato")
        pending = self._make_case(user, "WAIT_DOCTOR", "DIS-PEN")
        self._backfill()
        assert CaseProcedure.objects.get(case=accepted).doctor_disposition == DoctorDisposition.APPROVED
        assert CaseProcedure.objects.get(case=accepted).doctor_reason == ""
        assert CaseProcedure.objects.get(case=denied).doctor_disposition == DoctorDisposition.DENIED
        assert CaseProcedure.objects.get(case=denied).doctor_reason == "motivo exato"
        assert CaseProcedure.objects.get(case=pending).doctor_disposition == DoctorDisposition.PENDING
        assert CaseProcedure.objects.get(case=pending).doctor_reason == ""

    def test_backfill_preserves_fields_and_events(self, user) -> None:
        CaseProcedure.objects.all().delete()
        case = Case.objects.create(
            created_by=user,
            exam_type=ExamType.COLONOSCOPY,
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="recusa",
            agency_record_number="PRES-001",
        )
        events_before = case.events.count()
        self._backfill()
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.exam_type == ExamType.COLONOSCOPY
        assert reloaded.status == CaseStatus.DOCTOR_DENIED
        assert reloaded.doctor_reason == "recusa"
        row = CaseProcedure.objects.get(case=case)
        assert row.procedure_type == ExamType.COLONOSCOPY
        assert row.declared_by_nir is True
        # Nenhum evento novo: backfill não reprocessa nem audita
        assert case.events.count() == events_before

    def test_forward_and_reverse_are_deterministic(self, user) -> None:
        CaseProcedure.objects.all().delete()
        case = self._make_case(user, "NEW", "REV-001")
        self._backfill()
        assert CaseProcedure.objects.filter(case=case).count() == 1
        self._reverse()
        assert CaseProcedure.objects.filter(case=case).count() == 0
        assert Case.objects.get(pk=case.pk).status == CaseStatus.NEW


class TestDeclaredProjectionService:
    """R3 — serviço único de declaração: conjunto, ponte, evento e atomicidade."""

    def test_combined_creates_exactly_two_declared_rows_and_bridge(self, user, case_factory) -> None:
        case = case_factory(user)
        set_declared_procedures(case=case, procedure_types=["colonoscopy", "eda"], actor=user)
        rows = list(CaseProcedure.objects.filter(case=case).order_by("procedure_type"))
        assert len(rows) == 2
        assert {r.procedure_type for r in rows} == {"eda", "colonoscopy"}
        assert all(r.declared_by_nir for r in rows)
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.exam_type == EDA_COLONOSCOPY

    def test_single_selection_unmarks_other_row(self, user, case_factory) -> None:
        case = case_factory(user)
        set_declared_procedures(case=case, procedure_types=["eda", "colonoscopy"], actor=user)
        set_declared_procedures(case=case, procedure_types=["colonoscopy"], actor=user)
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.exam_type == ExamType.COLONOSCOPY
        assert CaseProcedure.objects.get(case=reloaded, procedure_type="eda").declared_by_nir is False
        assert CaseProcedure.objects.get(case=reloaded, procedure_type="colonoscopy").declared_by_nir is True

    def test_invalid_or_empty_selection_creates_nothing(self, user, case_factory) -> None:
        case = case_factory(user)
        with pytest.raises(ValueError):
            set_declared_procedures(case=case, procedure_types=[], actor=user)
        with pytest.raises(ValueError):
            set_declared_procedures(case=case, procedure_types=["cpre"], actor=user)
        assert CaseProcedure.objects.filter(case=case).count() == 0
        assert Case.objects.get(pk=case.pk).exam_type == ExamType.EDA

    def test_event_contains_ordered_set_without_clinical_text(self, user, case_factory) -> None:
        case = case_factory(user)
        set_declared_procedures(case=case, procedure_types=["colonoscopy", "eda"], actor=user)
        event = CaseEvent.objects.get(case=case, event_type="CASE_PROCEDURES_DECLARED")
        assert event.payload["procedures"] == ["eda", "colonoscopy"]
        assert "text" not in event.payload
        assert event.actor_id == user.pk

    def test_failure_rolls_back_projection_and_bridge(self, user, case_factory) -> None:
        case = case_factory(user)
        with mock.patch("apps.cases.procedures._sync_declared_rows", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                set_declared_procedures(case=case, procedure_types=["eda"], actor=user)
        assert CaseProcedure.objects.filter(case=case).count() == 0
        assert Case.objects.get(pk=case.pk).exam_type == ExamType.EDA

    def test_get_declared_and_format_helpers(self, user, case_factory) -> None:
        case = case_factory(user)
        # ponte transitória: caso antigo sem projeção reflete o exam_type
        assert get_declared_procedure_types(case) == ("eda",)
        set_declared_procedures(case=case, procedure_types=["colonoscopy"], actor=user)
        assert get_declared_procedure_types(case) == ("colonoscopy",)
        assert format_procedure_selection(["eda"]) == "EDA"
        assert format_procedure_selection(["colonoscopy"]) == "Colonoscopia"
        assert format_procedure_selection(["colonoscopy", "eda"]) == "EDA + Colonoscopia"
