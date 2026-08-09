"""Slice 011-C — Contrato final pós-cutover: payload CASE_CREATED, schema e projeção.

A migration 0016 (Slice 011-C) removeu a coluna ``Case.exam_type`` e o índice
composto ``cases_status_exam_type_idx``; a classe ``ExamType`` permanece apenas
por compatibilidade e é removida no Slice 011-E — por isso este módulo NÃO a
importa. Os testes de enum/campo/índice/backfill 0014 morreram com a coluna e
foram substituídos por testes do contrato final (R5): payload de criação com
somente ``status`` (decisão 1), schema sem field/índice e radios da correção
marcando "(atual)" pela projeção declarada (decisão 2) — nunca pela coluna.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, ProcedureType
from apps.cases.procedures import (
    get_declared_procedure_types,
    selection_key,
    set_declared_procedures,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_user(django_user_model: Any, username: str) -> Any:
    """Cria usuário com o papel NIR atribuído (sem sessão HTTP)."""
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _nir_client(client: Any, username: str) -> tuple[Any, Any]:
    """Cria usuário NIR, faz login e retorna (client, user)."""
    user = _nir_user(User, username)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _eligible_case(*, user: Any, declared: str = "eda") -> Case:
    """Cria caso em WAIT_R1_CLEANUP_THUMBS com manual review elegível.

    A projeção declarada vem exclusivamente da row ``CaseProcedure``; nenhum
    kwarg de coluna é usado (o campo não existe mais no modelo final).
    """
    case = Case.objects.create(
        created_by=user,
        status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        extracted_text=(
            "RELATÓRIO DE OCORRÊNCIAS\nGoverno do Estado da Bahia\nCódigo: 123\nMotivo da Solicitação: EDA"
        ),
        agency_record_number="REC-CORR-011C",
        regulation_days_on_screen=3,
        structured_data={"patient": {"name": "Paciente de Teste"}},
        summary_text="Resumo antigo do perfil anterior.",
        suggested_action={
            "decision": "manual_review_required",
            "suggestion": "manual_review_required",
            "reason_code": "exam_type_mismatch",
            "reason_text": "Tipo de exame declarado difere da solicitacao atual.",
            "exam_type": "colonoscopy",
            "declared_exam_type": declared,
            "detected_exam_type": "colonoscopy",
        },
        priority_signals=[{"code": "foreign_body", "label": "Corpo estranho"}],
    )
    CaseProcedure.objects.create(case=case, procedure_type=declared, declared_by_nir=True)
    return case


# ── Decisão 1 — payload CASE_CREATED de novos casos ───────────────────────


class TestCaseCreatedAuditPayloadFinal:
    """Decisão 1 — payload de ``CASE_CREATED`` de NOVOS casos tem somente status."""

    def test_case_created_payload_has_status_only(self, user) -> None:
        case = Case.objects.create(created_by=user)
        event = CaseEvent.objects.get(case=case, event_type="CASE_CREATED")
        assert event.payload == {"status": CaseStatus.NEW}
        assert "exam_type" not in event.payload

    def test_case_created_payload_with_declared_projection(self, user) -> None:
        """Mesmo com projeção declarada, o payload de criação não grava a chave."""
        case = set_declared_procedures(
            case=Case.objects.create(created_by=user),
            procedure_types=[ProcedureType.COLONOSCOPY],
            actor=user,
        )
        event = CaseEvent.objects.get(case=case, event_type="CASE_CREATED")
        assert event.payload == {"status": CaseStatus.NEW}
        assert "exam_type" not in event.payload


# ── R2/R3 — schema final sem a coluna e o índice compostos ────────────────


class TestCaseSchemaFinal:
    """R2/R3 — o modelo final não possui field nem índice compostos."""

    def test_case_model_has_no_exam_type_field(self) -> None:
        field_names = {f.name for f in Case._meta.get_fields()}
        assert "exam_type" not in field_names

    def test_composite_index_cases_status_exam_type_removed(self) -> None:
        index_names = {idx.name for idx in Case._meta.indexes}
        assert "cases_status_exam_type_idx" not in index_names

    def test_case_creation_requires_no_exam_type(self, user) -> None:
        case = Case.objects.create(created_by=user)
        assert case.status == CaseStatus.NEW
        assert get_declared_procedure_types(case) == ()

    def test_declared_projection_drives_selection_key(self, user) -> None:
        """``EDA_COLONOSCOPY`` permanece apenas como chave derivada da projeção."""
        case = set_declared_procedures(
            case=Case.objects.create(created_by=user),
            procedure_types=[ProcedureType.EDA, ProcedureType.COLONOSCOPY],
            actor=user,
        )
        assert selection_key(get_declared_procedure_types(case)) == "eda_colonoscopy"
        assert "eda_colonoscopy" not in {f.name for f in Case._meta.get_fields()}


# ── Decisão 2 — radios da correção pela projeção, nunca pela coluna ───────


class TestCorrectionScreenRadiosUseProjection:
    """Decisão 2 — radios da correção marcam (atual)/disabled pela PROJEÇÃO.

    Um caso com histórico legado divergente (payload antigo de ``CASE_CREATED``
    com ``exam_type`` de outro tipo) continua marcando o conjunto declarado
    projetado das rows.
    """

    def _assert_radio_state(self, content: str, radio_id: str, label_for: str, current: bool) -> None:
        """Verifica o estado de um radio pelo bloco input (disabled) e label ((atual))."""
        input_block = content.split(f'id="{radio_id}"')[1].split("<label")[0]
        label_block = content.split(f'for="{label_for}"')[1].split("</label>")[0]
        if current:
            assert "disabled" in input_block, f"radio {radio_id} deveria estar disabled"
            assert "(atual)" in label_block, f"label {label_for} deveria marcar (atual)"
        else:
            assert "disabled" not in input_block, f"radio {radio_id} não deveria estar disabled"
            assert "(atual)" not in label_block, f"label {label_for} não deveria marcar (atual)"

    def test_eda_projection_marks_eda_radio_current(self, client) -> None:
        """Projeção EDA → radio EDA disabled com (atual); demais habilitados."""
        client, user = _nir_client(client, "nir-011c-eda@test.com")
        case = _eligible_case(user=user, declared="eda")
        # Histórico legado: payload antigo de criação apontava colonoscopia —
        # deve ser IGNORADO pelos radios (append-only, sem coluna).
        CaseEvent.objects.filter(case=case, event_type="CASE_CREATED").update(
            payload={"status": CaseStatus.NEW, "exam_type": "colonoscopy"}
        )

        content = client.get(reverse("intake:case_detail", args=[case.case_id])).content.decode()
        assert "Correção de Tipo de Exame" in content
        self._assert_radio_state(content, "exam-type-eda", "exam-type-eda", current=True)
        self._assert_radio_state(content, "exam-type-colonoscopy", "exam-type-colonoscopy", current=False)
        self._assert_radio_state(content, "exam-type-combined", "exam-type-combined", current=False)

    def test_combined_projection_marks_combined_radio_current(self, client) -> None:
        """Projeção combinada → radio EDA + Colonoscopia disabled com (atual)."""
        client, user = _nir_client(client, "nir-011c-comb@test.com")
        case = _eligible_case(user=user, declared="eda")
        set_declared_procedures(
            case=case,
            procedure_types=[ProcedureType.EDA, ProcedureType.COLONOSCOPY],
            actor=user,
        )

        content = client.get(reverse("intake:case_detail", args=[case.case_id])).content.decode()
        assert "Correção de Tipo de Exame" in content
        self._assert_radio_state(content, "exam-type-eda", "exam-type-eda", current=False)
        self._assert_radio_state(content, "exam-type-colonoscopy", "exam-type-colonoscopy", current=False)
        self._assert_radio_state(content, "exam-type-combined", "exam-type-combined", current=True)
