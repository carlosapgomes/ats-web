"""Slice 005 — família Retossigmoidoscopia no pipeline 4.0 (R2–R4, R6).

Cobre:

- R2: nome canônico atual detecta a identidade exata; dilatação/argônio exigem
  vínculo local com Retossigmoidoscopia solicitada; histórico, negação, achado
  isolado e termo solto não criam identidade;
- R3: a variação suprime a base da mesma expressão e em trecho independente;
  duas variações, variação + Colonoscopia ou qualquer par fora da matriz
  seguem fail-closed ao NIR sem descartar valores;
- R4: as três identidades executam exatamente os requisitos/thresholds/
  condicionais do profile de Colonoscopia, com textos determinísticos sob a
  label da identidade (nunca "Colonoscopia") e o código original preservado;
- R6: EDA + Colonoscopia continua a única combinação suportada.
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, DetectionStatus
from apps.cases.procedures import ALLOWED_PROCEDURE_SETS, PROCEDURE_LABELS, set_declared_procedures
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.policy import evaluate_procedure_policy
from apps.pipeline.procedure_reconciliation import (
    reconcile_detected_procedures,
    serialize_procedure_precedence,
)
from apps.pipeline.scope_detection import detect_procedure_occurrences, detect_requested_procedures_v4
from apps.pipeline.tests.test_slice_002_pipeline import (
    _llm1_json,
    _llm2_json,
    _single_procedure_recommendation,
)

pytestmark = pytest.mark.django_db

SCHEMA_VERSION = "4.0"

RECTOSIGMOIDOSCOPY_TYPES = (
    "rectosigmoidoscopy",
    "rectosigmoidoscopy_dilation",
    "rectosigmoidoscopy_argon",
)

BASE_TEXT = "Solicito Retossigmoidoscopia para rastreamento."
DILATION_TEXT = "Solicito Retossigmoidoscopia com dilatação de anastomose por estenose."
ARGON_TEXT = "Solicito Retossigmoidoscopia com plasma de argônio em angiodisplasias."

# Mesmo conteúdo clínico comum (menção a corpo estranho incluída) para a
# comparação de igualdade com Colonoscopia (R4).
COMMON_CLINICAL_TAIL = " Historia de suspeita de corpo estranho descrita no encaminhamento."
REQUEST_TEXTS: dict[str, str] = {
    "colonoscopy": "Solicito colonoscopia diagnostica." + COMMON_CLINICAL_TAIL,
    "rectosigmoidoscopy": BASE_TEXT + COMMON_CLINICAL_TAIL,
    "rectosigmoidoscopy_dilation": DILATION_TEXT + COMMON_CLINICAL_TAIL,
    "rectosigmoidoscopy_argon": ARGON_TEXT + COMMON_CLINICAL_TAIL,
}


# ── Fixtures v4 ────────────────────────────────────────────────────────────


def _recto_procedure(procedure_type: str = "rectosigmoidoscopy", *, excerpt: str | None = None) -> dict[str, Any]:
    """Item 4.0 mínimo e schema-válido para qualquer identidade do catálogo."""
    return {
        "procedure_type": procedure_type,
        "name": PROCEDURE_LABELS[procedure_type],
        "urgency": "eletivo",
        "indication_category": "screening",
        "evidence_spans": [{"field_path": "requested_procedures.0", "excerpt": excerpt or BASE_TEXT}],
    }


def _make_declared_case(user, *, procedure_types: tuple[str, ...], extracted_text: str) -> Case:
    """Caso pronto para o pipeline 4.0 com a projeção declarada informada."""
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
    """Executa o pipeline 4.0 com LLM2 apontando para o case_id real."""
    case = _make_declared_case(user, procedure_types=procedure_types, extracted_text=extracted_text)
    client = RecordingLlmClient(
        responses=[
            llm1,
            _llm2_json(str(case.case_id), recommendations=recommendations),
        ]
    )
    run_pipeline(case.case_id, llm_client=client)
    return Case.objects.get(case_id=case.case_id), client


def _suggested_action(case: Case) -> dict[str, Any]:
    return cast("dict[str, Any]", case.suggested_action or {})


def _recommendations(case: Case) -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", _suggested_action(case).get("procedure_recommendations") or [])


def _preop_decision(case: Case) -> dict[str, object]:
    return cast("dict[str, object]", _recommendations(case)[0]["preop_decision"])


def _policy_decision(procedure_type: str, *, hb_g_dl: float) -> dict[str, object]:
    """Policy determinística do procedimento a partir do artefato 4.0 real."""
    artifact = json.loads(_llm1_json(procedures=[_recto_procedure(procedure_type)], hb_g_dl=hb_g_dl))
    from apps.pipeline.schemas.adapters import project_v4_to_llm1_shape

    projection = project_v4_to_llm1_shape(v4_data=artifact, procedure_type=procedure_type)
    return evaluate_procedure_policy(structured_data=projection, procedure_type=procedure_type)


def _foreign_body_projection() -> dict[str, object]:
    """Entrada clínica idêntica com subtipo EDA de exceção de corpo estranho."""
    return {
        "eda": {
            "requested_procedure": {"name": "procedimento", "subtype": "foreign_body"},
            "indication_category": "foreign_body",
            "is_pediatric": False,
        },
        "preop_screening": {
            "exam_type": "colonoscopy",
            "hb_g_dl": 13.0,
            "platelets_per_mm3": 200000,
            "inr": 1.0,
            "rulebook_signals": {},
            "evidence_spans": [],
        },
    }


# ── R2: detecção conservadora da família ───────────────────────────────────


class TestRectosigmoidoscopyDetectionV4:
    def _detect(
        self, cleaned_text: str, structured_data: dict[str, object] | None = None
    ) -> dict[str, dict[str, bool]]:
        return detect_requested_procedures_v4(
            llm1_structured_data=structured_data or {},
            cleaned_text=cleaned_text,
        )

    def test_canonical_current_name_detects_the_exact_identity(self) -> None:
        detection = self._detect(BASE_TEXT)
        assert detection["rectosigmoidoscopy"] == {"strong": True, "any": True}

    def test_identity_never_detects_colonoscopy(self) -> None:
        """R2/D4: compartilhar profile não transforma a identidade."""
        detection = self._detect(BASE_TEXT)
        assert detection["colonoscopy"] == {"strong": False, "any": False}
        assert detection["eda"]["any"] is False

    def test_history_negation_and_isolated_mention_do_not_create_the_identity(self) -> None:
        for text in (
            "Retossigmoidoscopia realizada em 2023.",
            "Nao solicito retossigmoidoscopia neste momento.",
            "Exame previo: retossigmoidoscopia descartada pela equipe.",
        ):
            assert self._detect(text)["rectosigmoidoscopy"]["any"] is False, text

    def test_colonoscopy_request_never_creates_the_identity(self) -> None:
        detection = self._detect("Solicito colonoscopia diagnostica.")
        assert detection["rectosigmoidoscopy"]["any"] is False

    def test_dilation_linked_to_the_base_detects_the_variation(self) -> None:
        detection = self._detect(DILATION_TEXT)
        assert detection["rectosigmoidoscopy_dilation"] == {"strong": True, "any": True}
        # A base segue detectada: o colapso é decisão da reconciliação.
        assert detection["rectosigmoidoscopy"]["any"] is True

    def test_argon_linked_to_the_base_detects_the_variation(self) -> None:
        detection = self._detect(ARGON_TEXT)
        assert detection["rectosigmoidoscopy_argon"] == {"strong": True, "any": True}
        assert detection["rectosigmoidoscopy"]["any"] is True

    def test_dilation_never_links_to_eda(self) -> None:
        detection = self._detect("Solicito EDA com dilatação esofágica.")
        assert detection["rectosigmoidoscopy_dilation"]["any"] is False

    def test_dilation_without_local_link_is_not_a_variation(self) -> None:
        """Termo ambíguo: a ambiguidade nunca é resolvida por proximidade global."""
        for text in (
            "Paciente encaminhado para dilatação de anastomose colorretal.",
            "Relatorio de imagem demonstra dilatação de cólon. Solicito Retossigmoidoscopia.",
        ):
            assert self._detect(text)["rectosigmoidoscopy_dilation"]["any"] is False, text

    def test_choledochal_dilation_is_not_a_variation_even_linked_to_the_base(self) -> None:
        detection = self._detect("Solicito Retossigmoidoscopia com dilatação de colédoco.")
        assert detection["rectosigmoidoscopy_dilation"]["any"] is False

    def test_argon_without_local_link_is_not_a_variation(self) -> None:
        detection = self._detect("Plasma de argonio disponivel no servico. Solicito Retossigmoidoscopia.")
        assert detection["rectosigmoidoscopy_argon"]["any"] is False

    def test_historical_and_negated_variations_do_not_create_identities(self) -> None:
        for text in (
            "Retossigmoidoscopia com dilatação realizada em 2022.",
            "Nao solicito retossigmoidoscopia com plasma de argonio.",
        ):
            detection = self._detect(text)
            assert detection["rectosigmoidoscopy_dilation"]["any"] is False, text
            assert detection["rectosigmoidoscopy_argon"]["any"] is False, text

    def test_structured_item_without_text_occurrence_is_a_candidate(self) -> None:
        structured: dict[str, object] = {"requested_procedures": [_recto_procedure("rectosigmoidoscopy_dilation")]}
        detection = self._detect("Relatorio clinico sem mencao ao procedimento.", structured_data=structured)
        assert detection["rectosigmoidoscopy_dilation"] == {"strong": True, "any": True}
        # A identidade base não é inferida do item da variação (singleton).
        assert detection["rectosigmoidoscopy"]["any"] is False

    def test_non_current_occurrence_overrides_the_structured_item(self) -> None:
        """Slice 003 gate: o item estruturado não autoriza sem ocorrência atual."""
        structured: dict[str, object] = {"requested_procedures": [_recto_procedure("rectosigmoidoscopy_dilation")]}
        detection = self._detect("Dilatação de anastomose realizada em 2022.", structured_data=structured)
        assert detection["rectosigmoidoscopy_dilation"] == {"strong": False, "any": False}


# ── R2/R3: reconciliação — colapso da base e fail-closed ───────────────────


class TestRectosigmoidoscopyReconciliation:
    def _reconcile(self, *, declared, strong, any_evidence, cleaned_text):
        occurrences = detect_procedure_occurrences(
            llm1_structured_data={},
            cleaned_text=cleaned_text,
        )
        return reconcile_detected_procedures(
            declared=declared,
            strong=strong,
            any_evidence=any_evidence,
            occurrences=occurrences,
        )

    def test_base_singleton_proceeds_without_precedence(self) -> None:
        result = self._reconcile(
            declared=("rectosigmoidoscopy",),
            strong=("rectosigmoidoscopy",),
            any_evidence=("rectosigmoidoscopy",),
            cleaned_text=BASE_TEXT,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("rectosigmoidoscopy",)
        assert result.variation_precedence_applied is False
        assert serialize_procedure_precedence(result) is None

    def test_current_variation_collapses_the_base_in_the_same_expression(self) -> None:
        result = self._reconcile(
            declared=("rectosigmoidoscopy_dilation",),
            strong=("rectosigmoidoscopy", "rectosigmoidoscopy_dilation"),
            any_evidence=("rectosigmoidoscopy", "rectosigmoidoscopy_dilation"),
            cleaned_text=DILATION_TEXT,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("rectosigmoidoscopy_dilation",)
        assert result.variation_precedence_applied is True
        assert result.selected_variation_type == "rectosigmoidoscopy_dilation"
        assert result.suppressed_base_types == ("rectosigmoidoscopy",)

    def test_variation_suppresses_the_base_detected_in_another_section(self) -> None:
        result = self._reconcile(
            declared=("rectosigmoidoscopy_argon",),
            strong=("rectosigmoidoscopy", "rectosigmoidoscopy_argon"),
            any_evidence=("rectosigmoidoscopy", "rectosigmoidoscopy_argon"),
            cleaned_text="Cabecalho administrativo: Retossigmoidoscopia.\nSolicito Retossigmoidoscopia com argônio.",
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("rectosigmoidoscopy_argon",)
        assert result.variation_precedence_applied is True
        assert result.suppressed_base_types == ("rectosigmoidoscopy",)

    def test_structured_item_without_current_occurrence_does_not_suppress(self) -> None:
        result = self._reconcile(
            declared=("rectosigmoidoscopy_dilation",),
            strong=("rectosigmoidoscopy", "rectosigmoidoscopy_dilation"),
            any_evidence=("rectosigmoidoscopy", "rectosigmoidoscopy_dilation"),
            cleaned_text="Solicito Retossigmoidoscopia. Dilatação de anastomose realizada em 2022.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {"rectosigmoidoscopy", "rectosigmoidoscopy_dilation"}
        assert result.variation_precedence_applied is False

    def test_two_current_variations_fail_closed_without_discarding_values(self) -> None:
        result = self._reconcile(
            declared=("rectosigmoidoscopy_dilation",),
            strong=(
                "rectosigmoidoscopy",
                "rectosigmoidoscopy_dilation",
                "rectosigmoidoscopy_argon",
            ),
            any_evidence=(
                "rectosigmoidoscopy",
                "rectosigmoidoscopy_dilation",
                "rectosigmoidoscopy_argon",
            ),
            cleaned_text="Solicito Retossigmoidoscopia com dilatação e plasma de argônio.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {
            "rectosigmoidoscopy",
            "rectosigmoidoscopy_dilation",
            "rectosigmoidoscopy_argon",
        }
        assert result.variation_precedence_applied is False

    def test_variation_plus_colonoscopy_fails_closed(self) -> None:
        result = self._reconcile(
            declared=("rectosigmoidoscopy_dilation",),
            strong=("rectosigmoidoscopy", "rectosigmoidoscopy_dilation", "colonoscopy"),
            any_evidence=("rectosigmoidoscopy", "rectosigmoidoscopy_dilation", "colonoscopy"),
            cleaned_text=f"{DILATION_TEXT} Solicito colonoscopia diagnostica.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {"rectosigmoidoscopy_dilation", "colonoscopy"}
        assert result.variation_precedence_applied is True
        assert result.suppressed_base_types == ("rectosigmoidoscopy",)

    def test_base_plus_colonoscopy_is_not_a_supported_set(self) -> None:
        result = self._reconcile(
            declared=("rectosigmoidoscopy",),
            strong=("rectosigmoidoscopy", "colonoscopy"),
            any_evidence=("rectosigmoidoscopy", "colonoscopy"),
            cleaned_text=f"{BASE_TEXT} Solicito colonoscopia diagnostica.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {"rectosigmoidoscopy", "colonoscopy"}

    def test_metadata_mirrors_the_variation_precedence_shape(self) -> None:
        result = self._reconcile(
            declared=("rectosigmoidoscopy_argon",),
            strong=("rectosigmoidoscopy", "rectosigmoidoscopy_argon"),
            any_evidence=("rectosigmoidoscopy", "rectosigmoidoscopy_argon"),
            cleaned_text=ARGON_TEXT,
        )
        assert serialize_procedure_precedence(result) == {
            "rule": "variation_over_base",
            "selected": "rectosigmoidoscopy_argon",
            "suppressed": ["rectosigmoidoscopy"],
        }


# ── R6: matriz fechada preservada ──────────────────────────────────────────


class TestClosedMatrixRemains:
    def test_eda_plus_colonoscopy_is_still_the_only_combination(self) -> None:
        singletons = {frozenset({procedure_type}) for procedure_type in PROCEDURE_LABELS}
        assert ALLOWED_PROCEDURE_SETS == singletons | {frozenset({"eda", "colonoscopy"})}

    def test_retosigmoidoscopy_pairs_are_not_supported(self) -> None:
        for pair in (
            frozenset({"rectosigmoidoscopy", "colonoscopy"}),
            frozenset({"rectosigmoidoscopy", "rectosigmoidoscopy_dilation"}),
            frozenset({"rectosigmoidoscopy_dilation", "rectosigmoidoscopy_argon"}),
            frozenset({"eda", "rectosigmoidoscopy"}),
        ):
            assert pair not in ALLOWED_PROCEDURE_SETS


# ── R2/R4: as três identidades chegam ao médico ────────────────────────────


class TestRectosigmoidoscopyReachesDoctor:
    def test_base_identity_reaches_wait_doctor(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir5_base")
        case, client = _run(
            user,
            procedure_types=("rectosigmoidoscopy",),
            extracted_text=BASE_TEXT,
            llm1=_llm1_json(procedures=[_recto_procedure()], one_liner="Retossigmoidoscopia indicada."),
            recommendations=_single_procedure_recommendation("rectosigmoidoscopy"),
        )
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        assert [item["procedure_type"] for item in _recommendations(case)] == ["rectosigmoidoscopy"]
        rows = CaseProcedure.objects.filter(case=case)
        assert [(row.procedure_type, row.detection_status) for row in rows] == [
            ("rectosigmoidoscopy", DetectionStatus.DETECTED)
        ]
        event = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")
        assert event.payload["schema_version"] == SCHEMA_VERSION
        assert event.payload["detected_procedures"] == ["rectosigmoidoscopy"]
        assert event.payload["declared_procedures"] == ["rectosigmoidoscopy"]

    def test_dilation_reaches_wait_doctor_with_the_exact_identity(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir5_dilation")
        case, client = _run(
            user,
            procedure_types=("rectosigmoidoscopy_dilation",),
            extracted_text=DILATION_TEXT,
            llm1=_llm1_json(
                procedures=[_recto_procedure("rectosigmoidoscopy_dilation", excerpt=DILATION_TEXT)],
                one_liner="Retossigmoidoscopia + Dilatação indicada.",
            ),
            recommendations=_single_procedure_recommendation("rectosigmoidoscopy_dilation"),
        )
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        assert [item["procedure_type"] for item in _recommendations(case)] == ["rectosigmoidoscopy_dilation"]
        rows = CaseProcedure.objects.filter(case=case)
        assert [(row.procedure_type, row.detection_status) for row in rows] == [
            ("rectosigmoidoscopy_dilation", DetectionStatus.DETECTED)
        ]
        event = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")
        assert event.payload["procedure_precedence"] == {
            "rule": "variation_over_base",
            "selected": "rectosigmoidoscopy_dilation",
            "suppressed": ["rectosigmoidoscopy"],
        }
        assert _suggested_action(case)["procedure_precedence"] == event.payload["procedure_precedence"]

    def test_argon_reaches_wait_doctor_with_the_exact_identity(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir5_argon")
        case, client = _run(
            user,
            procedure_types=("rectosigmoidoscopy_argon",),
            extracted_text=ARGON_TEXT,
            llm1=_llm1_json(
                procedures=[_recto_procedure("rectosigmoidoscopy_argon", excerpt=ARGON_TEXT)],
                one_liner="Retossigmoidoscopia + Argônio indicada.",
            ),
            recommendations=_single_procedure_recommendation("rectosigmoidoscopy_argon"),
        )
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        assert [item["procedure_type"] for item in _recommendations(case)] == ["rectosigmoidoscopy_argon"]
        codes = [signal["code"] for signal in case.priority_signals]
        assert codes == []

    def test_variation_plus_colonoscopy_goes_to_nir_review_without_calling_llm2(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir5_mixed")
        case, client = _run(
            user,
            procedure_types=("rectosigmoidoscopy_dilation",),
            extracted_text=f"{DILATION_TEXT} Solicito colonoscopia diagnostica.",
            llm1=_llm1_json(
                procedures=[_recto_procedure("rectosigmoidoscopy_dilation", excerpt=DILATION_TEXT)],
                one_liner="Retossigmoidoscopia + Dilatação indicada.",
            ),
            recommendations=_single_procedure_recommendation("rectosigmoidoscopy_dilation"),
        )
        assert len(client.calls) == 1
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        payload = _suggested_action(case)
        assert payload["decision"] == "manual_review_required"
        assert payload["reason_code"] == "unsupported_procedure_combination"
        assert set(payload["detected_procedures"]) == {"rectosigmoidoscopy_dilation", "colonoscopy"}


# ── R4: profile de Colonoscopia reutilizado sob a identidade exata ─────────


class TestColonoscopyProfileReuse:
    @pytest.mark.parametrize("procedure_type", RECTOSIGMOIDOSCOPY_TYPES)
    def test_pendency_requirements_and_texts_match_colonoscopy(self, procedure_type: str) -> None:
        baseline = _policy_decision("colonoscopy", hb_g_dl=6.0)
        actual = _policy_decision(procedure_type, hb_g_dl=6.0)
        identity_label = PROCEDURE_LABELS[procedure_type]
        baseline_failures = cast("list[dict[str, Any]]", baseline["failed_requirements"])
        actual_failures = cast("list[dict[str, Any]]", actual["failed_requirements"])

        assert baseline["decision"] == "deny"
        assert actual["decision"] == baseline["decision"]
        assert actual["reason_code"] == baseline["reason_code"]
        assert [item["category"] for item in actual_failures] == [item["category"] for item in baseline_failures]
        assert [item["code"] for item in actual_failures] == [item["code"] for item in baseline_failures]
        assert actual["reason_text"] == str(baseline["reason_text"]).replace("Colonoscopia", identity_label)
        assert "Colonoscopia" not in str(actual["reason_text"])
        assert identity_label in str(actual["reason_text"])

    @pytest.mark.parametrize("procedure_type", RECTOSIGMOIDOSCOPY_TYPES)
    def test_satisfied_criteria_text_uses_the_identity_label(self, procedure_type: str) -> None:
        baseline = _policy_decision("colonoscopy", hb_g_dl=13.0)
        actual = _policy_decision(procedure_type, hb_g_dl=13.0)
        identity_label = PROCEDURE_LABELS[procedure_type]

        assert baseline["decision"] == "accept"
        assert actual["decision"] == baseline["decision"]
        assert actual["reason_code"] == "criteria_met"
        assert actual["reason_text"] == str(baseline["reason_text"]).replace("Colonoscopia", identity_label)
        assert "Colonoscopia" not in str(actual["reason_text"])

    @pytest.mark.parametrize("procedure_type", RECTOSIGMOIDOSCOPY_TYPES)
    def test_eda_only_conditional_outcome_is_not_inherited(self, procedure_type: str) -> None:
        """A exceção de corpo estranho é exclusiva de EDA — igual à Colonoscopia."""
        eda = evaluate_procedure_policy(structured_data=_foreign_body_projection(), procedure_type="eda")
        baseline = evaluate_procedure_policy(structured_data=_foreign_body_projection(), procedure_type="colonoscopy")
        actual = evaluate_procedure_policy(structured_data=_foreign_body_projection(), procedure_type=procedure_type)
        identity_label = PROCEDURE_LABELS[procedure_type]

        assert eda["reason_code"] == "foreign_body_exception"
        assert baseline["reason_code"] != "foreign_body_exception"
        assert actual["reason_code"] == baseline["reason_code"]
        assert actual["decision"] == baseline["decision"]
        assert actual["reason_text"] == str(baseline["reason_text"]).replace("Colonoscopia", identity_label)

    def test_orchestrated_clinical_outcome_matches_colonoscopy(self, django_user_model) -> None:
        """Mesma entrada clínica: mesmos requisitos, thresholds e sinais (R4/D4)."""
        user = django_user_model.objects.create_user(username="nir5_equal")
        colon_case, _ = _run(
            user,
            procedure_types=("colonoscopy",),
            extracted_text=REQUEST_TEXTS["colonoscopy"],
            llm1=_llm1_json(procedures=[_recto_procedure("colonoscopy")], one_liner="Colonoscopia indicada."),
            recommendations=_single_procedure_recommendation("colonoscopy"),
        )
        baseline = _preop_decision(colon_case)
        baseline_signals = [signal["code"] for signal in colon_case.priority_signals]
        # A menção a corpo estranho é clínica comum: o profile de Colonoscopia
        # não persiste o sinal EDA-only (R4/D4).
        assert baseline_signals == []

        for procedure_type in RECTOSIGMOIDOSCOPY_TYPES:
            case, _ = _run(
                user,
                procedure_types=(procedure_type,),
                extracted_text=REQUEST_TEXTS[procedure_type],
                llm1=_llm1_json(
                    procedures=[_recto_procedure(procedure_type)],
                    one_liner="Procedimento indicado.",
                ),
                recommendations=_single_procedure_recommendation(procedure_type),
            )
            decision = _preop_decision(case)
            identity_label = PROCEDURE_LABELS[procedure_type]

            assert decision["decision"] == baseline["decision"], procedure_type
            assert decision["reason_code"] == baseline["reason_code"], procedure_type
            assert decision["reason_text"] == str(baseline["reason_text"]).replace("Colonoscopia", identity_label)
            assert [signal["code"] for signal in case.priority_signals] == baseline_signals, procedure_type
            assert _recommendations(case)[0]["procedure_type"] == procedure_type
