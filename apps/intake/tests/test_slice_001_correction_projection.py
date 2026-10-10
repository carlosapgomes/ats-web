"""Slice 001 — correção legada single→single reroteada pela projeção (R3).

Cobre:
- R3: confirm_case_procedure_review (S2) atualiza atomicamente CaseProcedure.declared_by_nir
      e a projeção declarada sob a transação/lock já existentes;
- EDA→Colonoscopia e Colonoscopia→EDA mantêm ponte/projeção coerentes;
- falha na projeção faz rollback TOTAL (ponte, derivados, eventos e FSM).
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    ProcedureType,
)
from apps.cases.procedures import get_declared_procedure_types
from apps.cases.services import claim_case_lock
from apps.intake.services import confirm_case_procedure_review

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("colonoscopy_intake_enabled")]

User = get_user_model()


# ── Helpers (mesmo protocolo dos testes de correção existentes) ──────────


def _nir_user(django_user_model, username: str = "nir-proj@test.com"):
    """Cria usuário com o papel NIR atribuído (sem sessão HTTP)."""
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _eligible_case(*, user, exam_type: str = "eda") -> Case:
    """Cria um caso em WAIT_R1_CLEANUP_THUMBS com manual review elegível."""
    return Case.objects.create(
        created_by=user,
        status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        extracted_text="RELATÓRIO DE OCORRÊNCIAS\nGoverno do Estado da Bahia\nCódigo: 123",
        agency_record_number="REC-PROJ-001",
        regulation_days_on_screen=3,
        structured_data={"patient": {"name": "Paciente de Teste"}},
        summary_text="Resumo antigo do perfil anterior.",
        suggested_action={
            "decision": "manual_review_required",
            "suggestion": "manual_review_required",
            "reason_code": "exam_type_mismatch",
            "reason_text": "Tipo declarado difere da solicitacao atual.",
            "exam_type": exam_type,
            "declared_exam_type": exam_type,
            "detected_exam_type": "colonoscopy" if exam_type == "eda" else "eda",
        },
        priority_signals=[{"code": "foreign_body", "label": "Corpo estranho"}],
    )


def _claim_receipt_lease(case: Case, user) -> uuid.UUID:
    result = claim_case_lock(
        case_id=case.case_id,
        user=user,
        expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        context="nir_receipt",
        role="nir",
    )
    assert result.acquired
    assert result.token is not None
    return result.token


def _review_event(case: Case) -> CaseEvent:
    """Revisao manual vista pelo NIR (origem da confirmacao, S2/D3)."""
    return CaseEvent.objects.create(
        case=case,
        event_type="EDA_SCOPE_GATED_MANUAL_REVIEW",
        actor=None,
        actor_type="system",
        payload={"reason_code": "exam_type_mismatch", "reason_text": "Tipo declarado difere."},
    )


def _confirm(*, case, user, new_exam_type, token=None) -> Case:
    """Confirmacao S2 com consentimento: mesma ou outra selecao habilitada."""
    from apps.cases.procedure_review import source_fingerprint_for_case

    review = _review_event(case)
    return confirm_case_procedure_review(
        case_id=case.case_id,
        exam_type=new_exam_type,
        user=user,
        active_role="nir",
        lock_token=token if token is not None else _claim_receipt_lease(case, user),
        review_acknowledged="on",
        review_justification="Revisei o relatorio e confirmo a selecao.",
        review_event_id=review.pk,
        source_fingerprint=source_fingerprint_for_case(case),
    )


class TestCorrectionReroutedThroughProjection:
    """R3 — correção single→single atualiza a projeção declarada atomicamente."""

    def test_eda_to_colonoscopy_updates_projection(self, django_user_model) -> None:
        user = _nir_user(django_user_model)
        case = _eligible_case(user=user, exam_type="eda")
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        _confirm(case=case, user=user, new_exam_type=ProcedureType.COLONOSCOPY)

        reloaded = Case.objects.get(pk=case.pk)
        assert get_declared_procedure_types(reloaded) == (ProcedureType.COLONOSCOPY,)
        colon = CaseProcedure.objects.get(case=reloaded, procedure_type=ProcedureType.COLONOSCOPY)
        assert colon.declared_by_nir is True
        eda_row = CaseProcedure.objects.get(case=reloaded, procedure_type=ProcedureType.EDA)
        assert eda_row.declared_by_nir is False

    def test_colonoscopy_to_eda_updates_projection(self, django_user_model) -> None:
        user = _nir_user(django_user_model, "nir-proj-col@test.com")
        case = _eligible_case(user=user, exam_type="colonoscopy")
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.COLONOSCOPY, declared_by_nir=True)
        _confirm(case=case, user=user, new_exam_type=ProcedureType.EDA)

        reloaded = Case.objects.get(pk=case.pk)
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        eda_row = CaseProcedure.objects.get(case=reloaded, procedure_type=ProcedureType.EDA)
        assert eda_row.declared_by_nir is True
        colon = CaseProcedure.objects.get(case=reloaded, procedure_type=ProcedureType.COLONOSCOPY)
        assert colon.declared_by_nir is False

    def test_correction_keeps_existing_audit_events(self, django_user_model) -> None:
        """CASE_PROCEDURE_DECLARATION_CORRECTED antes de CASE_REPROCESSING_REQUESTED."""
        user = _nir_user(django_user_model, "nir-proj-ev@test.com")
        case = _eligible_case(user=user, exam_type="eda")
        # Slice 008 (R5): row declarada explícita (sem fallback da coluna).
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        _confirm(case=case, user=user, new_exam_type=ProcedureType.COLONOSCOPY)

        types = [e.event_type for e in CaseEvent.objects.filter(case=case).order_by("id")]
        assert types.index("CASE_PROCEDURE_REVIEW_CONFIRMED") < types.index("CASE_REPROCESSING_REQUESTED")

    def test_combined_correction_single_to_combined(self, django_user_model) -> None:
        """Slice 005: correção aceita combinado — single→combined cria duas rows."""
        user = _nir_user(django_user_model, "nir-proj-cmb@test.com")
        case = _eligible_case(user=user, exam_type="eda")
        # Slice 008 (R5): row declarada explícita (sem fallback da coluna).
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        _confirm(case=case, user=user, new_exam_type=EDA_COLONOSCOPY)

        reloaded = Case.objects.get(pk=case.pk)
        assert get_declared_procedure_types(reloaded) == (
            ProcedureType.EDA,
            ProcedureType.COLONOSCOPY,
        )
        declared = {p.procedure_type for p in CaseProcedure.objects.filter(case=reloaded, declared_by_nir=True)}
        assert declared == {ProcedureType.EDA, ProcedureType.COLONOSCOPY}
        # Auditoria: evento humano de confirmação registrado; legados não são emitidos.
        assert CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="EXAM_TYPE_CORRECTED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()

    def test_projection_failure_rolls_back_bridge_derived_events_and_fsm(self, django_user_model) -> None:
        """Falha na projeção reverte ponte, derivados, eventos e FSM (R3)."""
        user = _nir_user(django_user_model, "nir-proj-rb@test.com")
        case = _eligible_case(user=user, exam_type="eda")
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        token = _claim_receipt_lease(case, user)
        structured_data_before = case.structured_data

        with mock.patch("apps.intake.services.sync_declared_projection", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                _confirm(case=case, user=user, new_exam_type=ProcedureType.COLONOSCOPY, token=token)

        reloaded = Case.objects.get(pk=case.pk)
        # projeção declarada intacta
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        # FSM intacto
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        # derivados NÃO foram limpos (rollback total)
        assert reloaded.structured_data == structured_data_before
        assert reloaded.summary_text == "Resumo antigo do perfil anterior."
        # nenhum evento de correção/reprocessamento
        assert not CaseEvent.objects.filter(
            case=case,
            event_type__in=["CASE_PROCEDURE_REVIEW_CONFIRMED", "CASE_REPROCESSING_REQUESTED"],
        ).exists()
        # projeção declarada inalterada (row pré-existente preservada; nada novo)
        assert CaseProcedure.objects.filter(case=reloaded).count() == 1
        assert CaseProcedure.objects.get(case=reloaded, procedure_type=ProcedureType.EDA).declared_by_nir is True
        # reserva NIR permanece (não foi liberada no rollback)
        assert reloaded.locked_by_id == user.pk
