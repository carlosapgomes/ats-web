"""Slice 004 — painel consultivo de revisão infecciosa no relatório médico (R4/R5).

Cobre:

- R4: o painel mostra TODOS os grupos de categoria encontrados, inclusive
  normal/negativo e valores ``unclassified``, com o trecho ancorado;
- R5: só preocupação explicitamente documentada gera destaque; normais,
  negativos e valores sem interpretação permanecem visíveis sem alerta;
- D8: o painel comunica apoio consultivo (não diagnóstico nem critério
  automático) e não altera blocos, pendências ou a sugestão automática;
- o painel existe SOMENTE para ``eda_gastrostomy`` — nunca por herança de
  família/sinal legado — e artefato ausente/vazio é seção neutra, nunca
  pendência.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from apps.cases.models import Case, CaseProcedure, CaseStatus
from apps.cases.procedures import set_declared_procedures
from apps.doctor.presenters import DoctorReportPresenter
from apps.doctor.reporting import prepare_doctor_case_report
from apps.pipeline.infection_review import INFECTION_EVIDENCE_ARTIFACT_KEY

pytestmark = pytest.mark.django_db

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DECISION_TEMPLATE = PROJECT_ROOT / "templates" / "doctor" / "decision.html"
APP_CSS = PROJECT_ROOT / "static" / "css" / "app.css"

ALERT_COPY = (
    "Possível infecção sistêmica — revisar evidências; informação consultiva, não altera a sugestão automática."
)
NEUTRAL_COPY = (
    "Nenhum sinal de preocupação explicitamente documentado; informação consultiva, não altera a sugestão automática."
)

ALL_CATEGORIES: tuple[str, ...] = (
    "leukocytes",
    "crp",
    "procalcitonin",
    "lactate",
    "culture",
    "temperature_or_fever",
    "infectious_disease",
    "antibiotic",
)


# ── Fixtures 4.0 ───────────────────────────────────────────────────────────


def _common_preop() -> dict[str, Any]:
    return {
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
        "abdominal_imaging": [],
        "evidence_spans": [],
    }


def _structured_data(*, procedure_types: tuple[str, ...]) -> dict[str, Any]:
    return {
        "schema_version": "4.0",
        "language": "pt-BR",
        "agency_record_number": "12345",
        "patient": {"name": "Paciente", "age": 35, "sex": "M", "document_id": None},
        "common_preop": _common_preop(),
        "requested_procedures": [
            {
                "procedure_type": procedure_type,
                "name": procedure_type,
                "urgency": "eletivo",
                "indication_category": "dyspepsia",
                "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito EDA com GTT"}],
            }
            for procedure_type in procedure_types
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
        "summary": {"one_liner": "EDA + GTT indicada.", "bullet_points": ["a", "b", "c"]},
        "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
        "transfusion": {"had_transfusion": "no"},
        "tracked_exams": [],
    }


def _item(
    *,
    category: str,
    assessment: str,
    temporal_status: str = "current",
    value_text: str = "",
    evidence_excerpt: str,
    concerning: bool,
) -> dict[str, Any]:
    return {
        "assessment": assessment,
        "temporal_status": temporal_status,
        "value_text": value_text,
        "evidence_excerpt": evidence_excerpt,
        "concerning": concerning,
    }


def _review(*, concerning: bool, groups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"concerning": concerning, "groups": groups or []}


def _normal_group() -> dict[str, Any]:
    return {
        "category": "leukocytes",
        "items": [
            _item(
                category="leukocytes",
                assessment="normal_explicit",
                value_text="Leucócitos 8.200/mm3",
                evidence_excerpt="Leucócitos 8.200/mm3 (normais)",
                concerning=False,
            )
        ],
    }


def _culture_group() -> dict[str, Any]:
    return {
        "category": "culture",
        "items": [
            _item(
                category="culture",
                assessment="negative_explicit",
                evidence_excerpt="Hemoculturas negativas",
                concerning=False,
            )
        ],
    }


def _panel_case(
    user,
    *,
    procedure_types: tuple[str, ...] = ("eda_gastrostomy",),
    review: dict[str, Any] | None = None,
) -> Case:
    suggested: dict[str, Any] = {
        "schema_version": "4.0",
        "procedure_recommendations": [
            {
                "procedure_type": procedure_type,
                "suggestion": "accept",
                "support_recommendation": "none",
                "preop_decision": {"decision": "accept", "reason_code": "criteria_met", "failed_requirements": []},
            }
            for procedure_type in procedure_types
        ],
        "global_support_recommendation": "none",
    }
    if review is not None:
        suggested[INFECTION_EVIDENCE_ARTIFACT_KEY] = review
    case = Case.objects.create(
        created_by=user,
        agency_record_number="12345",
        extracted_text="Solicito EDA com GTT. Leucócitos 8.200/mm3 (normais). Hemoculturas negativas.",
        structured_data=_structured_data(procedure_types=procedure_types),
        suggested_action=suggested,
    )
    set_declared_procedures(case=case, procedure_types=list(procedure_types), actor=user)
    return Case.objects.get(case_id=case.case_id)


def _report(case: Case) -> dict[str, Any]:
    return prepare_doctor_case_report(case).presenter.build_report()


def _group_labels(review: dict[str, Any]) -> list[str]:
    return [str(group["category_label"]) for group in review["groups"]]


# ── R4: todos os grupos encontrados aparecem ───────────────────────────────


class TestPanelShowsEveryFoundGroup:
    def test_all_eight_categories_are_rendered_in_canonical_order(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-all")
        groups = [
            {
                "category": category,
                "items": [
                    _item(
                        category=category,
                        assessment="unclassified",
                        temporal_status="unknown",
                        evidence_excerpt="Resultado documentado",
                        concerning=False,
                    )
                ],
            }
            for category in ALL_CATEGORIES
        ]
        case = _panel_case(user, review=_review(concerning=False, groups=groups))

        review = _report(case)["infection_review"]

        assert review is not None
        assert review["groups"] and len(review["groups"]) == len(ALL_CATEGORIES)
        assert _group_labels(review) == [
            "Leucócitos",
            "PCR (proteína C reativa)",
            "Procalcitonina",
            "Lactato",
            "Culturas",
            "Temperatura/febre",
            "Infectologia",
            "Antibióticos",
        ]

    def test_normal_and_negative_results_stay_visible_without_alert(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-normal")
        case = _panel_case(
            user,
            review=_review(concerning=False, groups=[_normal_group(), _culture_group()]),
        )

        review = _report(case)["infection_review"]

        assert review["concerning"] is False
        assert review["alert_message"] == NEUTRAL_COPY
        items = [item for group in review["groups"] for item in group["items"]]
        assert [item["assessment_label"] for item in items] == [
            "normal (documentado)",
            "negativo (documentado)",
        ]
        assert items[0]["value_text"] == "Leucócitos 8.200/mm3"
        assert items[0]["evidence_excerpt"] == "Leucócitos 8.200/mm3 (normais)"
        assert [item["concerning"] for item in items] == [False, False]

    def test_unclassified_value_keeps_the_documented_text(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-unclassified")
        case = _panel_case(
            user,
            review=_review(
                concerning=False,
                groups=[
                    {
                        "category": "crp",
                        "items": [
                            _item(
                                category="crp",
                                assessment="unclassified",
                                value_text="PCR 12 mg/L",
                                evidence_excerpt="PCR 12 mg/L",
                                concerning=False,
                            )
                        ],
                    }
                ],
            ),
        )

        item = _report(case)["infection_review"]["groups"][0]["items"][0]

        assert item["assessment_label"] == "sem interpretação documentada"
        assert item["value_text"] == "PCR 12 mg/L"
        assert item["evidence_excerpt"] == "PCR 12 mg/L"


# ── R5/D8: alerta só com preocupação explícita ─────────────────────────────


class TestPanelAlert:
    def test_concerning_evidence_shows_the_alert_copy_and_the_evidence(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-alert")
        case = _panel_case(
            user,
            review=_review(
                concerning=True,
                groups=[
                    _normal_group(),
                    {
                        "category": "temperature_or_fever",
                        "items": [
                            _item(
                                category="temperature_or_fever",
                                assessment="febrile_explicit",
                                value_text="38,5 C",
                                evidence_excerpt="Febre 38,5 C",
                                concerning=True,
                            )
                        ],
                    },
                ],
            ),
        )

        review = _report(case)["infection_review"]

        assert review["concerning"] is True
        assert review["alert_message"] == ALERT_COPY
        flagged = [item for group in review["groups"] for item in group["items"] if item["concerning"]]
        assert len(flagged) == 1
        assert flagged[0]["evidence_excerpt"] == "Febre 38,5 C"
        assert flagged[0]["assessment_label"] == "febre documentada"

    def test_only_normal_results_do_not_trigger_the_alert(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-quiet")
        case = _panel_case(user, review=_review(concerning=False, groups=[_normal_group(), _culture_group()]))

        review = _report(case)["infection_review"]

        assert review["concerning"] is False
        assert review["alert_message"] == NEUTRAL_COPY

    def test_neutral_copy_still_states_the_consultive_nature(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-consultive")
        case = _panel_case(user, review=_review(concerning=False, groups=[_normal_group()]))

        assert (
            "informação consultiva, não altera a sugestão automática"
            in (_report(case)["infection_review"]["alert_message"])
        )


# ── D8/R6: consultivo, neutro e sem herança de identidade ─────────────────


class TestNeutralSectionOnEmptyExtraction:
    """D7/D8: ausência/falha de extração produz seção vazia/neutra, nunca pendência.

    A seção neutra é a mesma da identidade exata ``eda_gastrostomy``, com o
    título e a copy consultiva, sem grupos de evidência, sem alerta, sem
    pendência e sem efeito de bloqueio sobre a decisão médica.
    """

    def test_empty_extraction_renders_the_neutral_section_without_alert_or_pendency(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-neutral")
        case = _panel_case(user, review=None)

        report = _report(case)
        review = report["infection_review"]

        assert review is not None
        assert review["concerning"] is False
        assert review["alert_message"] == NEUTRAL_COPY
        assert review["groups"] == []
        assert "Possível infecção" not in " ".join(report["blocks"]["pendencias_criticas"])

    def test_neutral_section_does_not_change_blocks_or_pendencies(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-neutral-blocks")
        neutral = _report(_panel_case(user, review=None))
        presented = _report(_panel_case(user, review=_review(concerning=False, groups=[_normal_group()])))

        assert neutral["blocks"] == presented["blocks"]
        assert neutral["notices"] == presented["notices"]

    def test_other_identities_still_render_no_neutral_section(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-neutral-inherit")
        for procedure_types in (("eda",), ("eda_capsule",), ("eda_dilation",)):
            case = _panel_case(user, procedure_types=procedure_types, review=None)

            assert _report(case)["infection_review"] is None, procedure_types


class TestPanelIsConsultiveAndScoped:
    def test_panel_does_not_change_blocks_or_pendencies(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-blocks")
        without = _panel_case(user, review=None)
        concerning = _panel_case(
            user,
            review=_review(
                concerning=True,
                groups=[
                    {
                        "category": "temperature_or_fever",
                        "items": [
                            _item(
                                category="temperature_or_fever",
                                assessment="febrile_explicit",
                                evidence_excerpt="Febre 38,5 C",
                                concerning=True,
                            )
                        ],
                    }
                ],
            ),
        )

        report_without = _report(without)
        report_with = _report(concerning)

        assert report_with["blocks"] == report_without["blocks"]
        assert report_with["notices"] == report_without["notices"]
        assert report_with["procedure_sections"] == report_without["procedure_sections"]
        assert "Possível infecção" not in " ".join(report_with["blocks"]["pendencias_criticas"])

    def test_panel_is_never_inherited_by_other_identities(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-gtt-inherit")
        review = _review(
            concerning=True,
            groups=[
                {
                    "category": "temperature_or_fever",
                    "items": [
                        _item(
                            category="temperature_or_fever",
                            assessment="febrile_explicit",
                            evidence_excerpt="Febre 38,5 C",
                            concerning=True,
                        )
                    ],
                }
            ],
        )
        for procedure_types in (("eda",), ("eda_capsule",), ("eda_dilation",)):
            case = _panel_case(user, procedure_types=procedure_types, review=review)

            assert _report(case)["infection_review"] is None, procedure_types

    def test_presenter_without_the_artifact_renders_the_neutral_section(self) -> None:
        report = DoctorReportPresenter(
            structured_data=_structured_data(procedure_types=("eda_gastrostomy",)),
            suggested_action={
                "schema_version": "4.0",
                "procedure_recommendations": [{"procedure_type": "eda_gastrostomy", "suggestion": "accept"}],
            },
        ).build_report()

        review = report["infection_review"]
        assert review is not None
        assert review["concerning"] is False
        assert review["groups"] == []
        assert review["alert_message"] == NEUTRAL_COPY


# ── R4/R5: página de decisão médica renderiza o painel ────────────────────


@pytest.mark.django_db
class TestGastrostomyDecisionPage:
    def _login_as(self, client, role_name: str):
        from django.contrib.auth import get_user_model

        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=role_name)
        user = get_user_model().objects.create_user(username=f"{role_name}@gtt.test", password="testpass123")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _claim_lock(self, case_id, doctor) -> str:
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True
        return str(result.token)

    def _case_at_wait_doctor(self, user, *, review: dict[str, Any] | None) -> Case:
        case = _panel_case(user, review=review)
        CaseProcedure.objects.filter(case=case).update(detection_status="detected")
        case.start_processing(user=user)
        case.save()
        case.start_extraction(user=user)
        case.save()
        case.extraction_complete(success=True, user=user)
        case.save()
        case.llm1_complete(success=True, user=user)
        case.save()
        case.llm2_complete(success=True, user=user)
        case.save()
        case.ready_for_doctor()
        case.save()
        return Case.objects.get(case_id=case.case_id)

    def test_decision_page_shows_the_consultive_panel_with_the_alert(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._case_at_wait_doctor(
            nir,
            review=_review(
                concerning=True,
                groups=[
                    _normal_group(),
                    {
                        "category": "temperature_or_fever",
                        "items": [
                            _item(
                                category="temperature_or_fever",
                                assessment="febrile_explicit",
                                value_text="38,5 C",
                                evidence_excerpt="Febre 38,5 C",
                                concerning=True,
                            )
                        ],
                    },
                ],
            ),
        )
        doctor = self._login_as(client, "doctor")
        self._claim_lock(case.case_id, doctor)

        response = client.get(f"/doctor/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Revisão infecciosa consultiva" in content
        assert "Leucócitos 8.200/mm3 (normais)" in content
        assert "Febre 38,5 C" in content
        assert ALERT_COPY in content

    def test_decision_page_without_evidence_shows_the_neutral_section(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._case_at_wait_doctor(nir, review=None)
        doctor = self._login_as(client, "doctor")
        self._claim_lock(case.case_id, doctor)

        response = client.get(f"/doctor/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Revisão infecciosa consultiva" in content
        assert NEUTRAL_COPY in content
        assert ALERT_COPY not in content


# ── Template, copy e vocabulário (AGENTS.md §8) ────────────────────────────


class TestPanelTemplateAndVocabulary:
    def test_decision_template_renders_the_review_section(self) -> None:
        template = DECISION_TEMPLATE.read_text(encoding="utf-8")

        assert "report.infection_review" in template
        assert "infection_review.groups" in template
        assert "infection_review.alert_message" in template

    def test_panel_reuses_existing_classes_without_new_css_vocabulary(self) -> None:
        """Fronteira AGENTS §8: nenhuma classe CSS nova precisou entrar em app.css."""
        template = DECISION_TEMPLATE.read_text(encoding="utf-8")
        block = template[template.index("report.infection_review") :]
        block = block[: block.index("{% endif %}")]

        for css_class in re.findall(r'class="([^"]*)"', block):
            assert "infection" not in css_class, css_class

        assert "infection" not in APP_CSS.read_text(encoding="utf-8")
