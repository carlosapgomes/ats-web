"""Slice 006 — correção de tipo e confirmação NIR serializadas (correção).

Cobre C1–C7:
- C1: correção e confirmação usam o MESMO row lock (``select_for_update``)
      sobre o mesmo ``case_id`` e revalidam estado/reserva na instância
      bloqueada e atualizada — exatamente uma ação vence;
- C2: o serviço valida ator NIR explicitamente (papel ativo da sessão + papel
      atribuído), sem derivar papel ativo de papéis existentes;
- C3: o serviço valida a reserva completa sob o lock (owner, token exato,
      contexto ``nir_receipt``, papel ``nir``, validade) — inclusive lock do
      mesmo usuário incompatível;
- C4: ``confirm_receipt`` é view fina; a mutação vive em serviço transacional
      coeso (sem instância obsoleta para salvar);
- C5: um único enqueue LLM pós-commit; falha agenda retry automático
      (Schedule ONCE → execute_pdf_extraction, sem reextrair PDF) e a view
      mostra erro verdadeiro — sem prometer retomada inexistente;
- C6: auditoria/dados consistentes (mesmo UUID, fontes preservadas, derivados
      limpos apenas se a correção vencer, eventos em ordem);
- C7: escopo estreito (sem migration/estado novo/criação de Case).
"""

from __future__ import annotations

import threading
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, ExamType
from apps.cases.services import (
    assert_case_lock as real_assert_case_lock,
)
from apps.cases.services import claim_case_lock
from apps.intake.services import (
    EnqueueAfterCommitError,
    confirm_case_receipt,
    correct_case_exam_type,
    is_exam_type_correction_eligible,
)

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client, username: str = "nir-corr@test.com") -> tuple:  # type: ignore[type-arg]
    """Cria usuário NIR, faz login e retorna (client, user)."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client) -> tuple:  # type: ignore[type-arg]
    """Cria usuário doctor, faz login e retorna (client, user)."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc-corr@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


def _nir_user(django_user_model, username: str = "nir-svc@test.com"):
    """Cria usuário com o papel NIR atribuído (sem sessão HTTP)."""
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _multi_role_nir_user(django_user_model, username: str = "multi-nir@test.com"):
    """Usuário multi-role que possui NIR (para provar active_role errado)."""
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username, password="testpass123")
    nir, _ = Role.objects.get_or_create(name="nir")
    doctor, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(nir, doctor)
    return user


def _plain_user(django_user_model, username: str = "plain@test.com"):
    """Usuário sem nenhum papel."""
    return django_user_model.objects.create_user(username=username, password="testpass123")


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


def _regulation_pass_text() -> str:
    """Texto de relatório de regulação válido (>500 chars, gate aceita)."""
    return (
        "RELATÓRIO DE OCORRÊNCIAS\n"
        "Governo do Estado da Bahia\n"
        "Secretaria da Saúde do Estado\n"
        "Central Estadual de Regulação\n"
        "Código: 123456\n"
        "Abertura: 01/01/2025\n"
        "Unid. Origem: Hospital Central\n"
        "Motivo da Solicitação: Colonoscopia para rastreamento oncológico\n"
        "Complemento da Solicitação: Paciente com histórico familiar de neoplasia.\n"
        "Resumo Clínico: Paciente de 55 anos, sem comorbidades, encaminhado para colonoscopia.\n"
        "Dias em tela: 5\n"
        "Data Adm. Unid.: 15/03/2025\n"
        + "\n".join(
            f"Linha de preenchimento número {i} para atingir o tamanho mínimo exigido pelo detector." for i in range(6)
        )
    )


def _eligible_case(
    *,
    user,
    exam_type: str = ExamType.EDA,
    reason_code: str = "exam_type_mismatch",
    detected: str = "colonoscopy",
    extracted_text: str | None = None,
) -> Case:
    """Cria um caso em WAIT_R1_CLEANUP_THUMBS com manual review elegível."""
    case = Case.objects.create(
        created_by=user,
        exam_type=exam_type,
        status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        extracted_text=extracted_text
        or ("RELATÓRIO DE OCORRÊNCIAS\nGoverno do Estado da Bahia\nCódigo: 123\nMotivo da Solicitação: Colonoscopia"),
        agency_record_number="REC-CORR-001",
        regulation_days_on_screen=3,
        structured_data={"patient": {"name": "Paciente de Teste"}},
        summary_text="Resumo antigo do perfil anterior.",
        suggested_action={
            "decision": "manual_review_required",
            "suggestion": "manual_review_required",
            "reason_code": reason_code,
            "reason_text": "Tipo de exame declarado difere da solicitacao atual.",
            "exam_type": detected,
            "declared_exam_type": exam_type,
            "detected_exam_type": detected,
        },
        priority_signals=[{"code": "foreign_body", "label": "Corpo estranho"}],
    )
    # Slice 008 (R5): row declarada explícita — a correção lê o conjunto das
    # rows (nunca a coluna), então a fixture cria a projeção declarada.
    CaseProcedure.objects.create(case=case, procedure_type=exam_type, declared_by_nir=True)
    return case


