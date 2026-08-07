"""Pipeline orchestrator — runs the procedure-neutral v2 LLM pipeline for a case.

Ties together: LLM1 v2 extraction → detection/reconciliation →
per-component preop policy → prior context per procedure →
LLM2 v2 suggestion → support synthesis → FSM transitions.

Slice 007 (D5/D6/ADR-0004): o caminho executável é EXCLUSIVAMENTE o contrato
2.0. O branch 1.1 (``classify_exam_scope``/``Llm1Service``/``Llm2Service`` e os
oito nomes de prompts antigos) foi removido do dispatch — esses módulos/schemas
permanecem como leitores históricos, mas nunca são importados/chamados por um
job novo. Casos sem procedimentos declarados válidos em ``CaseProcedure`` falham
de modo explícito/auditável (R1), nunca caem em perfil singular/EDA.
"""

from __future__ import annotations

import logging
import uuid

from apps.cases.exam_profiles import get_exam_profile
from apps.cases.models import Case
from apps.cases.priority_signals import resolve_priority_signals
from apps.cases.procedures import set_detected_procedures
from apps.llm.models import PromptTemplate
from apps.pipeline.llm import LlmClient
from apps.pipeline.llm1_service_v2 import (
    LLM1_V2_DEFAULT_SYSTEM_PROMPT,
    LLM1_V2_DEFAULT_USER_PROMPT,
    Llm1ServiceV2,
    Llm1V2Result,
)
from apps.pipeline.llm2_service_v2 import (
    LLM2_V2_DEFAULT_SYSTEM_PROMPT,
    LLM2_V2_DEFAULT_USER_PROMPT,
    Llm2ServiceV2,
    strictest_global_support,
)
from apps.pipeline.policy import (
    EdaPolicyPrecheckInput,
    Llm2PolicyAlignmentInput,
    Llm2SuggestionInput,
    evaluate_preop_policy,
    reconcile_eda_policy,
    synthesize_eda_support_context,
)
from apps.pipeline.prior_case import PriorCaseContext, lookup_prior_case_context
from apps.pipeline.procedure_reconciliation import (
    build_v2_review_payload,
    reconcile_detected_procedures,
)
from apps.pipeline.schemas.adapters import project_v2_to_llm1_shape
from apps.pipeline.scope_detection import detect_requested_procedures_v2

logger = logging.getLogger(__name__)


def run_pipeline(
    case_id: uuid.UUID,
    *,
    llm_client: LlmClient | None = None,
    llm1_system_prompt: str | None = None,
    llm1_user_template: str | None = None,
    llm2_system_prompt: str | None = None,
    llm2_user_template: str | None = None,
) -> None:
    """Orchestrate the procedure-neutral v2 LLM pipeline for a case.

    FSM flow (happy path):
        LLM_STRUCT → LLM_SUGGEST → R2_POST_WIDGET → WAIT_DOCTOR
    On error at any step: → FAILED

    All injectable parameters default to production values (settings/DB).
    Override them in tests to avoid needing DB templates or real LLM calls.

    R1: o pipeline é exclusivamente v2. Caso sem 1–2 procedimentos declarados
    válidos em ``CaseProcedure`` falha de modo explícito/auditável (PIPELINE_FAILED),
    sem cair em perfil singular/EDA nem em prompt 1.1.
    """
    case = Case.objects.get(case_id=case_id)

    # Use separate stage-specific clients in production mode.
    # When a single client is injected (tests), use it for both.
    if llm_client is None:
        from apps.pipeline.llm import create_openai_llm1_client, create_openai_llm2_client

        client_llm1: LlmClient = create_openai_llm1_client()
        client_llm2: LlmClient = create_openai_llm2_client()
    else:
        client_llm1 = llm_client
        client_llm2 = llm_client

    try:
        _run_v2_pipeline(
            case=case,
            client_llm1=client_llm1,
            client_llm2=client_llm2,
            llm1_system_prompt=llm1_system_prompt,
            llm1_user_template=llm1_user_template,
            llm2_system_prompt=llm2_system_prompt,
            llm2_user_template=llm2_user_template,
        )
    except Exception as exc:
        logger.exception("Pipeline failed for case %s", case_id)
        try:
            case._record_event(
                "PIPELINE_FAILED",
                payload={"error": str(exc)},
            )
            case.save()  # persist PIPELINE_FAILED event before FSM transition
            _try_fail_case(case)
        except Exception:
            logger.exception("Failed to record pipeline failure for case %s", case_id)


