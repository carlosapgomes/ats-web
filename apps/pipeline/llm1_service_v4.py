"""LLM1 Service v4 — extração procedure-neutral (uma chamada por caso).

Schema 4.0 (design D5/D6/D7 / ADR-0010): valida contra ``Llm1ResponseV4``,
exige evidence spans por procedimento, aceita as DEZ identidades atômicas
(pacotes indivisíveis) e transporta a coleção tipada de imagem abdominal mais
os detalhes clínicos tipados de EDA + Dilatação (``dilation_detail``) e EDA +
GTT (``infection_evidence``). A extração orientada desses detalhes pertence aos
Slices 003/004 — o schema apenas os define e valida.

Os adapters 1.1/2.0/3.0 permanecem como leitura histórica: artefatos antigos
nunca são reescritos.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError as PydanticValidationError

from apps.pipeline.json_parser import LlmJsonParseError, decode_llm_json_object
from apps.pipeline.llm import LlmClient, create_openai_client
from apps.pipeline.ptbr_language_guard import collect_forbidden_terms
from apps.pipeline.schemas.llm1_v4 import Llm1ResponseV4

_LANGUAGE_RETRY_INSTRUCTION = (
    "Regra obrigatoria adicional: todo texto narrativo deve estar em portugues "
    "brasileiro (pt-BR), sem palavras em ingles."
)

# ── Prompts neutros canônicos schema 4.0 (fallback; seed/admin usam o mesmo) ──


LLM1_V4_DEFAULT_SYSTEM_PROMPT = (
    "Voce e um assistente clinico de triagem para procedimentos endoscopicos "
    "digestivos. Retorne APENAS JSON valido que siga estritamente o "
    "schema_version 4.0. Escreva todos os campos narrativos em portugues "
    "brasileiro (pt-BR). Nao use palavras em ingles nos campos narrativos. Nao "
    "inclua markdown, blocos de codigo ou chaves extras. Extraia UMA historia "
    "clinica e um pre-operatorio COMUNS ao caso (common_preop), "
    "independentemente do numero de procedimentos. Liste em requested_procedures "
    "SOMENTE os procedimentos sustentados por evidencia textual explicita da "
    "solicitacao atual; cada item exige evidence_spans com field_path e excerpt "
    "do texto. Cada pacote (EDA + Gastrostomia/GTT, EDA + Capsula, EDA + "
    "Dilatacao, Retossigmoidoscopia + Dilatacao, Retossigmoidoscopia + Argonio) "
    "e UMA identidade unica: nunca o represente tambem como o procedimento base. "
    "Nao invente procedimento, subtipo, dado laboratorial ou medicamento; use "
    "unknown/null quando faltar informacao. Nao codifique limiares clinicos nem "
    "decida aceite/recusa: apenas extraia evidencia."
)

LLM1_V4_REQUIRED_SCHEMA_INSTRUCTIONS = """
CONTRATO JSON OBRIGATORIO — NAO INVENTE OUTRO SCHEMA.
Retorne APENAS um objeto JSON com estas chaves de topo, e nenhuma outra:
schema_version, language, agency_record_number, patient, common_preop,
requested_procedures, policy_precheck, summary, extraction_quality,
origin_context, transfusion, tracked_exams.

Valores fixos e enums obrigatorios:
- schema_version: exatamente "4.0".
- language: exatamente "pt-BR".
- patient.sex: apenas "M", "F" ou "Outro".
- requested_procedures[]: 1 a 10 itens, um por identidade, sem duplicatas;
  procedure_type apenas "eda", "eda_gastrostomy", "eda_capsule", "eda_dilation",
  "colonoscopy", "rectosigmoidoscopy", "rectosigmoidoscopy_dilation",
  "rectosigmoidoscopy_argon", "echoendoscopy" ou "cpre".
- requested_procedures[].evidence_spans: 1 a 3 itens {field_path, excerpt}
  com texto real do relatorio; nunca vazio.
- EDA: subtype standard, gastrostomy, esophageal_dilation, foreign_body ou
  unknown; indication_category foreign_body, bleeding, abdominal_pain,
  dyspepsia, other ou unknown.
- Colonoscopia e Retossigmoidoscopia: indication_category screening, follow_up,
  bleeding, other ou unknown; subtype apenas standard ou unknown.
- EDA + Gastrostomia (GTT): incluir infection_evidence[] (pode ser vazio) com
  {category, assessment, temporal_status, value_text, evidence_excerpt};
  category leukocytes|crp|procalcitonin|lactate|culture|temperature_or_fever|
  infectious_disease|antibiotic; assessment normal_explicit|abnormal_explicit|
  positive_explicit|negative_explicit|febrile_explicit|current_care_explicit|
  antibiotic_in_use|antibiotic_started|antibiotic_escalated|unclassified;
  temporal_status current|historical|unknown. Nao invente limiar nem conclusao:
  use unclassified quando o relatorio nao afirmar explicitamente.
