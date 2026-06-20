"""Tests for prior case lookup — ``lookup_prior_case_context``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apps.cases.models import Case, CaseStatus
from apps.pipeline.prior_case import (
    PRIOR_CASE_WINDOW_DAYS,
    PriorCaseContext,
    PriorCaseSummary,
    _normalize_reason,
    lookup_prior_case_context,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_case(
    user,
    *,
    agency_record_number: str = "AR99999",
    doctor_decision: str = "",
    doctor_reason: str = "",
    doctor_decided_at: datetime | None = None,
    appointment_status: str = "",
    appointment_reason: str = "",
    appointment_decided_at: datetime | None = None,
    created_at: datetime | None = None,
    status: str | None = None,
) -> Case:
    """Cria um Case para testes de lookup.

    Se ``status`` for fornecido explicitamente, ele é usado diretamente.
    Caso contrário, o status é inferido dos campos de decisão.
    """
    if status is None:
        if doctor_decision == "deny":
            status = CaseStatus.DOCTOR_DENIED
        elif appointment_status == "denied":
            status = CaseStatus.APPT_DENIED
        elif doctor_decision == "accept":
            status = CaseStatus.DOCTOR_ACCEPTED
        elif appointment_status == "confirmed":
            status = CaseStatus.APPT_CONFIRMED
        else:
            status = CaseStatus.NEW

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
    # created_at tem auto_now_add=True, então precisamos atualizar via update()
    # (refresh_from_db() conflita com FSMFieldDescriptor.protected)
    if created_at is not None:
        Case.objects.filter(case_id=case.case_id).update(created_at=created_at)
    return case


def _utc_datetime(days_ago: int = 0) -> datetime:
    """Retorna um datetime UTC no passado."""
    return datetime.now(tz=UTC) - timedelta(days=days_ago)


NOW = _utc_datetime()


# ── Tests: lookup_prior_case_context ─────────────────────────────────────────


@pytest.mark.django_db
class TestPriorCaseNoResults:
    """Cenários que retornam PriorCaseContext vazio."""

    def test_no_prior_cases(self, django_user_model) -> None:
        """Sem casos anteriores → prior_case=None, count=None."""
        user = django_user_model.objects.create_user(username="u1", password="pw")
        current = _make_case(user, agency_record_number="AR001")

        result = lookup_prior_case_context(current.case_id, "AR001", now=NOW)

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_different_agency_record_number_excluded(self, django_user_model) -> None:
        """ARN diferente → não é considerado mesmo paciente."""
        user = django_user_model.objects.create_user(username="u2", password="pw")
        current = _make_case(user, agency_record_number="AR001")
        _make_case(
            user,
            agency_record_number="AR002",
            doctor_decision="deny",
            doctor_reason="Exames insuficientes",
            created_at=_utc_datetime(1),
        )

        result = lookup_prior_case_context(current.case_id, "AR001", now=NOW)

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_same_case_id_excluded(self, django_user_model) -> None:
        """O próprio caso não deve aparecer como prior case."""
        user = django_user_model.objects.create_user(username="u3", password="pw")
        current = _make_case(
            user,
            agency_record_number="AR003",
            doctor_decision="deny",
            doctor_reason="Teste",
            created_at=_utc_datetime(1),
        )

        result = lookup_prior_case_context(current.case_id, "AR003", now=NOW)

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_denial_outside_7d_window(self, django_user_model) -> None:
        """Negação fora dos 7 dias → não incluída."""
        user = django_user_model.objects.create_user(username="u4", password="pw")
        current = _make_case(user, agency_record_number="AR004")
        _make_case(
            user,
            agency_record_number="AR004",
            doctor_decision="deny",
            doctor_reason="Antigo",
            created_at=_utc_datetime(PRIOR_CASE_WINDOW_DAYS + 1),
        )

        result = lookup_prior_case_context(current.case_id, "AR004", now=NOW)

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_empty_agency_record_number(self, django_user_model) -> None:
        """ARN vazio → lookup retorna vazio sem query."""
        user = django_user_model.objects.create_user(username="u5", password="pw")
        current = _make_case(user, agency_record_number="AR005")

        result = lookup_prior_case_context(current.case_id, "", now=NOW)

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0

    def test_blank_agency_record_number(self, django_user_model) -> None:
        """ARN com apenas espaços → lookup retorna vazio."""
        user = django_user_model.objects.create_user(username="u6", password="pw")
        current = _make_case(user, agency_record_number="AR006")

        result = lookup_prior_case_context(current.case_id, "   ", now=NOW)

        assert result.prior_case is None
        assert result.prior_denial_count_7d == 0


@pytest.mark.django_db
class TestPriorCaseDoctorDenied:
    """Cenários com negação do médico (DOCTOR_DENIED)."""

    def test_one_doctor_denial_within_7d(self, django_user_model) -> None:
        """Uma negação do médico dentro de 7d → retornada como prior_case."""
        user = django_user_model.objects.create_user(username="u7", password="pw")
        current = _make_case(user, agency_record_number="AR007")
        prior = _make_case(
            user,
            agency_record_number="AR007",
            doctor_decision="deny",
            doctor_reason="Risco cirúrgico elevado",
            created_at=_utc_datetime(2),
        )
        # Assign doctor to the prior case for decided_by assertion
        prior.doctor = user
        prior.save()

        result = lookup_prior_case_context(current.case_id, "AR007", now=NOW)

        assert result.prior_case is not None
        assert result.prior_case.prior_case_id == str(prior.case_id)
        assert result.prior_case.decision == "doctor_denied"
        assert result.prior_case.reason == "Risco cirúrgico elevado"
        assert result.prior_case.decided_by_role == "doctor"
        assert user.display_name in result.prior_case.decided_by
        assert result.prior_denial_count_7d == 1

    def test_multiple_doctor_denials_most_recent(self, django_user_model) -> None:
        """Múltiplas negações → a mais recente é retornada, count correto."""
        user = django_user_model.objects.create_user(username="u8", password="pw")
        current = _make_case(user, agency_record_number="AR008")
        _make_case(
            user,
            agency_record_number="AR008",
            doctor_decision="deny",
            doctor_reason="Primeira",
            created_at=_utc_datetime(5),
        )
        prior = _make_case(
            user,
            agency_record_number="AR008",
            doctor_decision="deny",
            doctor_reason="Segunda",
            created_at=_utc_datetime(1),
        )

        result = lookup_prior_case_context(current.case_id, "AR008", now=NOW)

        assert result.prior_case is not None
        assert result.prior_case.prior_case_id == str(prior.case_id)
        assert result.prior_case.reason == "Segunda"
        assert result.prior_denial_count_7d == 2

    def test_doctor_denial_empty_reason_normalized(self, django_user_model) -> None:
        """Reason vazio/None → normalizado para 'não informado'."""
        user = django_user_model.objects.create_user(username="u9", password="pw")
        current = _make_case(user, agency_record_number="AR009")
        _make_case(
            user,
            agency_record_number="AR009",
            doctor_decision="deny",
            doctor_reason="",
            created_at=_utc_datetime(1),
        )

        result = lookup_prior_case_context(current.case_id, "AR009", now=NOW)

        assert result.prior_case is not None
        assert result.prior_case.reason == "não informado"


@pytest.mark.django_db
class TestPriorCaseAppointmentDenied:
    """Cenários com negação de agendamento (APPT_DENIED)."""

    def test_one_appointment_denial_within_7d(self, django_user_model) -> None:
        """Uma negação de agendamento dentro de 7d → retornada como prior_case."""
        user = django_user_model.objects.create_user(username="u10", password="pw")
        current = _make_case(user, agency_record_number="AR010")
        prior = _make_case(
            user,
            agency_record_number="AR010",
            appointment_status="denied",
            appointment_reason="Paciente não compareceu",
            created_at=_utc_datetime(3),
        )
        # Assign scheduler to the prior case for decided_by assertion
        prior.scheduler = user
        prior.save()

        result = lookup_prior_case_context(current.case_id, "AR010", now=NOW)

        assert result.prior_case is not None
        assert result.prior_case.prior_case_id == str(prior.case_id)
        assert result.prior_case.decision == "appointment_denied"
        assert result.prior_case.reason == "Paciente não compareceu"
        assert result.prior_case.decided_by_role == "scheduler"
        assert user.display_name in result.prior_case.decided_by
        assert result.prior_denial_count_7d == 1

    def test_appointment_denial_reason_empty_normalized(self, django_user_model) -> None:
        """Reason vazio em appt denied → normalizado para 'não informado'."""
        user = django_user_model.objects.create_user(username="u11", password="pw")
        current = _make_case(user, agency_record_number="AR011")
        _make_case(
            user,
            agency_record_number="AR011",
            appointment_status="denied",
            appointment_reason="",
            created_at=_utc_datetime(1),
        )

        result = lookup_prior_case_context(current.case_id, "AR011", now=NOW)

        assert result.prior_case is not None
        assert result.prior_case.reason == "não informado"


@pytest.mark.django_db
class TestPriorCaseMixedDenials:
    """Mistura de negações (doctor + appointment)."""

    def test_mix_doctor_deny_and_appt_denied(self, django_user_model) -> None:
        """Ambos os tipos de negação são contados corretamente."""
        user = django_user_model.objects.create_user(username="u12", password="pw")
        current = _make_case(user, agency_record_number="AR012")
        _make_case(
            user,
            agency_record_number="AR012",
            doctor_decision="deny",
            doctor_reason="Risco alto",
            created_at=_utc_datetime(4),
        )
        prior = _make_case(
            user,
            agency_record_number="AR012",
            appointment_status="denied",
            appointment_reason="Faltou",
            created_at=_utc_datetime(1),
        )

        result = lookup_prior_case_context(current.case_id, "AR012", now=NOW)

        assert result.prior_case is not None
        assert result.prior_case.prior_case_id == str(prior.case_id)
        assert result.prior_case.decision == "appointment_denied"
        assert result.prior_denial_count_7d == 2

    def test_non_denial_statuses_not_counted(self, django_user_model) -> None:
        """Casos aceitos não entram na contagem de negações."""
        user = django_user_model.objects.create_user(username="u13", password="pw")
        current = _make_case(user, agency_record_number="AR013")
        _make_case(
            user,
            agency_record_number="AR013",
            doctor_decision="accept",
            created_at=_utc_datetime(1),
        )
        _make_case(
            user,
            agency_record_number="AR013",
            appointment_status="confirmed",
            created_at=_utc_datetime(2),
        )

        result = lookup_prior_case_context(current.case_id, "AR013", now=NOW)

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


# ── Tests: PriorCaseContext dataclass ────────────────────────────────────────


@pytest.mark.django_db
class TestPriorCaseDecisionFields:
    """Testes para lookup usar campos de decisão em vez de status transitório.

    Verifica R2-R7 do slice: negativas encontradas mesmo com status CLEANED,
    janela usa decided_at, ordenação por decided_at.
    """

    def test_doctor_denial_cleaned_status_still_found(self, django_user_model) -> None:
        """Caso CLEANED com doctor_decision=deny é encontrado.

        R2: status não importa, apenas doctor_decision e doctor_decided_at.
        """
        user = django_user_model.objects.create_user(username="u14", password="pw")
        current = _make_case(user, agency_record_number="AR100")
        _make_case(
            user,
            agency_record_number="AR100",
            doctor_decision="deny",
            doctor_reason="Risco cirúrgico",
            doctor_decided_at=_utc_datetime(2),
            status=CaseStatus.CLEANED,
        )

        result = lookup_prior_case_context(current.case_id, "AR100", now=NOW)

        assert result.prior_case is not None, (
            "Expected prior_case for CLEANED case with doctor_decision=deny, "
            "got None because implementation still filters by status"
        )
        assert result.prior_case.decision == "doctor_denied"
        assert result.prior_denial_count_7d == 1

    def test_appointment_denial_cleaned_status_still_found(self, django_user_model) -> None:
        """Caso CLEANED com appointment_status=denied é encontrado.

        R3: status não importa, apenas appointment_status e appointment_decided_at.
        """
        user = django_user_model.objects.create_user(username="u15", password="pw")
        current = _make_case(user, agency_record_number="AR101")
        _make_case(
            user,
            agency_record_number="AR101",
            appointment_status="denied",
            appointment_reason="Paciente faltou",
            appointment_decided_at=_utc_datetime(1),
            status=CaseStatus.CLEANED,
        )

        result = lookup_prior_case_context(current.case_id, "AR101", now=NOW)

        assert result.prior_case is not None, (
            "Expected prior_case for CLEANED case with appointment_status=denied, "
            "got None because implementation still filters by status"
        )
        assert result.prior_case.decision == "appointment_denied"
        assert result.prior_denial_count_7d == 1

    def test_doctor_denial_uses_decided_at_not_created_at_for_window(self, django_user_model) -> None:
        """Janela usa doctor_decided_at, não created_at.

        R4: caso com created_at recente mas doctor_decided_at fora da janela
        não deve contar.
        """
        user = django_user_model.objects.create_user(username="u16", password="pw")
        current = _make_case(user, agency_record_number="AR102")
        _make_case(
            user,
            agency_record_number="AR102",
            doctor_decision="deny",
            doctor_reason="Antigo",
            created_at=_utc_datetime(1),  # recente
            doctor_decided_at=_utc_datetime(PRIOR_CASE_WINDOW_DAYS + 1),  # fora da janela
        )

        result = lookup_prior_case_context(current.case_id, "AR102", now=NOW)

        assert result.prior_case is None, (
            "Expected None because doctor_decided_at is outside window, "
            "got a prior_case because implementation uses created_at"
        )
        assert result.prior_denial_count_7d == 0

    def test_doctor_denial_old_created_at_but_recent_decision_is_found(self, django_user_model) -> None:
        """Caso com created_at antigo mas doctor_decided_at recente é encontrado.

        R4: janela usa decided_at.
        """
        user = django_user_model.objects.create_user(username="u17", password="pw")
        current = _make_case(user, agency_record_number="AR103")
        _make_case(
            user,
            agency_record_number="AR103",
            doctor_decision="deny",
            doctor_reason="Decisão recente",
            created_at=_utc_datetime(30),  # antigo
            doctor_decided_at=_utc_datetime(2),  # dentro da janela
        )

        result = lookup_prior_case_context(current.case_id, "AR103", now=NOW)

        assert result.prior_case is not None, (
            "Expected prior_case because doctor_decided_at is within window, "
            "got None because implementation uses created_at for window"
        )
        assert result.prior_case.decision == "doctor_denied"
        assert result.prior_denial_count_7d == 1

    def test_appointment_denial_uses_decided_at_not_created_at_for_window(self, django_user_model) -> None:
        """Janela usa appointment_decided_at, não created_at.

        R4: caso com created_at recente mas appointment_decided_at fora da janela
        não deve contar.
        """
        user = django_user_model.objects.create_user(username="u18", password="pw")
        current = _make_case(user, agency_record_number="AR104")
        _make_case(
            user,
            agency_record_number="AR104",
            appointment_status="denied",
            appointment_reason="Falta antiga",
            created_at=_utc_datetime(1),  # recente
            appointment_decided_at=_utc_datetime(PRIOR_CASE_WINDOW_DAYS + 1),  # fora
        )

        result = lookup_prior_case_context(current.case_id, "AR104", now=NOW)

        assert result.prior_case is None, (
            "Expected None because appointment_decided_at is outside window, "
            "got a prior_case because implementation uses created_at"
        )
        assert result.prior_denial_count_7d == 0

    def test_most_recent_prior_case_uses_decision_timestamp_not_created_at(self, django_user_model) -> None:
        """Prior case retornado é o de maior decided_at, não created_at.

        R5: dois casos, um com created_at recente mas decisão antiga,
        outro com created_at antigo mas decisão recente.
        """
        user = django_user_model.objects.create_user(username="u19", password="pw")
        current = _make_case(user, agency_record_number="AR105")
        # Caso A: created_at recente (1d) mas decisão antiga (6d)
        _make_case(
            user,
            agency_record_number="AR105",
            doctor_decision="deny",
            doctor_reason="Decisão antiga",
            created_at=_utc_datetime(1),
            doctor_decided_at=_utc_datetime(6),
        )
        # Caso B: created_at antigo (8d) mas decisão recente (1d)
        case_b = _make_case(
            user,
            agency_record_number="AR105",
            appointment_status="denied",
            appointment_reason="Decisão recente",
            created_at=_utc_datetime(8),
            appointment_decided_at=_utc_datetime(1),
        )

        result = lookup_prior_case_context(current.case_id, "AR105", now=NOW)

        assert result.prior_case is not None
        assert result.prior_case.prior_case_id == str(case_b.case_id), (
            "Expected most recent by decision timestamp (case B, 1d ago), "
            "got case A because implementation orders by created_at"
        )
        assert result.prior_case.decision == "appointment_denied"
        assert result.prior_denial_count_7d == 2


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