# ── V2 pipeline (procedure-neutral — Slice 002/007) ────────────────────────


_PROCEDURE_TYPES: tuple[str, ...] = ("eda", "colonoscopy")


class DeclaredProceduresMissingError(Exception):
    """Caso sem procedimentos declarados válidos na projeção ``CaseProcedure``."""


def _require_declared_procedures(case: Case) -> tuple[str, ...]:
    """Declaração autoritativa de ``CaseProcedure`` (sem fallback da ponte).

    Novos jobs exigem 1–2 procedimentos declarados válidos (R1/ADR-0004). A
    leitura é feita diretamente das rows ``declared_by_nir=True`` — não usa o
    fallback transitório de ``Case.exam_type`` — para que um caso sem projeção
    falhe de modo explícito/auditável em vez de cair em perfil singular/EDA.
    """
    declared = sorted(
        (
            row.procedure_type
            for row in case.procedures.filter(declared_by_nir=True)
            if row.procedure_type in _PROCEDURE_TYPES
        ),
        key=lambda t: _PROCEDURE_TYPES.index(t),
    )
    if not declared:
        raise DeclaredProceduresMissingError(
            f"Pipeline v2 exige procedimentos declarados em CaseProcedure (case_id={case.case_id}); nenhum encontrado."
        )
    return tuple(declared)


def _resolve_prompt(name: str) -> tuple[str, int]:
    """Resolve conteúdo + versão de um prompt ativo (fallback com versão 0)."""
    template = PromptTemplate.get_active(name)
    if template is not None:
        return template.content, template.version
    return _get_prompt_content(name), 0


def _collect_v2_evidence_spans(structured_data: dict[str, object]) -> list[dict[str, str]]:
    """Spans comuns + por procedimento para payload enxuto de revisão (R8)."""
    spans: list[dict[str, str]] = []
    common = structured_data.get("common_preop")
    if isinstance(common, dict):
        raw = common.get("evidence_spans")
        if isinstance(raw, list):
            spans.extend(item for item in raw if isinstance(item, dict))
    raw_procedures = structured_data.get("requested_procedures")
    if isinstance(raw_procedures, list):
        for procedure in raw_procedures:
            if not isinstance(procedure, dict):
                continue
            raw_spans = procedure.get("evidence_spans")
            if isinstance(raw_spans, list):
                spans.extend(item for item in raw_spans if isinstance(item, dict))
    return spans