- EDA + Dilatacao: incluir dilation_detail {anatomical_site, evidence_excerpt}
  com anatomical_site esophagus|pylorus|duodenum|anastomosis|jejunum|other|
  unknown; evidence_excerpt obrigatorio quando o local nao for "unknown".
- Ecoendoscopia e CPRE sao procedimentos independentes: NAO usar subtype de
  EDA; preencher apenas name, urgency e evidence_spans.
- common_preop: labs {hb_g_dl, hct_percent, platelets_per_mm3, tp_seconds,
  inr, rni, ttpa_seconds, urea_mg_dl, creatinine_mg_dl}, ecg
  {report_present, abnormal_flag}, asa {bucket}, cardiovascular_risk {level},
  rulebook_signals (minimum_exam_evidence, conditional_exam_requirements,
  clinical_flags), comorbidities_described[], medications_described[],
  abdominal_imaging[], evidence_spans[].
- common_preop.abdominal_imaging[]: {modality, anatomical_site,
  report_finding_present, source_document, evidence_context_excerpt,
  finding_excerpt, exam_datetime_iso} com modality ultrasound|ct|mri|mrcp|other,
  anatomical_site abdomen|upper_abdomen|hepatobiliary|unspecified|other,
  report_finding_present yes|no|unknown e source_document "main_report".
  Quando report_finding_present="yes", evidence_context_excerpt e
  finding_excerpt sao obrigatorios e devem ser trechos reais do relatorio
  principal; uso somente de solicitacao/agendamento NAO conta como achado.
  Registre cada imagem qualificante do relatorio principal: para Ecoendoscopia,
  TC ou RM de abdome/abdome superior; para CPRE, USG (ultrasound) de
  abdome/abdome superior/hepatobiliar, TC ou RM de abdome/abdome superior, ou
  colangiorressonancia/CPRM (mrcp) hepatobiliar.
- policy_precheck: {excluded_from_eda_flow, exclusion_reason, labs_required,
  labs_pass, labs_failed_items, ecg_required, ecg_present, pediatric_flag,
  notes}.
- summary: {one_liner, bullet_points} com 3 a 8 bullets.
- extraction_quality: {confidence (alta|media|baixa), missing_fields, notes}.
- transfusion.had_transfusion: apenas "yes" ou "no".

