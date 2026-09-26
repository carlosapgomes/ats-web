"""Pipeline orchestrator — runs the procedure-neutral v4 LLM pipeline for a case.

Ties together: LLM1 v4 extraction → detection/reconciliation →
per-component preop policy → prior context per procedure →
LLM2 v4 suggestion → support synthesis → FSM transitions.

Cutover 4.0 (design D5/D14 / ADR-0010): o caminho executável é EXCLUSIVAMENTE o
contrato 4.0 (dez identidades atômicas). Serviços/schemas 3.0 permanecem como
leitores históricos e para rollback anterior ao primeiro write 4.0, mas nunca
são chamados por um job novo. Casos sem procedimentos declarados válidos em
``CaseProcedure`` falham de modo explícito/auditável (R1), nunca caem em perfil
singular/EDA.
"""

from __future__ import annotations

import copy
import logging
import uuid
from collections.abc import Container
from dataclasses import dataclass

from apps.cases.exam_profiles import require_exam_profile
from apps.cases.models import Case, ProcedureType
from apps.cases.priority_signals import resolve_priority_signals
from apps.cases.procedures import (
    ALLOWED_PROCEDURE_SETS,
    PROCEDURE_CATALOG,
    PROCEDURE_ORDER,
    set_detected_procedures,
)
from apps.llm.models import PromptTemplate
from apps.pipeline.imaging_evidence import normalize_evidence_text, verify_abdominal_imaging_evidence
from apps.pipeline.infection_review import (
    INFECTION_EVIDENCE_ARTIFACT_KEY,
    INFECTION_EVIDENCE_FIELD,
    serialize_infection_review,
    verify_infection_evidence,
)
from apps.pipeline.llm import LlmClient
from apps.pipeline.llm1_service_v4 import (
    LLM1_V4_DEFAULT_SYSTEM_PROMPT,
    LLM1_V4_DEFAULT_USER_PROMPT,
    Llm1ServiceV4,
    Llm1V4Result,
)
from apps.pipeline.llm2_service_v4 import (
    LLM2_V4_DEFAULT_SYSTEM_PROMPT,
    LLM2_V4_DEFAULT_USER_PROMPT,
    Llm2ServiceV4,
    strictest_global_support,
)
from apps.pipeline.policy import (
    EdaPolicyPrecheckInput,
    Llm2PolicyAlignmentInput,
    Llm2SuggestionInput,
    evaluate_procedure_policy,
    reconcile_eda_policy,
    synthesize_eda_support_context,
)
from apps.pipeline.prior_case import PriorCaseContext, lookup_prior_case_context
from apps.pipeline.procedure_reconciliation import (
    build_v2_review_payload,
    reconcile_detected_procedures,
    serialize_procedure_precedence,
    serialize_procedure_precedence_rules,
)
from apps.pipeline.schemas.adapters import project_v4_to_llm1_shape, requested_procedure_for_type
from apps.pipeline.scope_detection import detect_procedure_occurrences, detect_requested_procedures_v4

logger = logging.getLogger(__name__)


# D5/Slices 003/004/005: o writer 4.0 detecta as dez identidades; os pacotes EDA
# entram nos Slices 003 (Cápsula e Dilatação) e 004 (GTT), a família
# Retossigmoidoscopia no Slice 005 e os especializados no Slice 001.
_DETECTABLE_PROCEDURE_TYPES: tuple[str, ...] = (
    ProcedureType.EDA,
    ProcedureType.EDA_GASTROSTOMY,
    ProcedureType.EDA_CAPSULE,
    ProcedureType.EDA_DILATION,
    ProcedureType.COLONOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
    ProcedureType.ECHOENDOSCOPY,
    ProcedureType.CPRE,
)
_SCHEMA_VERSION = "4.0"

# ── Local informativo da dilatação (D6/R5) ──────────────────────────────────

_DILATION_ANATOMICAL_SITES: frozenset[str] = frozenset(
    {
        "esophagus",
        "pylorus",
        "duodenum",
        "anastomosis",
        "jejunum",
        "other",
    }
)
DILATION_SITE_NOT_DECLARED = "dilation_site_not_declared"
DILATION_SITE_EXCERPT_NOT_ANCHORED = "dilation_excerpt_not_anchored"
DILATION_SITE_EXCERPT_AMBIGUOUS = "dilation_excerpt_ambiguous"