def _run_v2_pipeline(
    *,
    case: Case,
    client_llm1: LlmClient,
    client_llm2: LlmClient,
    llm1_system_prompt: str | None,
    llm1_user_template: str | None,
    llm2_system_prompt: str | None,
    llm2_user_template: str | None,
) -> None:
    """Pipeline procedure-neutral 2.0 (uma chamada por estágio).

    Fluxo entregue (R1–R8): LLM1 v2 (história comum + requested_procedures) →
    detecção/reconciliação D7 → projeção atômica → policy por componente →
    prior context por componente (D10) → LLM2 v2 (conjunto exato) → suporte
    global mais restritivo → WAIT_DOCTOR com relatório neutro legível. Gates de
    revisão NIR (combined→single, mismatch, unknown) nunca executam LLM2.
    """
    declared = _require_declared_procedures(case)

    # ── 1. LLM1 v2 — uma chamada ────────────────────────────────────────
    if llm1_system_prompt is not None:
        sp1, sp1_version = llm1_system_prompt, 0
    else:
        sp1, sp1_version = _resolve_prompt("exam_llm1_system")
    if llm1_user_template is not None:
        ut1, ut1_version = llm1_user_template, 0
    else:
        ut1, ut1_version = _resolve_prompt("exam_llm1_user")

    service1 = Llm1ServiceV2(client_llm1)
    result1 = service1.run(
        case_id=str(case.case_id),
        agency_record_number=case.agency_record_number,
        extracted_text=case.extracted_text,
        declared_procedure_types=declared,
        system_prompt=sp1,
        user_prompt_template=ut1,
        prompt_system_version=sp1_version,
        prompt_user_version=ut1_version,
    )

    case.structured_data = result1.structured_data
    case.summary_text = result1.summary_text

    # ── 2. Detecção + reconciliação (D7) ───────────────────────────────
    detection = detect_requested_procedures_v2(
        llm1_structured_data=result1.structured_data,
        cleaned_text=case.extracted_text,
    )
    strong = tuple(t for t in _PROCEDURE_TYPES if detection[t]["strong"])
    any_evidence = tuple(t for t in _PROCEDURE_TYPES if detection[t]["any"])
    reconciliation = reconcile_detected_procedures(
        declared=declared,
        strong=strong,
        any_evidence=any_evidence,
    )

    # ── 3. Projeção de detecção atômica (R4) ───────────────────────────
    set_detected_procedures(
        case=case,
        detected_types=reconciliation.detected_procedure_types,
    )

    # Sinais prioritários por projeção compatível (R5): EDA quando presente,
    # senão Colonoscopia (perfil restringe códigos permitidos).
    signals_type = "eda" if "eda" in reconciliation.detected_procedure_types else "colonoscopy"
    signals_projection = project_v2_to_llm1_shape(
        v2_data=result1.structured_data,
        procedure_type=signals_type,
    )
    case.priority_signals = resolve_priority_signals(
        structured_data=signals_projection,
        source_text=case.extracted_text,
        exam_type=signals_type,
    )

    # ── 4. Eventos de detecção (R8: versões de schema/prompt + conjuntos) ─
    detection_payload: dict[str, object] = {
        "schema_version": "2.0",
        "declared_procedures": list(declared),
        "detected_procedures": list(reconciliation.detected_procedure_types),
        "reason_code": reconciliation.reason_code,
        "prompt_system_name": result1.prompt_system_name,
        "prompt_system_version": result1.prompt_system_version,
        "prompt_user_name": result1.prompt_user_name,
        "prompt_user_version": result1.prompt_user_version,
    }
    case._record_event("CASE_PROCEDURES_DETECTED", payload=detection_payload)
    case.save()
    if reconciliation.upgraded:
        case._record_event(
            "PROCEDURE_SELECTION_AUTO_UPGRADED",
            payload={
                "schema_version": "2.0",
                "declared_procedures": list(declared),
                "detected_procedures": list(reconciliation.detected_procedure_types),
                "reason_code": reconciliation.reason_code,
            },
        )
        case.save()

    # ── 5. Gate de revisão NIR (sem LLM2) ──────────────────────────────
    if reconciliation.action == "nir_review":
        review_payload = build_v2_review_payload(
            case_id=str(case.case_id),
            agency_record_number=case.agency_record_number,
            reason_code=reconciliation.reason_code,
            reason_text=reconciliation.reason_text,
            declared=declared,
            detected=reconciliation.detected_procedure_types,
            evidence_spans=_collect_v2_evidence_spans(result1.structured_data),
        )
        case.suggested_action = review_payload
        case.save()
        case._record_event(
            "EDA_SCOPE_GATED_MANUAL_REVIEW",
            payload=review_payload,
        )
        case.save()
        reason_code = str(review_payload.get("reason_code", ""))
        case.scope_gate_bypass(reason_code=reason_code)
        case.save()
        case._record_event("FINAL_REPLY_POSTED")
        case.save()
        return

    # ── 6. LLM1 concluído (LLM_STRUCT → LLM_SUGGEST) ──────────────────
    case.llm1_complete(success=True, user=None, payload=_build_v2_llm1_ok_payload(case, result1))
    case.save()

    # ── 7. Policy determinística por componente (R5/D8) ────────────────
    policy_results: dict[str, dict[str, object]] = {}
    for procedure_type in reconciliation.detected_procedure_types:
        projection = project_v2_to_llm1_shape(
            v2_data=result1.structured_data,
            procedure_type=procedure_type,
        )
        decision = evaluate_preop_policy(structured_data=projection, exam_type=procedure_type)
        policy_results[procedure_type] = decision
        case._record_event(
            "EDA_PREOP_POLICY_DECISION",
            payload={**decision, "procedure_type": procedure_type, "schema_version": "2.0"},
        )
        case.save()

    # ── 8. Prior case por componente (D10) ─────────────────────────────
    prior_contexts: dict[str, dict[str, object]] = {}
    for procedure_type in reconciliation.detected_procedure_types:
        context = lookup_prior_case_context(
            case_id=case.case_id,
            agency_record_number=case.agency_record_number,
            procedure_type=procedure_type,
        )
        prior_contexts[procedure_type] = _serialize_prior_context(context)
        if context.prior_case is not None:
            case._record_event(
                "PRIOR_CASE_LOOKUP",
                payload={
                    "procedure_type": procedure_type,
                    "schema_version": "2.0",
                    "prior_case_id": context.prior_case.prior_case_id,
                    "decision": context.prior_case.decision,
                    "reason": context.prior_case.reason,
                    "decided_at": context.prior_case.decided_at,
                    "decided_by": context.prior_case.decided_by,
                    "decided_by_role": context.prior_case.decided_by_role,
                    "prior_denial_count_7d": context.prior_denial_count_7d,
                },
            )
            case.save()

    # ── 9. LLM2 v2 — uma chamada com conjunto exato (R6) ──────────────
    if llm2_system_prompt is not None:
        sp2, sp2_version = llm2_system_prompt, 0
    else:
        sp2, sp2_version = _resolve_prompt("exam_llm2_system")
    if llm2_user_template is not None:
        ut2, ut2_version = llm2_user_template, 0
    else:
        ut2, ut2_version = _resolve_prompt("exam_llm2_user")

    service2 = Llm2ServiceV2(client_llm2)
    result2 = service2.run(
        case_id=str(case.case_id),
        agency_record_number=case.agency_record_number,
        llm1_structured_data=result1.structured_data,
        detected_procedure_types=reconciliation.detected_procedure_types,
        policy_results=policy_results,
        prior_contexts=prior_contexts,
        system_prompt=sp2,
        user_prompt_template=ut2,
    )

    # ── 10. Reconciliação por item + suporte global (D8) ──────────────
    recommendations: list[dict[str, object]] = []
    for item in result2.procedure_recommendations:
        procedure_type = str(item["procedure_type"])
        projection = project_v2_to_llm1_shape(
            v2_data=result1.structured_data,
            procedure_type=procedure_type,
        )
        profile = get_exam_profile(procedure_type)
        precheck = _build_policy_precheck(
            projection,
            allow_foreign_body_exception=profile.allows_foreign_body_exception,
        )
        reconciled = reconcile_eda_policy(precheck=precheck, llm2=_build_llm2_suggestion_input(item))
        # Invariante legada (R5/R6): a política determinística vence o LLM. Se
        # ``evaluate_preop_policy`` negou (exames mínimos, thresholds, gates
        # condicionais), a sugestão final do item é ``deny``.
        suggestion = reconciled.suggestion
        if policy_results[procedure_type].get("decision") == "deny":
            suggestion = "deny"
        support_ctx = synthesize_eda_support_context(structured_data=projection)
        contradictions = [
            {
                "rule": c.rule,
                "field": c.field,
                "previous_value": c.previous_value,
                "reconciled_value": c.reconciled_value,
            }
            for c in reconciled.contradictions
        ]
        recommendations.append(
            {
                **item,
                "suggestion": suggestion,
                "policy_alignment": {
                    "excluded_request": reconciled.policy_alignment.excluded_request,
                    "labs_ok": reconciled.policy_alignment.labs_ok,
                    "ecg_ok": reconciled.policy_alignment.ecg_ok,
                    "pediatric_flag": reconciled.policy_alignment.pediatric_flag,
                    "notes": reconciled.policy_alignment.notes,
                },
                "contradictions": contradictions,
                # Suporte por componente é recomendação (soft) do LLM2 v2;
                # a síntese determinística de ASA segue apenas para exibição.
                "support_recommendation": item["support_recommendation"],
                "asa": {
                    "bucket": support_ctx.asa_bucket,
                    "display_text": support_ctx.asa_display,
                },
                "preop_decision": policy_results[procedure_type],
            }
        )

    global_support = strictest_global_support(tuple(str(r["support_recommendation"]) for r in recommendations))
    case.suggested_action = {
        "schema_version": "2.0",
        "procedure_recommendations": recommendations,
        "global_support_recommendation": global_support,
    }
    case.save()

    # ── 11. Transições finais (LLM_SUGGEST → R2_POST_WIDGET → WAIT_DOCTOR) ─
    # llm2_complete não aceita payload (ao contrário de llm1_complete); o evento
    # LLM2_OK do fluxo v2 é re-registrado com payload enxuto ANTES do save — o
    # slot _pending_event é sobrescrito, persistindo exatamente UM evento com a
    # auditoria de prompt/schema (R8), sem alterar FSM.
    case.llm2_complete(success=True, user=None)
    case._record_event(
        "LLM2_OK",
        payload=_build_v2_llm2_ok_payload(
            case=case,
            prompt_system_version=sp2_version,
            prompt_user_version=ut2_version,
            detected_procedure_types=reconciliation.detected_procedure_types,
        ),
    )
    case.save()
    case.ready_for_doctor()
    case.save()
    case._record_event("CASE_READY_FOR_DOCTOR")
    case.save()


