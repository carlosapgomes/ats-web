"""Fronteira LLM mascarada e fail-closed (Slice 3, PI-03/PI-06/PI-07/PI-09).

Nomes/CNS sintéticos (PI-13). Captura prompts via RecordingLlmClient.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.cases.models import Case, CaseStatus
from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.orchestrator import run_pipeline

NAME = "Maria Clara Souza Teste"
CNS = "700123456789012"

HEADER_TEXT = (
    "RELATORIO DE OCORRENCIAS\n"
    "Governo do Estado da Bahia\n"
    "Codigo: 12345\n"
    f"{NAME} - Idade: 45a.  - Sexo Feminino\n"
    "Paciente:\n"
    f"CNS: {CNS}\n"
    "Nome Social:\n"
    "Central. Reg.:\n"
    "Motivo da Solicitacao: EDA\n"
    "Resumo Clinico: Solicito EDA. "
    f"Paciente {NAME} relata dispepsia.\n"
)


def _make_case(user: Any, *, extracted_text: str) -> Case:
    from apps.cases.procedures import set_declared_procedures

    case = Case.objects.create(created_by=user, agency_record_number="12345", extracted_text=extracted_text)
    set_declared_procedures(case=case, procedure_types=("eda",), actor=user)
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()
    return case


def _llm1_response(*, one_liner: str = "EDA eletiva indicada.") -> str:
    return json.dumps(
        {
            "schema_version": "4.0",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": NAME, "age": 45, "sex": "F", "document_id": CNS},
            "common_preop": {
                "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0, "source_text_hint": None},
                "ecg": {"report_present": "unknown", "abnormal_flag": "unknown", "source_text_hint": None},
                "asa": {"bucket": "I-II", "source_text_hint": None},
                "cardiovascular_risk": {"level": "low", "source_text_hint": None},
                "rulebook_signals": {
                    "eda_subtype": "standard",
                    "minimum_exam_evidence": {
                        "hb_numeric_present": "yes",
                        "platelets_numeric_present": "yes",
                        "tp_inr_rni_numeric_present": "yes",
                        "ttpa_present": "yes",
                        "urea_present": "yes",
                        "creatinine_present": "yes",
                    },
                    "conditional_exam_requirements": {},
                    "clinical_flags": {},
                },
                "comorbidities_described": [],
                "medications_described": [],
                "evidence_spans": [],
            },
            "requested_procedures": [
                {
                    "procedure_type": "eda",
                    "name": "EDA",
                    "urgency": "eletivo",
                    "indication_category": "dyspepsia",
                    "subtype": "standard",
                    "evidence_spans": [{"field_path": "motivo_da_solicitacao", "excerpt": "Solicito EDA"}],
                }
            ],
            "policy_precheck": {
                "excluded_from_eda_flow": False,
                "exclusion_reason": None,
                "labs_required": True,
                "labs_pass": "yes",
                "labs_failed_items": [],
                "ecg_required": False,
                "ecg_present": "unknown",
                "pediatric_flag": False,
                "notes": None,
            },
            "summary": {"one_liner": one_liner, "bullet_points": ["Ponto 1", "Ponto 2", "Ponto 3"]},
            "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
            "origin_context": {
                "city": None,
                "hospital": None,
                "unit": None,
                "state_uf": None,
                "source_text_hint": None,
            },
            "transfusion": {"had_transfusion": "no"},
            "tracked_exams": [],
        }
    )


def _llm2_response(case_id: str) -> str:
    return json.dumps(
        {
            "schema_version": "4.0",
            "language": "pt-BR",
            "case_id": case_id,
            "agency_record_number": "12345",
            "procedure_recommendations": [
                {
                    "procedure_type": "eda",
                    "suggestion": "accept",
                    "support_recommendation": "none",
                    "rationale": {
                        "short_reason": "Critérios atendidos.",
                        "details": ["Sem contraindicação.", "Exames compatíveis."],
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
            ],
            "global_support_recommendation": "none",
            "summary": None,
        }
    )


@pytest.mark.django_db
class TestMaskedLlmBoundary:
    def test_prompts_masked_and_local_name_injected(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-pii", password="pw")
        case = _make_case(user, extracted_text=HEADER_TEXT)
        client = RecordingLlmClient(
            responses=[
                _llm1_response(one_liner=f"{NAME} com dispepsia; EDA indicada."),
                _llm2_response(str(case.case_id)),
            ]
        )

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
            llm2_system_prompt="sp2",
            llm2_user_template="ut2",
        )

        assert len(client.calls) == 2
        for call in client.calls:
            assert NAME not in call["user_prompt"]
            assert CNS not in call["user_prompt"]
        assert "[NOME_REMOVIDO]" in client.calls[0]["user_prompt"]
        assert "[CNS_REMOVIDO]" in client.calls[0]["user_prompt"]

        reloaded = Case.objects.get(case_id=case.case_id)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        assert reloaded.structured_data is not None
        patient = reloaded.structured_data["patient"]
        assert patient["name"] == NAME  # proveniência local, não do modelo
        assert patient["document_id"] is None
        assert NAME not in reloaded.summary_text
        assert reloaded.patient_identity_name == NAME
        assert reloaded.patient_identity_status == "extracted"

    def test_ambiguous_identity_blocks_without_llm_call(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-amb", password="pw")
        divergent = HEADER_TEXT + "\n" + HEADER_TEXT.replace(NAME, "Outra Pessoa Teste")
        case = _make_case(user, extracted_text=divergent)
        client = RecordingLlmClient(responses=[_llm1_response(), _llm2_response(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        assert client.calls == []
        reloaded = Case.objects.get(case_id=case.case_id)
        assert reloaded.status == CaseStatus.FAILED


class TestLlm1ServiceStripsIdentity:
    def test_service_forces_patient_identity_null(self) -> None:
        from apps.pipeline.llm1_service_v4 import Llm1ServiceV4

        service = Llm1ServiceV4(StaticLlmClient(_llm1_response()))
        result = service.run(
            case_id="00000000-0000-0000-0000-000000000001",
            agency_record_number="12345",
            extracted_text="[NOME_REMOVIDO] Solicito EDA.",
            declared_procedure_types=("eda",),
            system_prompt="sp",
            user_prompt_template="ut",
        )
        patient = result.structured_data["patient"]
        assert isinstance(patient, dict)
        assert patient["name"] is None
        assert patient["document_id"] is None
        assert patient["age"] == 45
