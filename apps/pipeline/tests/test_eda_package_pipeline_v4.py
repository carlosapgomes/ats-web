"""Slice 003 — EDA + Cápsula e EDA + Dilatação do intake ao médico (R2–R5).

Cobre:

- R2: solicitação ATUAL local de EDA + cápsula/dilatação reconcilia SOMENTE o
  pacote; histórico, negação, procedimento realizado, termo solto e dilatação
  de colédoco não criam pacote;
- R3: duas variações atuais ou variação + Colonoscopia seguem fail-closed à
  revisão NIR sem descartar nenhum valor;
- R4: os pacotes usam o profile de EDA, mas recommendation/eventos mantêm o
  código exato e nenhum sinal legado equivalente é persistido (D13);
- R5: o local da dilatação é ancorado no relatório principal; local ausente ou
  inventado projeta ``unknown`` sem alterar policy/FSM.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, DetectionStatus
from apps.cases.procedures import set_declared_procedures
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
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

CAPSULE_TEXT = "Solicito EDA com cápsula endoscópica para investigação."
DILATION_ESOPHAGUS_TEXT = "Solicito EDA com dilatação esofágica por estenose."
DILATION_PYLORUS_TEXT = "Solicito EDA com dilatação de piloro por estenose."


# ── Fixtures v4 ────────────────────────────────────────────────────────────


def _capsule_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "eda_capsule",
        "name": "EDA + Cápsula",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "evidence_spans": [{"field_path": "requested_procedures.0", "excerpt": CAPSULE_TEXT}],
    }
    item.update(overrides)
    return item


def _dilation_procedure(
    *,
    site: str = "unknown",
    excerpt: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "eda_dilation",
        "name": "EDA + Dilatação",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "evidence_spans": [{"field_path": "requested_procedures.0", "excerpt": DILATION_ESOPHAGUS_TEXT}],
        "dilation_detail": {"anatomical_site": site, "evidence_excerpt": excerpt},
    }
    item.update(overrides)
    return item


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


def _dilation_detail(case: Case) -> dict[str, object]:
    return cast("dict[str, object]", _recommendations(case)[0]["dilation_detail"])


def _preop_decision(case: Case) -> dict[str, object]:
    return cast("dict[str, object]", _recommendations(case)[0]["preop_decision"])


# ── R2: detecção conservadora dos pacotes (contrato 4.0) ───────────────────


class TestPackageDetectionV4:
    def _detect(
        self, cleaned_text: str, structured_data: dict[str, object] | None = None
    ) -> dict[str, dict[str, bool]]:
        return detect_requested_procedures_v4(
            llm1_structured_data=structured_data or {},
            cleaned_text=cleaned_text,
        )

    def test_eda_with_capsule_is_a_current_package_request(self) -> None:
        detection = self._detect(CAPSULE_TEXT)
        assert detection["eda_capsule"] == {"strong": True, "any": True, "conflicting": False}
        # A base EDA continua detectada: o colapso é decisão da reconciliação.
        assert detection["eda"]["any"] is True

    def test_isolated_capsule_request_detects_the_package_without_base(self) -> None:
        detection = self._detect("Solicito cápsula endoscópica para investigação.")
        assert detection["eda_capsule"]["any"] is True
        assert detection["eda"]["any"] is False

    def test_eda_with_dilation_is_a_current_package_request(self) -> None:
        detection = self._detect(DILATION_ESOPHAGUS_TEXT)
        assert detection["eda_dilation"] == {"strong": True, "any": True, "conflicting": False}
        assert detection["eda"]["any"] is True

    def test_historical_capsule_does_not_create_a_package(self) -> None:
        detection = self._detect("Cápsula endoscópica realizada em 2023. Solicito EDA.")
        assert detection["eda_capsule"]["any"] is False

    def test_negated_capsule_does_not_create_a_package(self) -> None:
        detection = self._detect("Nao solicito capsula endoscopica neste momento. Solicito EDA.")
        assert detection["eda_capsule"]["any"] is False

    def test_historical_dilation_does_not_create_a_package(self) -> None:
        detection = self._detect("Esôfago: dilatação esofágica realizada em 2022. Solicito EDA.")
        assert detection["eda_dilation"]["any"] is False

    def test_negated_dilation_does_not_create_a_package(self) -> None:
        detection = self._detect("Sem indicação de dilatação esofágica. Solicito EDA.")
        assert detection["eda_dilation"]["any"] is False

    def test_dilation_without_local_eda_link_is_not_a_package(self) -> None:
        """Termo ambíguo: a ambiguidade nunca é resolvida por proximidade global."""
        detection = self._detect("Paciente encaminhado para dilatação esofágica por estenose.")
        assert detection["eda_dilation"]["any"] is False

    def test_choledochal_dilation_is_not_a_package(self) -> None:
        detection = self._detect("Ultrassonografia de abdome demonstrou dilatação de colédoco. Solicito EDA.")
        assert detection["eda_dilation"]["any"] is False

    def test_choledochal_dilation_is_not_a_package_even_linked_to_eda(self) -> None:
        """Achado anatômico (anatomia dilatada) nunca vira o pacote endoscópico."""
        detection = self._detect("Solicito EDA com dilatação de colédoco.")
        assert detection["eda_dilation"]["any"] is False

    def test_structured_item_alone_marks_the_package_as_candidate(self) -> None:
        structured: dict[str, object] = {"requested_procedures": [_capsule_procedure()]}
        detection = self._detect("Solicito EDA.", structured_data=structured)
        assert detection["eda_capsule"] == {"strong": True, "any": True, "conflicting": False}

    def test_negated_capsule_occurrence_overrides_the_structured_item(self) -> None:
        """P1 review: item estruturado não autoriza o pacote quando a ÚNICA
        ocorrência textual é negada — o caso falha fechado ao NIR."""
        structured: dict[str, object] = {"requested_procedures": [_capsule_procedure()]}
        detection = self._detect("Nao solicito capsula endoscopica neste momento.", structured_data=structured)
        assert detection["eda_capsule"] == {"strong": False, "any": False, "conflicting": True}

    def test_historical_capsule_occurrence_overrides_the_structured_item(self) -> None:
        structured: dict[str, object] = {"requested_procedures": [_capsule_procedure()]}
        detection = self._detect("Cápsula endoscópica realizada em 2023.", structured_data=structured)
        assert detection["eda_capsule"] == {"strong": False, "any": False, "conflicting": True}

    def test_loose_dilation_term_overrides_the_structured_item(self) -> None:
        """Termo solto (sem vínculo local com EDA) contradiz o item estruturado."""
        structured: dict[str, object] = {"requested_procedures": [_dilation_procedure()]}
        detection = self._detect(
            "Paciente encaminhado para dilatação esofágica por estenose.",
            structured_data=structured,
        )
        assert detection["eda_dilation"] == {"strong": False, "any": False, "conflicting": True}


# ── R2/R3: reconciliação — colapso da base e fail-closed ───────────────────


class TestPackageReconciliationV4:
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

    def test_current_capsule_collapses_the_detected_base_eda(self) -> None:
        result = self._reconcile(
            declared=("eda_capsule",),
            strong=("eda", "eda_capsule"),
            any_evidence=("eda", "eda_capsule"),
            cleaned_text=CAPSULE_TEXT,
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("eda_capsule",)
        assert result.variation_precedence_applied is True
        assert result.selected_variation_type == "eda_capsule"
        assert result.suppressed_base_types == ("eda",)

    def test_current_dilation_collapses_the_base_eda_detected_in_another_section(self) -> None:
        result = self._reconcile(
            declared=("eda_dilation",),
            strong=("eda", "eda_dilation"),
            any_evidence=("eda", "eda_dilation"),
            cleaned_text=f"Cabeçalho administrativo: EDA.\n{DILATION_PYLORUS_TEXT}",
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("eda_dilation",)
        assert result.variation_precedence_applied is True
        assert result.suppressed_base_types == ("eda",)

    def test_capsule_in_an_independent_section_suppresses_the_base_eda(self) -> None:
        result = self._reconcile(
            declared=("eda_capsule",),
            strong=("eda", "eda_capsule"),
            any_evidence=("eda", "eda_capsule"),
            cleaned_text="Cabeçalho administrativo: EDA.\nSolicito cápsula endoscópica.",
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("eda_capsule",)

    def test_structured_item_without_current_occurrence_does_not_suppress(self) -> None:
        result = self._reconcile(
            declared=("eda_dilation",),
            strong=("eda", "eda_dilation"),
            any_evidence=("eda", "eda_dilation"),
            cleaned_text="Solicito EDA. Dilatação esofágica realizada em 2022.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {"eda", "eda_dilation"}
        assert result.variation_precedence_applied is False

    def test_two_current_variations_fail_closed_without_discarding_values(self) -> None:
        result = self._reconcile(
            declared=("eda_capsule",),
            strong=("eda", "eda_capsule", "eda_dilation"),
            any_evidence=("eda", "eda_capsule", "eda_dilation"),
            cleaned_text="Solicito EDA com cápsula endoscópica e dilatação de piloro.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {"eda", "eda_capsule", "eda_dilation"}
        assert result.variation_precedence_applied is False

    def test_package_plus_colonoscopy_fails_closed(self) -> None:
        result = self._reconcile(
            declared=("eda_capsule",),
            strong=("eda", "eda_capsule", "colonoscopy"),
            any_evidence=("eda", "eda_capsule", "colonoscopy"),
            cleaned_text=f"{CAPSULE_TEXT} Solicito colonoscopia diagnóstica.",
        )
        assert result.action == "nir_review"
        assert result.reason_code == "unsupported_procedure_combination"
        assert set(result.detected_procedure_types) == {"eda_capsule", "colonoscopy"}
        assert result.variation_precedence_applied is True
        assert result.suppressed_base_types == ("eda",)

    def test_serialized_metadata_mirrors_the_specialized_precedence_shape(self) -> None:
        result = self._reconcile(
            declared=("eda_capsule",),
            strong=("eda", "eda_capsule"),
            any_evidence=("eda", "eda_capsule"),
            cleaned_text=CAPSULE_TEXT,
        )
        assert serialize_procedure_precedence(result) == {
            "rule": "variation_over_base",
            "selected": "eda_capsule",
            "suppressed": ["eda"],
        }

    def test_specialized_precedence_keeps_its_own_rule_identifier(self) -> None:
        result = self._reconcile(
            declared=("echoendoscopy",),
            strong=("eda", "echoendoscopy"),
            any_evidence=("eda", "echoendoscopy"),
            cleaned_text="Solicito EDA com ecoendoscopia.",
        )
        assert serialize_procedure_precedence(result) == {
            "rule": "specialized_over_conventional",
            "selected": "echoendoscopy",
            "suppressed": ["eda"],
        }


# ── R2/R4: pacotes chegam ao médico ───────────────────────────────────────


class TestPackageReachesDoctor:
    def test_capsule_reaches_wait_doctor_with_the_exact_identity(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_capsule")
        case, client = _run(
            user,
            procedure_types=("eda_capsule",),
            extracted_text=CAPSULE_TEXT,
            llm1=_llm1_json(procedures=[_capsule_procedure()], one_liner="EDA + Cápsula indicada."),
            recommendations=_single_procedure_recommendation("eda_capsule"),
        )
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        recommendations = _recommendations(case)
        assert [item["procedure_type"] for item in recommendations] == ["eda_capsule"]
        rows = CaseProcedure.objects.filter(case=case)
        assert [(row.procedure_type, row.detection_status) for row in rows] == [
            ("eda_capsule", DetectionStatus.DETECTED)
        ]

    def test_dilation_reaches_wait_doctor_with_the_exact_identity(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_dilation")
        case, client = _run(
            user,
            procedure_types=("eda_dilation",),
            extracted_text=DILATION_ESOPHAGUS_TEXT,
            llm1=_llm1_json(
                procedures=[_dilation_procedure(site="esophagus", excerpt="dilatação esofágica")],
                one_liner="EDA + Dilatação indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda_dilation"),
        )
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        assert [item["procedure_type"] for item in _recommendations(case)] == ["eda_dilation"]
        event = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")
        assert event.payload["detected_procedures"] == ["eda_dilation"]
        assert event.payload["declared_procedures"] == ["eda_dilation"]

    def test_package_uses_the_eda_profile_but_persists_its_own_label(self, django_user_model) -> None:
        """R4/D4: profile da família para as regras; label canônica da identidade."""
        user = django_user_model.objects.create_user(username="nir3_profile")
        case, _ = _run(
            user,
            procedure_types=("eda_capsule",),
            extracted_text=CAPSULE_TEXT,
            llm1=_llm1_json(procedures=[_capsule_procedure()], one_liner="EDA + Cápsula indicada."),
            recommendations=_single_procedure_recommendation("eda_capsule"),
        )
        decision = _preop_decision(case)
        assert decision["decision"] == "accept"
        assert decision["reason_code"] == "criteria_met"
        assert "EDA + Cápsula" in str(decision["reason_text"])

    def test_dilation_does_not_persist_the_legacy_esophageal_dilation_signal(self, django_user_model) -> None:
        """R4/D13: a identidade atômica substitui o sinal legado equivalente."""
        user = django_user_model.objects.create_user(username="nir3_signal")
        case, _ = _run(
            user,
            procedure_types=("eda_dilation",),
            extracted_text=DILATION_ESOPHAGUS_TEXT,
            llm1=_llm1_json(
                procedures=[_dilation_procedure(site="esophagus", excerpt="dilatação esofágica")],
                one_liner="EDA + Dilatação indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda_dilation"),
        )
        codes = [signal["code"] for signal in case.priority_signals]
        assert "esophageal_dilation" not in codes

    def test_capsule_and_colonoscopy_go_to_nir_review_without_calling_llm2(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_mixed")
        case, client = _run(
            user,
            procedure_types=("eda_capsule",),
            extracted_text=f"{CAPSULE_TEXT} Solicito colonoscopia diagnóstica.",
            llm1=_llm1_json(procedures=[_capsule_procedure()], one_liner="EDA + Cápsula indicada."),
            recommendations=_single_procedure_recommendation("eda_capsule"),
        )
        assert len(client.calls) == 1
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        payload = _suggested_action(case)
        assert payload["decision"] == "manual_review_required"
        assert payload["reason_code"] == "unsupported_procedure_combination"
        assert set(payload["detected_procedures"]) == {"eda_capsule", "colonoscopy"}
        assert payload["procedure_precedence"] == {
            "rule": "variation_over_base",
            "selected": "eda_capsule",
            "suppressed": ["eda"],
        }

    def test_historical_dilation_with_declared_package_returns_to_nir(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_hist")
        case, client = _run(
            user,
            procedure_types=("eda_dilation",),
            extracted_text="Solicito EDA. Dilatação esofágica realizada em 2022.",
            llm1=_llm1_json(
                procedures=[_dilation_procedure(site="unknown", excerpt=None)],
                one_liner="EDA indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda_dilation"),
        )
        assert len(client.calls) == 1
        payload = _suggested_action(case)
        assert payload["decision"] == "manual_review_required"
        # Slice 004/R5: a ocorrência histórica contradiz o item estruturado. O
        # pacote não vira detecção (strong/any falsos), mas fica sinalizado como
        # conflito e entra no conjunto detectado → revisão NIR por conflito.
        assert payload["reason_code"] == "conflicting_procedure_evidence"
        assert set(payload["detected_procedures"]) == {"eda", "eda_dilation"}
        # Conjunto fora da matriz: a projeção é pulada e a row declarada fica no
        # estado pendente (nenhum NOT_DETECTED silencioso para o pacote).
        row = CaseProcedure.objects.get(case=case, procedure_type="eda_dilation")
        assert row.detection_status == DetectionStatus.PENDING


# ── P1 review fix: item estruturado não sobrepõe texto não-atual ──────────


class TestStructuredItemWithoutCurrentOccurrence:
    """Item estruturado não autoriza o pacote quando o texto o contradiz.

    Se a ÚNICA ocorrência do termo for histórica ou negada (ou apenas menção),
    o pacote não vira detecção (``strong``/``any`` falsos) e o caso falha fechado
    ao NIR — nunca prossegue só porque o item estruturado coincide com a
    declaração. Slice 004/R5: o item contraditado deixa de ser invisível — ele é
    sinalizado como conflito e INCLUÍDO no conjunto detectado
    (``conflicting_procedure_evidence``), não mais descartado em silêncio.
    """

    def test_negated_capsule_with_structured_item_fails_closed(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_negated_structured")
        case, client = _run(
            user,
            procedure_types=("eda_capsule",),
            extracted_text="Nao solicito capsula endoscopica neste momento.",
            llm1=_llm1_json(procedures=[_capsule_procedure()], one_liner="EDA + Cápsula indicada."),
            recommendations=_single_procedure_recommendation("eda_capsule"),
        )
        assert len(client.calls) == 1
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        payload = _suggested_action(case)
        assert payload["decision"] == "manual_review_required"
        assert payload["reason_code"] == "conflicting_procedure_evidence"
        assert payload["detected_procedures"] == ["eda_capsule"]
        row = CaseProcedure.objects.get(case=case, procedure_type="eda_capsule")
        assert row.detection_status == DetectionStatus.DETECTED

    def test_historical_capsule_with_structured_item_fails_closed(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_historical_structured")
        case, client = _run(
            user,
            procedure_types=("eda_capsule",),
            extracted_text="Cápsula endoscópica realizada em 2023.",
            llm1=_llm1_json(procedures=[_capsule_procedure()], one_liner="EDA + Cápsula indicada."),
            recommendations=_single_procedure_recommendation("eda_capsule"),
        )
        assert len(client.calls) == 1
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        payload = _suggested_action(case)
        assert payload["decision"] == "manual_review_required"
        assert payload["reason_code"] == "conflicting_procedure_evidence"
        assert payload["detected_procedures"] == ["eda_capsule"]
        row = CaseProcedure.objects.get(case=case, procedure_type="eda_capsule")
        assert row.detection_status == DetectionStatus.DETECTED


# ── R5: local da dilatação ancorado no relatório principal ────────────────


class TestDilationSiteAnchoring:
    def test_explicit_pylorus_is_projected_for_the_doctor(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_pylorus")
        case, _ = _run(
            user,
            procedure_types=("eda_dilation",),
            extracted_text=DILATION_PYLORUS_TEXT,
            llm1=_llm1_json(
                procedures=[_dilation_procedure(site="pylorus", excerpt="dilatação de piloro")],
                one_liner="EDA + Dilatação de piloro.",
            ),
            recommendations=_single_procedure_recommendation("eda_dilation"),
        )
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert _dilation_detail(case) == {"anatomical_site": "pylorus", "reason_code": ""}

    def test_missing_site_is_projected_as_unknown_without_pendency(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_nosite")
        case, _ = _run(
            user,
            procedure_types=("eda_dilation",),
            extracted_text=DILATION_ESOPHAGUS_TEXT,
            llm1=_llm1_json(
                procedures=[_dilation_procedure(site="unknown", excerpt=None)],
                one_liner="EDA + Dilatação indicada.",
            ),
            recommendations=_single_procedure_recommendation("eda_dilation"),
        )
        assert _dilation_detail(case) == {"anatomical_site": "unknown", "reason_code": "dilation_site_not_declared"}
        assert _preop_decision(case)["failed_requirements"] == []

    def test_invented_excerpt_is_downgraded_without_changing_policy(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_invented")
        case, _ = _run(
            user,
            procedure_types=("eda_dilation",),
            extracted_text=DILATION_ESOPHAGUS_TEXT,
            llm1=_llm1_json(
                procedures=[_dilation_procedure(site="pylorus", excerpt="dilatação de piloro")],
                one_liner="EDA + Dilatação de piloro.",
            ),
            recommendations=_single_procedure_recommendation("eda_dilation"),
        )
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert _dilation_detail(case) == {
            "anatomical_site": "unknown",
            "reason_code": "dilation_excerpt_not_anchored",
        }
        decision = _preop_decision(case)
        assert decision["decision"] == "accept"
        assert decision["failed_requirements"] == []

    def test_ambiguous_excerpt_is_downgraded(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_ambiguous")
        case, _ = _run(
            user,
            procedure_types=("eda_dilation",),
            extracted_text=("Solicito EDA com dilatação de piloro. Dilatação de piloro. Dilatação de piloro."),
            llm1=_llm1_json(
                procedures=[_dilation_procedure(site="pylorus", excerpt="dilatação de piloro")],
                one_liner="EDA + Dilatação de piloro.",
            ),
            recommendations=_single_procedure_recommendation("eda_dilation"),
        )
        assert _dilation_detail(case) == {
            "anatomical_site": "unknown",
            "reason_code": "dilation_excerpt_ambiguous",
        }

    def test_capsule_recommendation_has_no_dilation_detail(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3_nodetail")
        case, _ = _run(
            user,
            procedure_types=("eda_capsule",),
            extracted_text=CAPSULE_TEXT,
            llm1=_llm1_json(procedures=[_capsule_procedure()], one_liner="EDA + Cápsula indicada."),
            recommendations=_single_procedure_recommendation("eda_capsule"),
        )
        recommendations = _recommendations(case)
        assert "dilation_detail" not in recommendations[0]
