"""LLM2 Service v2 — sugestão por procedimento em uma única chamada.

Schema 2.0 (R6/D8): recebe exatamente o conjunto detectado e os resultados de
policy, valida igualdade exata de conjuntos (sem omissão/duplicata/adição),
aplica retry de idioma e devolve itens normalizados. A reconciliação
determinística por item e o suporte global mais restritivo são aplicados pelo
orchestrator; este serviço garante o contrato e a chamada única.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from apps.pipeline.json_parser import LlmJsonParseError, decode_llm_json_object
from apps.pipeline.llm import LlmClient
from apps.pipeline.ptbr_language_guard import collect_forbidden_terms
from apps.pipeline.schemas.llm2_v2 import Llm2ResponseV2

_LANGUAGE_RETRY_INSTRUCTION = (
    "Regra obrigatoria adicional: todo texto narrativo deve estar em portugues "
    "brasileiro (pt-BR), sem palavras em ingles."
)

# Ordenação explícita do suporte global: none < anesthesist < anesthesist_icu (D8).
GLOBAL_SUPPORT_ORDER: dict[str, int] = {
    "none": 0,
    "anesthesist": 1,
    "anesthesist_icu": 2,
}


def strictest_global_support(support_values: tuple[str, ...]) -> str:
    """Retorna o nível de suporte mais restritivo da coleção (máximo explícito)."""
    if not support_values:
        return "none"
    return max(support_values, key=lambda value: GLOBAL_SUPPORT_ORDER.get(value, 0))


LLM2_V2_DEFAULT_SYSTEM_PROMPT = (
    "Voce e um assistente de apoio a decisao clinica para triagem de "
    "Endoscopia Digestiva Alta (EDA) e Colonoscopia. Retorne APENAS JSON "
    "valido que siga estritamente o schema_version 2.0. Escreva todos os "
    "campos narrativos em portugues brasileiro (pt-BR). Nao use palavras em "
    "ingles nos campos narrativos. Use apenas valores de enum permitidos para "
    "suggestion e support_recommendation. Produza exatamente um item em "
    "procedure_recommendations para cada procedimento detectado recebido: nao "
    "omita, nao duplique e nao adicione procedimento. Nao invente "
    "recomendacoes, razoes ou dados sem evidencia; baseie-se apenas nos dados "
    "recebidos. Nao inclua markdown, blocos de codigo ou chaves extras."
)

LLM2_V2_DEFAULT_USER_PROMPT = (
    "Tarefa: sugerir accept/deny e recomendacao de suporte para cada "
    "procedimento detectado (EDA e/ou Colonoscopia), usando os dados "
    "estruturados comuns do LLM1, os resultados deterministicos da politica "
    "pre-operatoria por procedimento e os casos anteriores por procedimento. "
    "Retorne um item por procedimento em procedure_recommendations e o "
    "global_support_recommendation no nivel mais restritivo entre os itens. "
    "Baseie-se apenas na evidencia recebida; nao invente dados, razoes ou "
    "procedimentos. Nao use palavras em ingles nos campos narrativos."
)


class Llm2V2ValidationError(RuntimeError):
    """Resposta LLM2 v2 falhou validação de schema/igualdade de conjuntos."""


@dataclass
class Llm2V2Result:
    """Itens de recomendação validados (igualdade exata garantida)."""

    procedure_recommendations: list[dict[str, Any]] = field(default_factory=list)
    suggested_action: dict[str, object] = field(default_factory=dict)


class Llm2ServiceV2:
    """Executa a chamada LLM2 v2 (uma por caso) com contrato estrito."""

    def __init__(self, client: LlmClient) -> None:
        self._client = client

    def run(
        self,
        *,
        case_id: str,
        agency_record_number: str,
        llm1_structured_data: dict[str, object],
        detected_procedure_types: tuple[str, ...],
        policy_results: dict[str, dict[str, object]],
        prior_contexts: dict[str, dict[str, object]],
        system_prompt: str,
        user_prompt_template: str,
    ) -> Llm2V2Result:
        user_prompt = _render_user_prompt(
            template=user_prompt_template,
            case_id=case_id,
            agency_record_number=agency_record_number,
            llm1_structured_data=llm1_structured_data,
            policy_results=policy_results,
            prior_contexts=prior_contexts,
        )
        raw_response = self._client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        validated = _decode_and_validate(
            raw_response=raw_response,
            case_id=case_id,
            agency_record_number=agency_record_number,
            detected_procedure_types=detected_procedure_types,
        )

        forbidden_terms = _collect_v2_forbidden_terms(validated=validated)
        if forbidden_terms:
            retry_user_prompt = f"{user_prompt}\n\n{_LANGUAGE_RETRY_INSTRUCTION}"
            retry_response = self._client.complete(system_prompt=system_prompt, user_prompt=retry_user_prompt)
            validated = _decode_and_validate(
                raw_response=retry_response,
                case_id=case_id,
                agency_record_number=agency_record_number,
                detected_procedure_types=detected_procedure_types,
            )
            forbidden_terms = _collect_v2_forbidden_terms(validated=validated)
            if forbidden_terms:
                joined = ", ".join(forbidden_terms)
                raise Llm2V2ValidationError(f"LLM2 v2 output contains non-ptbr narrative terms after retry: {joined}")

        recommendations = [item.model_dump(mode="json") for item in validated.procedure_recommendations]
        return Llm2V2Result(
            procedure_recommendations=recommendations,
            suggested_action={
                "schema_version": "2.0",
                "procedure_recommendations": recommendations,
                "global_support_recommendation": validated.global_support_recommendation,
                "summary": validated.summary,
            },
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def _render_user_prompt(
    *,
    template: str,
    case_id: str,
    agency_record_number: str,
    llm1_structured_data: dict[str, object],
    policy_results: dict[str, dict[str, object]],
    prior_contexts: dict[str, dict[str, object]],
) -> str:
    llm1_json = json.dumps(llm1_structured_data, ensure_ascii=False)
    policy_json = json.dumps(policy_results, ensure_ascii=False, default=str)
    prior_json = json.dumps(prior_contexts, ensure_ascii=False, default=str)
    return (
        f"{template}\n\n"
        f"case_id: {case_id}\n"
        f"agency_record_number: {agency_record_number}\n\n"
        f"Dados extraídos (JSON LLM1 v2):\n{llm1_json}\n\n"
        f"Resultados da política pré-operatória por procedimento:\n{policy_json}\n\n"
        f"Casos anteriores por procedimento:\n{prior_json}\n\n"
        "Retorne JSON schema_version 2.0 com um item por procedimento detectado "
        "e global_support_recommendation mais restritivo.\n"
        "Todos os campos narrativos devem estar em português brasileiro (pt-BR).\n"
        "Não use palavras em inglês nos campos narrativos."
    )


def _decode_and_validate(
    *,
    raw_response: str,
    case_id: str,
    agency_record_number: str,
    detected_procedure_types: tuple[str, ...],
) -> Llm2ResponseV2:
    try:
        decoded = decode_llm_json_object(raw_response)
    except LlmJsonParseError as error:
        raise Llm2V2ValidationError("LLM2 v2 returned non-JSON payload") from error
    try:
        validated = Llm2ResponseV2.model_validate(decoded)
    except ValidationError as error:
        raise Llm2V2ValidationError(f"LLM2 v2 schema validation failed: {error}") from error

    if validated.case_id != str(case_id):
        raise Llm2V2ValidationError(f"LLM2 v2 case_id mismatch: expected {case_id!r}")
    if validated.agency_record_number != str(agency_record_number):
        raise Llm2V2ValidationError(f"LLM2 v2 agency_record_number mismatch: expected {agency_record_number!r}")

    # Igualdade exata de conjuntos: sem omissão, duplicata ou adição (R6).
    returned = {item.procedure_type for item in validated.procedure_recommendations}
    expected = set(detected_procedure_types)
    if returned != expected:
        raise Llm2V2ValidationError(
            f"LLM2 v2 procedure set mismatch: expected {sorted(expected)}, got {sorted(returned)}"
        )
    return validated


def _collect_v2_forbidden_terms(*, validated: Llm2ResponseV2) -> list[str]:
    """Coleta termos em inglês nos campos narrativos do LLM2 v2."""
    texts: list[str] = []
    for item in validated.procedure_recommendations:
        texts.append(item.rationale.short_reason)
        texts.extend(item.rationale.details)
        texts.extend(item.rationale.missing_info_questions)
        if item.policy_alignment.notes:
            texts.append(item.policy_alignment.notes)
    return collect_forbidden_terms(texts=texts)