# ═══════════════════════════════════════════════════════════════════════════
# C1/C2/C3/C5/R1-R6 — serviço de correção transacional
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCorrectionService:
    """R1/R2: mesmo UUID, status LLM_STRUCT e transição FSM nomeada."""

    def test_corrects_same_uuid_and_returns_to_llm_struct(self, django_user_model) -> None:
        """Correção mantém o MESMO caso (uuid) e volta a LLM_STRUCT."""
        user = _nir_user(django_user_model, "nir-same-uuid@test.com")
        case = _eligible_case(user=user)
        original_id = case.case_id
        token = _claim_receipt_lease(case, user)

        result = correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        assert result.case_id == original_id
        reloaded = Case.objects.get(pk=result.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == ExamType.COLONOSCOPY

    def test_fsm_transition_reprocess_after_exam_type_correction(self, user) -> None:
        """Transição nomeada existe e registra CASE_REPROCESSING_REQUESTED."""
        case = _eligible_case(user=user)
        case.reprocess_after_exam_type_correction(user=user, payload={"reason_code": "other"})
        case.save()
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert CaseEvent.objects.filter(case=case, event_type="CASE_REPROCESSING_REQUESTED").exists()

    def test_fsm_transition_not_allowed_from_wait_doctor(self, user, advance_to) -> None:
        """Transição NÃO é permitida a partir de WAIT_DOCTOR (FSM protegida)."""
        from django_fsm import TransitionNotAllowed

        case = Case.objects.create(created_by=user)
        case = advance_to(case, CaseStatus.WAIT_DOCTOR)
        with pytest.raises(TransitionNotAllowed):
            case.reprocess_after_exam_type_correction(user=user)

    def test_events_recorded_with_old_new_and_ordered(self, django_user_model) -> None:
        """CASE_PROCEDURE_DECLARATION_CORRECTED (sets/reason/actor) antes de reprocessar."""
        user = _nir_user(django_user_model, "nir-events@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        events = list(CaseEvent.objects.filter(case=case).order_by("id"))
        types = [e.event_type for e in events]
        assert "CASE_PROCEDURE_DECLARATION_CORRECTED" in types
        assert "CASE_REPROCESSING_REQUESTED" in types
        assert types.index("CASE_PROCEDURE_DECLARATION_CORRECTED") < types.index("CASE_REPROCESSING_REQUESTED")

        corrected = next(e for e in events if e.event_type == "CASE_PROCEDURE_DECLARATION_CORRECTED")
        assert corrected.payload == {
            "old_procedures": [ExamType.EDA],
            "new_procedures": [ExamType.COLONOSCOPY],
            "reason_code": "nir_identified_exam",
        }
        assert corrected.actor_id == user.pk
        # payload não carrega texto clínico integral
        assert "extracted_text" not in corrected.payload

    def test_derived_cleared_sources_preserved(self, django_user_model) -> None:
        """R3: derivados LLM limpos; PDF/anexos/texto/ocorrência preservados."""
        user = _nir_user(django_user_model, "nir-derived@test.com")
        case = _eligible_case(user=user)
        created_at = case.created_at
        case.pdf_file = "pdfs/2025/01/original.pdf"  # apenas nome — não é tocado
        case.save()
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        reloaded = Case.objects.get(pk=case.pk)
        # Derivados limpos
        assert reloaded.structured_data is None
        assert reloaded.summary_text == ""
        assert reloaded.suggested_action is None
        assert reloaded.priority_signals == []
        # Fontes preservadas
        assert reloaded.case_id == case.case_id
        assert reloaded.created_by_id == user.pk
        assert reloaded.created_at == created_at
        assert reloaded.pdf_file.name == "pdfs/2025/01/original.pdf"
        assert reloaded.extracted_text == case.extracted_text
        assert reloaded.agency_record_number == "REC-CORR-001"
        assert reloaded.regulation_days_on_screen == 3
        # Timeline preservada (eventos anteriores continuam)
        assert CaseEvent.objects.filter(case=case).exists()

    def test_enqueue_pipeline_once_no_pdf_extraction(self, django_user_model, monkeypatch) -> None:
        """R4: enqueue_pipeline 1x, enqueue_pdf_extraction 0x."""
        pipeline_calls: list[object] = []
        pdf_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        monkeypatch.setattr(
            "apps.intake.tasks.enqueue_pdf_extraction",
            lambda case_id: pdf_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-enq-once@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        assert len(pipeline_calls) == 1
        assert pipeline_calls[0] == case.case_id
        assert pdf_calls == []

    @pytest.mark.parametrize(
        ("reason_code", "detected"),
        [
            ("mixed_exam_request", "mixed"),
            ("unknown_exam_type", "unknown"),
        ],
    )
    def test_mixed_and_unknown_eligible(self, django_user_model, reason_code: str, detected: str) -> None:
        """R1: mixed e unknown são elegíveis para correção."""
        user = _nir_user(django_user_model, "nir-mixed@test.com")
        case = _eligible_case(user=user, reason_code=reason_code, detected=detected)
        assert is_exam_type_correction_eligible(case) is True
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="other",
        )
        assert Case.objects.get(pk=case.pk).status == CaseStatus.LLM_STRUCT

    def test_same_type_rejected_without_mutation(self, django_user_model) -> None:
        """R1: novo tipo igual ao atual é rejeitado sem mutação."""
        user = _nir_user(django_user_model, "nir-same-type@test.com")
        case = _eligible_case(user=user, exam_type=ExamType.EDA)
        token = _claim_receipt_lease(case, user)

        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.EDA,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert reloaded.structured_data is not None
        assert reloaded.suggested_action is not None

    def test_invalid_new_type_rejected(self, django_user_model) -> None:
        """R1: tipo fora do enum é rejeitado (falha pré-transação)."""
        user = _nir_user(django_user_model, "nir-invalid-type@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type="cpre",
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA

    def test_invalid_reason_code_rejected(self, django_user_model) -> None:
        """R5: reason_code do NIR fora do conjunto é rejeitado."""
        user = _nir_user(django_user_model, "nir-reason@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="bogus",
            )

    def test_wait_doctor_and_later_rejected(self, django_user_model, advance_to) -> None:
        """R1: WAIT_DOCTOR e decisões posteriores são rejeitados."""
        user = _nir_user(django_user_model, "nir-wait-doc@test.com")
        case = Case.objects.create(created_by=user)
        case = advance_to(case, CaseStatus.WAIT_DOCTOR)
        case.suggested_action = {
            "decision": "manual_review_required",
            "reason_code": "exam_type_mismatch",
        }
        case.save()

        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=uuid.uuid4(),
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        assert reloaded.exam_type == ExamType.EDA

    @pytest.mark.parametrize(
        "target",
        [
            CaseStatus.R1_ACK_PROCESSING,
            CaseStatus.EXTRACTING,
            CaseStatus.LLM_STRUCT,
            CaseStatus.LLM_SUGGEST,
            CaseStatus.R2_POST_WIDGET,
        ],
    )
    def test_transient_worker_states_rejected_without_mutation(
        self, django_user_model, advance_to, target: CaseStatus
    ) -> None:
        """R1: estados transitórios de worker não podem ser mutados."""
        user = _nir_user(django_user_model, "nir-transient@test.com")
        case = Case.objects.create(created_by=user)
        case = advance_to(case, target)
        case.suggested_action = {
            "decision": "manual_review_required",
            "reason_code": "exam_type_mismatch",
        }
        case.save()

        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=uuid.uuid4(),
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == target
        assert reloaded.exam_type == ExamType.EDA
        assert reloaded.suggested_action is not None

    def test_non_eda_and_invalid_regulation_not_eligible(self, django_user_model) -> None:
        """R1: non_eda_request e invalid_regulation_report NÃO são elegíveis."""
        for reason_code in ("non_eda_request", "invalid_regulation_report"):
            user = _nir_user(django_user_model, f"nir-not-eligible-{reason_code}@test.com")
            case = _eligible_case(user=user, reason_code=reason_code, detected="non_eda")
            assert is_exam_type_correction_eligible(case) is False
            token = _claim_receipt_lease(case, user)
            with pytest.raises(ValueError):
                correct_case_exam_type(
                    case_id=case.case_id,
                    new_exam_type=ExamType.COLONOSCOPY,
                    user=user,
                    active_role="nir",
                    lock_token=token,
                    reason_code="nir_identified_exam",
                )
            reloaded = Case.objects.get(pk=case.pk)
            assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
            assert reloaded.structured_data is not None

    # ── C2: ator NIR explícito ────────────────────────────────────────────

    def test_service_rejects_actor_without_nir_role(self, django_user_model, monkeypatch) -> None:
        """C2: ator sem papel NIR é rejeitado sem mutação/evento/enqueue."""
        enqueue_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: enqueue_calls.append(case_id),
        )
        actor = _plain_user(django_user_model, "not-nir@test.com")
        case = _eligible_case(user=actor)
        token = _claim_receipt_lease(case, actor)  # lease existe, ator não é NIR

        with pytest.raises(PermissionError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=actor,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert reloaded.structured_data is not None
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert enqueue_calls == []

    def test_service_rejects_wrong_active_role_multi_role_user(self, django_user_model, monkeypatch) -> None:
        """C2: usuário multi-role com NIR mas active_role doctor é rejeitado."""
        enqueue_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: enqueue_calls.append(case_id),
        )
        actor = _multi_role_nir_user(django_user_model, "multi-role@test.com")
        case = _eligible_case(user=actor)
        token = _claim_receipt_lease(case, actor)

        with pytest.raises(PermissionError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=actor,
                active_role="doctor",  # papel ativo da sessão ≠ nir
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert enqueue_calls == []

    # ── C3: reserva completa sob o lock ───────────────────────────────────

    def test_service_rejects_wrong_token_same_user(self, django_user_model, monkeypatch) -> None:
        """C3: token errado do mesmo usuário é rejeitado sem mutação."""
        enqueue_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: enqueue_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-wrong-token@test.com")
        case = _eligible_case(user=user)
        _claim_receipt_lease(case, user)  # token T1 registrado no caso

        with pytest.raises(PermissionError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=uuid.uuid4(),  # token T2 ≠ T1
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert reloaded.structured_data is not None
        assert enqueue_calls == []

    def test_service_rejects_incompatible_context_same_user(self, django_user_model, monkeypatch) -> None:
        """C3: lock do mesmo usuário com contexto incompatível é rejeitado."""
        enqueue_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: enqueue_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-bad-context@test.com")
        case = _eligible_case(user=user)
        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            context="incompatible_context",
            role="nir",
        )
        assert result.acquired
        assert result.token is not None

        with pytest.raises(PermissionError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=result.token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert enqueue_calls == []

    def test_service_rejects_incompatible_role_same_user(self, django_user_model, monkeypatch) -> None:
        """C3: lock do mesmo usuário com papel incompatível é rejeitado."""
        enqueue_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: enqueue_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-bad-role@test.com")
        case = _eligible_case(user=user)
        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            context="nir_receipt",
            role="doctor",  # papel da reserva ≠ nir
        )
        assert result.acquired
        assert result.token is not None

        with pytest.raises(PermissionError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=result.token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert enqueue_calls == []

    def test_service_rejects_expired_lease(self, django_user_model, monkeypatch) -> None:
        """C3: lease expirada é rejeitada sem mutação."""
        enqueue_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: enqueue_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-expired@test.com")
        case = _eligible_case(user=user)
        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            context="nir_receipt",
            role="nir",
            lease_seconds=0,
        )
        assert result.acquired
        assert result.token is not None

        with pytest.raises(PermissionError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=result.token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert enqueue_calls == []

    def test_incompatible_lock_other_user_rejected_without_mutation(self, django_user_model) -> None:
        """C3: reserva de outro usuário rejeita sem limpar dados."""
        user = _nir_user(django_user_model, "nir-owner@test.com")
        other = _nir_user(django_user_model, "nir-other@test.com")
        case = _eligible_case(user=user)
        result = claim_case_lock(
            case_id=case.case_id,
            user=other,
            expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            context="nir_receipt",
            role="nir",
        )
        assert result.acquired
        assert result.token is not None

        with pytest.raises(PermissionError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=result.token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert reloaded.structured_data is not None
        assert reloaded.suggested_action is not None

    def test_same_user_lock_allowed_and_cleared(self, django_user_model, monkeypatch) -> None:
        """Lock nir_receipt do próprio NIR é permitido e limpo após correção."""
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-same-lock@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.locked_by is None
        assert reloaded.lock_token is None
        assert reloaded.lock_context == ""

    # ── R7: dois requests de correção — um vencedor, um enqueue ──────────

    def test_two_corrections_one_winner_one_enqueue(self, django_user_model, monkeypatch) -> None:
        """Segundo request de correção não enfileira novamente."""
        pipeline_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-two@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )
        assert pipeline_calls == [case.case_id]

        # Estado já LLM_STRUCT (lease limpa): rejeitado sem segundo enqueue.
        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.EDA,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )
        assert pipeline_calls == [case.case_id]

    # ── C5: falha de enqueue pós-commit ───────────────────────────────────

    def test_enqueue_failure_raises_after_commit_and_schedules_recovery(self, django_user_model, monkeypatch) -> None:
        """Falha pós-commit de enqueue: correção commitada + retry agendado."""
        from django_q.models import Schedule

        def _boom(case_id) -> None:  # noqa: ARG001
            raise RuntimeError("fila indisponível")

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", _boom)
        monkeypatch.setattr(
            "apps.intake.tasks.enqueue_pdf_extraction",
            lambda case_id: pytest.fail("PDF não deve ser enfileirado"),
        )
        user = _nir_user(django_user_model, "nir-enq-fail@test.com")
        case = _eligible_case(user=user, extracted_text=_regulation_pass_text())
        token = _claim_receipt_lease(case, user)

        with pytest.raises(EnqueueAfterCommitError) as excinfo:
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        assert excinfo.value.recovery_scheduled is True
        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == ExamType.COLONOSCOPY
        assert reloaded.structured_data is None
        schedule = Schedule.objects.filter(
            func="apps.intake.tasks.execute_pdf_extraction",
            args__contains=str(case.case_id),
        ).first()
        assert schedule is not None

    def test_enqueue_and_schedule_failure_reports_no_auto_retry(self, django_user_model, monkeypatch) -> None:
        """Falha de enqueue E de agendamento: recovery_scheduled=False."""

        def _boom(case_id) -> None:  # noqa: ARG001
            raise RuntimeError("fila indisponível")

        def _schedule_boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("agendador indisponível")

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", _boom)
        monkeypatch.setattr("django_q.tasks.schedule", _schedule_boom)
        user = _nir_user(django_user_model, "nir-enq-sched-fail@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        with pytest.raises(EnqueueAfterCommitError) as excinfo:
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        assert excinfo.value.recovery_scheduled is False
        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == ExamType.COLONOSCOPY

    def test_recovery_reenqueues_same_case_without_pdf(self, django_user_model, monkeypatch) -> None:
        """C5: retry automático do MESMO caso re-enfileira LLM sem extrair PDF."""
        from django_q.models import Schedule

        from apps.intake.tasks import execute_pdf_extraction

        calls: list[object] = []
        attempts = {"n": 0}

        def flaky_enqueue(case_id) -> None:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("fila indisponível no primeiro enqueue")
            calls.append(case_id)

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", flaky_enqueue)
        monkeypatch.setattr(
            "apps.intake.tasks.enqueue_pdf_extraction",
            lambda case_id: pytest.fail("PDF não deve ser enfileirado"),
        )
        user = _nir_user(django_user_model, "nir-recovery@test.com")
        case = _eligible_case(user=user, extracted_text=_regulation_pass_text())
        token = _claim_receipt_lease(case, user)

        with pytest.raises(EnqueueAfterCommitError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )
        assert calls == []
        assert Schedule.objects.filter(
            func="apps.intake.tasks.execute_pdf_extraction",
            args__contains=str(case.case_id),
        ).exists()

        # Scheduler (simulado) dispara o retry do MESMO caso em LLM_STRUCT.
        execute_pdf_extraction(str(case.case_id))

        assert calls == [case.case_id]
        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.LLM_STRUCT


# ═══════════════════════════════════════════════════════════════════════════
# C1/C4 — serviço de confirmação (fluxos legados + exclusão mútua)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestConfirmReceiptService:
    """C1/C4: confirmação em serviço transacional, fluxos legados preservados."""

    def test_confirm_common_flow_to_cleaned(self, django_user_model) -> None:
        """Fluxo comum: confirmação transita para CLEANED e limpa a reserva."""
        user = _nir_user(django_user_model, "nir-confirm-common@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        result = confirm_case_receipt(
            case_id=case.case_id,
            user=user,
            active_role="nir",
            lock_token=token,
        )

        assert result.status == CaseStatus.CLEANED
        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.CLEANED
        assert reloaded.locked_by is None
        assert reloaded.lock_token is None
        event_types = [e.event_type for e in CaseEvent.objects.filter(case=case)]
        assert "CLEANUP_TRIGGERED" in event_types
        assert "CLEANUP_COMPLETED" in event_types

    def test_confirm_rejects_without_lease(self, django_user_model) -> None:
        """Confirmação sem reserva é rejeitada sem mutação."""
        user = _nir_user(django_user_model, "nir-confirm-nolock@test.com")
        case = _eligible_case(user=user)

        with pytest.raises(PermissionError):
            confirm_case_receipt(
                case_id=case.case_id,
                user=user,
                active_role="nir",
                lock_token=uuid.uuid4(),
            )

        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_confirm_rejects_actor_without_nir_role(self, django_user_model) -> None:
        """C2: confirmação com ator sem papel NIR é rejeitada."""
        actor = _plain_user(django_user_model, "confirm-not-nir@test.com")
        case = _eligible_case(user=actor)
        token = _claim_receipt_lease(case, actor)

        with pytest.raises(PermissionError):
            confirm_case_receipt(
                case_id=case.case_id,
                user=actor,
                active_role="nir",
                lock_token=token,
            )

        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert not CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").exists()

    def test_confirm_after_correction_rejected_without_cleanup(self, django_user_model, monkeypatch) -> None:
        """Ordem correção→confirmação: confirmação perde sem cleanup."""
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-order-corr@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )
        assert Case.objects.get(pk=case.case_id).status == CaseStatus.LLM_STRUCT

        with pytest.raises((ValueError, PermissionError)):
            confirm_case_receipt(
                case_id=case.case_id,
                user=user,
                active_role="nir",
                lock_token=token,
            )

        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == ExamType.COLONOSCOPY
        assert reloaded.structured_data is None
        assert not CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").exists()

    def test_correction_after_confirm_rejected_without_events(self, django_user_model, monkeypatch) -> None:
        """Ordem confirmação→correção: correção perde sem evento/enqueue."""
        enqueue_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: enqueue_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-order-confirm@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        confirm_case_receipt(
            case_id=case.case_id,
            user=user,
            active_role="nir",
            lock_token=token,
        )
        assert Case.objects.get(pk=case.case_id).status == CaseStatus.CLEANED

        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.CLEANED
        assert reloaded.exam_type == ExamType.EDA
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert enqueue_calls == []

    def test_confirm_ack_flow_responded_issue(self, django_user_model, case_factory, advance_to) -> None:
        """Fluxo legado ACK: issue respondida → CLEANED + evento de ciência."""
        from apps.cases.services import open_post_schedule_issue, respond_post_schedule_issue

        user = _nir_user(django_user_model, "nir-ack@test.com")
        case = advance_to(case_factory(user), CaseStatus.CLEANED)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.appointment_status = "confirmed"
        case.save(
            update_fields=[
                "doctor_decision",
                "doctor_admission_flow",
                "appointment_status",
            ]
        )
        case = open_post_schedule_issue(
            case=case,
            user=user,
            reason="transport_unavailable",
            message="Transporte indisponível.",
        )
        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="cancel",
            response_message="Agendamento cancelado conforme solicitação.",
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        token = _claim_receipt_lease(case, user)

        result = confirm_case_receipt(
            case_id=case.case_id,
            user=user,
            active_role="nir",
            lock_token=token,
        )

        assert result.status == CaseStatus.CLEANED
        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.post_schedule_issue_status == ""
        assert CaseEvent.objects.filter(
            case=case,
            event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED",
        ).exists()
        assert reloaded.locked_by is None


# ═══════════════════════════════════════════════════════════════════════════
# R7/C1 — corrida real entre correção e confirmação (row lock serializa)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db(transaction=True)
class TestCorrectionConfirmSerialization:
    """C1/R7: exclusão mútua real — exatamente uma ação vence, sem stale write."""

    @staticmethod
    def _run_in_thread(target, name: str) -> tuple[threading.Thread, dict[str, object]]:
        results: dict[str, object] = {}

        def runner() -> None:
            try:
                results["ok"] = True
                results["value"] = target()
            except Exception as exc:  # noqa: BLE001
                results["ok"] = False
                results["error"] = exc

        thread = threading.Thread(target=runner, name=name, daemon=True)
        thread.start()
        return thread, results

    def test_correction_holds_lock_then_confirm_rejected(self, django_user_model, monkeypatch) -> None:
        """Correção segura o row lock; confirmação bloqueia e depois perde."""
        pipeline_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-race-corr@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        correction_locked = threading.Event()
        let_correction_finish = threading.Event()

        def coordinated_assert(*, case, user, token, context) -> None:  # noqa: ARG001
            real_assert_case_lock(case=case, user=user, token=token, context=context)
            if threading.current_thread().name == "correction-race" and not correction_locked.is_set():
                correction_locked.set()
                assert let_correction_finish.wait(timeout=30), "timeout aguardando liberação"

        monkeypatch.setattr("apps.cases.services.assert_case_lock", coordinated_assert)

        def run_correction() -> Case:
            return correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        def run_confirm() -> Case:
            return confirm_case_receipt(
                case_id=case.case_id,
                user=user,
                active_role="nir",
                lock_token=token,
            )

        t_corr, res_corr = self._run_in_thread(run_correction, "correction-race")
        assert correction_locked.wait(timeout=30), "correção não adquiriu o row lock"

        # Confirmação inicia enquanto a correção segura o lock: bloqueia.
        t_conf, res_conf = self._run_in_thread(run_confirm, "confirm-race")

        let_correction_finish.set()
        t_corr.join(timeout=30)
        t_conf.join(timeout=30)
        assert not t_corr.is_alive() and not t_conf.is_alive()

        assert res_corr["ok"] is True
        assert res_conf["ok"] is False  # confirmação perdeu

        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == ExamType.COLONOSCOPY
        assert reloaded.structured_data is None
        assert not CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").exists()
        assert pipeline_calls == [case.case_id]

    def test_confirm_holds_lock_then_correction_rejected(self, django_user_model, monkeypatch) -> None:
        """Confirmação segura o row lock; correção bloqueia e depois perde."""
        pipeline_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-race-conf@test.com")
        case = _eligible_case(user=user)
        token = _claim_receipt_lease(case, user)

        confirm_locked = threading.Event()
        let_confirm_finish = threading.Event()

        def coordinated_assert(*, case, user, token, context) -> None:  # noqa: ARG001
            real_assert_case_lock(case=case, user=user, token=token, context=context)
            if threading.current_thread().name == "confirm-race" and not confirm_locked.is_set():
                confirm_locked.set()
                assert let_confirm_finish.wait(timeout=30), "timeout aguardando liberação"

        monkeypatch.setattr("apps.cases.services.assert_case_lock", coordinated_assert)

        def run_confirm() -> Case:
            return confirm_case_receipt(
                case_id=case.case_id,
                user=user,
                active_role="nir",
                lock_token=token,
            )

        def run_correction() -> Case:
            return correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        t_conf, res_conf = self._run_in_thread(run_confirm, "confirm-race")
        assert confirm_locked.wait(timeout=30), "confirmação não adquiriu o row lock"

        # Correção inicia enquanto a confirmação segura o lock: bloqueia.
        t_corr, res_corr = self._run_in_thread(run_correction, "correction-race")

        let_confirm_finish.set()
        t_conf.join(timeout=30)
        t_corr.join(timeout=30)
        assert not t_conf.is_alive() and not t_corr.is_alive()

        assert res_conf["ok"] is True
        assert res_corr["ok"] is False  # correção perdeu

        reloaded = Case.objects.get(pk=case.case_id)
        assert reloaded.status == CaseStatus.CLEANED
        assert reloaded.exam_type == ExamType.EDA
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert pipeline_calls == []  # correção perdedora não enfileira


# ═══════════════════════════════════════════════════════════════════════════
# RR1–RR3 — routing do recovery ao cluster pdf (Schedule django-q2)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRecoveryClusterRouting:
    """RR1/RR2/RR3: Schedule de recovery aponta ao cluster 'pdf' implantado e
    ONCE é removido após o dispatch (sem nome residual bloqueando o mesmo caso)."""

    @staticmethod
    def _fail_first_enqueue(monkeypatch, calls: list[object]) -> None:
        """Faz o primeiro enqueue_pipeline falhar; PDF nunca pode ser enfileirado."""

        def fail_enqueue(case_id) -> None:
            calls.append(case_id)
            raise RuntimeError("fila indisponível")

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", fail_enqueue)
        monkeypatch.setattr(
            "apps.intake.tasks.enqueue_pdf_extraction",
            lambda case_id: pytest.fail("PDF não deve ser enfileirado"),
        )

    def test_recovery_schedule_targets_pdf_cluster(self, django_user_model, monkeypatch) -> None:
        """RR1: Schedule.cluster == 'pdf' (dev/prod rodam apenas llm e pdf)."""
        from django_q.models import Schedule

        self._fail_first_enqueue(monkeypatch, [])
        user = _nir_user(django_user_model, "nir-rr1@test.com")
        case = _eligible_case(user=user, extracted_text=_regulation_pass_text())
        token = _claim_receipt_lease(case, user)

        with pytest.raises(EnqueueAfterCommitError) as caught:
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )
        assert caught.value.recovery_scheduled is True

        recovery = Schedule.objects.get(name=f"slice006-recovery:{case.case_id}")
        assert recovery.cluster == "pdf", (
            "Schedule.cluster NULL só é consumido pelo cluster default 'ats', "
            "não implantado; dev/prod rodam apenas Q_CLUSTER_NAME=llm e pdf."
        )
        assert recovery.func == "apps.intake.tasks.execute_pdf_extraction"
        assert str(case.case_id) in (recovery.args or "")
        assert recovery.repeats < 0  # ONCE default → deletado após o dispatch

    @pytest.mark.django_db(transaction=True)
    def test_pdf_scheduler_dispatches_recovery(self, django_user_model, monkeypatch) -> None:
        """RR2: scheduler real do cluster pdf seleciona e despacha o Schedule."""
        import importlib
        from datetime import timedelta

        from django.utils import timezone
        from django_q.conf import Conf
        from django_q.models import Schedule

        enqueue_calls: list[object] = []
        self._fail_first_enqueue(monkeypatch, enqueue_calls)
        dispatched: list[tuple[tuple[object, ...], dict[str, object]]] = []
        monkeypatch.setattr(Conf, "CLUSTER_NAME", "pdf")
        monkeypatch.setattr(
            "django_q.scheduler.async_task",
            lambda *args, **kwargs: dispatched.append((args, kwargs)),
        )

        user = _nir_user(django_user_model, "nir-rr2@test.com")
        case = _eligible_case(user=user, extracted_text=_regulation_pass_text())
        token = _claim_receipt_lease(case, user)

        with pytest.raises(EnqueueAfterCommitError) as caught:
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )
        assert caught.value.recovery_scheduled is True
        # Uma única tentativa imediata de enqueue (falhou); zero enqueue de PDF.
        assert enqueue_calls == [case.case_id]
        assert Case.objects.get(pk=case.case_id).status == CaseStatus.LLM_STRUCT

        # Torna o Schedule vencido e roda o scheduler REAL do cluster pdf.
        Schedule.objects.filter(name=f"slice006-recovery:{case.case_id}").update(
            next_run=timezone.now() - timedelta(seconds=5)
        )
        scheduler_module = importlib.import_module("django_q.scheduler")
        scheduler_module.scheduler(broker=object())

        assert len(dispatched) == 1, f"scheduler pdf não despachou o recovery: {dispatched}"
        args, kwargs = dispatched[0]
        assert args[0] == "apps.intake.tasks.execute_pdf_extraction"
        assert args[1] == str(case.case_id)
        q_options = kwargs["q_options"]
        assert isinstance(q_options, dict)
        assert q_options.get("cluster") == "pdf"

        # ONCE default foi DELETADO após o dispatch (RR3 — sem nome residual).
        assert not Schedule.objects.filter(name=f"slice006-recovery:{case.case_id}").exists()

    @pytest.mark.django_db(transaction=True)
    def test_once_removed_allows_new_recovery_for_same_case(self, django_user_model, monkeypatch) -> None:
        """RR3: após o dispatch, o mesmo case_id pode ter novo recovery."""
        import importlib
        from datetime import timedelta

        from django.utils import timezone
        from django_q.conf import Conf
        from django_q.models import Schedule

        from apps.intake.services import _schedule_pipeline_recovery

        enqueue_calls: list[object] = []
        self._fail_first_enqueue(monkeypatch, enqueue_calls)
        dispatched: list[tuple[tuple[object, ...], dict[str, object]]] = []
        monkeypatch.setattr(Conf, "CLUSTER_NAME", "pdf")
        monkeypatch.setattr(
            "django_q.scheduler.async_task",
            lambda *args, **kwargs: dispatched.append((args, kwargs)),
        )

        user = _nir_user(django_user_model, "nir-rr3@test.com")
        case = _eligible_case(user=user, extracted_text=_regulation_pass_text())
        token = _claim_receipt_lease(case, user)

        with pytest.raises(EnqueueAfterCommitError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        # Despacha o ONCE pelo scheduler do cluster pdf.
        Schedule.objects.filter(name=f"slice006-recovery:{case.case_id}").update(
            next_run=timezone.now() - timedelta(seconds=5)
        )
        importlib.import_module("django_q.scheduler").scheduler(broker=object())
        assert len(dispatched) == 1
        assert not Schedule.objects.filter(name=f"slice006-recovery:{case.case_id}").exists()

        # Novo recovery do MESMO caso: sem IntegrityError e novo Schedule criado.
        _schedule_pipeline_recovery(case.case_id)
        assert Schedule.objects.filter(name=f"slice006-recovery:{case.case_id}").exists()

    @pytest.mark.django_db(transaction=True)
    def test_llm_cluster_does_not_dispatch_pdf_recovery(self, django_user_model, monkeypatch) -> None:
        """Scheduler do cluster llm NÃO consome Schedule direcionado ao pdf."""
        import importlib
        from datetime import timedelta

        from django.utils import timezone
        from django_q.conf import Conf
        from django_q.models import Schedule

        from apps.intake.services import _schedule_pipeline_recovery

        dispatched: list[object] = []
        monkeypatch.setattr(Conf, "CLUSTER_NAME", "llm")
        monkeypatch.setattr(
            "django_q.scheduler.async_task",
            lambda *args, **kwargs: dispatched.append((args, kwargs)),
        )
        user = _nir_user(django_user_model, "nir-rr4@test.com")
        case = _eligible_case(user=user, extracted_text=_regulation_pass_text())

        _schedule_pipeline_recovery(case.case_id)
        Schedule.objects.filter(name=f"slice006-recovery:{case.case_id}").update(
            next_run=timezone.now() - timedelta(seconds=5)
        )
        importlib.import_module("django_q.scheduler").scheduler(broker=object())

        assert dispatched == []
        # O Schedule permanece para o cluster pdf consumir.
        assert Schedule.objects.filter(name=f"slice006-recovery:{case.case_id}").exists()


# ═══════════════════════════════════════════════════════════════════════════
# R6/R7 — view NIR, idempotência e exclusão mútua com confirm receipt
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCorrectionView:
    """R6/R7: UI NIR, POST protegido, idempotência e exclusão mútua."""

    def _lock_token_for(self, case_id) -> str:
        return str(Case.objects.get(pk=case_id).lock_token)

    def test_get_detail_shows_correction_card_when_eligible(self, client) -> None:
        """R6: caso elegível mostra card com declarado/detectado/motivo e form."""
        client, user = _nir_client(client)
        case = _eligible_case(user=user)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Correção de Tipo de Exame" in content
        assert "Tipo declarado" in content
        assert "Tipo detectado" in content
        assert "Colonoscopia" in content
        assert reverse("intake:exam_type_correction", args=[case.case_id]) in content

    def test_get_detail_hides_card_when_not_manual_review(self, client) -> None:
        """R6: caso sem manual review elegível não mostra o card."""
        client, user = _nir_client(client)
        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        assert "Correção de Tipo de Exame" not in response.content.decode()

    def test_post_success_corrects_and_redirects(self, client, monkeypatch) -> None:
        """R6: POST NIR válido corrige, redireciona e enfileira 1x."""
        pipeline_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        client, user = _nir_client(client)
        case = _eligible_case(user=user)

        client.get(reverse("intake:case_detail", args=[case.case_id]))
        token = self._lock_token_for(case.case_id)

        response = client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": ExamType.COLONOSCOPY, "reason_code": "nir_identified_exam", "lock_token": token},
        )
        assert response.status_code == 302

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == ExamType.COLONOSCOPY
        assert len(pipeline_calls) == 1

    def test_second_post_idempotent_no_double_enqueue(self, client, monkeypatch) -> None:
        """R7: segundo POST com estado já movido não enfileira novamente."""
        pipeline_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        client, user = _nir_client(client)
        case = _eligible_case(user=user)

        client.get(reverse("intake:case_detail", args=[case.case_id]))
        token = self._lock_token_for(case.case_id)
        url = reverse("intake:exam_type_correction", args=[case.case_id])

        first = client.post(
            url,
            {"exam_type": ExamType.COLONOSCOPY, "reason_code": "nir_identified_exam", "lock_token": token},
        )
        assert first.status_code == 302
        assert len(pipeline_calls) == 1

        # Estado já LLM_STRUCT → POST inelegível retorna 404 seguro
        second = client.post(
            url,
            {"exam_type": ExamType.EDA, "reason_code": "nir_identified_exam", "lock_token": token},
        )
        assert second.status_code == 404
        assert len(pipeline_calls) == 1

    def test_post_ineligible_returns_404(self, client) -> None:
        """R6: POST em caso inelegível retorna 404 sem mutação."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.WAIT_R1_CLEANUP_THUMBS)

        response = client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": ExamType.COLONOSCOPY, "reason_code": "nir_identified_exam"},
        )
        assert response.status_code == 404
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA

    def test_doctor_cannot_post(self, client) -> None:
        """R6: role doctor é bloqueada no POST de correção."""
        client, user = _doctor_client(client)
        case = _eligible_case(user=user)

        response = client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": ExamType.COLONOSCOPY, "reason_code": "nir_identified_exam"},
        )
        assert response.status_code == 302
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA

    def test_post_without_lock_token_rejected(self, client) -> None:
        """R6/R7: POST sem token de reserva é rejeitado sem mutação."""
        client, user = _nir_client(client)
        case = _eligible_case(user=user)

        response = client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": ExamType.COLONOSCOPY, "reason_code": "nir_identified_exam"},
        )
        assert response.status_code == 302
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA

    def test_confirm_receipt_not_executed_after_correction(self, client, monkeypatch) -> None:
        """R7: após correção, confirm receipt não roda (estado saiu da fila)."""
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )
        client, user = _nir_client(client)
        case = _eligible_case(user=user)

        client.get(reverse("intake:case_detail", args=[case.case_id]))
        token = self._lock_token_for(case.case_id)
        client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": ExamType.COLONOSCOPY, "reason_code": "nir_identified_exam", "lock_token": token},
        )
        assert Case.objects.get(pk=case.pk).status == CaseStatus.LLM_STRUCT

        # POST confirm com token antigo (lock já limpo) não transiciona
        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )
        assert response.status_code == 302
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert not CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").exists()

    # ── C5: mensagens da view (pós-commit vs pré-commit) ──────────────────

    def test_precommit_failure_shows_no_corrected_message(self, client, monkeypatch) -> None:
        """Falha pré-commit não mostra 'tipo corrigido' nem muta o caso."""
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pytest.fail("não deve enfileirar em falha pré-commit"),
        )
        client, user = _nir_client(client)
        case = _eligible_case(user=user)

        client.get(reverse("intake:case_detail", args=[case.case_id]))
        token = self._lock_token_for(case.case_id)

        response = client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": "cpre", "reason_code": "nir_identified_exam", "lock_token": token},
            follow=True,
        )
        content = response.content.decode()
        assert "Tipo de exame corrigido para" not in content
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert reloaded.structured_data is not None

    def test_postcommit_enqueue_failure_shows_error_not_success(self, client, monkeypatch) -> None:
        """Falha pós-commit de enqueue mostra erro verdadeiro (retry agendado)."""

        def _boom(case_id) -> None:  # noqa: ARG001
            raise RuntimeError("fila indisponível")

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", _boom)
        client, user = _nir_client(client)
        case = _eligible_case(user=user)

        client.get(reverse("intake:case_detail", args=[case.case_id]))
        token = self._lock_token_for(case.case_id)

        response = client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": ExamType.COLONOSCOPY, "reason_code": "nir_identified_exam", "lock_token": token},
            follow=True,
        )
        content = response.content.decode()
        assert "reprocessamento automático não pôde ser agendado" in content
        assert "Tipo de exame corrigido para" not in content
        # A correção foi aplicada (commit) mesmo com a falha de enqueue.
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == ExamType.COLONOSCOPY


# ═══════════════════════════════════════════════════════════════════════════
# R5 — labels da timeline
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTimelineLabels:
    """R5: labels/dots legíveis para os novos eventos na timeline NIR."""

    def test_event_maps_contain_new_events(self) -> None:
        from apps.intake import views

        assert "CASE_PROCEDURE_DECLARATION_CORRECTED" in views.EVENT_LABELS
        assert "CASE_REPROCESSING_REQUESTED" in views.EVENT_LABELS
        assert views.EVENT_LABELS["CASE_PROCEDURE_DECLARATION_CORRECTED"].strip()
        assert views.EVENT_LABELS["CASE_REPROCESSING_REQUESTED"].strip()
        assert "CASE_PROCEDURE_DECLARATION_CORRECTED" in views.EVENT_DOT_CSS
        assert "CASE_REPROCESSING_REQUESTED" in views.EVENT_DOT_CSS

    def test_detail_renders_new_event_labels(self, client) -> None:
        """Timeline do detalhe NIR renderiza labels dos eventos de correção."""
        client, user = _nir_client(client)
        case = _eligible_case(user=user)
        # Mesma ordem de eventos do serviço: CASE_PROCEDURE_DECLARATION_CORRECTED
        # antes do CASE_REPROCESSING_REQUESTED (append-only).
        case._record_event(
            "CASE_PROCEDURE_DECLARATION_CORRECTED",
            user=user,
            payload={
                "old_procedures": [ExamType.EDA],
                "new_procedures": [ExamType.COLONOSCOPY],
                "reason_code": "other",
                "old_exam_type": ExamType.EDA,
                "new_exam_type": ExamType.COLONOSCOPY,
            },
        )
        case.save()
        case.reprocess_after_exam_type_correction(user=user, payload={"reason_code": "other"})
        case.save()

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Conjunto de procedimentos declarado corrigido pelo NIR" in content
        assert "Reprocessamento solicitado" in content
