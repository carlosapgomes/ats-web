"""Slice 002 (R5) — verificador determinístico de imagem e policy especializada.

Cobre o contrato do design D6/D7/D8 para a hard rule de imagem abdominal:

- ``imaging_evidence.verify_abdominal_imaging_evidence`` ancora contexto/achado
  em ``Case.extracted_text`` (relatório principal), rederiva modalidade e
  anatomia do MESMO contexto e exige predicado positivo de resultado ou heading
  estrito de linha. Substantivos isolados (``laudo``/``resultado``/``achado``)
  nunca são marcadores positivos e qualquer intenção/agendamento na mesma
  oração domina.
- A policy recebe SOMENTE evidência aprovada pelo verificador e agrega a
  pendência de imagem em ``failed_requirements[]`` (categoria ``imaging``).
- Data antiga é preservada e não expira.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.pipeline.imaging_evidence import verify_abdominal_imaging_evidence
from apps.pipeline.policy.procedure_policy import evaluate_procedure_policy

pytestmark = pytest.mark.django_db


def _entry(
    *,
    modality: str = "ct",
    site: str = "abdomen",
    finding: str = "yes",
    context: str,
    finding_excerpt: str | None = None,
    exam_datetime_iso: str | None = None,
) -> dict[str, object]:
    return {
        "modality": modality,
        "anatomical_site": site,
        "report_finding_present": finding,
        "source_document": "main_report",
        "evidence_context_excerpt": context,
        "finding_excerpt": finding_excerpt if finding_excerpt is not None else context,
        "exam_datetime_iso": exam_datetime_iso,
    }


def _failed_codes(policy: dict[str, object]) -> list[str]:
    """Códigos das pendências agregadas (contrato aditivo ``failed_requirements``)."""
    return [str(requirement["code"]) for requirement in _failed_requirements(policy)]


def _failed_categories(policy: dict[str, object]) -> set[str]:
    """Categorias das pendências agregadas (``minimum|threshold|conditional|imaging``)."""
    return {str(requirement["category"]) for requirement in _failed_requirements(policy)}


def _failed_requirements(policy: dict[str, object]) -> list[dict[str, Any]]:
    requirements = policy.get("failed_requirements")
    assert isinstance(requirements, list)
    return requirements


def _verify(*, context: str, report: str, **overrides: Any) -> Any:
    return verify_abdominal_imaging_evidence(
        entries=[_entry(context=context, **overrides)],
        main_report_text=report,
    )


# ── R5: ancoragem e rederivação ─────────────────────────────────────────────


class TestVerifiedResultAnchoring:
    def test_heading_line_with_real_context_qualifies(self) -> None:
        report = "Paciente estavel.\nConclusao: TC de abdome sem alteracoes significativas."
        result = _verify(
            context="Conclusao: TC de abdome sem alteracoes significativas",
            report=report,
        )
        assert len(result.outcomes) == 1
        assert result.outcomes[0].verified is True
        assert result.outcomes[0].modality == "ct"
        assert result.outcomes[0].anatomical_site == "abdomen"

    def test_positive_result_predicate_qualifies(self) -> None:
        report = "Tomografia de abdome demonstrou leve espessamento parietal."
        result = _verify(
            context="Tomografia de abdome demonstrou leve espessamento parietal",
            report=report,
        )
        assert result.outcomes[0].verified is True

    def test_accents_and_case_are_normalized_for_anchoring(self) -> None:
        report = "CONCLUSÃO: Ressonância magnética de abdome superior evidenciou cisto simples."
        result = _verify(
            modality="mri",
            site="upper_abdomen",
            context="conclusao: ressonancia magnetica de abdome superior evidenciou cisto simples",
            report=report,
        )
        assert result.outcomes[0].verified is True

    def test_old_exam_date_is_preserved_and_does_not_expire(self) -> None:
        report = "Conclusao: TC de abdome demonstrou calculo renal."
        result = _verify(
            context="Conclusao: TC de abdome demonstrou calculo renal",
            report=report,
            exam_datetime_iso="2015-03-04",
        )
        assert result.outcomes[0].verified is True
        assert result.outcomes[0].exam_datetime_iso == "2015-03-04"


class TestRejectedImagingEvidence:
    def test_context_not_found_in_main_report_is_rejected(self) -> None:
        result = _verify(
            context="Conclusao: TC de abdome demonstrou nodulo hepatico",
            report="Solicito EDA.",
        )
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_context_not_anchored"

    @pytest.mark.parametrize(
        "context",
        [
            "Solicito TC de abdome",
            "Solicita tomografia de abdome",
            "Solicitamos TC de abdome",
        ],
    )
    def test_plain_request_is_rejected(self, context: str) -> None:
        result = _verify(context=context, report=f"{context}.")
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code in {
            "imaging_no_result_predicate",
            "imaging_intent_marker",
        }

    @pytest.mark.parametrize(
        "context",
        [
            "Solicito laudo de TC de abdome",
            "Solicitacao de laudo de TC de abdome",
        ],
    )
    def test_request_with_laudo_noun_is_rejected(self, context: str) -> None:
        result = _verify(context=context, report=f"{context}.")
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code in {
            "imaging_no_result_predicate",
            "imaging_intent_marker",
        }

    def test_scheduled_laudo_is_rejected_by_intent_marker(self) -> None:
        report = "Laudo: TC de abdome agendado para proxima semana."
        result = _verify(context="Laudo: TC de abdome agendado para proxima semana", report=report)
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_intent_marker"

    def test_mere_mention_without_result_form_is_rejected(self) -> None:
        report = "Historico de TC de abdome em 2019."
        result = _verify(context="TC de abdome", report=report)
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code in {
            "imaging_no_result_predicate",
            "imaging_context_not_anchored",
        }

    def test_modalidade_declarada_nao_corresponde_ao_contexto(self) -> None:
        report = "Conclusao: ultrassom de abdome demonstrou esteatose."
        result = _verify(
            modality="ct",
            context="Conclusao: ultrassom de abdome demonstrou esteatose",
            report=report,
        )
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_modality_mismatch"

    def test_anatomia_declarada_nao_corresponde_ao_contexto(self) -> None:
        report = "Conclusao: TC de torax demonstrou derrame pleural."
        result = _verify(site="abdomen", context="Conclusao: TC de torax demonstrou derrame pleural", report=report)
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_site_mismatch"

    def test_conflicting_modality_aliases_are_ambiguous(self) -> None:
        report = "Conclusao: ultrassom e tomografia de abdome demonstrou alteracao."
        result = _verify(context="Conclusao: ultrassom e tomografia de abdome demonstrou alteracao", report=report)
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_ambiguous_context"

    def test_duplicated_context_is_ambiguous(self) -> None:
        context = "Conclusao: TC de abdome demonstrou cisto"
        report = f"{context}.\n{context}."
        result = _verify(context=context, report=report)
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_ambiguous_context"

    def test_broad_context_with_two_images_is_ambiguous(self) -> None:
        report = "Conclusao: TC de abdome e ressonancia de abdome demonstraram cistos."
        result = _verify(context="Conclusao: TC de abdome e ressonancia de abdome demonstraram cistos", report=report)
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_ambiguous_context"

    def test_finding_excerpt_not_inside_context_is_rejected(self) -> None:
        report = "Conclusao: TC de abdome demonstrou cisto simples."
        result = verify_abdominal_imaging_evidence(
            entries=[
                _entry(
                    context="Conclusao: TC de abdome demonstrou cisto simples",
                    finding_excerpt="nódulo pulmonar",
                )
            ],
            main_report_text=report,
        )
        assert result.outcomes[0].verified is False
        assert result.outcomes[0].reason_code == "imaging_finding_excerpt_not_anchored"


# ── R5: policy consome somente evidência aprovada ───────────────────────────


def _echoendoscopy_structured_data() -> dict[str, object]:
    """Projeção 1.1 mínima com exames mínimos completos (sem pendências comuns)."""
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


class TestSpecializedImagingPolicy:
    def test_verified_ct_abdomen_has_no_imaging_failure(self) -> None:
        report = "Conclusao: TC de abdome demonstrou cisto simples."
        verified = verify_abdominal_imaging_evidence(
            entries=[_entry(context="Conclusao: TC de abdome demonstrou cisto simples")],
            main_report_text=report,
        )
        policy = evaluate_procedure_policy(
            structured_data=_echoendoscopy_structured_data(),
            procedure_type="echoendoscopy",
            verified_imaging=verified.outcomes,
        )
        assert policy["decision"] == "accept"
        assert policy["failed_requirements"] == []

    def test_ultrasound_only_does_not_satisfy_echoendoscopy(self) -> None:
        report = "Conclusao: ultrassom de abdome demonstrou esteatose."
        verified = verify_abdominal_imaging_evidence(
            entries=[_entry(modality="ultrasound", context="Conclusao: ultrassom de abdome demonstrou esteatose")],
            main_report_text=report,
        )
        policy = evaluate_procedure_policy(
            structured_data=_echoendoscopy_structured_data(),
            procedure_type="echoendoscopy",
            verified_imaging=verified.outcomes,
        )
        assert policy["decision"] == "deny"
        codes = _failed_codes(policy)
        assert "abdominal_imaging_modality_absent" in codes
        assert policy["reason_code"] == "abdominal_imaging_modality_absent"
        categories = _failed_categories(policy)
        assert "imaging" in categories

    def test_site_outside_accepted_set_is_denied(self) -> None:
        report = "Conclusao: TC de vias biliares demonstrou dilatacao."
        verified = verify_abdominal_imaging_evidence(
            entries=[
                _entry(
                    modality="ct",
                    site="hepatobiliary",
                    context="Conclusao: TC de vias biliares demonstrou dilatacao",
                )
            ],
            main_report_text=report,
        )
        assert verified.outcomes[0].verified is True
        policy = evaluate_procedure_policy(
            structured_data=_echoendoscopy_structured_data(),
            procedure_type="echoendoscopy",
            verified_imaging=verified.outcomes,
        )
        assert policy["decision"] == "deny"
        codes = _failed_codes(policy)
        assert "abdominal_imaging_site_not_accepted" in codes

    def test_request_only_requested_imaging_forces_suggestion_deny(self) -> None:
        """Excerpt real de solicitação não vira achado: sugestão deny agregada."""
        report = "Solicito TC de abdome."
        verified = verify_abdominal_imaging_evidence(
            entries=[_entry(context="Solicito TC de abdome")],
            main_report_text=report,
        )
        policy = evaluate_procedure_policy(
            structured_data=_echoendoscopy_structured_data(),
            procedure_type="echoendoscopy",
            verified_imaging=verified.outcomes,
        )
        assert policy["decision"] == "deny"
        codes = _failed_codes(policy)
        assert "abdominal_imaging_finding_absent" in codes

    def test_missing_imaging_evidence_is_denied(self) -> None:
        policy = evaluate_procedure_policy(
            structured_data=_echoendoscopy_structured_data(),
            procedure_type="echoendoscopy",
            verified_imaging=(),
        )
        assert policy["decision"] == "deny"
        codes = _failed_codes(policy)
        assert "abdominal_imaging_modality_absent" in codes

    def test_tracked_exams_only_does_not_satisfy_hard_rule(self) -> None:
        """``tracked_exams`` textual nunca é promovido a evidência (D6)."""
        structured = _echoendoscopy_structured_data()
        preop = structured["preop_screening"]
        assert isinstance(preop, dict)
        preop["tracked_exams"] = [{"exam": "TC de abdome", "conclusion": "cisto simples"}]

        verified = verify_abdominal_imaging_evidence(entries=[], main_report_text="Solicito ecoendoscopia.")
        policy = evaluate_procedure_policy(
            structured_data=structured,
            procedure_type="echoendoscopy",
            verified_imaging=verified.outcomes,
        )
        assert policy["decision"] == "deny"
        codes = _failed_codes(policy)
        assert "abdominal_imaging_modality_absent" in codes

    def test_eda_profile_keeps_no_imaging_requirement(self) -> None:
        """R5: EDA/Colonoscopia permanecem exatamente como no Slice 001."""
        policy = evaluate_procedure_policy(
            structured_data=_echoendoscopy_structured_data(),
            procedure_type="eda",
            verified_imaging=(),
        )
        assert policy["decision"] == "accept"
        assert policy["failed_requirements"] == []
