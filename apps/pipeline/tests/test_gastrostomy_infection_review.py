"""Slice 004 — revisão infecciosa consultiva de EDA + GTT (R1–R7).

Cobre:

- R1: EDA + GTT é detectada/reconciliada como pacote único e o painel existe
  SOMENTE para a identidade exata (GTT histórica/negada não cria pacote nem
  painel);
- R2/R3: verificador determinístico — âncora única, categoria rederivada,
  marcador local explícito, histórico dominante, rebaixamento para
  ``unclassified``, dedup e ordem canônica; nada ancorado/inventado é
  apresentado como fato;
- R5: alerta só com preocupação atual explicitamente documentada;
- R6: policy, ``failed_requirements``, recomendação LLM2, suporte, campos/
  validação do formulário e FSM permanecem idênticos ao variar apenas a
  revisão infecciosa;
- R7: writes 4.0 não persistem o sinal legado ``gastrostomy`` quando a
  identidade atômica já é ``eda_gastrostomy``.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from apps.cases.models import Case, CaseProcedure, CaseStatus, DetectionStatus, ProcedureType
from apps.cases.priority_signals import build_priority_signal_badges, resolve_priority_signals
from apps.cases.procedures import set_declared_procedures
from apps.pipeline.infection_review import (
    CONCERNING_ASSESSMENTS,
    INFECTION_CATEGORY_ORDER,
    verify_infection_evidence,
)
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.procedure_reconciliation import reconcile_detected_procedures, serialize_procedure_precedence
from apps.pipeline.schemas.adapters import project_v4_to_llm1_shape
from apps.pipeline.scope_detection import detect_procedure_occurrences, detect_requested_procedures_v4
from apps.pipeline.tests.test_slice_002_pipeline import (
    _eda_procedure,
    _extract_llm1_json_from_prompt,
    _llm1_json,
    _llm2_json,
    _single_procedure_recommendation,
)

pytestmark = pytest.mark.django_db

SCHEMA_VERSION = "4.0"

GTT_TEXT = "Solicito EDA com GTT para confecção de gastrostomia."

# Relatório principal com resultados normais, negativos, sem interpretação e
# preocupantes ancorados (documentação clínica, nunca limiar).
NORMAL_REPORT = "Leucócitos 8.200/mm3 (normais). Hemoculturas negativas."
UNINTERPRETED_REPORT = "PCR 12 mg/L."
CONCERNING_REPORT = "Febre 38,5 C há dois dias. Hemocultura positiva para E. coli."
ANTIBIOTIC_REPORT = "Em uso de ceftriaxona (antibiótico) desde a admissão."
HISTORICAL_REPORT = "Uso prévio de antibiótico em 2023."


# ── Fixtures v4 ────────────────────────────────────────────────────────────


def _evidence(
    *,
    category: str,
    assessment: str,
    temporal_status: str = "current",
    value_text: str | None = None,
    excerpt: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "assessment": assessment,
        "temporal_status": temporal_status,
        "value_text": value_text,
        "evidence_excerpt": excerpt,
    }


def _gastrostomy_procedure(*, evidence: list[dict[str, Any]] | None = None, **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "eda_gastrostomy",
        "name": "EDA + Gastrostomia (GTT)",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "evidence_spans": [{"field_path": "requested_procedures.0", "excerpt": GTT_TEXT}],
        "infection_evidence": evidence or [],
    }
    item.update(overrides)
    return item


def _make_declared_case(user, *, procedure_types: tuple[str, ...], extracted_text: str) -> Case:
    case = Case.objects.create(created_by=user, agency_record_number="12345", extracted_text=extracted_text)
    set_declared_procedures(case=case, procedure_types=list(procedure_types), actor=user)
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()
    return case


def _run(
    user,
    *,
    procedure_types: tuple[str, ...],
    extracted_text: str,
    llm1: str,
    recommendations: list[dict[str, Any]],
) -> tuple[Case, RecordingLlmClient]:
    case = _make_declared_case(user, procedure_types=procedure_types, extracted_text=extracted_text)
    client = RecordingLlmClient(
        responses=[llm1, _llm2_json(str(case.case_id), recommendations=recommendations)],
    )
    run_pipeline(case.case_id, llm_client=client)
    return Case.objects.get(case_id=case.case_id), client


def _suggested_action(case: Case) -> dict[str, Any]:
    return cast("dict[str, Any]", case.suggested_action or {})


def _infection_review(case: Case) -> dict[str, Any]:
    review = _suggested_action(case).get("infection_review")
    assert isinstance(review, dict), "revisão infecciosa ausente no artefato 4.0"
    return review


def _groups_by_category(review: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        str(group["category"]): cast("list[dict[str, Any]]", group["items"])
        for group in cast("list[dict[str, Any]]", review["groups"])
    }


# ── R1: detecção conservadora de EDA + GTT ────────────────────────────────


class TestGastrostomyDetectionV4:
    def _detect(self, cleaned_text: str, structured: dict[str, object] | None = None) -> dict[str, dict[str, bool]]:
        return detect_requested_procedures_v4(
            llm1_structured_data=structured or {},
            cleaned_text=cleaned_text,
        )

    def test_eda_with_gtt_is_a_current_package_request(self) -> None:
        detection = self._detect(GTT_TEXT)
        assert detection["eda_gastrostomy"] == {"strong": True, "any": True}
        assert detection["eda"]["any"] is True

    def test_isolated_gtt_request_detects_the_package_and_the_base(self) -> None:
        """GTT é marcador autoevidente da família EDA (legado preservado):

        a ocorrência atual isolada já detecta o pacote; o colapso para
        ``{eda_gastrostomy}`` é decisão da reconciliação (D3).
        """
        detection = self._detect("Solicito GTT para confecção de gastrostomia.")
        assert detection["eda_gastrostomy"]["any"] is True

    def test_historical_gtt_does_not_create_a_package(self) -> None:
        detection = self._detect("Gastrostomia realizada em 2023. Solicito EDA.")
        assert detection["eda_gastrostomy"]["any"] is False

    def test_prior_use_of_gtt_does_not_create_a_package(self) -> None:
        detection = self._detect("Uso prévio de GTT em 2022. Solicito EDA.")
        assert detection["eda_gastrostomy"]["any"] is False

    def test_negated_gtt_does_not_create_a_package(self) -> None:
        detection = self._detect("Nao solicito GTT neste momento. Solicito EDA.")
        assert detection["eda_gastrostomy"]["any"] is False

    def test_structured_item_alone_marks_the_package_as_candidate(self) -> None:
        structured: dict[str, object] = {"requested_procedures": [_gastrostomy_procedure()]}
        detection = self._detect("Solicito EDA.", structured)
        assert detection["eda_gastrostomy"] == {"strong": True, "any": True}

    def test_historical_gtt_occurrence_overrides_the_structured_item(self) -> None:
        structured: dict[str, object] = {"requested_procedures": [_gastrostomy_procedure()]}
        detection = self._detect("Gastrostomia realizada em 2023.", structured)
        assert detection["eda_gastrostomy"] == {"strong": False, "any": False}


# ── R1: reconciliação — uma row, supressão da base e fail-closed ─────────


class TestGastrostomyReconciliationV4:
    def _reconcile(self, *, declared, strong, any_evidence, cleaned_text):
        occurrences = detect_procedure_occurrences(llm1_structured_data={}, cleaned_text=cleaned_text)
        return reconcile_detected_procedures(
            declared=declared,
            strong=strong,
            any_evidence=any_evidence,
            occurrences=occurrences,
        )

    def test_current_gtt_collapses_the_detected_base_eda(self) -> None:
        result = self._reconcile(
            declared=("eda_gastrostomy",),
            strong=("eda", "eda_gastrostomy"),
            any_evidence=("eda", "eda_gastrostomy"),
            cleaned_text=GTT_TEXT,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("eda_gastrostomy",)
        assert serialize_procedure_precedence(result) == {
            "rule": "variation_over_base",
            "selected": "eda_gastrostomy",
            "suppressed": ["eda"],
        }

    def test_isolated_gtt_request_reconciles_as_a_single_package(self) -> None:
        cleaned_text = "Solicito GTT para confecção de gastrostomia."
        detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=cleaned_text)
        result = self._reconcile(
            declared=("eda_gastrostomy",),
            strong=tuple(code for code, flags in detection.items() if flags["strong"]),
            any_evidence=tuple(code for code, flags in detection.items() if flags["any"]),
            cleaned_text=cleaned_text,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("eda_gastrostomy",)

    def test_gtt_in_an_independent_section_suppresses_the_base_eda(self) -> None:
        result = self._reconcile(
            declared=("eda_gastrostomy",),
            strong=("eda", "eda_gastrostomy"),
            any_evidence=("eda", "eda_gastrostomy"),
            cleaned_text="Cabeçalho administrativo: EDA.\nSolicito GTT.",
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("eda_gastrostomy",)

    def test_historical_gtt_with_structured_item_fails_closed_without_the_package(self) -> None:
        result = self._reconcile(
            declared=("eda_gastrostomy",),
            strong=("eda",),
            any_evidence=("eda",),
            cleaned_text="Solicito EDA. Gastrostomia realizada em 2023.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "exam_type_mismatch"
        assert result.detected_procedure_types == ("eda",)

    def test_gtt_plus_colonoscopy_fails_closed(self) -> None:
        result = self._reconcile(
            declared=("eda_gastrostomy",),
            strong=("eda", "eda_gastrostomy", "colonoscopy"),
            any_evidence=("eda", "eda_gastrostomy", "colonoscopy"),
            cleaned_text=f"{GTT_TEXT} Solicito colonoscopia diagnóstica.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {"eda_gastrostomy", "colonoscopy"}
        assert result.suppressed_base_types == ("eda",)

    def test_two_current_variations_fail_closed(self) -> None:
        result = self._reconcile(
            declared=("eda_gastrostomy",),
            strong=("eda", "eda_gastrostomy", "eda_capsule"),
            any_evidence=("eda", "eda_gastrostomy", "eda_capsule"),
            cleaned_text="Solicito EDA com GTT e cápsula endoscópica.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {"eda", "eda_gastrostomy", "eda_capsule"}


class TestGastrostomyProfile:
    def test_package_resolves_the_eda_profile_under_its_own_label(self) -> None:
        from apps.cases.exam_profiles import require_exam_profile

        profile = require_exam_profile(ProcedureType.EDA_GASTROSTOMY)
        assert profile.label == ProcedureType.EDA_GASTROSTOMY.label
        assert profile.allows_foreign_body_exception is True
        assert "gastrostomy" in profile.allowed_priority_signal_codes


# ── R2/R3: verificador determinístico ─────────────────────────────────────


class TestInfectionReviewVerifier:
    def _verify(self, evidence: list[dict[str, Any]], report: str):
        return verify_infection_evidence(entries=evidence, main_report_text=report)

    def test_normal_leukocytes_and_negative_culture_are_visible_without_alert(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="leukocytes",
                    assessment="normal_explicit",
                    value_text="Leucócitos 8.200/mm3",
                    excerpt="Leucócitos 8.200/mm3 (normais)",
                ),
                _evidence(
                    category="culture",
                    assessment="negative_explicit",
                    excerpt="Hemoculturas negativas",
                ),
            ],
            NORMAL_REPORT,
        )

        groups = {group.category: group.items for group in view.groups}
        assert [item.assessment for item in groups["leukocytes"]] == ["normal_explicit"]
        assert [item.assessment for item in groups["culture"]] == ["negative_explicit"]
        assert groups["culture"][0].evidence_excerpt == "Hemoculturas negativas"
        assert view.concerning is False
        assert view.rejected == ()

    def test_numeric_inflammation_marker_without_interpretation_is_unclassified(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="crp",
                    assessment="abnormal_explicit",
                    value_text="PCR 12 mg/L",
                    excerpt="PCR 12 mg/L",
                )
            ],
            UNINTERPRETED_REPORT,
        )

        item = view.groups[0].items[0]
        assert item.assessment == "unclassified"
        # R3/D7: valor ancorado permanece visível, sem classificação inventada.
        assert item.value_text == "PCR 12 mg/L"
        assert item.evidence_excerpt == "PCR 12 mg/L"
        assert view.concerning is False

    def test_unclassified_is_accepted_without_a_marker(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="lactate",
                    assessment="unclassified",
                    temporal_status="unknown",
                    value_text="Lactato 1,8",
                    excerpt="Lactato 1,8",
                )
            ],
            "Lactato 1,8.",
        )
        assert view.groups[0].items[0].assessment == "unclassified"
        assert view.concerning is False

    @pytest.mark.parametrize(
        ("evidence", "report"),
        [
            (
                _evidence(
                    category="temperature_or_fever",
                    assessment="febrile_explicit",
                    value_text="38,5 C",
                    excerpt="Febre 38,5 C",
                ),
                CONCERNING_REPORT,
            ),
            (
                _evidence(
                    category="culture",
                    assessment="positive_explicit",
                    value_text="E. coli",
                    excerpt="Hemocultura positiva para E. coli",
                ),
                CONCERNING_REPORT,
            ),
        ],
    )
    def test_current_fever_or_positive_culture_alerts(self, evidence: dict[str, Any], report: str) -> None:
        view = self._verify([evidence], report)

        item = view.groups[0].items[0]
        assert item.concerning is True
        assert view.concerning is True
        assert item.assessment in CONCERNING_ASSESSMENTS

    @pytest.mark.parametrize(
        ("assessment", "excerpt"),
        [
            ("antibiotic_in_use", "Em uso de ceftriaxona (antibiótico)"),
            ("antibiotic_started", "Antibioticoterapia iniciada com meropenem"),
            ("antibiotic_escalated", "Antibiótico escalonado para maior espectro"),
        ],
    )
    def test_current_antibiotic_states_alert_without_diagnosis(self, assessment: str, excerpt: str) -> None:
        view = self._verify(
            [_evidence(category="antibiotic", assessment=assessment, excerpt=excerpt)],
            f"{excerpt}.",
        )

        item = view.groups[0].items[0]
        assert item.assessment == assessment
        assert item.concerning is True
        assert view.concerning is True

    def test_current_infectious_disease_care_alerts(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="infectious_disease",
                    assessment="current_care_explicit",
                    excerpt="Avaliação da infectologia",
                )
            ],
            "Avaliação da infectologia solicitada.",
        )
        assert view.concerning is True

    def test_antibiotic_and_infectious_disease_are_distinct_evidences(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="antibiotic",
                    assessment="antibiotic_in_use",
                    excerpt="Antibiótico em uso: ceftriaxona",
                ),
                _evidence(
                    category="infectious_disease",
                    assessment="current_care_explicit",
                    excerpt="Parecer da infectologia",
                ),
            ],
            "Antibiótico em uso: ceftriaxona. Parecer da infectologia registrado.",
        )

        assert [group.category for group in view.groups] == ["infectious_disease", "antibiotic"]
        assert [len(group.items) for group in view.groups] == [1, 1]
        assert view.concerning is True

    def test_local_historical_marker_dominates_the_declared_temporality(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="antibiotic",
                    assessment="antibiotic_in_use",
                    temporal_status="current",
                    excerpt="Uso prévio de antibiótico",
                )
            ],
            HISTORICAL_REPORT,
        )

        item = view.groups[0].items[0]
        assert item.temporal_status == "historical"
        assert item.concerning is False
        assert view.concerning is False

    def test_historical_fever_does_not_alert(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="temperature_or_fever",
                    assessment="febrile_explicit",
                    temporal_status="unknown",
                    excerpt="Histórico de febre",
                )
            ],
            "Histórico de febre há uma semana.",
        )
        assert view.concerning is False

    def test_negated_fever_is_demoted_and_does_not_alert(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="temperature_or_fever",
                    assessment="febrile_explicit",
                    excerpt="Sem febre",
                )
            ],
            "Sem febre no momento.",
        )
        assert view.groups[0].items[0].assessment == "unclassified"
        assert view.concerning is False

    def test_invented_excerpt_is_not_confirmed_and_does_not_alert(self) -> None:
        view = self._verify(
            [
                _evidence(
                    category="temperature_or_fever",
                    assessment="febrile_explicit",
                    excerpt="Febre 39 C com calafrios",
                )
            ],
            CONCERNING_REPORT,
        )

        assert view.groups == ()
        assert view.concerning is False
        assert [item.reason_code for item in view.rejected] == ["infection_excerpt_not_anchored"]

    def test_duplicated_excerpt_in_the_report_is_ambiguous(self) -> None:
        excerpt = "Hemocultura positiva para E. coli"
        view = self._verify(
            [_evidence(category="culture", assessment="positive_explicit", excerpt=excerpt)],
            f"{excerpt}. Repetido: {excerpt}.",
        )

        assert view.groups == ()
        assert [item.reason_code for item in view.rejected] == ["infection_excerpt_ambiguous"]

    def test_repeated_declared_item_is_deduplicated(self) -> None:
        entry = _evidence(category="culture", assessment="negative_explicit", excerpt="Hemoculturas negativas")
        view = self._verify([entry, dict(entry)], NORMAL_REPORT)

        assert len(view.groups[0].items) == 1
        assert [item.reason_code for item in view.rejected] == ["infection_evidence_duplicate"]

    def test_category_is_rederived_from_the_same_excerpt(self) -> None:
        view = self._verify(
            [_evidence(category="leukocytes", assessment="unclassified", excerpt="PCR 12 mg/L")],
            UNINTERPRETED_REPORT,
        )

        assert view.groups == ()
        assert [item.reason_code for item in view.rejected] == ["infection_category_mismatch"]

    def test_ambiguous_category_in_the_same_excerpt_is_rejected(self) -> None:
        excerpt = "Leucócitos 15.000/mm3 e PCR 120 mg/L"
        view = self._verify(
            [_evidence(category="leukocytes", assessment="unclassified", excerpt=excerpt)],
            f"{excerpt}.",
        )

        assert view.groups == ()
        assert [item.reason_code for item in view.rejected] == ["infection_category_ambiguous"]

    def test_out_of_vocabulary_entry_is_rejected(self) -> None:
        view = self._verify(
            [
                {
                    "category": "xray",
                    "assessment": "unclassified",
                    "temporal_status": "unknown",
                    "value_text": None,
                    "evidence_excerpt": "Radiografia de tórax",
                }
            ],
            "Radiografia de tórax.",
        )

        assert view.groups == ()
        assert [item.reason_code for item in view.rejected] == ["infection_evidence_not_in_vocabulary"]

    def test_groups_and_items_follow_the_canonical_vocabulary_order(self) -> None:
        view = self._verify(
            [
                _evidence(category="culture", assessment="negative_explicit", excerpt="Hemoculturas negativas"),
                _evidence(category="crp", assessment="unclassified", value_text="PCR 12 mg/L", excerpt="PCR 12 mg/L"),
                _evidence(
                    category="leukocytes",
                    assessment="normal_explicit",
                    value_text="Leucócitos 8.200/mm3",
                    excerpt="Leucócitos 8.200/mm3 (normais)",
                ),
            ],
            f"{NORMAL_REPORT} {UNINTERPRETED_REPORT}",
        )

        assert [group.category for group in view.groups] == ["leukocytes", "crp", "culture"]
        assert all(group.category in INFECTION_CATEGORY_ORDER for group in view.groups)

    def test_empty_or_failed_extraction_produces_an_empty_neutral_review(self) -> None:
        assert verify_infection_evidence(entries=[], main_report_text=NORMAL_REPORT).empty is True
        assert verify_infection_evidence(entries=None, main_report_text=NORMAL_REPORT).empty is True
        assert verify_infection_evidence(entries=[], main_report_text="").empty is True


# ── R1/R4/R5: painel chega ao artefato 4.0 somente em EDA + GTT ───────────


class TestGastrostomyReviewArtifact:
    def test_concerning_review_is_persisted_only_for_the_exact_identity(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_gtt_concern")
        case, client = _run(
            user,
            procedure_types=("eda_gastrostomy",),
            extracted_text=f"{GTT_TEXT} {CONCERNING_REPORT}",
            llm1=_llm1_json(
                procedures=[
                    _gastrostomy_procedure(
                        evidence=[
                            _evidence(
                                category="temperature_or_fever",
                                assessment="febrile_explicit",
                                value_text="38,5 C",
                                excerpt="Febre 38,5 C",
                            )
                        ]
                    )
                ],
                one_liner="EDA + GTT indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda_gastrostomy"),
        )

        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        assert _infection_review(case)["concerning"] is True
        groups = _groups_by_category(_infection_review(case))
        assert [item["assessment"] for item in groups["temperature_or_fever"]] == ["febrile_explicit"]
        assert [item["concerning"] for item in groups["temperature_or_fever"]] == [True]

    def test_no_evidence_persists_no_artifact_section(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_gtt_empty")
        case, _ = _run(
            user,
            procedure_types=("eda_gastrostomy",),
            extracted_text=GTT_TEXT,
            llm1=_llm1_json(procedures=[_gastrostomy_procedure()], one_liner="EDA + GTT indicada."),
            recommendations=_single_procedure_recommendation("eda_gastrostomy"),
        )

        assert case.status == CaseStatus.WAIT_DOCTOR
        assert "infection_review" not in _suggested_action(case)

    def test_eda_with_historical_gtt_creates_no_package_and_no_review(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_gtt_historical")
        case, client = _run(
            user,
            procedure_types=("eda",),
            extracted_text="Solicito EDA. Gastrostomia realizada em 2023. Febre 38,5 C.",
            llm1=_llm1_json(
                procedures=[_eda_procedure()],
                one_liner="EDA indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda"),
        )

        assert case.status == CaseStatus.WAIT_DOCTOR
        assert "infection_review" not in _suggested_action(case)
        assert len(client.calls) == 2
        rows = CaseProcedure.objects.filter(case=case, detection_status=DetectionStatus.DETECTED)
        assert [row.procedure_type for row in rows] == ["eda"]

    def test_eda_declared_with_current_gtt_detected_returns_to_nir_without_review(self, django_user_model) -> None:
        """R1 negativo: o pacote substitui a base detectada e o mismatch volta ao NIR."""
        user = django_user_model.objects.create_user(username="nir4_gtt_mismatch")
        case, client = _run(
            user,
            procedure_types=("eda",),
            extracted_text=GTT_TEXT,
            llm1=_llm1_json(procedures=[_eda_procedure()], one_liner="EDA indicada."),
            recommendations=_single_procedure_recommendation("eda"),
        )

        assert len(client.calls) == 1
        payload = _suggested_action(case)
        assert payload["decision"] == "manual_review_required"
        assert payload["reason_code"] == "exam_type_mismatch"
        assert payload["detected_procedures"] == ["eda_gastrostomy"]
        assert "infection_review" not in payload

    def test_unconfirmed_excerpt_never_becomes_a_fact(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_gtt_invented")
        case, _ = _run(
            user,
            procedure_types=("eda_gastrostomy",),
            extracted_text=GTT_TEXT,
            llm1=_llm1_json(
                procedures=[
                    _gastrostomy_procedure(
                        evidence=[
                            _evidence(
                                category="temperature_or_fever",
                                assessment="febrile_explicit",
                                excerpt="Febre 39 C com calafrios",
                            )
                        ]
                    )
                ],
                one_liner="EDA + GTT indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda_gastrostomy"),
        )

        assert "infection_review" not in _suggested_action(case)
        assert case.status == CaseStatus.WAIT_DOCTOR


# ── D7/D8: a coleção infecciosa é consultiva e nunca regra do LLM2 ────────


class TestLlm2EphemeralView:
    """D7: o reconciliador LLM2 recebe a visão efêmera SEM ``infection_evidence``.

    A coleção permanece no artefato 4.0 e no relatório médico, mas variar
    somente ``infection_evidence`` não pode alterar o prompt do LLM2 (D8).
    """

    def test_llm2_prompt_omits_the_collection_and_its_content(self, django_user_model) -> None:
        marker_excerpt = "Febre 38,5 C"
        marker_value = "38,5 C"
        user = django_user_model.objects.create_user(username="nir4_gtt_llm2_view")
        case, client = _run(
            user,
            procedure_types=("eda_gastrostomy",),
            extracted_text=f"{GTT_TEXT} {CONCERNING_REPORT}",
            llm1=_llm1_json(
                procedures=[
                    _gastrostomy_procedure(
                        evidence=[
                            _evidence(
                                category="temperature_or_fever",
                                assessment="febrile_explicit",
                                value_text=marker_value,
                                excerpt=marker_excerpt,
                            )
                        ]
                    )
                ],
                one_liner="EDA + GTT indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda_gastrostomy"),
        )

        assert len(client.calls) == 2
        llm2_prompt = client.calls[1]["user_prompt"]

        assert "infection_evidence" not in llm2_prompt
        assert marker_excerpt not in llm2_prompt
        assert marker_value not in llm2_prompt
        ephemeral_view = _extract_llm1_json_from_prompt(llm2_prompt)
        procedure_item = ephemeral_view["requested_procedures"][0]
        assert "infection_evidence" not in procedure_item

        # A coleção verificada continua no artefato 4.0 e no relatório médico.
        review = _infection_review(case)
        assert review["concerning"] is True
        assert _groups_by_category(review)["temperature_or_fever"][0]["evidence_excerpt"] == marker_excerpt

        from apps.doctor.presenters import DoctorReportPresenter

        report = DoctorReportPresenter(
            structured_data=case.structured_data or {},
            summary_text=case.summary_text or "",
            suggested_action=case.suggested_action or {},
        ).build_report()
        assert report["infection_review"]["concerning"] is True
        assert report["infection_review"]["groups"][0]["items"][0]["evidence_excerpt"] == marker_excerpt


# ── R6: invariância consultiva ─────────────────────────────────────────────


EMPTY_EVIDENCE: list[dict[str, Any]] = []
NORMAL_ONLY_EVIDENCE: list[dict[str, Any]] = [
    {
        "category": "leukocytes",
        "assessment": "normal_explicit",
        "temporal_status": "current",
        "value_text": "Leucócitos 8.200/mm3",
        "evidence_excerpt": "Leucócitos 8.200/mm3 (normais)",
    },
    {
        "category": "culture",
        "assessment": "negative_explicit",
        "temporal_status": "current",
        "value_text": None,
        "evidence_excerpt": "Hemoculturas negativas",
    },
]
CONCERNING_EVIDENCE: list[dict[str, Any]] = [
    {
        "category": "temperature_or_fever",
        "assessment": "febrile_explicit",
        "temporal_status": "current",
        "value_text": "38,5 C",
        "evidence_excerpt": "Febre 38,5 C",
    }
]
INVARIANCE_REPORTS = {
    "empty": GTT_TEXT,
    "normal_only": f"{GTT_TEXT} {NORMAL_REPORT}",
    "concerning": f"{GTT_TEXT} {CONCERNING_REPORT}",
}


class TestConsultiveInvariance:
    """R6/D8: só a revisão infecciosa varia; todo o resto permanece idêntico."""

    def _run_variant(self, user, variant: str) -> Case:
        evidence = {
            "empty": EMPTY_EVIDENCE,
            "normal_only": NORMAL_ONLY_EVIDENCE,
            "concerning": CONCERNING_EVIDENCE,
        }[variant]
        case, _ = _run(
            user,
            procedure_types=("eda_gastrostomy",),
            extracted_text=INVARIANCE_REPORTS[variant],
            llm1=_llm1_json(
                procedures=[_gastrostomy_procedure(evidence=evidence)],
                one_liner="EDA + GTT indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda_gastrostomy"),
        )
        return case

    def _snapshot(self, case: Case) -> dict[str, Any]:
        recommendation = cast("list[dict[str, Any]]", _suggested_action(case)["procedure_recommendations"])[0]
        decision = cast("dict[str, Any]", recommendation["preop_decision"])
        return {
            "status": case.status,
            "decision": decision["decision"],
            "reason_code": decision["reason_code"],
            "failed_requirements": decision["failed_requirements"],
            "suggestion": recommendation["suggestion"],
            "support": recommendation["support_recommendation"],
            "global_support": _suggested_action(case)["global_support_recommendation"],
            "detected": [row.procedure_type for row in case.procedures.filter(detection_status="detected")],
            "priority_signals": [signal["code"] for signal in case.priority_signals],
            "form_fields": self._form_fields(case),
        }

    def _form_fields(self, case: Case) -> list[str]:
        from apps.doctor.forms import DoctorDecisionForm

        return sorted(DoctorDecisionForm(case=case).fields)

    @pytest.mark.parametrize("variant", ["empty", "normal_only", "concerning"])
    def test_snapshot_is_stable_and_review_varies(self, django_user_model, variant: str) -> None:
        user = django_user_model.objects.create_user(username=f"nir4_inv_{variant}")
        case = self._run_variant(user, variant)
        snapshot = self._snapshot(case)

        assert snapshot["status"] == CaseStatus.WAIT_DOCTOR
        assert snapshot["decision"] == "accept"
        assert snapshot["failed_requirements"] == []
        assert snapshot["suggestion"] == "accept"
        assert snapshot["support"] == "none"
        assert snapshot["global_support"] == "none"
        assert snapshot["detected"] == ["eda_gastrostomy"]
        assert "gastrostomy" not in snapshot["priority_signals"]
        assert snapshot["form_fields"] == sorted(self._form_fields(case))

    def test_policy_recommendation_support_and_fields_are_identical_across_variants(self, django_user_model) -> None:
        snapshots: dict[str, dict[str, Any]] = {}
        reviews: dict[str, Any] = {}
        for variant in ("empty", "normal_only", "concerning"):
            user = django_user_model.objects.create_user(username=f"nir4_cmp_{variant}")
            case = self._run_variant(user, variant)
            snapshots[variant] = self._snapshot(case)
            reviews[variant] = _suggested_action(case).get("infection_review")

        baseline = snapshots["empty"]
        assert baseline["decision"] == "accept"
        for variant in ("normal_only", "concerning"):
            assert snapshots[variant] == baseline, variant

        # A revisão consultiva é a ÚNICA diferença observável.
        assert reviews["empty"] is None
        assert reviews["normal_only"] is not None and reviews["normal_only"]["concerning"] is False
        assert reviews["concerning"] is not None and reviews["concerning"]["concerning"] is True

    def test_form_validation_is_identical_across_variants(self, django_user_model) -> None:
        from apps.doctor.forms import DoctorDecisionForm

        results: dict[str, Any] = {}
        for variant in ("empty", "normal_only", "concerning"):
            user = django_user_model.objects.create_user(username=f"nir4_form_{variant}")
            case = self._run_variant(user, variant)
            form = DoctorDecisionForm(
                {"procedure_eda": "approved", "procedure_eda_reason": "Aprovação registrada."},
                case=case,
            )
            results[variant] = {
                "is_valid": form.is_valid(),
                "errors": sorted(form.errors.keys()),
                "fields": sorted(form.fields),
            }

        assert results["empty"] == results["normal_only"] == results["concerning"]

    def test_fsm_transition_and_destination_are_identical_across_variants(self, django_user_model, client) -> None:
        """Fluxo da FSM (WAIT_DOCTOR → destino) igual com e sem alerta.

        Slice 006 (R1): o submit real da identidade nova (o pacote
        ``eda_gastrostomy``) exige disposição própria e é aplicado de forma
        idêntica às três variantes para provar que o alerta consultivo não
        altera a transição nem o destino.
        """
        from django.urls import reverse

        from apps.accounts.models import Role
        from apps.cases.services import claim_case_lock

        role, _ = Role.objects.get_or_create(name="doctor")
        destinations: dict[str, Any] = {}
        events: dict[str, list[str]] = {}
        for variant in ("empty", "normal_only", "concerning"):
            user = django_user_model.objects.create_user(username=f"nir4_fsm_{variant}")
            case = self._run_variant(user, variant)
            doctor = django_user_model.objects.create_user(username=f"doc4_fsm_{variant}")
            doctor.roles.add(role)
            client.force_login(doctor)
            session = client.session
            session["active_role"] = "doctor"
            session.save()
            lock = claim_case_lock(
                case_id=case.case_id,
                user=doctor,
                expected_status=CaseStatus.WAIT_DOCTOR,
                context="doctor_decision",
                role="doctor",
            )
            assert lock.acquired is True

            pipeline_event_count = case.events.count()

            response = client.post(
                reverse("doctor:submit", args=[case.case_id]),
                {
                    "lock_token": str(lock.token),
                    "procedure_eda_gastrostomy": "approved",
                    "procedure_eda_gastrostomy_reason": "Aprovação registrada.",
                    "support_flag": "none",
                    "admission_flow": "scheduled",
                },
            )
            assert response.status_code == 302

            reloaded = Case.objects.get(case_id=case.case_id)
            destinations[variant] = {
                "status": reloaded.status,
                "decision": reloaded.doctor_decision,
                "approved": sorted(
                    row.procedure_type for row in reloaded.procedures.all() if row.doctor_disposition == "approved"
                ),
            }
            # Somente os eventos da jornada médica: o slice 006 grava row
            # aprovada e o ARN de teste é compartilhado, de modo que a 2ª
            # variante enxerga o caso decidido da 1ª no lookup de histórico.
            events[variant] = list(reloaded.events.values_list("event_type", flat=True))[pipeline_event_count:]

        assert destinations["empty"] == destinations["normal_only"] == destinations["concerning"]
        assert events["empty"] == events["normal_only"] == events["concerning"]
        assert destinations["empty"]["status"] == CaseStatus.WAIT_APPT
        assert destinations["empty"]["decision"] == "accept"
        assert destinations["empty"]["approved"] == ["eda_gastrostomy"]


# ── R7: sinal legado permanece legível, mas não é writer de identidade ────


class TestLegacyGastrostomySignal:
    def test_four_zero_write_does_not_persist_the_legacy_signal(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_signal")
        case, _ = _run(
            user,
            procedure_types=("eda_gastrostomy",),
            extracted_text=GTT_TEXT,
            llm1=_llm1_json(procedures=[_gastrostomy_procedure()], one_liner="EDA + GTT indicada."),
            recommendations=_single_procedure_recommendation("eda_gastrostomy"),
        )

        codes = [signal["code"] for signal in case.priority_signals]
        assert "gastrostomy" not in codes
        assert codes == []
        # O mesmo texto/projeção SEM a exclusão do writer 4.0 produziria o sinal
        # legado: é a exclusão (D13) que impede a duplicação identidade + sinal.
        legacy = resolve_priority_signals(
            structured_data=project_v4_to_llm1_shape(v4_data=case.structured_data or {}, procedure_type="eda"),
            source_text=case.extracted_text,
            exam_type="eda",
        )
        assert [signal["code"] for signal in legacy] == ["gastrostomy"]

    def test_legacy_artifacts_keep_the_signal_readable(self) -> None:
        structured: dict[str, object] = {
            "schema_version": "1.1",
            "eda": {"requested_procedure": {"subtype": "gastrostomy"}},
            "preop_screening": {"rulebook_signals": {"eda_subtype": "gastrostomy"}},
        }
        signals = resolve_priority_signals(structured_data=structured, source_text="", exam_type="eda")

        assert [signal["code"] for signal in signals] == ["gastrostomy"]
        assert [badge["code"] for badge in build_priority_signal_badges(signals)] == ["gastrostomy"]

    def test_legacy_case_with_the_signal_remains_presentable(self) -> None:
        from apps.doctor.presenters import DoctorReportPresenter

        signals = resolve_priority_signals(
            structured_data={
                "schema_version": "1.1",
                "eda": {"requested_procedure": {"subtype": "gastrostomy"}},
            },
            source_text="",
            exam_type="eda",
        )
        report = DoctorReportPresenter(
            structured_data={"schema_version": "1.1", "eda": {"requested_procedure": {"subtype": "gastrostomy"}}},
            priority_signals=signals,
        ).build_report()

        assert [badge["code"] for badge in report["priority_signal_badges"]] == ["gastrostomy"]