def _build_v2_llm1_ok_payload(case: Case, result1: Llm1V2Result) -> dict[str, object]:
    """Payload enxuto de LLM1_OK para contrato 2.0 (sem texto clínico integral)."""
    return {
        "schema_version": "2.0",
        "summary_text": case.summary_text,
        "priority_signal_codes": [signal["code"] for signal in case.priority_signals],
        "prompt_system_name": result1.prompt_system_name,
        "prompt_system_version": result1.prompt_system_version,
        "prompt_user_name": result1.prompt_user_name,
        "prompt_user_version": result1.prompt_user_version,
    }


def _build_v2_llm2_ok_payload(
    *,
    case: Case,
    prompt_system_version: int,
    prompt_user_version: int,
    detected_procedure_types: tuple[str, ...],
) -> dict[str, object]:
    """Payload enxuto de LLM2_OK para o fluxo v2 (R8, sem texto clínico)."""
    return {
        "schema_version": "2.0",
        "prompt_system_name": "exam_llm2_system",
        "prompt_system_version": prompt_system_version,
        "prompt_user_name": "exam_llm2_user",
        "prompt_user_version": prompt_user_version,
        "detected_procedures": list(detected_procedure_types),
    }


def _serialize_prior_context(context: PriorCaseContext) -> dict[str, object]:
    """Serializa PriorCaseContext por componente para o prompt do LLM2 (D10)."""
    if context.prior_case is None:
        return {"prior_case": None, "prior_denial_count_7d": context.prior_denial_count_7d}
    return {
        "prior_case": {
            "prior_case_id": context.prior_case.prior_case_id,
            "decided_at": context.prior_case.decided_at,
            "decision": context.prior_case.decision,
            "reason": context.prior_case.reason,
            "decided_by": context.prior_case.decided_by,
            "decided_by_role": context.prior_case.decided_by_role,
        },
        "prior_denial_count_7d": context.prior_denial_count_7d,
    }


