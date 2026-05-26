"""Pipeline orchestrator — runs the full LLM pipeline for a case.

Ties together: LLM1 extraction → scope detection → preop policy →
LLM2 suggestion → reconciliation → support synthesis → FSM transitions.
"""

from __future__ import annotations

import logging
import uuid

from apps.cases.models import Case
from apps.llm.models import PromptTemplate
from apps.pipeline.llm import LlmClient
from apps.pipeline.llm1_service import (
    LLM1_DEFAULT_SYSTEM_PROMPT,
    LLM1_DEFAULT_USER_PROMPT,
    Llm1Service,
)
from apps.pipeline.llm2_service import Llm2Service
from apps.pipeline.policy import (
    EdaPolicyPrecheckInput,
    Llm2PolicyAlignmentInput,
    Llm2SuggestionInput,
    evaluate_eda_preop_policy,
    reconcile_eda_policy,
    synthesize_eda_support_context,
)
from apps.pipeline.scope_detection import classify_exam_scope

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
    """Orchestrate the full LLM pipeline for a case.

    FSM flow (happy path):
        LLM_STRUCT → LLM_SUGGEST → R2_POST_WIDGET
    On error at any step: → FAILED

    All injectable parameters default to production values (settings/DB).
    Override them in tests to avoid needing DB templates or real LLM calls.
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
        _run_llm1_step(
            case=case,
            client=client_llm1,
            system_prompt=llm1_system_prompt,
            user_template=llm1_user_template,
        )
        _run_scope_and_llm2(
            case=case,
            client=client_llm2,
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


# ── Step helpers ────────────────────────────────────────────────────────────


def _run_llm1_step(
    *,
    case: Case,
    client: LlmClient,
    system_prompt: str | None,
    user_template: str | None,
) -> None:
    """Run LLM1: structured data extraction + persist artifacts + audit events."""

    sp = system_prompt or _get_prompt_content("llm1_system")
    ut = user_template or _get_prompt_content("llm1_user")

    service = Llm1Service(client)
    result = service.run(
        case_id=str(case.case_id),
        agency_record_number=case.agency_record_number,
        extracted_text=case.extracted_text,
        system_prompt=sp,
        user_prompt_template=ut,
    )

    case.structured_data = result.structured_data
    case.summary_text = result.summary_text
    case.save()
    case._record_event(
        "LLM1_OK",
        payload={"summary_text": result.summary_text},
    )


def _run_scope_and_llm2(
    *,
    case: Case,
    client: LlmClient,
    llm2_system_prompt: str | None,
    llm2_user_template: str | None,
) -> None:
    """Scope detection gate + (optional) LLM2 + policy + reconciliation."""

    assert case.structured_data is not None, "LLM1 must have populated structured_data"

    structured_data: dict[str, object] = case.structured_data

    # ── 1. Scope detection ───────────────────────────────────────
    scope_result = classify_exam_scope(
        llm1_structured_data=structured_data,
        cleaned_text=case.extracted_text,
        case_id=str(case.case_id),
        agency_record_number=case.agency_record_number,
    )

    if scope_result is not None:
        # Non-EDA or unknown — manual review, skip LLM2
        case.suggested_action = scope_result
        case.save()
        case._record_event(
            "EDA_SCOPE_GATED_MANUAL_REVIEW",
            payload=scope_result,
        )
        case.save()  # persist event BEFORE FSM transition overwrites _pending_event
        # Direct transition LLM_STRUCT → WAIT_R1_CLEANUP_THUMBS (no misleading LLM2_OK event)
        reason_code = str(scope_result.get("reason_code", ""))
        case.scope_gate_bypass(reason_code=reason_code)
        case.save()
        case._record_event("FINAL_REPLY_POSTED")
        case.save()
        return

    # ── 2. Transition LLM_STRUCT → LLM_SUGGEST ──────────────────
    case.llm1_complete(success=True, user=None)
    case.save()

    # ── 3. Preop policy (deterministic) ─────────────────────────
    preop_decision = evaluate_eda_preop_policy(structured_data=structured_data)
    case._record_event(
        "EDA_PREOP_POLICY_DECISION",
        payload=preop_decision,
    )

    # ── 4. Prior case lookup ────────────────────────────────────
    from apps.pipeline.prior_case import lookup_prior_case_context

    prior_context = lookup_prior_case_context(
        case_id=case.case_id,
        agency_record_number=case.agency_record_number,
    )

    # Serializa prior_case para dict (ou None) para passar ao LLM2
    prior_case_json: dict[str, object] | None = None
    if prior_context.prior_case is not None:
        prior_case_json = {
            "prior_case_id": prior_context.prior_case.prior_case_id,
            "decided_at": prior_context.prior_case.decided_at,
            "decision": prior_context.prior_case.decision,
            "reason": prior_context.prior_case.reason,
            "prior_denial_count_7d": prior_context.prior_denial_count_7d,
        }
        case._record_event(
            "PRIOR_CASE_LOOKUP",
            payload={
                "prior_case_id": prior_context.prior_case.prior_case_id,
                "decision": prior_context.prior_case.decision,
                "prior_denial_count_7d": prior_context.prior_denial_count_7d,
            },
        )

    # ── 5. LLM2 suggestion ──────────────────────────────────────
    sp2 = llm2_system_prompt or _get_prompt_content("llm2_system")
    ut2 = llm2_user_template or _get_prompt_content("llm2_user")

    service2 = Llm2Service(client)
    result2 = service2.run(
        case_id=str(case.case_id),
        agency_record_number=case.agency_record_number,
        llm1_structured_data=structured_data,
        system_prompt=sp2,
        user_prompt_template=ut2,
        prior_case_json=prior_case_json,
    )

    # ── 6. Reconciliation (LLM2 ⊗ preop policy) ─────────────────
    reconciled = _apply_reconciliation(
        structured_data=structured_data,
        llm2_suggested_action=result2.suggested_action,
        preop_decision=preop_decision,
    )

    # ── 7. Support synthesis ────────────────────────────────────
    support_ctx = synthesize_eda_support_context(structured_data=structured_data)
    reconciled["support_recommendation"] = support_ctx.support_recommendation
    reconciled["asa"] = {
        "bucket": support_ctx.asa_bucket,
        "display_text": support_ctx.asa_display,
    }

    # ── 8. Attach preop gate ────────────────────────────────────
    reconciled["preop_gate"] = preop_decision

    case.suggested_action = reconciled
    case.save()

    # ── 9. Transition LLM_SUGGEST → R2_POST_WIDGET ─────────────
    case.llm2_complete(success=True, user=None)
    case.save()
    case.ready_for_doctor()
    case.save()
    case._record_event(
        "CASE_READY_FOR_DOCTOR",
    )


def _apply_reconciliation(
    *,
    structured_data: dict[str, object],
    llm2_suggested_action: dict[str, object],
    preop_decision: dict[str, object],
) -> dict[str, object]:
    """Reconcile LLM2 output with deterministic preop policy rules.

    Returns a merged suggested_action dict with reconciliation applied
    and contradictions recorded.
    """
    # Extract precheck inputs from LLM1 structured_data
    precheck = _build_policy_precheck(structured_data)

    # Extract LLM2 alignment from its output
    llm2_input = _build_llm2_suggestion_input(llm2_suggested_action)

    # Run reconciliation
    result = reconcile_eda_policy(precheck=precheck, llm2=llm2_input)

    # Start with LLM2's suggested_action as base
    reconciled = dict(llm2_suggested_action)

    # Apply reconciled values
    reconciled["suggestion"] = result.suggestion

    # If deterministic preop policy denies, override suggestion
    if preop_decision.get("decision") == "deny":
        reconciled["suggestion"] = "deny"
    reconciled["policy_alignment"] = {
        "excluded_request": result.policy_alignment.excluded_request,
        "labs_ok": result.policy_alignment.labs_ok,
        "ecg_ok": result.policy_alignment.ecg_ok,
        "pediatric_flag": result.policy_alignment.pediatric_flag,
        "notes": result.policy_alignment.notes,
    }

    # Record contradictions
    contradictions = [
        {"rule": c.rule, "field": c.field, "previous_value": c.previous_value, "reconciled_value": c.reconciled_value}
        for c in result.contradictions
    ]
    reconciled["contradictions"] = contradictions

    # Merge preop decision for audit
    reconciled["preop_decision"] = preop_decision

    return reconciled


def _build_policy_precheck(structured_data: dict[str, object]) -> EdaPolicyPrecheckInput:
    """Build EdaPolicyPrecheckInput from LLM1 structured_data."""
    eda = _get_dict(structured_data, "eda")
    preop = _get_dict(structured_data, "preop_screening")
    rulebook = _get_dict(preop, "rulebook_signals")

    excluded = _get_bool(rulebook, "excluded_from_eda_flow")
    indication = str(eda.get("indication_category", "") or "")

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
    """Resolve prompt content from DB or return a legacy-compatible fallback."""
    template = PromptTemplate.get_active(name)
    if template is not None:
        return template.content
    # Fallback: legacy default contents so the pipeline doesn't crash if
    # templates were not yet seeded. Production MUST seed templates.
    logger.warning("PromptTemplate %r not found — using fallback", name)
    fallbacks = {
        "llm1_system": LLM1_DEFAULT_SYSTEM_PROMPT,
        "llm1_user": LLM1_DEFAULT_USER_PROMPT,
        "llm2_system": (
            "Voce e um assistente de apoio a decisao clinica para triagem de "
            "Endoscopia Digestiva Alta (EDA). Retorne APENAS JSON valido que siga estritamente "
            "o schema_version 1.1. Escreva todos os campos narrativos em portugues "
            "brasileiro (pt-BR). Nao use palavras em ingles nos campos narrativos. "
            "Use apenas valores de enum permitidos para suggestion e support_recommendation. "
            "Nao inclua markdown, blocos de codigo ou chaves extras."
        ),
        "llm2_user": (
            "Tarefa: sugerir accept/deny e recomendacao de suporte para triagem EDA "
            "usando dados estruturados do LLM1 e contexto de caso anterior."
        ),
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
            case.refresh_from_db()  # reset state for next attempt
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