medications_described[] exige {name, medication_class, use_status,
source_text_hint} com evidencia textual; nao inferir medicamento por
comorbidade, idade ou exame. Medicamentos sao informativos e nunca alteram
sugestao/decisao. Retornar lista vazia quando nao descritos.
""".strip()

LLM1_V4_DEFAULT_USER_PROMPT = (
    "Tarefa: extrair dados estruturados procedure-neutral e resumo conciso de "
    "triagem a partir de um relatorio clinico que pode solicitar qualquer "
    "procedimento endoscopico digestivo do catalogo, isolado ou em pacote "
    "indivisivel, alem do combinado EDA + Colonoscopia. Exigir evidencia "
    "textual explicita para cada campo objetivo; sem evidencia, usar unknown "
    "(ou null para numericos). "
    "A declaracao do NIR consta abaixo como contexto, mas voce deve extrair "
    "somente o que o documento sustenta: um procedimento declarado sem "
    "evidencia de solicitacao atual NAO entra em requested_procedures. "
    "Referencias historicas ou negacoes nunca criam solicitacao atual. "
    "Incluir common_preop.evidence_spans com field_path e excerpt sempre que "
    "houver evidencia. Registrar imagens abdominais qualificantes do relatorio "
    "principal em common_preop.abdominal_imaging. Extrair comorbidades e "
    "medicamentos descritos explicitamente; retornar listas vazias quando "
    "negados/ausentes. Extrair origin_context, tracked_exams com recencia e "
    "had_transfusion binario (yes/no).\n\n"
    f"{LLM1_V4_REQUIRED_SCHEMA_INSTRUCTIONS}"
)


class Llm1V4ValidationError(RuntimeError):
    """Resposta LLM1 v4 falhou validação de schema/consistência."""


@dataclass
class Llm1V4Result:
    """Artefatos validados do LLM1 v4 para persistência."""

    structured_data: dict[str, object]
    summary_text: str
    prompt_system_name: str = "exam_llm1_system"
    prompt_system_version: int = 0
    prompt_user_name: str = "exam_llm1_user"
    prompt_user_version: int = 0


def create_openai_llm1_v4_client() -> LlmClient:
    """Cliente LLM1 de produção: strict ``json_schema`` do contrato 4.0 (R3).

    Este é o binding de produção do writer atual — a API recebe o JSON Schema
    das dez identidades com ``schema_version`` fixado em ``"4.0"``.
    """
    return create_openai_client(
        response_schema_name="llm1_response",
        response_schema=Llm1ResponseV4.model_json_schema(),
    )


class Llm1ServiceV4:
    """Executa a chamada LLM1 v4 (uma por caso) com validação estrita."""

    def __init__(self, client: LlmClient) -> None:
        self._client = client

    def run(
        self,
        *,
        case_id: str,
        agency_record_number: str,
        extracted_text: str,
        declared_procedure_types: tuple[str, ...],
        system_prompt: str,
        user_prompt_template: str,
        prompt_system_version: int = 0,
        prompt_user_version: int = 0,
    ) -> Llm1V4Result:
        user_prompt = _render_user_prompt(
            template=user_prompt_template,
            case_id=case_id,
            agency_record_number=agency_record_number,
            declared_procedure_types=declared_procedure_types,
            clean_text=extracted_text,
        )
        raw_response = self._client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        validated = _decode_and_validate(
            raw_response=raw_response,
            agency_record_number=agency_record_number,
        )

        forbidden_terms = _collect_v4_forbidden_terms(validated=validated)
        if forbidden_terms:
            retry_user_prompt = f"{user_prompt}\n\n{_LANGUAGE_RETRY_INSTRUCTION}"
            retry_response = self._client.complete(system_prompt=system_prompt, user_prompt=retry_user_prompt)
            validated = _decode_and_validate(
                raw_response=retry_response,
                agency_record_number=agency_record_number,
            )
            forbidden_terms = _collect_v4_forbidden_terms(validated=validated)
            if forbidden_terms:
                joined = ", ".join(forbidden_terms)
                raise Llm1V4ValidationError(f"LLM1 v4 output contains non-ptbr narrative terms after retry: {joined}")

        structured = validated.model_dump(mode="json")
        return Llm1V4Result(
            structured_data=structured,
            summary_text=validated.summary.one_liner,
            prompt_system_name="exam_llm1_system",
            prompt_system_version=prompt_system_version,
            prompt_user_name="exam_llm1_user",
            prompt_user_version=prompt_user_version,
        )


def _render_user_prompt(
    *,
    template: str,
    case_id: str,
    agency_record_number: str,
    declared_procedure_types: tuple[str, ...],
    clean_text: str,
) -> str:
    declared_label = " + ".join(declared_procedure_types) if declared_procedure_types else "não declarado"
    return (
        f"{template}\n\n"
        f"case_id: {case_id}\n"
        f"agency_record_number: {agency_record_number}\n\n"
        f"Procedimentos declarados pelo NIR (contexto; extraia apenas o que o documento sustenta): {declared_label}\n\n"
        "Retorne JSON schema_version 4.0 e preserve agency_record_number exatamente.\n"
        "Todos os campos narrativos devem estar em portugues brasileiro (pt-BR).\n"
        "Nao use palavras em ingles nos campos narrativos.\n"
        "Cada procedimento de requested_procedures exige evidence_spans com "
        "field_path e excerpt reais do texto; sem evidencia de solicitacao "
        "atual, nao inclua o procedimento.\n"
        "Historico/negacao nunca criam solicitacao atual; nao invente "
        "procedimentos, subtipos, exames ou medicamentos.\n"
        "Pacotes sao uma unica identidade: nunca liste o procedimento base "
        "junto do pacote pela mesma solicitacao.\n"
        f"Texto clinico do relatorio:\n{clean_text}"
    )


def _decode_and_validate(*, raw_response: str, agency_record_number: str) -> Llm1ResponseV4:
    try:
        decoded = decode_llm_json_object(raw_response)
    except LlmJsonParseError as error:
        raise Llm1V4ValidationError("LLM1 v4 returned non-JSON payload") from error
    try:
        validated = Llm1ResponseV4.model_validate(decoded)
    except PydanticValidationError as error:
        raise Llm1V4ValidationError(f"LLM1 v4 schema validation failed: {error}") from error
    if validated.agency_record_number != agency_record_number:
        raise Llm1V4ValidationError("LLM1 v4 agency_record_number mismatch")
    return validated


def _collect_v4_forbidden_terms(*, validated: Llm1ResponseV4) -> list[str]:
    """Coleta termos em inglês nos campos narrativos do LLM1 v4."""
    texts: list[str] = [
        validated.summary.one_liner,
        *validated.summary.bullet_points,
    ]
    if validated.policy_precheck.notes:
        texts.append(validated.policy_precheck.notes)
    if validated.extraction_quality.notes:
        texts.append(validated.extraction_quality.notes)
    return collect_forbidden_terms(texts=texts)
