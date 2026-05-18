"""LLM1 Service — structured data extraction with Pydantic v2 validation.

Validates and normalizes the LLM response against the schema 1.1 contract
ported from the legacy augmented-triage-system.

Key differences from legacy:
- No interaction repository (audit via CaseEvent in orchestrator).
- Sync interface (legacy was async).
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError as PydanticValidationError

from apps.pipeline.json_parser import LlmJsonParseError, decode_llm_json_object
from apps.pipeline.llm import LlmClient
from apps.pipeline.ptbr_language_guard import collect_forbidden_terms
from apps.pipeline.schemas.llm1 import Llm1Response

# ── Language retry instruction ──────────────────────────────────────────

_LANGUAGE_RETRY_INSTRUCTION = (
    "Regra obrigatoria adicional: todo texto narrativo deve estar em portugues "
    "brasileiro (pt-BR), sem palavras em ingles."
)

# ── Centralized default prompts (legacy v6) ─────────────────────────────────
# These are the single source of truth for LLM1 fallback defaults.
# Both the orchestrator and seed_prompts should reference these or be
# aligned with them to avoid divergence.

LLM1_DEFAULT_SYSTEM_PROMPT = (
    "Voce e um assistente clinico para triagem de Endoscopia Digestiva Alta "
    "(EDA). Retorne APENAS JSON valido que siga estritamente o schema_version "
    "1.1. Escreva todos os campos narrativos em portugues brasileiro (pt-BR). "
    "Nao use palavras em ingles nos campos narrativos. Nao inclua markdown, "
    "blocos de codigo ou chaves extras. Nao invente fatos; use null/unknown "
    "quando faltar informacao. Classifique o procedimento EDA suportado com "
    "subtype em standard, gastrostomy, esophageal_dilation ou foreign_body. "
    "Estime ASA pratico apenas nos buckets I-II, III ou mais, ou "
    "insufficient_data, sempre de forma conservadora e baseada no texto. "
    "Nao inferir Mallampati ou risco OSA. "
    "Extraia origin_context (cidade/hospital/unidade/UF) quando disponivel. "
    "Identifique tracked_exams com recencia por data/hora ou posicao textual. "
    "Registre had_transfusion como binario (yes/no); ausencia de evidencia "
    "de transfusao deve ser tratada como 'no'."
)

LLM1_REQUIRED_SCHEMA_INSTRUCTIONS = """
CONTRATO JSON OBRIGATORIO — NAO INVENTE OUTRO SCHEMA.
Retorne APENAS um objeto JSON com estas chaves de topo, e nenhuma outra:
schema_version, language, agency_record_number, patient, eda, preop_screening,
policy_precheck, summary, extraction_quality, origin_context, transfusion, tracked_exams.

Valores fixos e enums obrigatorios:
- schema_version: exatamente "1.1".
- language: exatamente "pt-BR".
- patient.sex: apenas "M", "F" ou "Outro"; nunca "masculino"/"feminino".
- Todos os EvidenceFlag devem ser strings "yes", "no" ou "unknown"; nunca true/false.
- transfusion.had_transfusion: apenas "yes" ou "no".
- eda.requested_procedure.subtype e preop_screening.rulebook_signals.eda_subtype: standard, gastrostomy, esophageal_dilation, foreign_body ou unknown.
- eda.asa.bucket: I-II, III ou mais ou insufficient_data.

