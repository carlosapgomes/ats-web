"""Slice 002 (R2–R4, R6, R7) — Ecoendoscopia do NIR à avaliação médica.

Cobre:

- R2: o detector textual produz ocorrências qualificadas por tipo com
  qualificação (current_request|historical|negated|mention), trecho/evidence id
  e vínculo ``com/e EDA`` no mesmo contexto.
- R3: ``EDA com/e ecoendoscopia`` (expressão vinculada) colapsa para
  ``{echoendoscopy}``; duas solicitações independentes não são colapsadas só
  pelo conjunto.
- R4: declaração = detecção segue ao médico; mismatch volta ao NIR sem
  auto-upgrade especializado.
- R6: o caso chega a ``WAIT_DOCTOR`` como singleton e o sinal legado
  ``echoendoscopy`` não é duplicado em artefatos 3.0 (D14).
- R7: payload legado 1.1/2.0 continua legível, sem nova row/backfill.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.cases.models import Case, CaseAttachment, CaseEvent, CaseProcedure, CaseStatus, DetectionStatus, ProcedureType
from apps.cases.procedures import set_declared_procedures
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.procedure_reconciliation import reconcile_detected_procedures
from apps.pipeline.scope_detection import (
    detect_procedure_occurrences,
    detect_requested_procedures_v3,
)

pytestmark = pytest.mark.django_db


# ── Helpers ─────────────────────────────────────────────────────────────────


def _span(excerpt: str) -> dict[str, str]:
    return {"field_path": "p.0", "excerpt": excerpt}


def _echo_procedure(name: str = "Ecoendoscopia") -> dict[str, Any]:
    return {
        "procedure_type": "echoendoscopy",
        "name": name,
        "urgency": "eletivo",
        "evidence_spans": [_span("Solicito ecoendoscopia")],
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
    modality: str = "ct",
    site: str = "abdomen",
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
    one_liner: str = "Ecoendoscopia indicada.",
) -> str:
    return json.dumps(
        {
            "schema_version": "3.0",
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
            "schema_version": "3.0",
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
    """Recomendações por componente do ``suggested_action`` com tipo explícito."""
    suggested = case.suggested_action
    assert isinstance(suggested, dict)
    recommendations = suggested.get("procedure_recommendations")
    assert isinstance(recommendations, list)
    return recommendations


def _decision_codes(decision: dict[str, Any]) -> list[str]:
    requirements = decision.get("failed_requirements")
    assert isinstance(requirements, list)
    return [str(requirement["code"]) for requirement in requirements]


# ── R2: ocorrências qualificadas com proveniência ───────────────────────────


class TestProcedureOccurrences:
    def test_linked_expression_marks_both_occurrences_current_and_linked(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA com ecoendoscopia para avaliacao de lesao.",
        )
        by_type = {(o.procedure_type, o.qualification) for o in occurrences}
        assert ("eda", "current_request") in by_type
        assert ("echoendoscopy", "current_request") in by_type
        echo = next(o for o in occurrences if o.procedure_type == "echoendoscopy")
        eda = next(o for o in occurrences if o.procedure_type == "eda")
        assert echo.linked_eda is True
        assert eda.linked_eda is True
        assert echo.excerpt.strip() != ""
        assert echo.evidence_id != eda.evidence_id

    def test_independent_requests_are_not_linked(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA. Solicito ecoendoscopia.",
        )
        echo = next(o for o in occurrences if o.procedure_type == "echoendoscopy")
        assert echo.qualification == "current_request"
        assert echo.linked_eda is False

    def test_historical_occurrence_is_qualified_as_historical(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Historico de ecoendoscopia realizada em 2019.",
        )
        echo = next(o for o in occurrences if o.procedure_type == "echoendoscopy")
        assert echo.qualification == "historical"

    def test_negated_occurrence_is_qualified_as_negated(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Sem indicacao de ecoendoscopia neste momento.",
        )
        echo = next(o for o in occurrences if o.procedure_type == "echoendoscopy")
        assert echo.qualification == "negated"

    def test_textual_echoendoscopy_is_detected_as_current_request(self) -> None:
        detection = detect_requested_procedures_v3(
            llm1_structured_data={},
            cleaned_text="Solicito ecoendoscopia para avaliacao.",
        )
        assert detection["echoendoscopy"] == {"strong": True, "any": True}

    def test_historical_echoendoscopy_does_not_create_detection(self) -> None:
        detection = detect_requested_procedures_v3(
            llm1_structured_data={},
            cleaned_text="Historico de ecoendoscopia realizada em 2019. Solicito EDA.",
        )
        assert detection["echoendoscopy"] == {"strong": False, "any": False}
        assert detection["eda"]["any"] is True


# ── R3: precedência por vínculo, não por conjunto ───────────────────────────


class TestSpecializedPrecedence:
    def test_linked_expression_collapses_to_echoendoscopy(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA com ecoendoscopia.",
        )
        result = reconcile_detected_procedures(
            declared=("echoendoscopy",),
            strong=("eda", "echoendoscopy"),
            any_evidence=("eda", "echoendoscopy"),
            occurrences=occurrences,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == (ProcedureType.ECHOENDOSCOPY,)

    def test_independent_requests_do_not_collapse(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA. Solicito ecoendoscopia.",
        )
        result = reconcile_detected_procedures(
            declared=("echoendoscopy",),
            strong=("eda", "echoendoscopy"),
            any_evidence=("eda", "echoendoscopy"),
            occurrences=occurrences,
        )
        assert result.action == "nir_review"
        assert result.reason_code in {"unsupported_procedure_combination", "mixed_exam_request"}

    def test_no_auto_upgrade_for_specialized(self) -> None:
        """Declarado EDA + detectado Eco nunca faz upgrade automático (D2/D3)."""
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA com ecoendoscopia.",
        )
        result = reconcile_detected_procedures(
            declared=("eda",),
            strong=("eda", "echoendoscopy"),
            any_evidence=("eda", "echoendoscopy"),
            occurrences=occurrences,
        )
        assert result.action == "nir_review"
        assert result.upgraded is False

    def test_linked_expression_without_declared_specialized_is_mismatch(self) -> None:
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA com ecoendoscopia.",
        )
        result = reconcile_detected_procedures(
            declared=("eda",),
            strong=("echoendoscopy",),
            any_evidence=("echoendoscopy",),
            occurrences=occurrences,
        )
        assert result.action == "nir_review"
        assert result.reason_code in {"exam_type_mismatch", "unsupported_procedure_combination"}


# ── R4/R6: ponta a ponta até WAIT_DOCTOR ────────────────────────────────────


class TestEchoendoscopyEndToEnd:
    def test_declared_and_detected_echoendoscopy_reaches_wait_doctor(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-echo")
        report = (
            "Solicito ecoendoscopia para avaliacao de lesao pancreatica.\n"
            "Conclusao: TC de abdome demonstrou lesao hipodensa em pancreas."
        )
        case = _make_case(user, procedure_types=(ProcedureType.ECHOENDOSCOPY,), extracted_text=report)
        client = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_echo_procedure()],
                    imaging=[_imaging(context="Conclusao: TC de abdome demonstrou lesao hipodensa em pancreas")],
                ),
                _llm2_json(str(case.case_id), procedure_type="echoendoscopy"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        assert reloaded.structured_data is not None
        assert reloaded.structured_data["schema_version"] == "3.0"
        recommendations = _recommendations(reloaded)
        assert [item["procedure_type"] for item in recommendations] == ["echoendoscopy"]
        preop = recommendations[0]["preop_decision"]
        assert isinstance(preop, dict)
        assert preop["decision"] == "accept"
        assert recommendations[0]["suggestion"] == "accept"

    def test_request_only_imaging_forces_deny_suggestion(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-echo-2")
        report = "Solicito ecoendoscopia.\nSolicito TC de abdome."
        case = _make_case(user, procedure_types=(ProcedureType.ECHOENDOSCOPY,), extracted_text=report)
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_echo_procedure()], imaging=[_imaging(context="Solicito TC de abdome")]),
                _llm2_json(str(case.case_id), procedure_type="echoendoscopy", suggestion="accept"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        recommendations = _recommendations(reloaded)
        decision = recommendations[0]["preop_decision"]
        assert isinstance(decision, dict)
        assert decision["decision"] == "deny"
        assert "abdominal_imaging_finding_absent" in _decision_codes(decision)

        assert recommendations[0]["suggestion"] == "deny"

    def test_specialized_signal_is_not_duplicated_in_v3_artifacts(self, django_user_model) -> None:
        """D14/R6: 3.0 não persiste o sinal legado ``echoendoscopy``."""
        user = django_user_model.objects.create_user(username="nir-eda-signal")
        report = "Solicito EDA. Mencao a ecoendoscopia previa em 2018."
        case = _make_case(user, procedure_types=(ProcedureType.EDA,), extracted_text=report)
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_procedure()]),
                _llm2_json(str(case.case_id), procedure_type="eda"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        codes = {signal["code"] for signal in (reloaded.priority_signals or [])}
        assert "echoendoscopy" not in codes

    def test_declared_echo_without_textual_evidence_returns_to_nir(self, django_user_model) -> None:
        """Detecção textual é autoridade: sem eco no relatório, volta ao NIR."""
        user = django_user_model.objects.create_user(username="nir-echo-mismatch")
        report = "Solicito colonoscopia para rastreio."
        case = _make_case(user, procedure_types=(ProcedureType.ECHOENDOSCOPY,), extracted_text=report)
        client = RecordingLlmClient(responses=[_llm1_json(procedures=[_colon_procedure()])])
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert reloaded.status != CaseStatus.WAIT_DOCTOR
        events = list(CaseEvent.objects.filter(case=reloaded).values_list("event_type", flat=True))
        assert "EDA_SCOPE_GATED_MANUAL_REVIEW" in events

    def test_llm2_is_not_called_when_reconciliation_gates(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-echo-gate")
        report = "Solicito colonoscopia para rastreio."
        case = _make_case(user, procedure_types=(ProcedureType.ECHOENDOSCOPY,), extracted_text=report)
        client = RecordingLlmClient(responses=[_llm1_json(procedures=[_colon_procedure()])])
        run_pipeline(case.case_id, llm_client=client)
        assert len(client.calls) == 1

    def test_independent_eda_and_echo_requests_reach_nir_review_without_pipeline_failure(
        self, django_user_model
    ) -> None:
        """R3 (dívida herdada do Slice 004): conjunto detectado fora da matriz → NIR.

        Declarado EDA + duas solicitações independentes (``Solicito EDA.
        Solicito ecoendoscopia.``) formam ``{eda, echoendoscopy}``, que não
        pertence a ``ALLOWED_PROCEDURE_SETS``: o caso deve chegar à revisão
        manual (``EDA_SCOPE_GATED_MANUAL_REVIEW`` + ``scope_gate_bypass``) com
        motivo explícito, sem tentar projetar o conjunto e cair em
        ``PIPELINE_FAILED``.
        """
        user = django_user_model.objects.create_user(username="nir-eda-echo-independent")
        report = "Solicito EDA. Solicito ecoendoscopia para avaliacao de lesao pancreatica."
        case = _make_case(user, procedure_types=(ProcedureType.EDA,), extracted_text=report)
        client = RecordingLlmClient(responses=[_llm1_json(procedures=[_eda_procedure(), _echo_procedure()])])
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
        assert suggested["reason_code"] == "unsupported_procedure_combination"
        assert set(suggested["detected_procedures"]) == {ProcedureType.EDA, ProcedureType.ECHOENDOSCOPY}

        # Declaração intacta e nenhuma projeção de detecção inválida.
        assert set(
            CaseProcedure.objects.filter(case=reloaded, declared_by_nir=True).values_list("procedure_type", flat=True)
        ) == {ProcedureType.EDA}
        assert not CaseProcedure.objects.filter(case=reloaded, detection_status=DetectionStatus.DETECTED).exists()

    def test_mismatch_singleton_echoendoscopy_is_still_projected(self, django_user_model) -> None:
        """Regressão: singleton válido de mismatch continua projetado e revisado."""
        user = django_user_model.objects.create_user(username="nir-eda-echo-singleton")
        report = "Solicito ecoendoscopia para avaliacao de lesao pancreatica."
        case = _make_case(user, procedure_types=(ProcedureType.EDA,), extracted_text=report)
        client = RecordingLlmClient(responses=[_llm1_json(procedures=[_echo_procedure()])])
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert len(client.calls) == 1
        events = list(CaseEvent.objects.filter(case=reloaded).values_list("event_type", flat=True))
        assert "EDA_SCOPE_GATED_MANUAL_REVIEW" in events
        assert "PIPELINE_FAILED" not in events
        assert set(
            CaseProcedure.objects.filter(case=reloaded, detection_status=DetectionStatus.DETECTED).values_list(
                "procedure_type", flat=True
            )
        ) == {ProcedureType.ECHOENDOSCOPY}
        suggested = reloaded.suggested_action
        assert isinstance(suggested, dict)
        assert suggested["reason_code"] == "exam_type_mismatch"


# ── R7: legado permanece legível ────────────────────────────────────────────


class TestLegacyReadable:
    def test_legacy_v2_artifact_is_not_rewritten(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-legacy")
        legacy = {
            "schema_version": "2.0",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "requested_procedures": [
                {"procedure_type": "eda", "evidence_spans": [_span("Solicito EDA")]},
            ],
        }
        case = Case.objects.create(
            created_by=user,
            agency_record_number="12345",
            extracted_text="Solicito EDA.",
            structured_data=legacy,
        )
        set_declared_procedures(case=case, procedure_types=[ProcedureType.EDA], actor=user)
        case = _reload(case)
        assert case.structured_data == legacy
        assert case.procedures.count() == 1

    def test_occurrence_detection_never_touches_database_rows(self) -> None:
        """R2/R7: detector é puro — sem ORM, sem I/O, sem row nova."""
        before = Case.objects.count()
        detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text="Solicito EDA com ecoendoscopia.",
        )
        assert Case.objects.count() == before


# ── R5: anexos nunca participam da automação ────────────────────────────────


class TestAttachmentsOutsideAutomation:
    """Prova que o texto de ``CaseAttachment`` não é consultado nem enviado.

    ``CaseAttachment`` guarda apenas arquivo (sem campo de texto extraído) e o
    pipeline alimenta LLM1/verificador exclusivamente com
    ``Case.extracted_text`` do relatório principal (D6/D9).
    """

    def _case_with_attachment(self, user, *, attachment_bytes: bytes) -> Case:
        from django.core.files.uploadedfile import SimpleUploadedFile

        case = _make_case(
            user,
            procedure_types=(ProcedureType.ECHOENDOSCOPY,),
            extracted_text="Solicito ecoendoscopia para avaliacao.",
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

    def test_attachment_bytes_are_not_sent_to_llm1(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-attach")
        secret = b"Conclusao: TC de abdome demonstrou lesao pancreatica."
        case = self._case_with_attachment(user, attachment_bytes=secret)
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_echo_procedure()]),
                _llm2_json(str(case.case_id), procedure_type="echoendoscopy"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        llm1_prompt = client.calls[0]["user_prompt"]
        assert "Solicito ecoendoscopia" in llm1_prompt
        assert "TC de abdome demonstrou" not in llm1_prompt

    def test_finding_only_in_attachment_does_not_satisfy_hard_rule(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-attach-2")
        secret = b"Conclusao: TC de abdome demonstrou lesao pancreatica."
        case = self._case_with_attachment(user, attachment_bytes=secret)
        # LLM declarou a imagem "vista no anexo": o verificador só enxerga o
        # relatório principal e rebaixa a evidência a insuficiente.
        client = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_echo_procedure()],
                    imaging=[_imaging(context="Conclusao: TC de abdome demonstrou lesao pancreatica")],
                ),
                _llm2_json(str(case.case_id), procedure_type="echoendoscopy"),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        recommendations = _recommendations(reloaded)
        decision = recommendations[0]["preop_decision"]
        assert isinstance(decision, dict)
        assert decision["decision"] == "deny"
        assert "abdominal_imaging_finding_absent" in _decision_codes(decision)
        assert recommendations[0]["suggestion"] == "deny"
