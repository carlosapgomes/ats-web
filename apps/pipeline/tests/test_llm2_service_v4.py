"""Echo mismatch nao-fatal no LLM2 v4 (change ``llm2-v4-echo-nonfatal-overwrite``).

Resposta schema-valida com ``case_id`` / ``agency_record_number`` divergentes
prossegue via overwrite com warning observavel, sem retry de eco e sem FAILED.
Sem DB.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.llm2_service_v4 import Llm2ServiceV4

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


# ── R1/R3/R4/R5: case_id divergente → overwrite + warning, 1 chamada ────────


def test_case_id_mismatch_overwrites_and_succeeds_with_single_call(caplog: Any) -> None:
    raw_response = json.dumps(_llm2_v4_payload(case_id="outro-id", agency_record_number="12345"))
    client = RecordingLlmClient(responses=[raw_response])

    with caplog.at_level(logging.WARNING, logger="apps.pipeline.llm2_service_v4"):
        result = _run_service(client, case_id="c1")

    assert [item["procedure_type"] for item in result.procedure_recommendations] == ["cpre"]
    assert len(client.calls) == 1
    warning_text = caplog.text
    assert "case_id mismatch" in warning_text
    assert "expected 'c1'" in warning_text
    assert "got 'outro-id'" in warning_text
    assert f"raw_len={len(raw_response)}" in warning_text
    expected_sha256_prefix = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()[:12]
    match = RAW_SHA256_PATTERN.search(warning_text)
    assert match is not None
    assert match.group(1) == expected_sha256_prefix


# ── R2/R3/R4/R5: agency_record_number divergente → idem ─────────────────────


def test_agency_record_number_mismatch_overwrites_and_succeeds_with_single_call(caplog: Any) -> None:
    raw_response = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="99999"))
    client = RecordingLlmClient(responses=[raw_response])

    with caplog.at_level(logging.WARNING, logger="apps.pipeline.llm2_service_v4"):
        result = _run_service(client, agency_record_number="12345")

    assert [item["procedure_type"] for item in result.procedure_recommendations] == ["cpre"]
    assert len(client.calls) == 1
    warning_text = caplog.text
    assert "agency_record_number mismatch" in warning_text
    assert "expected '12345'" in warning_text
    assert "got '99999'" in warning_text
    assert f"raw_len={len(raw_response)}" in warning_text
    expected_sha256_prefix = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()[:12]
    match = RAW_SHA256_PATTERN.search(warning_text)
    assert match is not None
    assert match.group(1) == expected_sha256_prefix


# ── R3: warning sem conteúdo clínico ────────────────────────────────────────


def test_mismatch_warning_carries_raw_metadata_without_clinical_text(caplog: Any) -> None:
    clinical_marker = "MARCADOR-CLINICO-NAO-DEVE-VAZAR"
    raw_response = json.dumps(
        _llm2_v4_payload(case_id="outro-id", agency_record_number="12345", short_reason=clinical_marker)
    )
    client = RecordingLlmClient(responses=[raw_response])

    with caplog.at_level(logging.WARNING, logger="apps.pipeline.llm2_service_v4"):
        result = _run_service(client, case_id="c1")

    assert [item["procedure_type"] for item in result.procedure_recommendations] == ["cpre"]
    assert len(client.calls) == 1
    warning_records = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert warning_records, "esperava ao menos um warning de overwrite"
    warning_text = "\n".join(record.getMessage() for record in warning_records)
    assert clinical_marker not in warning_text
    assert raw_response not in warning_text


# ── R5: caminho feliz inalterado (1 chamada, sem warning de eco) ────────────


def test_happy_path_single_call_without_echo_warning(caplog: Any) -> None:
    raw_response = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="12345"))
    client = RecordingLlmClient(responses=[raw_response])

    with caplog.at_level(logging.WARNING, logger="apps.pipeline.llm2_service_v4"):
        result = _run_service(client, case_id="c1", agency_record_number="12345")

    assert [item["procedure_type"] for item in result.procedure_recommendations] == ["cpre"]
    assert len(client.calls) == 1
    assert "mismatch" not in caplog.text


# ── R5: coexistência — eco divergente + conjunto errado → retry de conjunto ──


def test_echo_mismatch_with_wrong_procedure_set_still_retries_set(caplog: Any) -> None:
    wrong_ids_and_set_raw = json.dumps(
        _llm2_v4_payload(case_id="errado", agency_record_number="12345", procedure_types=("eda",))
    )
    correct_raw = json.dumps(_llm2_v4_payload(case_id="c1", agency_record_number="12345", procedure_types=("cpre",)))
    client = RecordingLlmClient(responses=[wrong_ids_and_set_raw, correct_raw])

    with caplog.at_level(logging.WARNING, logger="apps.pipeline.llm2_service_v4"):
        result = _run_service(client, case_id="c1", agency_record_number="12345", detected_procedure_types=("cpre",))

    assert [item["procedure_type"] for item in result.procedure_recommendations] == ["cpre"]
    assert len(client.calls) == 2
    base_prompt = client.calls[0]["user_prompt"]
    retry_prompt = client.calls[1]["user_prompt"]
    assert retry_prompt.startswith(base_prompt)
    assert "lista fechada" in retry_prompt[len(base_prompt) :]
    assert "case_id mismatch" in caplog.text
