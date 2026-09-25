"""Slice 006 — Histórico por código exato de procedimento (R5).

Prova que o contexto anterior é consultado por igualdade do código canônico
(design D11) e que reutilizar família/profile NÃO contamina histórico,
contadores ou razões entre:

- EDA e suas variações (``eda_gastrostomy``/``eda_capsule``/``eda_dilation``);
- Colonoscopia e a família Retossigmoidoscopia;
- ``eda_dilation`` e ``rectosigmoidoscopy_dilation`` (mesmo perfil, código
  diferente).

Não há fallback por família, por prefixo (``eda_*``) nem equivalência por
label; o apresentador do relatório consome ``prior_sections`` por row.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from apps.cases.models import Case, CaseProcedure, CaseStatus, ProcedureType
from apps.doctor.reporting import prepare_doctor_case_report
from apps.pipeline.prior_case import lookup_prior_case_context

NOW = datetime.now(tz=UTC)


def _ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


def _v4_structured(detected: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "4.0",
        "patient": {"name": "Paciente Histórico", "age": 52, "sex": "F"},
        "common_preop": {
            "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0},
            "ecg": {"report_present": "yes", "abnormal_flag": "no"},
        },
        "requested_procedures": [{"procedure_type": t, "evidence_spans": [{"excerpt": "x"}]} for t in detected],
    }


@pytest.mark.django_db
class TestExactProcedureHistory:
    """Histórico exato por código — sem equivalência de família/prefixo."""

    def _case(
        self,
        user,
        *,
        agency_record_number: str = "ARN-HIST-001",
        status: str = CaseStatus.NEW,
        doctor_decided_at: datetime | None = None,
        appointment_status: str = "",
        appointment_reason: str = "",
        appointment_decided_at: datetime | None = None,
        structured_data: dict[str, Any] | None = None,
    ) -> Case:
        case = Case.objects.create(
            created_by=user,
            agency_record_number=agency_record_number,
            status=status,
            doctor_decided_at=doctor_decided_at,
            appointment_status=appointment_status,
            appointment_reason=appointment_reason,
            appointment_decided_at=appointment_decided_at,
            structured_data=structured_data or {},
        )
        return case

    def _row(
        self,
        case: Case,
        procedure_type: str,
        *,
        disposition: str = "denied",
        reason: str = "",
    ) -> CaseProcedure:
        return CaseProcedure.objects.create(
            case=case,
            procedure_type=procedure_type,
            declared_by_nir=True,
            doctor_disposition=disposition,
            doctor_reason=reason,
        )

    # ── EDA × variações ──────────────────────────────────────────────────

    def test_eda_denial_does_not_enter_eda_gastrostomy_history(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="hist1", password="pw")
        current = self._case(user, agency_record_number="ARN-H1")
        prior = self._case(
            user,
            agency_record_number="ARN-H1",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decided_at=_ago(2),
        )
        self._row(prior, ProcedureType.EDA, disposition="denied", reason="EDA sem critério")

        package = lookup_prior_case_context(current.case_id, "ARN-H1", now=NOW, procedure_type="eda_gastrostomy")
        same_base = lookup_prior_case_context(current.case_id, "ARN-H1", now=NOW, procedure_type=ProcedureType.EDA)

        assert package.prior_case is None
        assert package.prior_denial_count_7d == 0
        assert same_base.prior_case is not None
        assert same_base.prior_case.decision == "doctor_denied"
        assert same_base.prior_denial_count_7d == 1

    def test_eda_dilation_does_not_count_for_rectosigmoidoscopy_dilation(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="hist2", password="pw")
        current = self._case(user, agency_record_number="ARN-H2")
        prior = self._case(
            user,
            agency_record_number="ARN-H2",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decided_at=_ago(2),
        )
        self._row(prior, ProcedureType.EDA_DILATION, disposition="denied", reason="dilatação esofágica negada")

        recto = lookup_prior_case_context(
            current.case_id, "ARN-H2", now=NOW, procedure_type=ProcedureType.RECTOSIGMOIDOSCOPY_DILATION
        )
        eda = lookup_prior_case_context(current.case_id, "ARN-H2", now=NOW, procedure_type=ProcedureType.EDA_DILATION)

        assert recto.prior_case is None
        assert recto.prior_denial_count_7d == 0
        assert eda.prior_case is not None
        assert eda.prior_denial_count_7d == 1

    def test_shared_profile_never_contaminates_other_counters(self, django_user_model) -> None:
        """EDA e EDA + Cápsula compartilham perfil, mas não contadores."""
        user = django_user_model.objects.create_user(username="hist3", password="pw")
        current = self._case(user, agency_record_number="ARN-H3")
        eda_prior = self._case(
            user,
            agency_record_number="ARN-H3",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decided_at=_ago(2),
        )
        capsule_prior = self._case(
            user,
            agency_record_number="ARN-H3",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decided_at=_ago(1),
        )
        self._row(eda_prior, ProcedureType.EDA, disposition="denied", reason="eda")
        self._row(capsule_prior, ProcedureType.EDA_CAPSULE, disposition="denied", reason="cápsula")

        eda = lookup_prior_case_context(current.case_id, "ARN-H3", now=NOW, procedure_type=ProcedureType.EDA)
        capsule = lookup_prior_case_context(
            current.case_id, "ARN-H3", now=NOW, procedure_type=ProcedureType.EDA_CAPSULE
        )

        assert eda.prior_denial_count_7d == 1
        assert eda.prior_case is not None
        assert eda.prior_case.reason == "eda"
        assert capsule.prior_denial_count_7d == 1
        assert capsule.prior_case is not None
        assert capsule.prior_case.reason == "cápsula"

    def test_rectosigmoidoscopy_family_is_isolated_per_code(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="hist4", password="pw")
        current = self._case(user, agency_record_number="ARN-H4")
        prior = self._case(
            user,
            agency_record_number="ARN-H4",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decided_at=_ago(2),
        )
        self._row(prior, ProcedureType.RECTOSIGMOIDOSCOPY_ARGON, disposition="denied", reason="argônio")

        base = lookup_prior_case_context(
            current.case_id, "ARN-H4", now=NOW, procedure_type=ProcedureType.RECTOSIGMOIDOSCOPY
        )
        argon = lookup_prior_case_context(
            current.case_id, "ARN-H4", now=NOW, procedure_type=ProcedureType.RECTOSIGMOIDOSCOPY_ARGON
        )

        assert base.prior_case is None
        assert base.prior_denial_count_7d == 0
        assert argon.prior_case is not None
        assert argon.prior_denial_count_7d == 1

    def test_no_prefix_or_family_fallback_for_dilation_variations(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="hist5", password="pw")
        current = self._case(user, agency_record_number="ARN-H5")
        colonic = self._case(
            user,
            agency_record_number="ARN-H5",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decided_at=_ago(1),
        )
        self._row(colonic, ProcedureType.RECTOSIGMOIDOSCOPY, disposition="denied", reason="retossigmoide")

        dilation = lookup_prior_case_context(
            current.case_id, "ARN-H5", now=NOW, procedure_type=ProcedureType.RECTOSIGMOIDOSCOPY_DILATION
        )

        assert dilation.prior_case is None
        assert dilation.prior_denial_count_7d == 0

    # ── Relatório: ``prior_sections`` por row exata ──────────────────────

    def test_report_sections_use_exact_code_not_family(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="hist6", password="pw")
        current = self._case(
            user,
            agency_record_number="ARN-H6",
            structured_data=_v4_structured([ProcedureType.EDA_GASTROSTOMY]),
        )
        self._row(current, ProcedureType.EDA_GASTROSTOMY)
        prior = self._case(
            user,
            agency_record_number="ARN-H6",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decided_at=_ago(2),
        )
        self._row(prior, ProcedureType.EDA, disposition="denied", reason="EDA antiga")

        prepared = prepare_doctor_case_report(current)

        assert prepared.prior_sections == []
        report = prepared.presenter.build_report()
        assert report["prior_sections"] == []

    def test_report_sections_return_exact_package_history(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="hist7", password="pw")
        current = self._case(
            user,
            agency_record_number="ARN-H7",
            structured_data=_v4_structured([ProcedureType.EDA_GASTROSTOMY]),
        )
        self._row(current, ProcedureType.EDA_GASTROSTOMY)
        prior = self._case(
            user,
            agency_record_number="ARN-H7",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decided_at=_ago(2),
        )
        self._row(prior, ProcedureType.EDA_GASTROSTOMY, disposition="denied", reason="GTT negada antes")

        prepared = prepare_doctor_case_report(current)

        assert [section["procedure_type"] for section in prepared.prior_sections] == [ProcedureType.EDA_GASTROSTOMY]
        assert prepared.prior_sections[0]["reason"] == "GTT negada antes"
        assert prepared.prior_sections[0]["decision"] == "doctor_denied"

    def test_combined_keeps_independent_row_history(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="hist8", password="pw")
        current = self._case(
            user,
            agency_record_number="ARN-H8",
            structured_data=_v4_structured([ProcedureType.EDA, ProcedureType.COLONOSCOPY]),
        )
        self._row(current, ProcedureType.EDA)
        self._row(current, ProcedureType.COLONOSCOPY)
        prior = self._case(
            user,
            agency_record_number="ARN-H8",
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decided_at=_ago(2),
        )
        self._row(prior, ProcedureType.EDA, disposition="denied", reason="EDA sem critério")
        self._row(prior, ProcedureType.COLONOSCOPY, disposition="approved")

        prepared = prepare_doctor_case_report(current)
        by_type = {section["procedure_type"]: section for section in prepared.prior_sections}

        assert by_type[ProcedureType.EDA]["decision"] == "doctor_denied"
        assert by_type[ProcedureType.EDA]["reason"] == "EDA sem critério"
        assert by_type[ProcedureType.COLONOSCOPY]["decision"] == "doctor_approved"
        assert by_type[ProcedureType.EDA]["prior_denial_count_7d"] == 1
        assert by_type[ProcedureType.COLONOSCOPY]["prior_denial_count_7d"] == 0

    def test_appointment_denial_applies_only_to_approved_row(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="hist9", password="pw")
        current = self._case(
            user,
            agency_record_number="ARN-H9",
            structured_data=_v4_structured([ProcedureType.EDA, ProcedureType.COLONOSCOPY]),
        )
        self._row(current, ProcedureType.EDA)
        self._row(current, ProcedureType.COLONOSCOPY)
        prior = self._case(
            user,
            agency_record_number="ARN-H9",
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decided_at=_ago(2),
            appointment_status="denied",
            appointment_reason="Sem sala disponível",
            appointment_decided_at=_ago(1),
        )
        self._row(prior, ProcedureType.EDA, disposition="denied", reason="EDA sem critério")
        self._row(prior, ProcedureType.COLONOSCOPY, disposition="approved")

        prepared = prepare_doctor_case_report(current)
        by_type = {section["procedure_type"]: section for section in prepared.prior_sections}

        assert by_type[ProcedureType.EDA]["decision"] == "doctor_denied"
        assert by_type[ProcedureType.COLONOSCOPY]["decision"] == "appointment_denied"
        assert by_type[ProcedureType.COLONOSCOPY]["reason"] == "Sem sala disponível"