Campos obrigatorios por bloco:
patient = {"name", "age", "sex", "document_id"}. Use null quando ausente.
eda = {"indication_category", "exclusion_type", "is_pediatric", "foreign_body_suspected", "requested_procedure", "labs", "ecg", "asa", "cardiovascular_risk"}.
eda.requested_procedure = {"name", "urgency", "subtype"}.
eda.labs = {"hb_g_dl", "hct_percent", "platelets_per_mm3", "tp_seconds", "inr", "rni", "ttpa_seconds", "urea_mg_dl", "creatinine_mg_dl", "source_text_hint"}.
eda.ecg = {"report_present", "abnormal_flag", "source_text_hint"}.
preop_screening = {"exam_type", "has_cardiovascular_disease", "has_active_respiratory_symptoms", "has_prior_respiratory_disease", "has_ecg_report", "has_chest_xray_report", "has_echocardiogram_report", "hb_g_dl", "platelets_per_mm3", "inr", "evidence_spans", "rulebook_signals"}.
policy_precheck = {"excluded_from_eda_flow", "exclusion_reason", "labs_required", "labs_pass", "labs_failed_items", "ecg_required", "ecg_present", "pediatric_flag", "notes"}.
summary = {"one_liner", "bullet_points"}; bullet_points deve ter 3 a 8 itens.
extraction_quality = {"confidence", "missing_fields", "notes"}; confidence: alta, media ou baixa.
origin_context = {"city", "hospital", "unit", "state_uf", "source_text_hint"}.
transfusion = {"had_transfusion", "total_units", "hemocomponent", "source_text_hint"}.
tracked_exams[] = {"exam_type", "exam_label", "result_value", "exam_datetime_iso", "is_most_recent", "source_text_hint"}.