@dataclass(frozen=True)
class DilationSiteProjection:
    """Projeção APRESENTÁVEL do local de dilatação (design D6).

    Informativa por definição: nunca cria pendência nem altera policy, sugestão
    ou disposição médica; ``reason_code`` é o motivo técnico enxuto da queda
    para ``unknown``.
    """

    anatomical_site: str
    reason_code: str = ""


def project_dilation_site(*, detail: object, main_report_text: str) -> DilationSiteProjection:
    """Ancora o local declarado no relatório principal (design D6/R5).

    O local só é projetado quando o ``evidence_excerpt`` ocorre de forma ÚNICA
    no relatório principal normalizado. Local ausente, não ancorado (trecho
    inventado) ou ambíguo (mais de uma ocorrência) cai para ``unknown`` com
    motivo técnico — nunca falha o pipeline nem muda policy/FSM.
    """
    if not isinstance(detail, dict):
        return DilationSiteProjection(
            anatomical_site="unknown",
            reason_code=DILATION_SITE_NOT_DECLARED,
        )
    anatomical_site = str(detail.get("anatomical_site") or "unknown")
    excerpt = detail.get("evidence_excerpt")
    if anatomical_site not in _DILATION_ANATOMICAL_SITES or not isinstance(excerpt, str) or not excerpt.strip():
        return DilationSiteProjection(
            anatomical_site="unknown",
            reason_code=DILATION_SITE_NOT_DECLARED,
        )
    normalized_excerpt = normalize_evidence_text(excerpt)
    normalized_report = normalize_evidence_text(main_report_text or "")
    if not normalized_excerpt or normalized_excerpt not in normalized_report:
        return DilationSiteProjection(
            anatomical_site="unknown",
            reason_code=DILATION_SITE_EXCERPT_NOT_ANCHORED,
        )
    if normalized_report.count(normalized_excerpt) > 1:
        return DilationSiteProjection(
            anatomical_site="unknown",
            reason_code=DILATION_SITE_EXCERPT_AMBIGUOUS,
        )
    return DilationSiteProjection(anatomical_site=anatomical_site)


def _project_detected_dilation_site(
    *,
    structured_data: dict[str, object],
    detected_procedure_types: tuple[str, ...],
    main_report_text: str,
) -> dict[str, object] | None:
    """Projeção consultiva do local, somente quando ``eda_dilation`` é detectada."""
    if ProcedureType.EDA_DILATION not in detected_procedure_types:
        return None
    item = requested_procedure_for_type(structured_data, ProcedureType.EDA_DILATION)
    projection = project_dilation_site(
        detail=item.get("dilation_detail"),
        main_report_text=main_report_text,
    )
    return {"anatomical_site": projection.anatomical_site, "reason_code": projection.reason_code}


# ── Revisão infecciosa consultiva de EDA + GTT (Slice 004, D7/D8) ───────────


def project_infection_review(
    *,
    structured_data: dict[str, object],
    detected_procedure_types: tuple[str, ...],
    main_report_text: str,
) -> dict[str, object] | None:
    """Verifica e projeta a revisão infecciosa do artefato 4.0 (D7/D8/R1).

    Existe SOMENTE para a identidade exata ``eda_gastrostomy`` — nenhuma outra
    variação de EDA herda o painel por família/sinal legado. A coleção é
    verificada contra o relatório principal (nunca anexos); ausência/falha de
    extração devolve ``None`` (seção vazia/neutra, nunca pendência). O DTO
    resultante NUNCA entra em ``failed_requirements``, ``priority_signals``,
    policy ou no reconciliador LLM2: é apresentação consultiva.
    """
    if detected_procedure_types != (ProcedureType.EDA_GASTROSTOMY,):
        return None
    item = requested_procedure_for_type(structured_data, ProcedureType.EDA_GASTROSTOMY)
    view = verify_infection_evidence(
        entries=item.get(INFECTION_EVIDENCE_FIELD),
        main_report_text=main_report_text,
    )
    if view.empty:
        return None
    return serialize_infection_review(view)


