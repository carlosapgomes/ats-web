"""Echo mismatch observável no LLM2 v4 (change ``llm2-v4-echo-mismatch-fix``, slice 001).

Cobre o diagnóstico de resposta schema-válida que ecoa ``case_id`` /
``agency_record_number`` divergentes: exceção tipada com ``field``/``expected``/
``got`` e metadados não-clínicos do raw (``raw_len`` + ``raw_sha256`` de 12 hex).

Sem DB e sem retry: um mismatch é erro imediato com exatamente uma chamada.
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
    client = RecordingLlmClient(responses=[raw_response])

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
    assert len(client.calls) == 1


# ── R2/R5: agency_record_number divergente ──────────────────────────────────


def test_agency_record_number_mismatch_reports_expected_and_got() -> None:
    raw_response = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="99999"))
    client = RecordingLlmClient(responses=[raw_response])

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
    assert len(client.calls) == 1


# ── R3: metadados do raw sem conteúdo clínico ───────────────────────────────


def test_mismatch_message_carries_raw_metadata_without_clinical_text() -> None:
    clinical_marker = "MARCADOR-CLINICO-NAO-DEVE-VAZAR"
    raw_response = json.dumps(
        _llm2_v4_payload(case_id="outro-id", agency_record_number="12345", short_reason=clinical_marker)
    )
    client = RecordingLlmClient(responses=[raw_response])

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