NUNCA use estes nomes/aliases: case_id no JSON de resposta, full_name, age_years,
race_color, weight_kg, gender, request_indication, clinical_question,
clinical_context, vitals, imaging_and_tests, asa_practical_estimate,
triage_summary, result_excerpt, exam_name, key_findings, labs no topo.
""".strip()

LLM1_DEFAULT_USER_PROMPT = (
    "Tarefa: extrair dados estruturados e gerar resumo conciso de triagem "
    "a partir de um relatorio clinico para triagem EDA. Exigir evidencia "
    "textual explicita para cada campo objetivo. Quando nao houver evidencia "
    "textual, retornar unknown (ou null para numericos). Preencher "
    "preop_screening.rulebook_signals para o novo rulebook, incluindo exames "
    "minimos, exames condicionais, subtipo EDA suportado e contexto de "
    "paciente pediatrico. Incluir preop_screening.evidence_spans com "
    "field_path e excerpt sempre que houver evidencia. "
    "Extrair origin_context (cidade/hospital/unidade/UF) quando disponivel "
    "no texto. Identificar exames rastreados (tracked_exams) com recencia "
    "determinada por data/hora ou posicao textual, com desempate pela ultima "
    "ocorrencia. Registrar had_transfusion como binario (yes/no); ausencia de "
    "evidencia de transfusao deve ser tratada como 'no'.\n\n"
    f"{LLM1_REQUIRED_SCHEMA_INSTRUCTIONS}"
)


# ── Exceptions ──────────────────────────────────────────────────────────────


class Llm1ValidationError(RuntimeError):
    """LLM1 response failed Pydantic validation or consistency checks."""


# ── Result ──────────────────────────────────────────────────────────────────


@dataclass
class Llm1Result:
    """Validated and normalized LLM1 artifacts for persistence."""

    structured_data: dict[str, object]
    summary_text: str
    prompt_system_name: str = "llm1_system"
    prompt_system_version: int = 0
    prompt_user_name: str = "llm1_user"
    prompt_user_version: int = 0


# ── Service ─────────────────────────────────────────────────────────────────


class Llm1Service:
    """Execute LLM1 call, enforce schema 1.1, and normalize output.

    Includes language retry: if validated output contains forbidden
    English terms in narrative fields, a single retry with an
    additional pt-BR instruction is attempted.
    """

    def __init__(self, client: LlmClient) -> None:
        self._client = client

    def run(
        self,
        *,
        case_id: str,
        agency_record_number: str,
        extracted_text: str,
        system_prompt: str,
        user_prompt_template: str,
    ) -> Llm1Result:
        """Execute LLM1 extraction with full Pydantic v2 validation.

        Args:
            case_id: Unique case identifier.
            agency_record_number: Agency record number from PDF.
            extracted_text: Raw text extracted from the medical report.
            system_prompt: System prompt for the LLM.
            user_prompt_template: Base user prompt template (before rendering).

        Returns:
            Llm1Result with structured_data (model_dump mode="json"),
            summary_text, and prompt metadata.

        Raises:
            Llm1ValidationError: If JSON parsing, schema validation,
                cross-field consistency checks, or language guard fail.
        """
        # Render the final user prompt with legacy instructions
        user_prompt = _render_user_prompt(
            template=user_prompt_template,
            case_id=case_id,
            agency_record_number=agency_record_number,
            clean_text=extracted_text,
        )

        # Call the LLM
        raw_response = self._client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Decode JSON, validate schema, check consistency
        validated = _decode_and_validate(
            raw_response=raw_response,
            agency_record_number=agency_record_number,
        )

        # Language guard: retry once with pt-BR instruction if needed
        forbidden_terms = _collect_llm1_forbidden_terms(validated=validated)
        if forbidden_terms:
            retry_user_prompt = f"{user_prompt}\n\n{_LANGUAGE_RETRY_INSTRUCTION}"
            retry_response = self._client.complete(
                system_prompt=system_prompt,
                user_prompt=retry_user_prompt,
            )
            validated = _decode_and_validate(
                raw_response=retry_response,
                agency_record_number=agency_record_number,
            )
            forbidden_terms = _collect_llm1_forbidden_terms(validated=validated)
            if forbidden_terms:
                joined_terms = ", ".join(forbidden_terms)
                raise Llm1ValidationError(f"LLM1 output contains non-ptbr narrative terms after retry: {joined_terms}")

        # Serialize to JSON-safe dict via model_dump
        structured = validated.model_dump(mode="json")

        return Llm1Result(
            structured_data=structured,
            summary_text=validated.summary.one_liner,
            prompt_system_name="llm1_system",
            prompt_system_version=0,
            prompt_user_name="llm1_user",
            prompt_user_version=0,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def _render_user_prompt(
    *,
    template: str,
    case_id: str,
    agency_record_number: str,
    clean_text: str,
) -> str:
    """Render the full user prompt with legacy EDA scope instructions.

    Ported from the legacy _render_user_prompt() in llm1_service.py.
    Appends case metadata, schema instructions, EDA scope rules,
    tracked exams rules, origin_context rules, and the clinical text.
    """
    return (
        f"{template}\n\n"
        f"case_id: {case_id}\n"
        f"agency_record_number: {agency_record_number}\n\n"
        "Retorne JSON schema_version 1.1 e preserve agency_record_number exatamente.\n"
        f"{LLM1_REQUIRED_SCHEMA_INSTRUCTIONS}\n"
        "Todos os campos narrativos devem estar em portugues brasileiro (pt-BR).\n"
        "Nao use palavras em ingles nos campos narrativos.\n"
        "Estimar ASA pratico apenas em I-II, III ou mais ou insufficient_data.\n"
        "Nao inferir Mallampati ou risco OSA.\n"
        "Cada campo objetivo deve ter evidencia textual; se nao houver, usar unknown.\n"
        "Para hb_g_dl, platelets_per_mm3 e inr sem evidencia numerica, usar null.\n"
        "Incluir preop_screening.evidence_spans com itens {field_path, excerpt}.\n"
        "Preencher eda.requested_procedure.subtype e preop_screening.rulebook_signals.eda_subtype "
        "com standard, gastrostomy, esophageal_dilation, foreign_body ou unknown.\n"
        "Para escopo do exame: classificar preop_screening.exam_type=eda para EDA padrao, "
        "gastrostomia/GTT/PEG, dilatacao esofagica e retirada de corpo estranho; usar non_eda "
        "apenas para solicitacoes claramente fora de escopo EDA, incluindo CPRE; usar unknown "
        "somente quando o tipo de exame permanecer indefinido.\n"
        "Quando houver gastrostomia/GTT/PEG, usar subtype gastrostomy; quando houver "
        "dilatacao esofagica, usar subtype esophageal_dilation; quando houver retirada de "
        "corpo estranho, usar subtype foreign_body; nos demais casos suportados, usar "
        "subtype standard.\n"
        "Preencher preop_screening.rulebook_signals.minimum_exam_evidence com hb_or_hct_present, "
        "hb_numeric_present, platelets_numeric_present, tp_inr_rni_numeric_present, ttpa_present, "
        "urea_present, creatinine_present, coagulogram_normal_supports_ttpa e "
        "renal_function_preserved_supports_urea_and_creatinine.\n"
        "Preencher preop_screening.rulebook_signals.conditional_exam_requirements com "
        "ecg_required, chest_xray_required, echocardiogram_required, "
        "ecg_report_finding_present, chest_xray_report_finding_present e "
        "echocardiogram_report_finding_present.\n"
        "Preencher preop_screening.rulebook_signals.clinical_flags com sinais clinicos do "
        "rulebook, inclusive contexto de paciente pediatrico, hepatopatia, cardiopatia, "
        "doenca cardiovascular, criterios respiratorios e gatilhos para ECG/ECO.\n"
        "Se patient.age < 16, marcar eda.is_pediatric=true e "
        "policy_precheck.pediatric_flag=true; se age >= 16, manter ambos false. "
        "Explicitar contexto de paciente pediatrico no resumo.\n\n"
        "Para origin_context (cidade/hospital/unidade): "
        "extrair cidade, hospital e unidade do texto; "
        "se houver sigla de UF (estado), preencher state_uf. "
        "Quando nao houver evidencia textual, preencher todos os subcampos como null.\n"
        "Para recencia de exames rastreados (tracked_exams): "
        "usar data/hora (exam_datetime_iso) quando disponivel para determinar o mais recente; "
        "sem data/hora, inferir recencia pela posicao textual; "
        "em caso de empate, desempate pela ultima ocorrencia no texto. "
        "Marcar is_most_recent=true apenas para o mais recente de cada tipo.\n"
        "Para had_transfusion: resposta estritamente binaria (yes/no); "
        "ausencia de evidencia de transfusao deve ser tratada como 'no'. "
        "Se had_transfusion=yes, informar total_units (inteiro) "
        "e hemocomponent quando disponivel.\n"
        f"Texto clinico do relatorio:\n{clean_text}"
    )


def _decode_and_validate(
    *,
    raw_response: str,
    agency_record_number: str,
) -> Llm1Response:
    """Decode LLM JSON, validate against schema 1.1, check consistency.

    Raises Llm1ValidationError on any failure.
    """
    try:
        decoded = decode_llm_json_object(raw_response)
    except LlmJsonParseError as error:
        raise Llm1ValidationError("LLM1 returned non-JSON payload") from error

    try:
        validated = Llm1Response.model_validate(decoded)
    except PydanticValidationError as error:
        raise Llm1ValidationError(f"LLM1 schema validation failed: {error}") from error

    if validated.agency_record_number != agency_record_number:
        raise Llm1ValidationError("LLM1 agency_record_number mismatch")

    return validated


def _collect_llm1_forbidden_terms(*, validated: Llm1Response) -> list[str]:
    """Collect forbidden English terms across all LLM1 narrative fields.

    Ported from the legacy _collect_llm1_forbidden_terms() in llm1_service.py.
    """
    texts: list[str] = [
        validated.summary.one_liner,
        *validated.summary.bullet_points,
    ]
    optional_texts = [
        validated.policy_precheck.notes,
        validated.extraction_quality.notes,
    ]
    texts.extend(text for text in optional_texts if text is not None)
    return collect_forbidden_terms(texts=texts)