def run_pipeline(
    case_id: uuid.UUID,
    *,
    llm_client: LlmClient | None = None,
    llm1_system_prompt: str | None = None,
    llm1_user_template: str | None = None,
    llm2_system_prompt: str | None = None,
    llm2_user_template: str | None = None,
) -> None:
    """Orchestrate the procedure-neutral v4 LLM pipeline for a case.

    FSM flow (happy path):
        LLM_STRUCT → LLM_SUGGEST → R2_POST_WIDGET → WAIT_DOCTOR
    On error at any step: → FAILED

    All injectable parameters default to production values (settings/DB).
    Override them in tests to avoid needing DB templates or real LLM calls.

    R1: o pipeline é exclusivamente 4.0. Caso sem procedimentos declarados
    válidos em ``CaseProcedure`` falha de modo explícito/auditável (PIPELINE_FAILED),
    sem cair em perfil singular/EDA nem em prompt 1.1.
    """
    case = Case.objects.get(case_id=case_id)

    # Use separate stage-specific clients in production mode.
    # When a single client is injected (tests), use it for both.
    if llm_client is None:
        from apps.pipeline.llm1_service_v4 import create_openai_llm1_v4_client
        from apps.pipeline.llm2_service_v4 import create_openai_llm2_v4_client

        client_llm1: LlmClient = create_openai_llm1_v4_client()
        client_llm2: LlmClient = create_openai_llm2_v4_client()
    else:
        client_llm1 = llm_client
        client_llm2 = llm_client

    try:
        _run_v4_pipeline(
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


# ── V4 pipeline (procedure-neutral — contract 4.0) ──────────────────────────


class DeclaredProceduresMissingError(Exception):
    """Caso sem procedimentos declarados válidos na projeção ``CaseProcedure``."""


class UnsupportedDeclaredProcedureError(Exception):
    """Row de ``CaseProcedure`` com valor fora do catálogo (dado anômalo).

    Dívida herdada do Slice 001: um valor desconhecido vindo do banco falha
    explícito em vez de ser filtrado em silêncio (senão o caso pareceria ter
    procedimentos válidos).
    """


def _require_declared_procedures(case: Case) -> tuple[str, ...]:
    """Declaração autoritativa de ``CaseProcedure`` (sem fallback da ponte).

    Novos jobs exigem 1–4 procedimentos declarados válidos (R1). A leitura é
    feita diretamente das rows ``declared_by_nir=True`` — não usa fallback —
    para que um caso sem projeção falhe de modo explícito/auditável em vez de
    cair em perfil singular/EDA. Um valor fora do catálogo falha explícito
    (nunca é filtrado em silêncio).
    """
    declared_values = [row.procedure_type for row in case.procedures.filter(declared_by_nir=True)]
    unknown = sorted({value for value in declared_values if value not in PROCEDURE_ORDER})
    if unknown:
        raise UnsupportedDeclaredProcedureError(
            f"Procedimento declarado fora do catálogo suportado (case_id={case.case_id}): {', '.join(unknown)}."
        )
    declared = sorted(set(declared_values), key=lambda t: PROCEDURE_ORDER[t])
    if not declared:
        raise DeclaredProceduresMissingError(
            f"Pipeline v4 exige procedimentos declarados em CaseProcedure (case_id={case.case_id}); nenhum encontrado."
        )
    return tuple(declared)


def _resolve_pipeline_signals_type(detected_procedure_types: tuple[str, ...]) -> str:
    """Profile que restringe os sinais persistidos para o conjunto detectado.

    D4: a família vem do ``profile_key`` do catálogo, então as três identidades
    de Retossigmoidoscopia reutilizam exatamente os sinais permitidos de
    Colonoscopia (e os pacotes EDA, os de EDA). EDA tem precedência histórica
    quando presente; sem conjunto detectado, o fallback é EDA.
    """
    profile_keys = {
        definition.profile_key for definition in PROCEDURE_CATALOG if definition.code in detected_procedure_types
    }
    for procedure_type in ("eda", "colonoscopy", "echoendoscopy", "cpre"):
        if procedure_type in profile_keys:
            return procedure_type
    return "eda"


# D13/D14: em writes 4.0 a Ecoendoscopia é persistida apenas como
# ``CaseProcedure`` e os pacotes atômicos cobrem os sinais equivalentes; o
# resolvedor não adiciona o MESMO código de sinal derivado.
_V4_EXCLUDED_SIGNAL_CODES: frozenset[str] = frozenset({"echoendoscopy"})

# Pacote atômico → código de sinal legado já coberto pela própria identidade.
_ATOMIC_PACKAGE_SIGNAL_CODES: dict[str, str] = {
    ProcedureType.EDA_GASTROSTOMY: "gastrostomy",
    ProcedureType.EDA_DILATION: "esophageal_dilation",
}


def _excluded_signal_codes(*, atomic_identity_types: Container[str]) -> frozenset[str]:
    """Códigos de sinal legado que um write 4.0 não persiste (design D13).

    Um sinal derivado nunca é gravado quando a identidade atômica correspondente
    já é o procedimento do caso; os artefatos históricos continuam legíveis.
    """
    return _V4_EXCLUDED_SIGNAL_CODES | {
        signal_code
        for identity_code, signal_code in _ATOMIC_PACKAGE_SIGNAL_CODES.items()
        if identity_code in atomic_identity_types
    }


def _resolve_prompt(name: str) -> tuple[str, int]:
    """Resolve conteúdo + versão de um prompt ativo (fallback com versão 0)."""
    template = PromptTemplate.get_active(name)
    if template is not None:
        return template.content, template.version
    return _get_prompt_content(name), 0


def _collect_v4_evidence_spans(structured_data: dict[str, object]) -> list[dict[str, str]]:
    """Spans comuns + por procedimento para payload enxuto de revisão (R8)."""
    spans: list[dict[str, str]] = []
    common = structured_data.get("common_preop")
    if isinstance(common, dict):
        raw = common.get("evidence_spans")
        if isinstance(raw, list):
            spans.extend(item for item in raw if isinstance(item, dict))
    if isinstance(common, dict):
        raw_imaging = common.get("abdominal_imaging")
        if isinstance(raw_imaging, list):
            for imaging in raw_imaging:
                if not isinstance(imaging, dict):
                    continue
                excerpt = imaging.get("finding_excerpt") or imaging.get("evidence_context_excerpt")
                if isinstance(excerpt, str) and excerpt.strip():
                    spans.append({"field_path": "common_preop.abdominal_imaging", "excerpt": excerpt.strip()})
    raw_procedures = structured_data.get("requested_procedures")
    if isinstance(raw_procedures, list):
        for procedure in raw_procedures:
            if not isinstance(procedure, dict):
                continue
            raw_spans = procedure.get("evidence_spans")
            if isinstance(raw_spans, list):
                spans.extend(item for item in raw_spans if isinstance(item, dict))
    return spans


def _build_llm2_structured_data_view(
    *,
    llm1_structured_data: dict[str, object],
    detected_procedure_types: tuple[str, ...],
) -> dict[str, object]:
    """Visão efêmera do LLM1 para o LLM2 (D1/ADR-0004).

    Cópia profunda com ``requested_procedures`` restrito ao conjunto
    reconciliado, na ordem canônica recebida e reaproveitando somente itens
    originais. Não muta o artefato persistido e nunca sintetiza item clínico
    ausente; campos comuns, summary e evidências são preservados.

    D7/D8: ``INFECTION_EVIDENCE_FIELD`` é removido da cópia — a coleção
    infecciosa é apresentação consultiva, nunca regra do reconciliador LLM2.
    """
    view = copy.deepcopy(llm1_structured_data)
    original_items = view.get("requested_procedures")
    if not isinstance(original_items, list):
        return view
    items_by_type: dict[str, dict[str, object]] = {}
    for item in original_items:
        if isinstance(item, dict) and isinstance(item.get("procedure_type"), str):
            item.pop(INFECTION_EVIDENCE_FIELD, None)
            items_by_type.setdefault(item["procedure_type"], item)
    view["requested_procedures"] = [
        items_by_type[procedure_type] for procedure_type in detected_procedure_types if procedure_type in items_by_type
    ]
    return view


def _run_v4_pipeline(
    *,
    case: Case,
    client_llm1: LlmClient,
    client_llm2: LlmClient,
    llm1_system_prompt: str | None,
    llm1_user_template: str | None,
    llm2_system_prompt: str | None,
    llm2_user_template: str | None,
) -> None:
    """Pipeline procedure-neutral 4.0 (uma análise conjunta por estágio).

        O LLM2 pode usar retries corretivos limitados sem dividir a análise por
        procedimento. Fluxo entregue (R1–R8): LLM1 4.0 (história comum + requested_procedures das
    dez identidades) → detecção/reconciliação D7 → projeção atômica → policy por
        componente → prior context por componente (D10) → LLM2 4.0 (conjunto exato) →
        suporte global mais restritivo → WAIT_DOCTOR com relatório neutro legível.
        Gates de revisão NIR (combined→single, mismatch, unknown) nunca executam
        LLM2.
    """
    declared = _require_declared_procedures(case)

    # ── 1. LLM1 4.0 — uma chamada ────────────────────────────────────────
    if llm1_system_prompt is not None:
        sp1, sp1_version = llm1_system_prompt, 0
    else:
        sp1, sp1_version = _resolve_prompt("exam_llm1_system")
    if llm1_user_template is not None:
        ut1, ut1_version = llm1_user_template, 0
    else:
        ut1, ut1_version = _resolve_prompt("exam_llm1_user")

    service1 = Llm1ServiceV4(client_llm1)
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
    detection = detect_requested_procedures_v4(
        llm1_structured_data=result1.structured_data,
        cleaned_text=case.extracted_text,
    )
    occurrences = detect_procedure_occurrences(
        llm1_structured_data=result1.structured_data,
        cleaned_text=case.extracted_text,
    )
    strong = tuple(t for t in _DETECTABLE_PROCEDURE_TYPES if detection[t]["strong"])
    any_evidence = tuple(t for t in _DETECTABLE_PROCEDURE_TYPES if detection[t]["any"])
    # Slice 004 (R3): o item estruturado contraditado por ocorrência não-atual
    # acompanha a reconciliação. ``.get`` protege entradas sem o campo (dicts
    # derivados de v3 antes desta slice).
    conflicting = tuple(t for t in _DETECTABLE_PROCEDURE_TYPES if detection[t].get("conflicting"))
    reconciliation = reconcile_detected_procedures(
        declared=declared,
        strong=strong,
        any_evidence=any_evidence,
        occurrences=occurrences,
        conflicting=conflicting,
    )

    # ── 3. Projeção de detecção atômica (R4) ───────────────────────────
    # Slice 007/R3: a projeção só é escrita quando o conjunto detectado é
    # projetável — vazio ou pertencente a ``ALLOWED_PROCEDURE_SETS``. A
    # reconciliação pode devolver ``nir_review`` com conjunto fora da matriz
    # (ex.: duas solicitações independentes ``Solicito EDA. Solicito CPRE.``);
    # projetar esse conjunto levantaria ValueError e derrubaria o caso em
    # PIPELINE_FAILED em vez do estado de revisão NIR desenhado (D2).
    # Singletons válidos de mismatch (declarado EDA + detectado Ecoendoscopia)
    # continuam projetados e chegam à revisão.
    detected_types = reconciliation.detected_procedure_types
    if not detected_types or frozenset(detected_types) in ALLOWED_PROCEDURE_SETS:
        set_detected_procedures(
            case=case,
            detected_types=detected_types,
        )

    # Sinais prioritários por projeção compatível (R5/D7/D13): EDA quando
    # presente, senão o próprio tipo detectado restringe os códigos permitidos.
    # Em 4.0 a Ecoendoscopia e os códigos de sinal já cobertos por um pacote
    # atômico (GTT/dilatação) não são persistidos (D13/D14).
    signals_type = _resolve_pipeline_signals_type(reconciliation.detected_procedure_types)
    signals_projection = project_v4_to_llm1_shape(
        v4_data=result1.structured_data,
        procedure_type=signals_type,
    )
    case.priority_signals = resolve_priority_signals(
        structured_data=signals_projection,
        source_text=case.extracted_text,
        exam_type=signals_type,
        excluded_signal_codes=_excluded_signal_codes(
            atomic_identity_types=set(declared) | set(reconciliation.detected_procedure_types)
        ),
    )

    # ── 4. Eventos de detecção (R8: versões de schema/prompt + conjuntos) ─
    # D3/ADR-0008: quando a precedência especializada suprimiu EDA/Colonoscopia,
    # o mesmo metadado enxuto (regra/selecionado/suprimidos, sem texto clínico)
    # acompanha o evento de detecção, a sugestão final e o payload de revisão.
    precedence_metadata = serialize_procedure_precedence(reconciliation)
    # D3/Slice 003: a lista aditiva registra TODAS as reduções aplicadas (o dict
    # acima preserva a mais significativa para os consumidores existentes).
    precedence_rules = serialize_procedure_precedence_rules(reconciliation)
    detection_payload: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "declared_procedures": list(declared),
        "detected_procedures": list(reconciliation.detected_procedure_types),
        "reason_code": reconciliation.reason_code,
        "prompt_system_name": result1.prompt_system_name,
        "prompt_system_version": result1.prompt_system_version,
        "prompt_user_name": result1.prompt_user_name,
        "prompt_user_version": result1.prompt_user_version,
    }
    if precedence_metadata is not None:
        detection_payload["procedure_precedence"] = precedence_metadata
    if precedence_rules:
        detection_payload["procedure_precedence_rules"] = precedence_rules
    case._record_event("CASE_PROCEDURES_DETECTED", payload=detection_payload)
    case.save()
    if reconciliation.upgraded:
        case._record_event(
            "PROCEDURE_SELECTION_AUTO_UPGRADED",
            payload={
                "schema_version": _SCHEMA_VERSION,
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
            evidence_spans=_collect_v4_evidence_spans(result1.structured_data),
        )
        if precedence_metadata is not None:
            review_payload = {**review_payload, "procedure_precedence": precedence_metadata}
        if precedence_rules:
            review_payload = {**review_payload, "procedure_precedence_rules": precedence_rules}
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
    case.llm1_complete(success=True, user=None, payload=_build_v4_llm1_ok_payload(case, result1))
    case.save()

    # ── 7. Policy determinística por componente (R5/D8) ────────────────
    # A imagem abdominal é verificada deterministicamente ANTES da policy: a
    # hard rule consome SOMENTE evidência ancorada no relatório principal (D6).
    common_preop = result1.structured_data.get("common_preop")
    raw_imaging = common_preop.get("abdominal_imaging") if isinstance(common_preop, dict) else None
    verified_imaging = verify_abdominal_imaging_evidence(
        entries=raw_imaging,
        main_report_text=case.extracted_text,
    )
    policy_results: dict[str, dict[str, object]] = {}
    for procedure_type in reconciliation.detected_procedure_types:
        projection = project_v4_to_llm1_shape(
            v4_data=result1.structured_data,
            procedure_type=procedure_type,
        )
        decision = evaluate_procedure_policy(
            structured_data=projection,
            procedure_type=procedure_type,
            verified_imaging=verified_imaging.outcomes,
        )
        policy_results[procedure_type] = decision
        case._record_event(
            "EDA_PREOP_POLICY_DECISION",
            payload={**decision, "procedure_type": procedure_type, "schema_version": _SCHEMA_VERSION},
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
                    "schema_version": _SCHEMA_VERSION,
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

    # ── 9. LLM2 4.0 — análise conjunta com conjunto exato (R6) ──────────
    if llm2_system_prompt is not None:
        sp2, sp2_version = llm2_system_prompt, 0
    else:
        sp2, sp2_version = _resolve_prompt("exam_llm2_system")
    if llm2_user_template is not None:
        ut2, ut2_version = llm2_user_template, 0
    else:
        ut2, ut2_version = _resolve_prompt("exam_llm2_user")

    service2 = Llm2ServiceV4(client_llm2)
    llm2_structured_data_view = _build_llm2_structured_data_view(
        llm1_structured_data=result1.structured_data,
        detected_procedure_types=reconciliation.detected_procedure_types,
    )
    result2 = service2.run(
        case_id=str(case.case_id),
        agency_record_number=case.agency_record_number,
        llm1_structured_data=llm2_structured_data_view,
        detected_procedure_types=reconciliation.detected_procedure_types,
        policy_results=policy_results,
        prior_contexts=prior_contexts,
        system_prompt=sp2,
        user_prompt_template=ut2,
    )

    # ── 10. Reconciliação por item + suporte global (D8) ──────────────
    # D6/R5: o local da dilatação é ancorado no relatório principal ANTES da
    # montagem do payload médico; local ausente/inventado/ambíguo projeta
    # ``unknown`` com motivo técnico e nunca muda policy ou disposição.
    dilation_site_projection = _project_detected_dilation_site(
        structured_data=result1.structured_data,
        detected_procedure_types=reconciliation.detected_procedure_types,
        main_report_text=case.extracted_text,
    )
    recommendations: list[dict[str, object]] = []
    for item in result2.procedure_recommendations:
        procedure_type = str(item["procedure_type"])
        projection = project_v4_to_llm1_shape(
            v4_data=result1.structured_data,
            procedure_type=procedure_type,
        )
        profile = require_exam_profile(procedure_type)
        precheck = _build_policy_precheck(
            projection,
            allow_foreign_body_exception=profile.allows_foreign_body_exception,
        )
        reconciled = reconcile_eda_policy(precheck=precheck, llm2=_build_llm2_suggestion_input(item))
        # Invariante legada (R5/R6): a política determinística vence o LLM. Se
        # ``evaluate_procedure_policy`` negou (exames mínimos, thresholds, gates
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
        recommendation: dict[str, object] = {
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
            # Suporte por componente é recomendação (soft) do LLM2 4.0;
            # a síntese determinística de ASA segue apenas para exibição.
            "support_recommendation": item["support_recommendation"],
            "asa": {
                "bucket": support_ctx.asa_bucket,
                "display_text": support_ctx.asa_display,
            },
            "preop_decision": policy_results[procedure_type],
        }
        if dilation_site_projection is not None and procedure_type == ProcedureType.EDA_DILATION:
            recommendation["dilation_detail"] = dilation_site_projection
        recommendations.append(recommendation)

    global_support = strictest_global_support(tuple(str(r["support_recommendation"]) for r in recommendations))
    # D7/R1: a revisão infecciosa é consultiva e exclusiva de EDA + GTT; ela
    # acompanha o artefato 4.0 de apresentação, nunca a policy/priority signals.
    infection_review = project_infection_review(
        structured_data=result1.structured_data,
        detected_procedure_types=reconciliation.detected_procedure_types,
        main_report_text=case.extracted_text,
    )
    case.suggested_action = {
        "schema_version": _SCHEMA_VERSION,
        "procedure_recommendations": recommendations,
        "global_support_recommendation": global_support,
    }
    if infection_review is not None:
        case.suggested_action[INFECTION_EVIDENCE_ARTIFACT_KEY] = infection_review
    if precedence_metadata is not None:
        case.suggested_action["procedure_precedence"] = precedence_metadata
    if precedence_rules:
        case.suggested_action["procedure_precedence_rules"] = precedence_rules
    case.save()

    # ── 11. Transições finais (LLM_SUGGEST → R2_POST_WIDGET → WAIT_DOCTOR) ─
    # llm2_complete não aceita payload (ao contrário de llm1_complete); o evento
    # LLM2_OK do fluxo v2 é re-registrado com payload enxuto ANTES do save — o
    # slot _pending_event é sobrescrito, persistindo exatamente UM evento com a
    # auditoria de prompt/schema (R8), sem alterar FSM.
    case.llm2_complete(success=True, user=None)
    case._record_event(
        "LLM2_OK",
        payload=_build_v4_llm2_ok_payload(
            case=case,
            prompt_system_version=sp2_version,
            prompt_user_version=ut2_version,
            detected_procedure_types=reconciliation.detected_procedure_types,
        ),
    )
    case.save()
    case.ready_for_doctor()
    case.save()


def _build_v4_llm1_ok_payload(case: Case, result1: Llm1V4Result) -> dict[str, object]:
    """Payload enxuto de LLM1_OK para contrato 4.0 (sem texto clínico integral)."""
    return {
        "schema_version": _SCHEMA_VERSION,
        "summary_text": case.summary_text,
        "priority_signal_codes": [signal["code"] for signal in case.priority_signals],
        "prompt_system_name": result1.prompt_system_name,
        "prompt_system_version": result1.prompt_system_version,
        "prompt_user_name": result1.prompt_user_name,
        "prompt_user_version": result1.prompt_user_version,
    }


def _build_v4_llm2_ok_payload(
    *,
    case: Case,
    prompt_system_version: int,
    prompt_user_version: int,
    detected_procedure_types: tuple[str, ...],
) -> dict[str, object]:
    """Payload enxuto de LLM2_OK para contrato 4.0 (R8, sem texto clínico)."""
    return {
        "schema_version": _SCHEMA_VERSION,
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
        "exam_llm1_system": LLM1_V4_DEFAULT_SYSTEM_PROMPT,
        "exam_llm1_user": LLM1_V4_DEFAULT_USER_PROMPT,
        "exam_llm2_system": LLM2_V4_DEFAULT_SYSTEM_PROMPT,
        "exam_llm2_user": LLM2_V4_DEFAULT_USER_PROMPT,
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
