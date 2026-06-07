"""Tests for LLM1 Service — structured data extraction with Pydantic validation.

Follows the legacy augmented-triage-system contract (schema 1.1).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.llm1_service import (
    LLM1_DEFAULT_SYSTEM_PROMPT,
    LLM1_DEFAULT_USER_PROMPT,
    Llm1Result,
    Llm1Service,
    Llm1ValidationError,
    _render_user_prompt,
)

# ── Test helpers ────────────────────────────────────────────────────────────


def _valid_llm1_payload(*, agency_record_number: str = "12345", age: int | None = 45) -> dict[str, Any]:
    """Build a minimal valid LLM1 response dict (schema 1.1)."""
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "agency_record_number": agency_record_number,
        "patient": {
            "name": "Maria Silva",
            "age": age,
            "sex": "F",
        },
        "eda": {
            "indication_category": "dyspepsia",
            "exclusion_type": "none",
            "is_pediatric": (age is not None and age < 16),
            "foreign_body_suspected": False,
            "requested_procedure": {
                "name": "EDA",
                "urgency": "eletivo",
                "subtype": "standard",
            },
            "labs": {
                "hb_g_dl": None,
                "platelets_per_mm3": None,
                "inr": None,
                "source_text_hint": None,
            },
            "ecg": {
                "report_present": "unknown",
                "abnormal_flag": "unknown",
                "source_text_hint": None,
            },
        },
        "preop_screening": {
            "exam_type": "eda",
            "has_cardiovascular_disease": "no",
            "has_active_respiratory_symptoms": "no",
            "has_prior_respiratory_disease": "no",
            "has_ecg_report": "unknown",
            "has_chest_xray_report": "unknown",
            "hb_g_dl": None,
            "platelets_per_mm3": None,
            "inr": None,
            "rulebook_signals": {
                "eda_subtype": "standard",
            },
        },
        "policy_precheck": {
            "excluded_from_eda_flow": False,
            "exclusion_reason": None,
            "labs_required": True,
            "labs_pass": "unknown",
            "labs_failed_items": [],
            "ecg_required": False,
            "ecg_present": "unknown",
            "pediatric_flag": (age is not None and age < 16),
            "notes": None,
        },
        "summary": {
            "one_liner": "Dispepsia crônica — EDA eletiva indicada.",
            "bullet_points": [
                "Paciente com queixa de dor epigástrica.",
                "Sem sinais de alarme.",
                "Exames laboratoriais pendentes.",
            ],
        },
        "extraction_quality": {
            "confidence": "media",
            "missing_fields": ["labs"],
            "notes": None,
        },
    }


def _make_service(llm_response: str) -> Llm1Service:
    """Create a Llm1Service with a static client returning the given response."""
    return Llm1Service(StaticLlmClient(response_text=llm_response))


# ── Valid payloads (schema 1.1) ─────────────────────────────────────────────


class TestLlm1ValidPayloadPasses:
    """LLM1 deve aceitar payload válido schema 1.1."""

    def test_valid_payload_passes(self) -> None:
        payload = _valid_llm1_payload()
        service = _make_service(json.dumps(payload))

        result = service.run(
            case_id="case-001",
            agency_record_number="12345",
            extracted_text="Paciente referiu dor epigástrica.",
            system_prompt="Extract structured data from the report.",
            user_prompt_template="Extract EDA triage data.",
        )

        assert isinstance(result, Llm1Result)
        assert result.structured_data["schema_version"] == "1.1"
        assert result.summary_text == "Dispepsia crônica — EDA eletiva indicada."

    def test_prompt_metadata_is_returned(self) -> None:
        payload = _valid_llm1_payload()
        service = _make_service(json.dumps(payload))

        result = service.run(
            case_id="case-002",
            agency_record_number="12345",
            extracted_text="...",
            system_prompt="SP",
            user_prompt_template="UT",
        )

        assert result.prompt_system_name == "llm1_system"
        assert result.prompt_system_version == 0
        assert result.prompt_user_name == "llm1_user"
        assert result.prompt_user_version == 0


# ── Schema version validation ───────────────────────────────────────────────


class TestLlm1RejectsWrongSchemaVersion:
    """LLM1 deve rejeitar schema_version != 1.1."""

    def test_rejects_schema_1_0(self) -> None:
        payload = _valid_llm1_payload()
        payload["schema_version"] = "1.0"
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="schema_version"):
            service.run(
                case_id="case-003",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )

    def test_rejects_schema_2_0(self) -> None:
        payload = _valid_llm1_payload()
        payload["schema_version"] = "2.0"
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="schema_version"):
            service.run(
                case_id="case-004",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )


# ── Extra fields rejected ───────────────────────────────────────────────────


class TestLlm1RejectsExtraFields:
    """LLM1 deve rejeitar campos extras (extra="forbid")."""

    def test_extra_top_level_field_fails(self) -> None:
        payload = _valid_llm1_payload()
        payload["clinical_history"] = "some text"
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="Extra inputs are not permitted"):
            service.run(
                case_id="case-005",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )

    def test_extra_nested_field_fails(self) -> None:
        payload = _valid_llm1_payload()
        patient = payload.get("patient")
        assert isinstance(patient, dict)
        patient["gender"] = "F"
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="Extra inputs are not permitted"):
            service.run(
                case_id="case-006",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )


# ── Agency record number mismatch ───────────────────────────────────────────


class TestLlm1RejectsAgencyRecordMismatch:
    """LLM1 deve rejeitar agency_record_number divergente."""

    def test_agency_record_mismatch_fails(self) -> None:
        payload = _valid_llm1_payload(agency_record_number="99999")
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="agency_record_number"):
            service.run(
                case_id="case-007",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )


# ── Pediatric consistency ───────────────────────────────────────────────────


class TestLlm1PediatricConsistency:
    """LLM1 deve validar consistência pediátrica (age < 16)."""

    def test_age_10_is_pediatric_false_fails(self) -> None:
        payload = _valid_llm1_payload(age=10)
        # Override to make it inconsistent
        eda = payload.get("eda")
        assert isinstance(eda, dict)
        eda["is_pediatric"] = False
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="is_pediatric"):
            service.run(
                case_id="case-008",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )

    def test_age_45_is_pediatric_true_fails(self) -> None:
        payload = _valid_llm1_payload(age=45)
        eda = payload.get("eda")
        assert isinstance(eda, dict)
        eda["is_pediatric"] = True
        precheck = payload.get("policy_precheck")
        assert isinstance(precheck, dict)
        precheck["pediatric_flag"] = True
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="is_pediatric"):
            service.run(
                case_id="case-009",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )

    def test_pediatric_flag_inconsistent_fails(self) -> None:
        payload = _valid_llm1_payload(age=10)
        # eda.is_pediatric is correct from helper, but we break policy_precheck
        precheck = payload.get("policy_precheck")
        assert isinstance(precheck, dict)
        precheck["pediatric_flag"] = False
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="pediatric_flag"):
            service.run(
                case_id="case-010",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )


# ── EDA subtype alignment ───────────────────────────────────────────────────


class TestLlm1EdaSubtypeAlignment:
    """LLM1 deve validar consistência entre os dois campos de subtipo EDA."""

    def test_duplicated_subtype_inconsistent_fails(self) -> None:
        payload = _valid_llm1_payload()
        eda = payload.get("eda")
        assert isinstance(eda, dict)
        rp = eda.get("requested_procedure")
        assert isinstance(rp, dict)
        rp["subtype"] = "standard"
        preop = payload.get("preop_screening")
        assert isinstance(preop, dict)
        rulebook = preop.get("rulebook_signals")
        assert isinstance(rulebook, dict)
        rulebook["eda_subtype"] = "esophageal_dilation"
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="subtype"):
            service.run(
                case_id="case-011",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )

    def test_unknown_subtype_allows_mismatch(self) -> None:
        """When one subtype is 'unknown', no consistency error."""
        payload = _valid_llm1_payload()
        eda = payload.get("eda")
        assert isinstance(eda, dict)
        rp = eda.get("requested_procedure")
        assert isinstance(rp, dict)
        rp["subtype"] = "unknown"
        service = _make_service(json.dumps(payload))

        result = service.run(
            case_id="case-012",
            agency_record_number="12345",
            extracted_text="...",
            system_prompt="SP",
            user_prompt_template="UT",
        )
        assert result.summary_text


# ── Missing required fields ─────────────────────────────────────────────────


class TestLlm1RejectsMissingRequiredFields:
    """LLM1 deve rejeitar payload sem campos obrigatórios."""

    def test_missing_eda_fails(self) -> None:
        payload = _valid_llm1_payload()
        del payload["eda"]
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="eda"):
            service.run(
                case_id="case-013",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )

    def test_missing_language_fails(self) -> None:
        payload = _valid_llm1_payload()
        payload["language"] = "en-US"
        service = _make_service(json.dumps(payload))

        with pytest.raises(Llm1ValidationError, match="language"):
            service.run(
                case_id="case-014",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )


# ── JSON parse errors ───────────────────────────────────────────────────────


class TestLlm1RaisesOnInvalidJson:
    """LLM1 deve levantar erro quando o client retorna JSON inválido."""

    def test_raises_on_plain_text_response(self) -> None:
        service = _make_service("just some random text")

        with pytest.raises(Llm1ValidationError, match="non-JSON"):
            service.run(
                case_id="case-015",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )

    def test_raises_on_empty_response(self) -> None:
        service = _make_service("")

        with pytest.raises(Llm1ValidationError, match="non-JSON"):
            service.run(
                case_id="case-016",
                agency_record_number="12345",
                extracted_text="...",
                system_prompt="SP",
                user_prompt_template="UT",
            )


# ── Prompt rendering: legacy instructions ───────────────────────────────────


class TestLlm1PromptContainsLegacyInstructions:
    """O prompt final do LLM1 deve conter instruções legadas de escopo EDA."""

    def test_prompt_contains_eda_scope_terms(self) -> None:
        payload = _valid_llm1_payload()
        client = RecordingLlmClient(responses=[json.dumps(payload)])
        service = Llm1Service(client)

        service.run(
            case_id="case-017",
            agency_record_number="12345",
            extracted_text="Paciente com queixa gástrica.",
            system_prompt="System prompt.",
            user_prompt_template="User template base.",
        )

        assert len(client.calls) == 1
        user_prompt = client.calls[0]["user_prompt"]

        # Must contain legacy EDA scope instructions
        assert "GTT/gastrostomia/PEG" in user_prompt or "gastrostomia" in user_prompt.lower()
        assert "dilatacao esofagica" in user_prompt.lower() or "dilatação esofágica" in user_prompt.lower()
        assert "corpo estranho" in user_prompt.lower()
        assert "CPRE" in user_prompt
        assert "non_eda" in user_prompt

    def test_prompt_contains_explicit_schema_contract_and_forbidden_aliases(self) -> None:
        payload = _valid_llm1_payload()
        client = RecordingLlmClient(responses=[json.dumps(payload)])
        service = Llm1Service(client)

        service.run(
            case_id="case-schema",
            agency_record_number="12345",
            extracted_text="Paciente masculino com solicitação de EDA.",
            system_prompt="SP",
            user_prompt_template="UT base",
        )

        user_prompt = client.calls[0]["user_prompt"]
        assert "CONTRATO JSON OBRIGATORIO" in user_prompt
        assert 'language: exatamente "pt-BR"' in user_prompt
        assert 'patient.sex: apenas "M", "F" ou "Outro"' in user_prompt
        assert 'EvidenceFlag devem ser strings "yes", "no" ou "unknown"' in user_prompt
        assert "nunca true/false" in user_prompt
        assert "tracked_exams[]" in user_prompt
        assert "NUNCA use estes nomes/aliases" in user_prompt
        assert "age_years" in user_prompt
        assert "triage_summary" in user_prompt
        assert "case_id no JSON de resposta" in user_prompt

    def test_prompt_includes_case_id_and_record(self) -> None:
        payload = _valid_llm1_payload(agency_record_number="99999")
        client = RecordingLlmClient(responses=[json.dumps(payload)])
        service = Llm1Service(client)

        service.run(
            case_id="case-018",
            agency_record_number="99999",
            extracted_text="Report text here.",
            system_prompt="SP",
            user_prompt_template="UT base",
        )

        user_prompt = client.calls[0]["user_prompt"]
        assert "case-018" in user_prompt
        assert "99999" in user_prompt

    def test_prompt_includes_clinical_text(self) -> None:
        payload = _valid_llm1_payload()
        client = RecordingLlmClient(responses=[json.dumps(payload)])
        service = Llm1Service(client)

        service.run(
            case_id="case-019",
            agency_record_number="12345",
            extracted_text="Paciente relata dor epigástrica há 3 meses.",
            system_prompt="SP",
            user_prompt_template="UT base",
        )

        user_prompt = client.calls[0]["user_prompt"]
        assert "Paciente relata dor epigástrica há 3 meses." in user_prompt


# ── Tracked-exam hardening ────────────────────────────────────────────────


class TestLlm1PromptTrackedExamHardening:
    """R1/R2: Prompt renderizado deve proibir ausência e pedir data para todos tracked_exams."""

    def test_render_user_prompt_prohibits_absent_exam_entries_in_tracked_exams(self) -> None:
        prompt = _render_user_prompt(
            template="Template base",
            case_id="case-teh-001",
            agency_record_number="12345",
            clean_text="Texto clinico.",
        )
        assert "tracked_exams" in prompt
        assert "inclua apenas exames efetivamente realizados" in prompt or "apenas exames realizados" in prompt
        assert "Sem Exame" in prompt or "sem exame" in prompt
        assert "não realizado" in prompt or "nao realizado" in prompt
        assert "não consta" in prompt or "nao consta" in prompt
        assert "não inclua" in prompt or "Nao inclua" in prompt or "nao inclua" in prompt

    def test_render_user_prompt_requires_datetime_for_all_tracked_exams_when_available(self) -> None:
        prompt = _render_user_prompt(
            template="Template base",
            case_id="case-teh-002",
            agency_record_number="12345",
            clean_text="Texto clinico.",
        )
        assert "exam_datetime_iso" in prompt
        assert "todo exame" in prompt
        assert "não apenas para o exame mais recente" in prompt or "nao apenas para o exame mais recente" in prompt

    def test_default_user_prompt_prohibits_absent_exam_entries_and_requires_all_dates(self) -> None:
        up = LLM1_DEFAULT_USER_PROMPT
        assert "Sem Exame" in up or "sem exame" in up
        assert "não realizado" in up or "nao realizado" in up
        assert "exam_datetime_iso" in up
        assert "realizados" in up


# ── Fallback / default LLM1 prompts ─────────────────────────────────────────


class TestLlm1FallbackDefaults:
    """Os defaults/fallback do LLM1 devem conter instruções críticas do legado v6."""

    def test_default_system_prompt_contains_v6_terms(self) -> None:
        sp = LLM1_DEFAULT_SYSTEM_PROMPT
        assert "schema_version" in sp
        assert "1.1" in sp
        assert "origin_context" in sp
        assert "tracked_exams" in sp
        assert "had_transfusion" in sp
        assert "gastrostomy" in sp or "gastrostomia" in sp or "GTT" in sp

    def test_default_user_prompt_contains_v6_terms(self) -> None:
        up = LLM1_DEFAULT_USER_PROMPT
        assert "origin_context" in up
        assert "tracked_exams" in up
        assert "had_transfusion" in up
        assert "rulebook_signals" in up
        assert "evidence_spans" in up
        assert "CONTRATO JSON OBRIGATORIO" in up
        assert "patient.sex" in up
        assert "full_name" in up
        assert "age_years" in up
        assert "triage_summary" in up

    def test_defaults_dont_diverge_from_v6_migration(self) -> None:
        """Seed e fallback não divergem nos blocos essenciais do legado v6."""
        # System prompt essentials
        for text in [LLM1_DEFAULT_SYSTEM_PROMPT]:
            assert "origin_context" in text
            assert "tracked_exams" in text
            assert "had_transfusion" in text
            # v6-specific: recency
            assert "recencia" in text or "recência" in text
            # v6-specific: binary transfusion
            assert "binario" in text or "binário" in text

        # User prompt essentials
        for text in [LLM1_DEFAULT_USER_PROMPT]:
            assert "origin_context" in text
            assert "tracked_exams" in text
            assert "had_transfusion" in text
            assert "recencia" in text or "recência" in text
            assert "binario" in text or "binário" in text
            assert "ausencia de evidencia" in text or "ausência de evidência" in text


# ── structured_data via model_dump(mode="json") ─────────────────────────────


class TestLlm1StructuredDataJsonMode:
    """LLM1 deve retornar structured_data serializado via model_dump(mode='json')."""

    def test_structured_data_is_json_serializable(self) -> None:
        payload = _valid_llm1_payload()
        service = _make_service(json.dumps(payload))

        result = service.run(
            case_id="case-020",
            agency_record_number="12345",
            extracted_text="...",
            system_prompt="SP",
            user_prompt_template="UT",
        )

        # Must be json-serializable (model_dump mode="json" ensures this)
        serialized = json.dumps(result.structured_data)
        roundtripped = json.loads(serialized)
        assert roundtripped["schema_version"] == "1.1"
        assert roundtripped["language"] == "pt-BR"


# ── Language retry ──────────────────────────────────────────────────────────


class TestLlm1LanguageRetry:
    """LLM1 deve fazer retry de linguagem quando houver termos em inglês."""

    def test_no_retry_when_all_ptbr(self) -> None:
        """Sem termos proibidos, apenas uma chamada é feita."""
        payload = _valid_llm1_payload()
        client = RecordingLlmClient(responses=[json.dumps(payload)])
        service = Llm1Service(client)

        service.run(
            case_id="case-lr-001",
            agency_record_number="12345",
            extracted_text="Relatório clínico.",
            system_prompt="SP",
            user_prompt_template="UT",
        )
        assert len(client.calls) == 1

    def test_retries_once_when_first_has_forbidden_terms(self) -> None:
        """Primeira resposta contém termo proibido → retry é chamado."""
        # First response: one_liner contains English word
        payload1 = _valid_llm1_payload()
        payload1["summary"]["one_liner"] = "Patient with dyspepsia — EDA indicated."
        # Second response: clean
        payload2 = _valid_llm1_payload()
        payload2["summary"]["one_liner"] = "Paciente com dispepsia — EDA indicada."

        client = RecordingLlmClient(
            responses=[
                json.dumps(payload1),
                json.dumps(payload2),
            ]
        )
        service = Llm1Service(client)

        result = service.run(
            case_id="case-lr-002",
            agency_record_number="12345",
            extracted_text="Relatório.",
            system_prompt="SP",
            user_prompt_template="UT",
        )
        assert len(client.calls) == 2
        # Second call should include retry instruction
        user_prompt2 = client.calls[1]["user_prompt"]
        assert "Regra obrigatoria adicional" in user_prompt2
        assert "portugues brasileiro" in user_prompt2
        # Result should be from second (clean) response
        assert "Paciente com dispepsia" in result.summary_text

    def test_raises_when_both_have_forbidden_terms(self) -> None:
        """Segunda resposta ainda contém termo proibido → Llm1ValidationError."""
        payload1 = _valid_llm1_payload()
        payload1["summary"]["one_liner"] = "Patient with dyspepsia."
        payload2 = _valid_llm1_payload()
        payload2["summary"]["one_liner"] = "Patient accepted for EDA."

        client = RecordingLlmClient(
            responses=[
                json.dumps(payload1),
                json.dumps(payload2),
            ]
        )
        service = Llm1Service(client)

        with pytest.raises(Llm1ValidationError, match="non-ptbr"):
            service.run(
                case_id="case-lr-003",
                agency_record_number="12345",
                extracted_text="Relatório.",
                system_prompt="SP",
                user_prompt_template="UT",
            )
        assert len(client.calls) == 2

    def test_forbidden_term_in_bullet_points_triggers_retry(self) -> None:
        """Termo proibido em bullet_points também dispara retry."""
        payload1 = _valid_llm1_payload()
        payload1["summary"]["bullet_points"] = [
            "Patient reported epigastric pain.",
            "Sem sinais de alarme.",
            "Exames pendentes.",
        ]
        payload2 = _valid_llm1_payload()

        client = RecordingLlmClient(
            responses=[
                json.dumps(payload1),
                json.dumps(payload2),
            ]
        )
        service = Llm1Service(client)

        service.run(
            case_id="case-lr-004",
            agency_record_number="12345",
            extracted_text="Relatório.",
            system_prompt="SP",
            user_prompt_template="UT",
        )
        assert len(client.calls) == 2
        assert "Regra obrigatoria adicional" in client.calls[1]["user_prompt"]

    def test_forbidden_term_in_notes_triggers_retry(self) -> None:
        """Termo proibido em policy_precheck.notes também dispara retry."""
        payload1 = _valid_llm1_payload()
        payload1["policy_precheck"]["notes"] = "Patient has no contraindications. Recommend accept."
        payload2 = _valid_llm1_payload()

        client = RecordingLlmClient(
            responses=[
                json.dumps(payload1),
                json.dumps(payload2),
            ]
        )
        service = Llm1Service(client)

        service.run(
            case_id="case-lr-005",
            agency_record_number="12345",
            extracted_text="Relatório.",
            system_prompt="SP",
            user_prompt_template="UT",
        )
        assert len(client.calls) == 2