# ── Shared policy/reconciliation helpers ────────────────────────────────────


def _build_policy_precheck(
    structured_data: dict[str, object],
    *,
    allow_foreign_body_exception: bool = True,
) -> EdaPolicyPrecheckInput:
    """Build EdaPolicyPrecheckInput from LLM1 structured_data.

    When the profile does not allow the foreign-body exception (colonoscopy),
    the foreign-body indication does not unlock EDA's alignment overrides (R4).
    """
    eda = _get_dict(structured_data, "eda")
    preop = _get_dict(structured_data, "preop_screening")
    rulebook = _get_dict(preop, "rulebook_signals")

    excluded = _get_bool(rulebook, "excluded_from_eda_flow")
    indication = str(eda.get("indication_category", "") or "")
    if not allow_foreign_body_exception and indication == "foreign_body":
        indication = ""

    return EdaPolicyPrecheckInput(
        excluded_from_eda_flow=excluded,
        indication_category=indication,
        labs_required=_get_text(rulebook, "labs_required") == "yes",
        labs_pass=_get_text(rulebook, "labs_pass") or "unknown",  # type: ignore[arg-type]
        ecg_required=_get_text(rulebook, "ecg_required") == "yes",
        ecg_present=_get_text(rulebook, "ecg_present") or "unknown",  # type: ignore[arg-type]
        pediatric_flag=_is_pediatric(structured_data),
    )


