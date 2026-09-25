"""Slice 004 (R2–R7) — CPRE do NIR à avaliação médica.

Reutiliza as fronteiras aprovadas nos Slices 002/003 (mesma proveniência por
ocorrência, mesmo verificador determinístico de imagem, mesma policy agregada)
e cobre exclusivamente o recorte CPRE:

- R2: o detector qualifica ``CPRE``/nome completo com a mesma proveniência por
  ocorrência; histórico/negação nunca criam solicitação atual; ``EDA com/e
  CPRE`` colapsa SOMENTE quando a ocorrência prova o vínculo textual.
- R3: a policy aceita US/TC/RM/CPRM apenas após verificação determinística
  (contexto único ancorado, modalidade/anatomia rederivadas, predicado/heading
  estrito). Solicitação com/sem ``laudo``, agendamento, menção, conflito de
  aliases, duplicidade, contexto amplo, mismatch, excerpt inventado,
  ``tracked_exams``-only e anexo-only falham; data antiga é preservada e não
  expira.
- R4: pendências agregadas forçam sugestão deny sem bloquear o médico.
- R5/R6/R7: CPRE chega a ``WAIT_DOCTOR`` como singleton com recomendação
  própria; as projeções CHD/NIR seguem as fronteiras aprovadas (cobertas nos
  testes de ``scheduler``/``intake``).

Slice 001 do change ``prioritize-specialized-procedure-requests`` (ADR-0008):

- R1: exatamente uma CPRE detectada com ocorrência textual ``current_request``
  suprime EDA/Colonoscopia mesmo em trechos independentes;
- R2: CPRE + Ecoendoscopia continuam fail-closed;
- R3: item estruturado de CPRE sem ocorrência atual não autoriza supressão;
- R5/R6: precedência auditada em evento/sugestão, ``structured_data`` original
  preservado, LLM2 só com CPRE e aviso médico informativo com label canônico.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.cases.models import Case, CaseAttachment, CaseEvent, CaseProcedure, CaseStatus, DetectionStatus, ProcedureType
from apps.cases.procedures import set_declared_procedures
from apps.pipeline.imaging_evidence import verify_abdominal_imaging_evidence
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.policy.procedure_policy import evaluate_procedure_policy
from apps.pipeline.procedure_reconciliation import reconcile_detected_procedures
from apps.pipeline.scope_detection import (
    detect_procedure_occurrences,
    detect_requested_procedures_v3,
)

pytestmark = pytest.mark.django_db


# ── Helpers ─────────────────────────────────────────────────────────────────


def _span(excerpt: str) -> dict[str, str]:
    return {"field_path": "p.0", "excerpt": excerpt}


def _cpre_procedure(name: str = "CPRE") -> dict[str, Any]:
    return {
        "procedure_type": "cpre",
        "name": name,
        "urgency": "eletivo",
        "evidence_spans": [_span("Solicito CPRE")],
    }


def _eda_procedure() -> dict[str, Any]:
    return {
        "procedure_type": "eda",
        "name": "EDA",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "subtype": "standard",
        "evidence_spans": [_span("Solicito EDA")],
    }


def _colon_procedure() -> dict[str, Any]:
    return {
        "procedure_type": "colonoscopy",
        "name": "Colonoscopia",
        "urgency": "eletivo",
        "indication_category": "screening",
        "subtype": "standard",
        "evidence_spans": [_span("Solicito colonoscopia")],
    }


def _imaging(
    *,
    context: str,
    modality: str,
    site: str,
    finding_present: str = "yes",
    finding_excerpt: str | None = None,
    exam_datetime_iso: str | None = None,
) -> dict[str, Any]:
    return {
        "modality": modality,
        "anatomical_site": site,
        "report_finding_present": finding_present,
        "source_document": "main_report",
        "evidence_context_excerpt": context,
        "finding_excerpt": finding_excerpt if finding_excerpt is not None else context,
        "exam_datetime_iso": exam_datetime_iso,
    }


def _llm1_json(
    *,
    procedures: list[dict[str, Any]],
    imaging: list[dict[str, Any]] | None = None,
    one_liner: str = "CPRE indicada.",
) -> str:
    return json.dumps(
        {
            "schema_version": "4.0",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": "Paciente", "age": 35, "sex": "M", "document_id": None},
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
                "abdominal_imaging": imaging or [],
                "evidence_spans": [],
            },
            "requested_procedures": procedures,
            "policy_precheck": {
                "excluded_from_eda_flow": "no",
                "exclusion_reason": None,
                "labs_required": "yes",
                "labs_pass": "yes",
                "labs_failed_items": [],
                "ecg_required": "no",
                "ecg_present": "unknown",
                "pediatric_flag": False,
                "notes": None,
            },
            "summary": {"one_liner": one_liner, "bullet_points": ["a", "b", "c"]},
            "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
            "transfusion": {"had_transfusion": "no"},
        }
    )


def _llm2_json(case_id: str, *, procedure_type: str, suggestion: str = "accept") -> str:
    return json.dumps(
        {
            "schema_version": "4.0",
            "language": "pt-BR",
            "case_id": case_id,
            "agency_record_number": "12345",
            "procedure_recommendations": [
                {
                    "procedure_type": procedure_type,
                    "suggestion": suggestion,
                    "support_recommendation": "none",
                    "rationale": {
                        "short_reason": "Criterios atendidos.",
                        "details": ["Sem contraindicacao.", "Exames compativeis."],
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


def _make_case(user, *, procedure_types: tuple[str, ...], extracted_text: str) -> Case:
    case = Case.objects.create(created_by=user, agency_record_number="12345", extracted_text=extracted_text)
    set_declared_procedures(case=case, procedure_types=list(procedure_types), actor=user)
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()
    return case


def _reload(case: Case) -> Case:
    return Case.objects.get(case_id=case.case_id)


def _recommendations(case: Case) -> list[dict[str, Any]]:
    suggested = case.suggested_action
    assert isinstance(suggested, dict)
    recommendations = suggested.get("procedure_recommendations")
    assert isinstance(recommendations, list)
    return recommendations


def _decision_codes(decision: dict[str, Any]) -> list[str]:
    requirements = decision.get("failed_requirements")
    assert isinstance(requirements, list)
    return [str(requirement["code"]) for requirement in requirements]


def _cpre_structured_data() -> dict[str, object]:
    """Projeção 1.1 mínima de CPRE com exames mínimos completos (D8)."""
    return {
        "schema_version": "1.1",
        "patient": {"age": 35},
        "eda": {"requested_procedure": {"subtype": "standard"}, "indication_category": "unknown"},
        "preop_screening": {
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
            }
        },
    }


def _verify(*, context: str, report: str, modality: str, site: str, **overrides: Any) -> Any:
    return verify_abdominal_imaging_evidence(
        entries=[_imaging(context=context, modality=modality, site=site, **overrides)],
        main_report_text=report,
    )


# ── R2: ocorrências qualificadas de CPRE ────────────────────────────────────


class TestCpreOccurrenceDetection:
    def test_cpre_acronym_current_request_is_detected(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito CPRE para avaliacao de via biliar.",
        )
        cpre = next(o for o in occurrences if o.procedure_type == "cpre")
        assert cpre.qualification == "current_request"
        assert cpre.excerpt.strip() != ""
        assert cpre.evidence_id.startswith("cpre:")

        detection = detect_requested_procedures_v3(
            llm1_structured_data={},
            cleaned_text="Solicito CPRE para avaliacao de via biliar.",
        )
        assert detection["cpre"] == {"strong": True, "any": True}

    def test_cpre_full_name_current_request_is_detected(self) -> None:
        detection = detect_requested_procedures_v3(
            llm1_structured_data={},
            cleaned_text="Solicito colangiopancreatografia endoscopica retrograda.",
        )
        assert detection["cpre"] == {"strong": True, "any": True}

    def test_historical_cpre_never_creates_detection(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Historico de CPRE realizada em 2018. Solicito EDA.",
        )
        cpre = next(o for o in occurrences if o.procedure_type == "cpre")
        assert cpre.qualification == "historical"

        detection = detect_requested_procedures_v3(
            llm1_structured_data={},
            cleaned_text="Historico de CPRE realizada em 2018. Solicito EDA.",
        )
        assert detection["cpre"] == {"strong": False, "any": False}
        assert detection["eda"]["any"] is True

    def test_negated_cpre_never_creates_detection(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Sem indicacao de CPRE neste momento.",
        )
        cpre = next(o for o in occurrences if o.procedure_type == "cpre")
        assert cpre.qualification == "negated"

        detection = detect_requested_procedures_v3(
            llm1_structured_data={},
            cleaned_text="Sem indicacao de CPRE neste momento.",
        )
        assert detection["cpre"] == {"strong": False, "any": False}

    def test_linked_expression_marks_both_occurrences(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA com CPRE para avaliacao de via biliar.",
        )
        cpre = next(o for o in occurrences if o.procedure_type == "cpre")
        eda = next(o for o in occurrences if o.procedure_type == "eda")
        assert cpre.linked_eda is True
        assert eda.linked_eda is True
        assert cpre.qualification == "current_request"
        assert cpre.evidence_id != eda.evidence_id

    def test_independent_requests_are_not_linked(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA. Solicito CPRE.",
        )
        cpre = next(o for o in occurrences if o.procedure_type == "cpre")
        assert cpre.qualification == "current_request"
        assert cpre.linked_eda is False


# ── R2: precedência por vínculo textual ─────────────────────────────────────


class TestCprePrecedence:
    def test_linked_expression_collapses_to_cpre(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA com CPRE.",
        )
        result = reconcile_detected_procedures(
            declared=("cpre",),
            strong=("eda", "cpre"),
            any_evidence=("eda", "cpre"),
            occurrences=occurrences,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == (ProcedureType.CPRE,)

    def test_independent_eda_and_cpre_requests_prioritize_cpre(self) -> None:
        """R1: solicitações independentes priorizam CPRE quando ela é atual."""
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA. Solicito CPRE.",
        )
        result = reconcile_detected_procedures(
            declared=("cpre",),
            strong=("cpre",),
            any_evidence=("eda", "cpre"),
            occurrences=occurrences,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == (ProcedureType.CPRE,)
        assert result.precedence_applied is True
        assert result.selected_specialized_type == ProcedureType.CPRE
        assert result.suppressed_conventional_types == (ProcedureType.EDA,)

    def test_unique_cpre_suppresses_all_conventional_types(self) -> None:
        """R1: a CPRE única suprime EDA e Colonoscopia detectadas."""
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA. Solicito colonoscopia. Solicito CPRE para via biliar.",
        )
        result = reconcile_detected_procedures(
            declared=("cpre",),
            strong=("cpre",),
            any_evidence=("eda", "colonoscopy", "cpre"),
            occurrences=occurrences,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == (ProcedureType.CPRE,)
        assert result.suppressed_conventional_types == (ProcedureType.EDA, ProcedureType.COLONOSCOPY)

    def test_both_specialized_still_require_nir_review(self) -> None:
        """R2: CPRE + Ecoendoscopia atuais não são escolhidas arbitrariamente."""
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito CPRE. Solicito ecoendoscopia.",
        )
        result = reconcile_detected_procedures(
            declared=("cpre",),
            strong=("echoendoscopy", "cpre"),
            any_evidence=("echoendoscopy", "cpre"),
            occurrences=occurrences,
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert result.precedence_applied is False
        assert result.suppressed_conventional_types == ()

    def test_no_auto_upgrade_for_cpre(self) -> None:
        """Declarado EDA + detectado CPRE nunca faz upgrade automático (D2/D3)."""
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA com CPRE.",
        )
        result = reconcile_detected_procedures(
            declared=("eda",),
            strong=("eda", "cpre"),
            any_evidence=("eda", "cpre"),
            occurrences=occurrences,
        )
        assert result.action == "nir_review"
        assert result.upgraded is False


# ── R3: matriz de modalidade × sítio aceita para CPRE ───────────────────────


class TestCpreAcceptedImagingMatrix:
    @pytest.mark.parametrize(
        ("modality", "site", "context"),
        [
            ("ultrasound", "abdomen", "Conclusao: ultrassom de abdome demonstrou esteatose hepatica"),
            ("ultrasound", "upper_abdomen", "Conclusao: ultrassonografia de abdome superior evidenciou calculo"),
            ("ultrasound", "hepatobiliary", "Conclusao: ultrassom de vias biliares identificou dilatacao"),
            ("ct", "abdomen", "Conclusao: tomografia computadorizada de abdome demonstrou espessamento"),
            ("ct", "upper_abdomen", "Achados: TC de abdome superior revelou lesao"),
            ("mri", "abdomen", "Conclusao: ressonancia magnetica de abdome demonstrou cisto simples"),
            ("mri", "upper_abdomen", "Conclusao: ressonancia magnetica de abdome superior evidenciou lesao"),
            ("mrcp", "hepatobiliary", "Conclusao: colangiorressonancia demonstrou dilatacao de vias biliares"),
        ],
    )
    def test_modality_site_pair_is_verified(self, modality: str, site: str, context: str) -> None:
        report = f"Paciente estavel.\n{context}."
        result = _verify(context=context, report=report, modality=modality, site=site)
        assert len(result.outcomes) == 1
        assert result.outcomes[0].verified is True
        assert result.outcomes[0].modality == modality
        assert result.outcomes[0].anatomical_site == site

    def test_old_imaging_date_is_preserved_and_does_not_expire(self) -> None:
        report = "Conclusao: ultrassom de abdome demonstrou esteatose hepatica."
        context = "Conclusao: ultrassom de abdome demonstrou esteatose hepatica"
        result = _verify(
            context=context,
            report=report,
            modality="ultrasound",
            site="abdomen",
            exam_datetime_iso="2014-05-06",
        )
        assert result.outcomes[0].verified is True
        assert result.outcomes[0].exam_datetime_iso == "2014-05-06"

        policy = evaluate_procedure_policy(
            structured_data=_cpre_structured_data(),
            procedure_type="cpre",
            verified_imaging=result.outcomes,
        )
        assert policy["decision"] == "accept"


# ── R3: negativos obrigatórios ──────────────────────────────────────────────


class TestCpreRejectedImagingEvidence:
    @pytest.mark.parametrize(
        ("context", "modality", "site", "report", "expected_reason"),
        [
            (
                "Solicito TC de abdome",
                "ct",
                "abdomen",
                "Solicito TC de abdome.",
                "imaging_no_result_predicate",
            ),
            (
                "Solicito laudo de TC de abdome",
                "ct",
                "abdomen",
                "Solicito laudo de TC de abdome.",
                "imaging_no_result_predicate",
            ),
            (
                "Laudo: TC de abdome agendado para proxima semana",
                "ct",
                "abdomen",
                "Laudo: TC de abdome agendado para proxima semana.",
                "imaging_intent_marker",
            ),
            (
                "TC de abdome",
                "ct",
                "abdomen",
                "Historico de TC de abdome em 2019.",
                "imaging_no_result_predicate",
            ),
            (
                "Conclusao: TC de abdome demonstrou cisto",
                "ct",
                "abdomen",
                "Conclusao: TC de abdome demonstrou cisto.\nConclusao: TC de abdome demonstrou cisto.",
                "imaging_ambiguous_context",
            ),
            (
                "Conclusao: ultrassom e tomografia de abdome demonstrou alteracao",
                "ultrasound",
                "abdomen",
                "Conclusao: ultrassom e tomografia de abdome demonstrou alteracao.",
                "imaging_ambiguous_context",
            ),
            (
                "Conclusao: TC de abdome e ressonancia de abdome demonstraram cistos",
                "ct",
                "abdomen",
                "Conclusao: TC de abdome e ressonancia de abdome demonstraram cistos.",
                "imaging_ambiguous_context",
            ),
            (
                "Conclusao: ultrassom de abdome demonstrou esteatose",
                "ct",
                "abdomen",
                "Conclusao: ultrassom de abdome demonstrou esteatose.",
                "imaging_modality_mismatch",
            ),
            (
                "Conclusao: TC de torax demonstrou derrame pleural",
                "ct",
                "abdomen",
                "Conclusao: TC de torax demonstrou derrame pleural.",
                "imaging_site_mismatch",
            ),
            (
                "Conclusao: ultrassom de abdome demonstrou esteatose hepatica",
                "ultrasound",
                "abdomen",
                "Solicito CPRE para avaliacao de via biliar.",
                "imaging_context_not_anchored",
            ),
        ],
    )
    def test_rejected_evidence_never_verifies(
        self,
        context: str,
        modality: str,
        site: str,
        report: str,
        expected_reason: str,
    ) -> None:
        result = _verify(context=context, report=report, modality=modality, site=site)
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == expected_reason

    def test_invented_finding_excerpt_is_rejected(self) -> None:
        report = "Conclusao: ultrassom de abdome demonstrou esteatose hepatica."
        result = _verify(
            context="Conclusao: ultrassom de abdome demonstrou esteatose hepatica",
            report=report,
            modality="ultrasound",
            site="abdomen",
            finding_excerpt="nodulo pulmonar",
        )
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_finding_excerpt_not_anchored"


# ── R3/R4: policy CPRE consome somente evidência aprovada e agrega falhas ────


class TestCpreImagingPolicy:
    def _policy(self, *, report: str, dataset: list[dict[str, Any]]):
        verified = verify_abdominal_imaging_evidence(entries=dataset, main_report_text=report)
        return evaluate_procedure_policy(
            structured_data=_cpre_structured_data(),
            procedure_type="cpre",
            verified_imaging=verified.outcomes,
        )

    def test_ultrasound_hepatobiliary_satisfies_cpre(self) -> None:
        context = "Conclusao: ultrassom de vias biliares identificou dilatacao"
        policy = self._policy(
            report=f"{context}.",
            dataset=[_imaging(context=context, modality="ultrasound", site="hepatobiliary")],
        )
        assert policy["decision"] == "accept"
        assert policy["failed_requirements"] == []

    def test_mrcp_hepatobiliary_satisfies_cpre(self) -> None:
        context = "Conclusao: colangiorressonancia demonstrou dilatacao de vias biliares"
        policy = self._policy(
            report=f"{context}.",
            dataset=[_imaging(context=context, modality="mrcp", site="hepatobiliary")],
        )
        assert policy["decision"] == "accept"

    def test_missing_imaging_is_denied(self) -> None:
        policy = self._policy(report="Solicito CPRE.", dataset=[])
        assert policy["decision"] == "deny"
        assert policy["reason_code"] == "abdominal_imaging_modality_absent"
        assert "abdominal_imaging_modality_absent" in _decision_codes(policy)

    def test_site_outside_accepted_set_is_denied(self) -> None:
        """CT de vias biliares qualifica a evidência (hepatobiliar), mas não é par aceito de CPRE."""
        context = "Conclusao: TC de vias biliares demonstrou dilatacao"
        policy = self._policy(
            report=f"{context}.",
            dataset=[_imaging(context=context, modality="ct", site="hepatobiliary")],
        )
        assert policy["decision"] == "deny"
        assert "abdominal_imaging_site_not_accepted" in _decision_codes(policy)

    def test_request_only_imaging_is_denied(self) -> None:
        context = "Solicito TC de abdome"
        policy = self._policy(
            report=f"{context}.",
            dataset=[_imaging(context=context, modality="ct", site="abdomen")],
        )
        assert policy["decision"] == "deny"
        assert "abdominal_imaging_finding_absent" in _decision_codes(policy)

    def test_tracked_exams_only_does_not_satisfy_hard_rule(self) -> None:
        structured = _cpre_structured_data()
        preop = structured["preop_screening"]
        assert isinstance(preop, dict)
        preop["tracked_exams"] = [{"exam": "USG de abdome", "conclusion": "esteatose"}]
        verified = verify_abdominal_imaging_evidence(entries=[], main_report_text="Solicito CPRE.")
        policy = evaluate_procedure_policy(
            structured_data=structured,
            procedure_type="cpre",
            verified_imaging=verified.outcomes,
        )
        assert policy["decision"] == "deny"
        assert "abdominal_imaging_modality_absent" in _decision_codes(policy)

    def test_multiple_failures_are_aggregated_in_stable_order(self) -> None:
        structured = _cpre_structured_data()
        preop = structured["preop_screening"]
        assert isinstance(preop, dict)
        rulebook = preop["rulebook_signals"]
        assert isinstance(rulebook, dict)
        minimum = rulebook["minimum_exam_evidence"]
        assert isinstance(minimum, dict)
        minimum["hb_numeric_present"] = "no"

        verified = verify_abdominal_imaging_evidence(entries=[], main_report_text="Solicito CPRE.")
        policy = evaluate_procedure_policy(
            structured_data=structured,
            procedure_type="cpre",
            verified_imaging=verified.outcomes,
        )
        assert policy["decision"] == "deny"
        failed = policy["failed_requirements"]
        assert isinstance(failed, list)
        categories = [str(requirement["category"]) for requirement in failed]
        assert categories.count("minimum") >= 1
        assert "imaging" in categories
        assert categories.index("minimum") < categories.index("imaging")


# ── R3/R4/R5: ponta a ponta até WAIT_DOCTOR ─────────────────────────────────


class TestCpreEndToEnd:
    def test_declared_and_detected_cpre_reaches_wait_doctor(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-cpre")
        report = (
            "Solicito CPRE para avaliacao de via biliar.\nConclusao: ultrassom de vias biliares identificou dilatacao"
        )
        case = _make_case(user, procedure_types=(ProcedureType.CPRE,), extracted_text=report)
        client = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_cpre_procedure()],
                    imaging=[
                        _imaging(
                            context="Conclusao: ultrassom de vias biliares identificou dilatacao",
                            modality="ultrasound",
                            site="hepatobiliary",
                        )
                    ],
                ),
                _llm2_json(str(case.case_id), procedure_type="cpre"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        structured = reloaded.structured_data
        assert isinstance(structured, dict)
        assert structured["schema_version"] == "4.0"
        recommendations = _recommendations(reloaded)
        assert [item["procedure_type"] for item in recommendations] == ["cpre"]
        preop = recommendations[0]["preop_decision"]
        assert isinstance(preop, dict)
        assert preop["decision"] == "accept"
        assert recommendations[0]["suggestion"] == "accept"

    def test_linked_eda_com_cpre_proceeds_as_cpre_singleton(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-cpre-linked")
        report = (
            "Solicito EDA com CPRE para avaliacao de via biliar.\n"
            "Conclusao: ultrassom de vias biliares identificou dilatacao"
        )
        case = _make_case(user, procedure_types=(ProcedureType.CPRE,), extracted_text=report)
        client = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_cpre_procedure()],
                    imaging=[
                        _imaging(
                            context="Conclusao: ultrassom de vias biliares identificou dilatacao",
                            modality="ultrasound",
                            site="hepatobiliary",
                        )
                    ],
                ),
                _llm2_json(str(case.case_id), procedure_type="cpre"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        recommendations = _recommendations(reloaded)
        assert [item["procedure_type"] for item in recommendations] == ["cpre"]

    def test_request_only_imaging_forces_deny_suggestion(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-cpre-request-only")
        report = "Solicito CPRE.\nSolicito TC de abdome."
        case = _make_case(user, procedure_types=(ProcedureType.CPRE,), extracted_text=report)
        client = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_cpre_procedure()],
                    imaging=[_imaging(context="Solicito TC de abdome", modality="ct", site="abdomen")],
                ),
                _llm2_json(str(case.case_id), procedure_type="cpre", suggestion="accept"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        recommendations = _recommendations(reloaded)
        decision = recommendations[0]["preop_decision"]
        assert isinstance(decision, dict)
        assert decision["decision"] == "deny"
        assert recommendations[0]["suggestion"] == "deny"

    def test_cpre_declared_without_textual_evidence_returns_to_nir(self, django_user_model) -> None:
        """Detecção textual é a autoridade: sem CPRE no relatório, volta ao NIR."""
        user = django_user_model.objects.create_user(username="nir-cpre-mismatch")
        report = "Solicito EDA para investigacao de dispepsia."
        case = _make_case(user, procedure_types=(ProcedureType.CPRE,), extracted_text=report)
        client = RecordingLlmClient(responses=[_llm1_json(procedures=[_eda_procedure()])])
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert reloaded.status != CaseStatus.WAIT_DOCTOR
        events = list(CaseEvent.objects.filter(case=reloaded).values_list("event_type", flat=True))
        assert "EDA_SCOPE_GATED_MANUAL_REVIEW" in events
        assert len(client.calls) == 1

    def test_combined_declared_with_cpre_detected_returns_to_nir(self, django_user_model) -> None:
        """Matriz bloqueia combinado declarado cujo único detectado é CPRE (R5)."""
        user = django_user_model.objects.create_user(username="nir-cpre-combined")
        report = "Solicito CPRE para avaliacao de via biliar."
        case = _make_case(
            user,
            procedure_types=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            extracted_text=report,
        )
        client = RecordingLlmClient(responses=[_llm1_json(procedures=[_cpre_procedure()])])
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert reloaded.status != CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 1

    def test_declared_eda_with_cpre_precedence_returns_to_nir_as_mismatch(self, django_user_model) -> None:
        """R4: a precedência não reescreve a declaração do NIR (mismatch real).

        Declarado EDA + solicitações independentes (``Solicito EDA. Solicito
        CPRE.``): a precedência reduz o conjunto bruto a ``{cpre}``, mas isso
        diverge da declaração — o caso retorna à revisão NIR como mismatch.
        """
        user = django_user_model.objects.create_user(username="nir-eda-cpre-independent")
        report = "Solicito EDA. Solicito CPRE para avaliacao de via biliar."
        case = _make_case(user, procedure_types=(ProcedureType.EDA,), extracted_text=report)
        client = RecordingLlmClient(responses=[_llm1_json(procedures=[_eda_procedure(), _cpre_procedure()])])
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert len(client.calls) == 1  # LLM2 nunca é chamado no gate de revisão
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        events = list(CaseEvent.objects.filter(case=reloaded).values_list("event_type", flat=True))
        assert "EDA_SCOPE_GATED_MANUAL_REVIEW" in events
        assert "SCOPE_GATE_BYPASS" in events
        assert "PIPELINE_FAILED" not in events

        suggested = reloaded.suggested_action
        assert isinstance(suggested, dict)
        assert suggested["reason_code"] == "exam_type_mismatch"
        assert suggested["detected_procedures"] == [ProcedureType.CPRE]
        assert suggested["procedure_precedence"] == {
            "rule": "specialized_over_conventional",
            "selected": ProcedureType.CPRE,
            "suppressed": [ProcedureType.EDA],
        }

        # Declaração intacta; a projeção de detecção contém somente a CPRE.
        assert set(
            CaseProcedure.objects.filter(case=reloaded, declared_by_nir=True).values_list("procedure_type", flat=True)
        ) == {ProcedureType.EDA}
        assert set(
            CaseProcedure.objects.filter(case=reloaded, detection_status=DetectionStatus.DETECTED).values_list(
                "procedure_type", flat=True
            )
        ) == {ProcedureType.CPRE}


# ── Slice 001: precedência do especializado até a avaliação médica ────────


# Cenário equivalente ao incidente: cabeçalho administrativo de EDA, EDA já
# realizada no histórico e solicitação atual de CPRE em outro trecho.
_INCIDENT_REPORT = "Motivo da Solicitacao: EDA.\nEDA realizada em 2019.\nSolicito CPRE via regulacao."


def _run_cpre_precedence_case(user) -> tuple[Case, RecordingLlmClient]:
    """Roda o pipeline do cenário incidente com declaração de CPRE."""
    case = _make_case(user, procedure_types=(ProcedureType.CPRE,), extracted_text=_INCIDENT_REPORT)
    client = RecordingLlmClient(
        responses=[
            _llm1_json(procedures=[_eda_procedure(), _cpre_procedure()]),
            _llm2_json(str(case.case_id), procedure_type="cpre"),
        ]
    )
    run_pipeline(case.case_id, llm_client=client)
    return _reload(case), client


def _doctor_notices(case: Case) -> list[str]:
    """Notices do relatório médico real (mesmo caminho da tela do médico)."""
    from apps.doctor.reporting import prepare_doctor_case_report

    report = prepare_doctor_case_report(case).presenter.build_report()
    notices = report["notices"]
    assert isinstance(notices, list)
    return notices


class TestCprePrecedenceToDoctor:
    def test_cpre_precedence_reaches_doctor_with_audit_metadata(self, django_user_model) -> None:
        """R5: projeção só da CPRE, artefato original e auditoria enxuta."""
        user = django_user_model.objects.create_user(username="nir-precedence-cpre")
        reloaded, client = _run_cpre_precedence_case(user)

        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        assert set(
            CaseProcedure.objects.filter(case=reloaded, detection_status=DetectionStatus.DETECTED).values_list(
                "procedure_type", flat=True
            )
        ) == {ProcedureType.CPRE}
        assert set(
            CaseProcedure.objects.filter(case=reloaded, declared_by_nir=True).values_list("procedure_type", flat=True)
        ) == {ProcedureType.CPRE}

        # Artefato LLM1 original preservado com os dois itens extraídos.
        structured = reloaded.structured_data
        assert isinstance(structured, dict)
        assert {item["procedure_type"] for item in structured["requested_procedures"]} == {"eda", "cpre"}

        # LLM2 recebeu a lista fechada com a CPRE apenas.
        llm2_prompt = client.calls[1]["user_prompt"]
        assert '["cpre"]' in llm2_prompt
        assert '"procedure_type": "eda"' not in llm2_prompt

        # Auditoria enxuta (regra/selecionado/suprimidos), sem texto clínico.
        expected_metadata = {
            "rule": "specialized_over_conventional",
            "selected": ProcedureType.CPRE,
            "suppressed": [ProcedureType.EDA],
        }
        detection_event = CaseEvent.objects.get(case=reloaded, event_type="CASE_PROCEDURES_DETECTED")
        assert detection_event.payload["procedure_precedence"] == expected_metadata
        suggested = reloaded.suggested_action
        assert isinstance(suggested, dict)
        assert suggested["procedure_precedence"] == expected_metadata
        assert [item["procedure_type"] for item in _recommendations(reloaded)] == [ProcedureType.CPRE]

    def test_cpre_precedence_notice_uses_canonical_label(self, django_user_model) -> None:
        """R6: aviso médico informativo com label canônico de CPRE."""
        user = django_user_model.objects.create_user(username="nir-precedence-cpre-notice")
        reloaded, _ = _run_cpre_precedence_case(user)

        notices = _doctor_notices(reloaded)
        precedence_notices = [notice for notice in notices if "precedência" in notice]
        assert len(precedence_notices) == 1
        assert "CPRE" in precedence_notices[0]
        assert "EDA" in precedence_notices[0]
        # Informativo: a sugestão automática permanece disponível ao médico.
        assert _recommendations(reloaded)

    def test_structured_negated_cpre_does_not_authorize_suppression(self, django_user_model) -> None:
        """R3: item estruturado de CPRE sem ocorrência atual não suprime convencionais."""
        user = django_user_model.objects.create_user(username="nir-precedence-cpre-negated")
        report = "Sem indicacao de CPRE neste momento. Solicito EDA."
        case = _make_case(user, procedure_types=(ProcedureType.CPRE,), extracted_text=report)
        client = RecordingLlmClient(responses=[_llm1_json(procedures=[_eda_procedure(), _cpre_procedure()])])
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert len(client.calls) == 1
        events = list(CaseEvent.objects.filter(case=reloaded).values_list("event_type", flat=True))
        assert "EDA_SCOPE_GATED_MANUAL_REVIEW" in events
        assert "PIPELINE_FAILED" not in events

        suggested = reloaded.suggested_action
        assert isinstance(suggested, dict)
        assert suggested["reason_code"] == "unsupported_procedure_combination"
        assert set(suggested["detected_procedures"]) == {ProcedureType.EDA, ProcedureType.CPRE}
        assert "procedure_precedence" not in suggested
        detection_event = CaseEvent.objects.get(case=reloaded, event_type="CASE_PROCEDURES_DETECTED")
        assert "procedure_precedence" not in detection_event.payload


# ── R5: anexos nunca participam da automação (mesma fronteira do Slice 002) ──


class TestCpreAttachmentsOutsideAutomation:
    def _case_with_attachment(self, user, *, attachment_bytes: bytes) -> Case:
        from django.core.files.uploadedfile import SimpleUploadedFile

        case = _make_case(
            user,
            procedure_types=(ProcedureType.CPRE,),
            extracted_text="Solicito CPRE para avaliacao de via biliar.",
        )
        attachment = SimpleUploadedFile("anexo.pdf", attachment_bytes, content_type="application/pdf")
        CaseAttachment.objects.create(
            case=case,
            file=attachment,
            original_filename="anexo.pdf",
            stored_filename="anexo.pdf",
            content_type="application/pdf",
            size_bytes=len(attachment_bytes),
            sha256="0" * 64,
            uploaded_by=user,
        )
        return case

    def test_attachment_only_finding_does_not_satisfy_hard_rule(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-cpre-attach")
        secret = b"Conclusao: ultrassom de vias biliares identificou dilatacao."
        case = self._case_with_attachment(user, attachment_bytes=secret)
        client = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_cpre_procedure()],
                    imaging=[
                        _imaging(
                            context="Conclusao: ultrassom de vias biliares identificou dilatacao",
                            modality="ultrasound",
                            site="hepatobiliary",
                        )
                    ],
                ),
                _llm2_json(str(case.case_id), procedure_type="cpre"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        llm1_prompt = client.calls[0]["user_prompt"]
        assert "Solicito CPRE" in llm1_prompt
        assert "ultrassom de vias biliares identificou" not in llm1_prompt

        recommendations = _recommendations(_reload(case))
        decision = recommendations[0]["preop_decision"]
        assert isinstance(decision, dict)
        assert decision["decision"] == "deny"
        assert "abdominal_imaging_finding_absent" in _decision_codes(decision)
        assert recommendations[0]["suggestion"] == "deny"
