"""Tests for prior case lookup — ``lookup_prior_case_context``.

Slice 009 (R3): ``procedure_type`` é obrigatório (keyword-only); o caminho
legado ``exam_type``/``filter(exam_type=...)`` foi removido. O comportamento
por componente (D10) é coberto em ``test_slice_002_contracts.py``; aqui
focamos no contrato da API e em casos-limite do módulo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apps.cases.models import Case, CaseProcedure, CaseStatus
from apps.pipeline.prior_case import (
    PRIOR_CASE_WINDOW_DAYS,
    PriorCaseContext,
    PriorCaseSummary,
    _normalize_reason,
    lookup_prior_case_context,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _utc_datetime(days_ago: int = 0) -> datetime:
    """Retorna um datetime UTC no passado."""
    return datetime.now(tz=UTC) - timedelta(days=days_ago)


def _make_case(
    user,
    *,
    agency_record_number: str = "AR99999",
    status: str = CaseStatus.NEW,
    doctor_decision: str = "",
    doctor_reason: str = "",
    doctor_decided_at: datetime | None = None,
    appointment_status: str = "",
    appointment_reason: str = "",
    appointment_decided_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Case:
    decided_at_default = created_at or datetime.now(tz=UTC)
    case = Case.objects.create(
        created_by=user,
        agency_record_number=agency_record_number,
        status=status,
        doctor_decision=doctor_decision,
        doctor_reason=doctor_reason,
        doctor_decided_at=doctor_decided_at or decided_at_default,
        appointment_status=appointment_status,
        appointment_reason=appointment_reason or "",
        appointment_decided_at=appointment_decided_at or decided_at_default,
    )
    if created_at is not None:
        Case.objects.filter(case_id=case.case_id).update(created_at=created_at)
    return case


def _add_row(case, procedure_type: str, *, disposition: str = "denied", reason: str = "") -> CaseProcedure:
    return CaseProcedure.objects.create(
        case=case,
        procedure_type=procedure_type,
        declared_by_nir=True,
        doctor_disposition=disposition,
        doctor_reason=reason,
    )


NOW = _utc_datetime()


# ── Tests: contrato da API (Slice 009 / R3) ──────────────────────────────────


class TestPriorCaseApiContract:
    """``procedure_type`` é obrigatório; ``exam_type`` não é mais aceito."""

    def test_procedure_type_is_required_keyword(self) -> None:
        """Sem ``procedure_type`` → TypeError (não há mais caminho legado)."""
        with pytest.raises(TypeError):
            lookup_prior_case_context("case-id", "AR001", now=NOW)  # type: ignore[call-arg]

    def test_exam_type_param_removed(self) -> None:
        """``exam_type`` não é mais um parâmetro aceito."""
        with pytest.raises(TypeError):
            lookup_prior_case_context("case-id", "AR001", now=NOW, exam_type="eda")  # type: ignore[call-arg]

    def test_procedure_type_is_keyword_only(self) -> None:
        """``procedure_type`` não pode ser posicional (evita ambiguidade)."""
        with pytest.raises(TypeError):
            lookup_prior_case_context("case-id", "AR001", "eda", now=NOW)  # type: ignore[misc]


@pytest.mark.django_db
class TestPriorCaseEmptyInputs:
    """ARN vazio/branco → contexto vazio sem consultar rows."""

    def test_empty_agency_record_number(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="u5", password="pw")
        current = _make_case(user, agency_record_number="AR005")

        result = lookup_prior_case_context(current.case_id, "", now=NOW, procedure_type="eda")

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_blank_agency_record_number(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="u6", password="pw")
        current = _make_case(user, agency_record_number="AR006")

        result = lookup_prior_case_context(current.case_id, "   ", now=NOW, procedure_type="eda")

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0


@pytest.mark.django_db
class TestPriorCaseProcedureLookup:
    """Núcleo do lookup por componente (rows); casos-limite do módulo.

    Cobertura completa por componente está em ``test_slice_002_contracts.py``.
    """

    def test_case_without_matching_row_not_found(self, django_user_model) -> None:
        """Caso anterior sem row do procedure_type solicitado → não entra."""
        user = django_user_model.objects.create_user(username="u7", password="pw")
        current = _make_case(user, agency_record_number="AR007")
        prior = _make_case(
            user,
            agency_record_number="AR007",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="Risco cirúrgico elevado",
            doctor_decided_at=_utc_datetime(2),
            created_at=_utc_datetime(2),
        )
        # Row existe, mas de OUTRO procedimento.
        _add_row(prior, "colonoscopy", disposition="denied", reason="Risco cirúrgico elevado")

        result = lookup_prior_case_context(current.case_id, "AR007", now=NOW, procedure_type="eda")

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_denial_outside_7d_window_excluded(self, django_user_model) -> None:
        """Negação fora dos 7 dias → não incluída."""
        user = django_user_model.objects.create_user(username="u8", password="pw")
        current = _make_case(user, agency_record_number="AR008")
        prior = _make_case(
            user,
            agency_record_number="AR008",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_decided_at=_utc_datetime(PRIOR_CASE_WINDOW_DAYS + 1),
            created_at=_utc_datetime(PRIOR_CASE_WINDOW_DAYS + 1),
        )
        _add_row(prior, "eda", disposition="denied", reason="Antigo")

        result = lookup_prior_case_context(current.case_id, "AR008", now=NOW, procedure_type="eda")

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_doctor_denial_within_window_returned(self, django_user_model) -> None:
        """Negação médica do procedimento dentro de 7d → retornada."""
        user = django_user_model.objects.create_user(username="u9", password="pw")
        current = _make_case(user, agency_record_number="AR009")
        prior = _make_case(
            user,
            agency_record_number="AR009",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_decided_at=_utc_datetime(2),
            created_at=_utc_datetime(2),
        )
        prior.doctor = user
        prior.save()
        _add_row(prior, "eda", disposition="denied", reason="Risco cirúrgico elevado")

        result = lookup_prior_case_context(current.case_id, "AR009", now=NOW, procedure_type="eda")

        assert result.prior_case is not None
        assert result.prior_case.prior_case_id == str(prior.case_id)
        assert result.prior_case.decision == "doctor_denied"
        assert result.prior_case.reason == "Risco cirúrgico elevado"
        assert result.prior_case.decided_by_role == "doctor"
        assert result.prior_denial_count_7d == 1

    def test_approved_does_not_increase_denial_count(self, django_user_model) -> None:
        """Aprovação anterior aparece como doctor_approved, mas não conta negativa."""
        user = django_user_model.objects.create_user(username="u10", password="pw")
        current = _make_case(user, agency_record_number="AR010")
        prior = _make_case(
            user,
            agency_record_number="AR010",
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=_utc_datetime(1),
            created_at=_utc_datetime(1),
        )
        _add_row(prior, "eda", disposition="approved")

        result = lookup_prior_case_context(current.case_id, "AR010", now=NOW, procedure_type="eda")

        assert result.prior_case is not None
        assert result.prior_case.decision == "doctor_approved"
        assert result.prior_denial_count_7d == 0

    def test_appointment_denial_within_window_returned(self, django_user_model) -> None:
        """Negação de agendamento do procedimento (row aprovada + agenda negada)."""
        user = django_user_model.objects.create_user(username="u11", password="pw")
        current = _make_case(user, agency_record_number="AR011")
        prior = _make_case(
            user,
            agency_record_number="AR011",
            status=CaseStatus.APPT_DENIED,
            doctor_decision="accept",
            appointment_status="denied",
            appointment_reason="Paciente não compareceu",
            doctor_decided_at=_utc_datetime(3),
            appointment_decided_at=_utc_datetime(1),
            created_at=_utc_datetime(3),
        )
        prior.scheduler = user
        prior.save()
        _add_row(prior, "eda", disposition="approved")

        result = lookup_prior_case_context(current.case_id, "AR011", now=NOW, procedure_type="eda")

        assert result.prior_case is not None
        assert result.prior_case.decision == "appointment_denied"
        assert result.prior_case.reason == "Paciente não compareceu"
        assert result.prior_case.decided_by_role == "scheduler"
        assert result.prior_denial_count_7d == 1

    def test_most_recent_by_decision_timestamp(self, django_user_model) -> None:
        """Ordenação pelo timestamp de decisão (não created_at)."""
        user = django_user_model.objects.create_user(username="u12", password="pw")
        current = _make_case(user, agency_record_number="AR012")
        older = _make_case(
            user,
            agency_record_number="AR012",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="antiga",
            doctor_decided_at=_utc_datetime(5),
            created_at=_utc_datetime(1),
        )
        _add_row(older, "eda", disposition="denied", reason="antiga")
        newer = _make_case(
            user,
            agency_record_number="AR012",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="recente",
            doctor_decided_at=_utc_datetime(1),
            created_at=_utc_datetime(8),
        )
        _add_row(newer, "eda", disposition="denied", reason="recente")

        result = lookup_prior_case_context(current.case_id, "AR012", now=NOW, procedure_type="eda")

        assert result.prior_case is not None
        assert result.prior_case.prior_case_id == str(newer.case_id)
        assert result.prior_case.reason == "recente"
        assert result.prior_denial_count_7d == 2

    def test_denial_outside_window_by_decided_at_excluded(self, django_user_model) -> None:
        """Janela usa decided_at: created_at recente mas decided_at fora → excluído."""
        user = django_user_model.objects.create_user(username="u13", password="pw")
        current = _make_case(user, agency_record_number="AR013")
        prior = _make_case(
            user,
            agency_record_number="AR013",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_decided_at=_utc_datetime(PRIOR_CASE_WINDOW_DAYS + 1),
            created_at=_utc_datetime(1),
        )
        _add_row(prior, "eda", disposition="denied", reason="antigo")

        result = lookup_prior_case_context(current.case_id, "AR013", now=NOW, procedure_type="eda")

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_denied_and_approved_rows_independent(self, django_user_model) -> None:
        """No mesmo caso anterior, EDA negada e Colonoscopia aprovada são independentes."""
        user = django_user_model.objects.create_user(username="u14", password="pw")
        current = _make_case(user, agency_record_number="AR014")
        prior = _make_case(
            user,
            agency_record_number="AR014",
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=_utc_datetime(1),
            created_at=_utc_datetime(1),
        )
        _add_row(prior, "eda", disposition="denied", reason="sem indicação")
        _add_row(prior, "colonoscopy", disposition="approved")

        eda = lookup_prior_case_context(current.case_id, "AR014", now=NOW, procedure_type="eda")
        colon = lookup_prior_case_context(current.case_id, "AR014", now=NOW, procedure_type="colonoscopy")

        assert eda.prior_case is not None
        assert eda.prior_case.decision == "doctor_denied"
        assert eda.prior_case.reason == "sem indicação"
        assert eda.prior_denial_count_7d == 1

        assert colon.prior_case is not None
        assert colon.prior_case.decision == "doctor_approved"
        assert colon.prior_denial_count_7d == 0

    def test_same_case_id_excluded(self, django_user_model) -> None:
        """O próprio caso atual não aparece como anterior."""
        user = django_user_model.objects.create_user(username="u15", password="pw")
        current = _make_case(
            user,
            agency_record_number="AR015",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_decided_at=_utc_datetime(1),
            created_at=_utc_datetime(1),
        )
        _add_row(current, "eda", disposition="denied", reason="teste")

        result = lookup_prior_case_context(current.case_id, "AR015", now=NOW, procedure_type="eda")

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0


# ── Tests: _normalize_reason ─────────────────────────────────────────────────


class TestNormalizeReason:
    """Testes diretos para o helper _normalize_reason."""

    def test_none_returns_nao_informado(self) -> None:
        assert _normalize_reason(None) == "não informado"

    def test_empty_string_returns_nao_informado(self) -> None:
        assert _normalize_reason("") == "não informado"

    def test_blank_string_returns_nao_informado(self) -> None:
        assert _normalize_reason("   ") == "não informado"

    def test_valid_reason_returned_as_is(self) -> None:
        assert _normalize_reason("Risco cirúrgico") == "Risco cirúrgico"

    def test_reason_stripped(self) -> None:
        """Espaços extras nas bordas são removidos."""
        assert _normalize_reason("  Motivo médico  ") == "Motivo médico"


# ── Tests: PriorCaseContext / PriorCaseSummary dataclasses ───────────────────


class TestPriorCaseContextDefaults:
    """Valores default do PriorCaseContext."""

    def test_default_prior_case_is_none(self) -> None:
        ctx = PriorCaseContext()
        assert ctx.prior_case is None

    def test_default_count_is_zero(self) -> None:
        ctx = PriorCaseContext()
        assert ctx.prior_denial_count_7d == 0

    def test_with_prior_case(self) -> None:
        summary = PriorCaseSummary(
            prior_case_id="abc-123",
            decided_at="2025-01-01T00:00:00+00:00",
            decision="doctor_denied",
            reason="Risco",
            decided_by="Dr. Teste — CRM 12345",
            decided_by_role="doctor",
        )
        ctx = PriorCaseContext(prior_case=summary, prior_denial_count_7d=1)
        assert ctx.prior_case == summary
        assert ctx.prior_case.decided_by == "Dr. Teste — CRM 12345"
        assert ctx.prior_case.decided_by_role == "doctor"
        assert ctx.prior_denial_count_7d == 1
