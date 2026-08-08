"""Slice 008 — NIR opera somente pela projeção declarada (rows autoritativas).

Cobre R2/R3 do Slice 008 (specs exam-type-correction, exam-type-work-queues):

- R2: a correção compara CONJUNTOS de ``CaseProcedure`` (nunca a ponte
      ``Case.exam_type``) para decidir igualdade e gravar old/new; o evento
      ``CASE_PROCEDURE_DECLARATION_CORRECTED`` traz apenas ``old_procedures``/
      ``new_procedures`` — sem chaves singulares ``old_exam_type``/
      ``new_exam_type``.
- R3: os filtros NIR (operacional e encerrados) são exclusivos por rows
      declaradas, SEM fallback da coluna: um caso sem rows (legado/inválido)
      não aparece em bucket específico e não recebe default EDA.

R1 (criação/reenvio) e R4 (apresentação/labels via helper projetado) já são
verdes desde os Slices 001/005 e não mudam de comportamento neste slice; as
fixtures NIR relevantes são tornadas explícitas (R5) nos arquivos existentes.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    ExamType,
    ProcedureType,
)
from apps.cases.services import claim_case_lock
from apps.intake.services import correct_case_exam_type

pytestmark = pytest.mark.django_db

User = get_user_model()


# ── Helpers (coesos, mesmo protocolo dos slices NIR anteriores) ──────────


def _nir_user(django_user_model, username: str = "nir-s8@test.com"):
    """Cria usuário com o papel NIR atribuído (sem sessão HTTP)."""
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _nir_client(client, username: str = "nir-s8-view@test.com"):
    """Cria usuário NIR, faz login e retorna (client, user)."""
    user = _nir_user(User, username)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _make_eligible_case(*, user, exam_type: str = ExamType.EDA) -> Case:
    """Cria caso em WAIT_R1_CLEANUP_THUMBS com manual review elegível (sem rows).

    As rows declaradas são criadas explicitamente por cada teste (R5) — nenhum
    comportamento NIR pode depender de fallback da coluna.
    """
    return Case.objects.create(
        created_by=user,
        exam_type=exam_type,
        status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        extracted_text="RELATÓRIO DE OCORRÊNCIAS\nGoverno do Estado da Bahia\nCódigo: 123",
        agency_record_number="REC-S8-001",
        regulation_days_on_screen=3,
        structured_data={"patient": {"name": "Paciente de Teste"}},
        summary_text="Resumo antigo do perfil anterior.",
        suggested_action={
            "decision": "manual_review_required",
            "suggestion": "manual_review_required",
            "reason_code": "exam_type_mismatch",
            "reason_text": "Conjunto declarado difere da solicitacao atual.",
            "exam_type": exam_type,
            "declared_exam_type": exam_type,
            "detected_exam_type": "colonoscopy" if exam_type == ExamType.EDA else "eda",
        },
        priority_signals=[{"code": "foreign_body", "label": "Corpo estranho"}],
    )


def _declare(case: Case, procedure_types: tuple[str, ...]) -> Case:
    """Cria rows declaradas explicitamente (R5 — fixture row-authoritativa)."""
    for procedure_type in procedure_types:
        CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)
    return case


def _claim_receipt_lease(case: Case, user) -> uuid.UUID:
    """Adquire a reserva nir_receipt e retorna o token."""
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


def _correct(*, case, user, new_exam_type, reason_code="nir_identified_exam") -> Case:
    return correct_case_exam_type(
        case_id=case.case_id,
        new_exam_type=new_exam_type,
        user=user,
        active_role="nir",
        lock_token=_claim_receipt_lease(case, user),
        reason_code=reason_code,
    )


# ═══════════════════════════════════════════════════════════════════════════
# R2 — correção compara CONJUNTOS de CaseProcedure (nunca a coluna)
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrectionComparesSets:
    """R2: igualdade, old/new e reroteamento usam conjuntos de CaseProcedure."""

    def test_rejects_same_set_even_when_bridge_diverges(self, django_user_model) -> None:
        """Igualdade pelo CONJUNTO declarado, não pela ponte.

        Caso com rows declarando o conjunto combinado {EDA, Colonoscopia} mas
        com a ponte ``exam_type`` divergente (EDA). Corrigir para a seleção
        combinada (``eda_colonoscopy``) significa o MESMO conjunto já declarado
        — deve ser rejeitado como "igual". Antes do Slice 008 a comparação pela
        coluna aceitava essa correção (bug). Prova que a decisão de igualdade
        não consulta a coluna.
        """
        user = _nir_user(django_user_model, "nir-cmp-set@test.com")
        case = _make_eligible_case(user=user, exam_type=EDA_COLONOSCOPY)
        _declare(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))
        # Estado divergente ponte↔rows (não deveria existir em produção, mas
        # isola a comparação da coluna).
        case.exam_type = ExamType.EDA
        case.save(update_fields=["exam_type"])

        with pytest.raises(ValueError):
            _correct(case=case, user=user, new_exam_type=EDA_COLONOSCOPY)

        # Nenhuma mutação: FSM, derivados e reserva intactos.
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.summary_text == "Resumo antigo do perfil anterior."
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()

    def test_payload_records_sets_without_singular_keys(self, django_user_model) -> None:
        """Evento canônico traz apenas old_procedures/new_procedures.

        Não grava as chaves singulares ``old_exam_type``/``new_exam_type``
        (essas pertenciam à ponte e não são fonte NIR). old/new refletem os
        conjuntos lidos das rows declaradas.
        """
        user = _nir_user(django_user_model, "nir-payload-set@test.com")
        case = _make_eligible_case(user=user, exam_type=ExamType.EDA)
        _declare(case, (ProcedureType.EDA,))

        _correct(case=case, user=user, new_exam_type=EDA_COLONOSCOPY)

        event = CaseEvent.objects.get(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED")
        assert set(event.payload.keys()) == {"old_procedures", "new_procedures", "reason_code"}
        assert "old_exam_type" not in event.payload
        assert "new_exam_type" not in event.payload
        assert event.payload["old_procedures"] == [ProcedureType.EDA]
        assert event.payload["new_procedures"] == [ProcedureType.EDA, ProcedureType.COLONOSCOPY]
        assert event.actor_id == user.pk

    def test_old_procedures_read_from_declared_rows(self, django_user_model) -> None:
        """old_procedures vem das rows declaradas (R5 — fixture explícita).

        Caso declarado combinado corrige para EDA: old = [eda, colonoscopy]
        lido das rows, não da coluna.
        """
        user = _nir_user(django_user_model, "nir-old-rows@test.com")
        case = _make_eligible_case(user=user, exam_type=EDA_COLONOSCOPY)
        _declare(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))

        _correct(case=case, user=user, new_exam_type=ExamType.EDA)

        event = CaseEvent.objects.get(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED")
        assert event.payload["old_procedures"] == [ProcedureType.EDA, ProcedureType.COLONOSCOPY]
        assert event.payload["new_procedures"] == [ProcedureType.EDA]


# ═══════════════════════════════════════════════════════════════════════════
# R3 — filtros NIR por DECLARADO sem fallback de coluna (fail-closed)
# ═══════════════════════════════════════════════════════════════════════════


class TestDeclaredFilterIsRowAuthoritative:
    """R3: buckets exclusivos por rows declaradas; caso sem row não recebe default."""

    def test_my_cases_case_without_rows_appears_in_no_specific_bucket(self, client) -> None:
        """Caso legado/inválido sem rows não aparece em EDA/Colon/Combinado.

        Antes do Slice 008 o fallback da ponte incluía o caso no bucket da
        coluna (default EDA quando sem rows). Slice 008: fail-closed — só
        "Todos" mostra o caso.
        """
        client, user = _nir_client(client, "nir-fc-myc@test.com")
        legacy = Case.objects.create(
            created_by=user,
            exam_type=ExamType.EDA,
            status=CaseStatus.NEW,
            agency_record_number="LEGACY-NO-ROW-MYC",
        )

        for dimension in (ExamType.EDA, ExamType.COLONOSCOPY, EDA_COLONOSCOPY):
            response = client.get(reverse("intake:my_cases") + f"?exam_type={dimension}")
            content = response.content.decode()
            assert str(legacy.case_id) not in content, (
                f"caso sem rows apareceu no bucket {dimension} (esperado fail-closed)"
            )

        # Default "Todos" ainda lista o caso (não é filtrado por dimensão).
        response = client.get(reverse("intake:my_cases"))
        assert str(legacy.case_id) in response.content.decode()

    def test_closed_search_case_without_rows_appears_in_no_specific_bucket(self, client) -> None:
        """Caso encerrado sem rows não aparece em bucket específico da busca."""
        client, user = _nir_client(client, "nir-fc-closed@test.com")
        legacy = Case.objects.create(
            created_by=user,
            exam_type=ExamType.EDA,
            status=CaseStatus.CLEANED,
            agency_record_number="LEGACY-NO-ROW-CLS",
        )

        for dimension in (ExamType.EDA, ExamType.COLONOSCOPY, EDA_COLONOSCOPY):
            response = client.get(reverse("intake:closed_cases_search") + f"?exam_type={dimension}")
            content = response.content.decode()
            assert str(legacy.case_id) not in content, (
                f"caso sem rows apareceu no bucket {dimension} da busca de encerrados"
            )

    def test_my_cases_bucket_excludes_other_declared(self, client) -> None:
        """Buckets exclusivos: EDA-declarado não cai em Combinado mesmo se a
        ponte for combinada, e combinado exige as DUAS rows declaradas."""
        client, user = _nir_client(client, "nir-bucket@test.com")
        # Declarado EDA (1 row) com ponte combinada divergente.
        eda_only = Case.objects.create(
            created_by=user,
            exam_type=EDA_COLONOSCOPY,
            status=CaseStatus.NEW,
            agency_record_number="EDA-ONLY",
        )
        CaseProcedure.objects.create(case=eda_only, procedure_type=ProcedureType.EDA, declared_by_nir=True)

        response = client.get(reverse("intake:my_cases") + "?exam_type=eda_colonoscopy")
        content = response.content.decode()
        assert str(eda_only.case_id) not in content

        response = client.get(reverse("intake:my_cases") + "?exam_type=eda")
        assert str(eda_only.case_id) in response.content.decode()