def _build_llm2_suggestion_input(suggested_action: dict[str, object]) -> Llm2SuggestionInput:
    """Build Llm2SuggestionInput from LLM2 suggested_action dict."""
    suggestion = str(suggested_action.get("suggestion", "deny"))
    pa = _get_dict(suggested_action, "policy_alignment")

    alignment = Llm2PolicyAlignmentInput(
        excluded_request=bool(pa.get("excluded_request", False)),
        labs_ok=str(pa.get("labs_ok", "unknown")),  # type: ignore[arg-type]
        ecg_ok=str(pa.get("ecg_ok", "unknown")),  # type: ignore[arg-type]
        pediatric_flag=bool(pa.get("pediatric_flag", False)),
        notes=_get_text_or_none(pa, "notes"),
    )

    return Llm2SuggestionInput(
        suggestion=suggestion,  # type: ignore[arg-type]
        policy_alignment=alignment,
    )


# ── Prompt helpers ───────────────────────────────────────────────────────────


def _get_prompt_content(name: str) -> str:
    """Resolve prompt content from DB or return a neutral-name fallback.

    Slice 007 (R3): o fallback contém SOMENTE os quatro nomes neutros
    ``exam_llm{1,2}_{system,user}``. Os oito nomes legados saíram do caminho
    executável; seus defaults permanecem nos módulos históricos 1.1.
    """
    template = PromptTemplate.get_active(name)
    if template is not None:
        return template.content
    logger.warning("PromptTemplate %r not found — using fallback", name)
    fallbacks = {
        "exam_llm1_system": LLM1_V2_DEFAULT_SYSTEM_PROMPT,
        "exam_llm1_user": LLM1_V2_DEFAULT_USER_PROMPT,
        "exam_llm2_system": LLM2_V2_DEFAULT_SYSTEM_PROMPT,
        "exam_llm2_user": LLM2_V2_DEFAULT_USER_PROMPT,
    }
    return fallbacks.get(name, "{case_id}")


# ── Data helpers ─────────────────────────────────────────────────────────────


def _get_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _get_text(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _get_bool(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    return bool(value)


def _get_text_or_none(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _try_fail_case(case: Case) -> None:
    """Attempt to transition case to FAILED, best-effort.

    Tries llm1_complete(success=False) first (valid from LLM_STRUCT),
    then llm2_complete(success=False) (valid from LLM_SUGGEST).
    If neither applies, just saves to persist the PIPELINE_FAILED event.
    """
    from django_fsm import TransitionNotAllowed

    for method in [case.llm1_complete, case.llm2_complete]:
        try:
            method(success=False, user=None)
            case.save()
            return
        except TransitionNotAllowed:
            # A instância já está no estado salvo atual (cada etapa persiste);
            # refresh_from_db violaria a proteção do FSMField e a reatribuição
            # quebraria os métodos bound desta instância.
            continue

    # Could not transition — still persist the event
    case.save()


def _is_pediatric(structured_data: dict[str, object]) -> bool:
    patient = _get_dict(structured_data, "patient")
    age = patient.get("age")
    if isinstance(age, bool):
        return False
    if isinstance(age, int):
        return age < 16
    return False
