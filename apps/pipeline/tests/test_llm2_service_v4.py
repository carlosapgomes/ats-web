"""Echo mismatch no LLM2 v4 (change ``llm2-v4-echo-mismatch-fix``, slices 001 e 002).

Cobre o diagnóstico de resposta schema-válida que ecoa ``case_id`` /
``agency_record_number`` divergentes (exceção tipada com ``field``/``expected``/
``got`` e metadados não-clínicos do raw) e o retry one-shot corretivo: 1º mismatch
→ 2ª chamada com os IDs esperados + o ``got`` recebido; 2º mismatch → aborta com o
``got`` da 2ª tentativa; o retry de eco coexiste com o retry de procedure-set.

Sem DB.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import pytest

from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.llm2_service_v4 import (
    Llm2ServiceV4,
    Llm2V4EchoMismatchError,
    Llm2V4ValidationError,
)

RAW_SHA256_PATTERN = re.compile(r"raw_sha256=([0-9a-f]{12})(?![0-9a-f])")


# ── Builders (payload v4 mínimo — ver test_llm_v4_contracts.py) ─────────────


def _recommendation(procedure_type: str, *, short_reason: str = "Indicacao registrada.") -> dict[str, Any]:
    return {
        "procedure_type": procedure_type,
        "suggestion": "accept",
        "support_recommendation": "none",
        "rationale": {
            "short_reason": short_reason,
            "details": ["Detalhe operacional 1", "Detalhe operacional 2"],
            "missing_info_questions": [],
        },
        "policy_alignment": {
            "excluded_request": False,
            "labs_ok": "yes",
            "ecg_ok": "yes",
            "pediatric_flag": False,
            "notes": None,
        },
        "confidence": "alta",
    }


def _llm2_v4_payload(
    *,
    case_id: str,
    agency_record_number: str,
    procedure_types: tuple[str, ...] = ("cpre",),
    short_reason: str = "Indicacao registrada.",
) -> dict[str, Any]:
    return {
        "schema_version": "4.0",
        "language": "pt-BR",
        "case_id": case_id,
        "agency_record_number": agency_record_number,
        "procedure_recommendations": [
            _recommendation(procedure_type, short_reason=short_reason) for procedure_type in procedure_types
        ],
        "global_support_recommendation": "none",
        "summary": None,
    }


def _run_service(
    client: RecordingLlmClient,
    *,
    case_id: str = "c1",
    agency_record_number: str = "12345",
    detected_procedure_types: tuple[str, ...] = ("cpre",),
) -> Any:
    return Llm2ServiceV4(client).run(
        case_id=case_id,
        agency_record_number=agency_record_number,
        llm1_structured_data={},
        detected_procedure_types=detected_procedure_types,
        policy_results={"cpre": {"decision": "deny"}},
        prior_contexts={"cpre": {"prior_case": None}},
        system_prompt="sp",
        user_prompt_template="ut",
    )


# ── R1/R4/R5: case_id divergente ────────────────────────────────────────────


def test_case_id_mismatch_reports_expected_and_got() -> None:
    raw_response = json.dumps(_llm2_v4_payload(case_id="outro-id", agency_record_number="12345"))
    # 2ª resposta repete o mismatch (slice 002): retry esgotado → aborta.
    client = RecordingLlmClient(responses=[raw_response, raw_response])

    with pytest.raises(Llm2V4EchoMismatchError) as exc_info:
        _run_service(client, case_id="c1")

    error = exc_info.value
    assert isinstance(error, Llm2V4ValidationError)
    assert error.field == "case_id"
    assert error.expected == "c1"
    assert error.got == "outro-id"
    message = str(error)
    assert "case_id mismatch" in message
    assert "expected 'c1'" in message
    assert "got 'outro-id'" in message
    assert len(client.calls) == 2


# ── R2/R5: agency_record_number divergente ──────────────────────────────────


def test_agency_record_number_mismatch_reports_expected_and_got() -> None:
    raw_response = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="99999"))
    # 2ª resposta repete o mismatch (slice 002): retry esgotado → aborta.
    client = RecordingLlmClient(responses=[raw_response, raw_response])

    with pytest.raises(Llm2V4EchoMismatchError) as exc_info:
        _run_service(client, agency_record_number="12345")

    error = exc_info.value
    assert error.field == "agency_record_number"
    assert error.expected == "12345"
    assert error.got == "99999"
    message = str(error)
    assert "agency_record_number mismatch" in message
    assert "expected '12345'" in message
    assert "got '99999'" in message
    assert len(client.calls) == 2


# ── R3: metadados do raw sem conteúdo clínico ───────────────────────────────


def test_mismatch_message_carries_raw_metadata_without_clinical_text() -> None:
    clinical_marker = "MARCADOR-CLINICO-NAO-DEVE-VAZAR"
    raw_response = json.dumps(
        _llm2_v4_payload(case_id="outro-id", agency_record_number="12345", short_reason=clinical_marker)
    )
    # 2ª resposta repete o mismatch (slice 002): retry esgotado → aborta.
    client = RecordingLlmClient(responses=[raw_response, raw_response])

    with pytest.raises(Llm2V4EchoMismatchError) as exc_info:
        _run_service(client, case_id="c1")

    message = str(exc_info.value)
    expected_sha256_prefix = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()[:12]
    assert f"raw_len={len(raw_response)}" in message
    match = RAW_SHA256_PATTERN.search(message)
    assert match is not None
    assert match.group(1) == expected_sha256_prefix
    assert clinical_marker not in message
    assert raw_response not in message
    assert len(client.calls) == 2


# ── R1/R2: 1º mismatch de IDs dispara um único retry com os IDs exatos ──────


def test_echo_mismatch_triggers_single_retry_with_exact_ids() -> None:
    first_raw = json.dumps(_llm2_v4_payload(case_id="id-errado", agency_record_number="12345"))
    second_raw = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="12345"))
    client = RecordingLlmClient(responses=[first_raw, second_raw])

    result = _run_service(client, case_id="c1", agency_record_number="12345")

    assert len(client.calls) == 2
    assert [item["procedure_type"] for item in result.procedure_recommendations] == ["cpre"]
    base_prompt = client.calls[0]["user_prompt"]
    retry_prompt = client.calls[1]["user_prompt"]
    assert retry_prompt.startswith(base_prompt)
    retry_instruction = retry_prompt[len(base_prompt) :]
    assert "c1" in retry_instruction
    assert "12345" in retry_instruction
    assert "id-errado" in retry_instruction
    assert '"cpre"' in retry_instruction
    assert "lista fechada" in retry_instruction


# ── R3: 2º mismatch aborta sem 3ª chamada ───────────────────────────────────


def test_second_echo_mismatch_aborts_without_third_call() -> None:
    first_raw = json.dumps(_llm2_v4_payload(case_id="primeiro-errado", agency_record_number="12345"))
    second_raw = json.dumps(_llm2_v4_payload(case_id="segundo-errado", agency_record_number="12345"))
    client = RecordingLlmClient(responses=[first_raw, second_raw])

    with pytest.raises(Llm2V4EchoMismatchError) as exc_info:
        _run_service(client, case_id="c1", agency_record_number="12345")

    assert exc_info.value.field == "case_id"
    assert exc_info.value.expected == "c1"
    assert exc_info.value.got == "segundo-errado"
    assert len(client.calls) == 2


def test_second_agency_record_mismatch_aborts_without_third_call() -> None:
    first_raw = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="11111"))
    second_raw = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="22222"))
    client = RecordingLlmClient(responses=[first_raw, second_raw])

    with pytest.raises(Llm2V4EchoMismatchError) as exc_info:
        _run_service(client, case_id="c1", agency_record_number="12345")

    assert exc_info.value.field == "agency_record_number"
    assert exc_info.value.got == "22222"
    assert len(client.calls) == 2


# ── R4: retry de eco coexiste com o retry de procedure-set ──────────────────


def test_echo_retry_then_procedure_set_retry_coexist() -> None:
    wrong_ids_raw = json.dumps(_llm2_v4_payload(case_id="errado", agency_record_number="12345"))
    wrong_set_raw = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="12345", procedure_types=("eda",)))
    correct_raw = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="12345", procedure_types=("cpre",)))
    client = RecordingLlmClient(responses=[wrong_ids_raw, wrong_set_raw, correct_raw])

    result = _run_service(client, case_id="c1", agency_record_number="12345", detected_procedure_types=("cpre",))

    assert len(client.calls) == 3
    assert [item["procedure_type"] for item in result.procedure_recommendations] == ["cpre"]
    assert "lista fechada" in client.calls[1]["user_prompt"][len(client.calls[0]["user_prompt"]) :]
    assert "lista fechada" in client.calls[2]["user_prompt"][len(client.calls[0]["user_prompt"]) :]
