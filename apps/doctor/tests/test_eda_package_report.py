"""Slice 003 — pacotes EDA no relatório médico (R6).

Cobre:

- uma seção por pacote detectado (uma identidade → uma seção; EDA +
  Colonoscopia continua com duas);
- o local da dilatação é traduzido e exibido SOMENTE em EDA + Dilatação, a
  partir da projeção ancorada pelo pipeline, sem criar pendência;
- a supressão da base EDA por uma variação atual usa copy própria (não a copy
  da precedência especializada);
- o template e o CSS publicam o badge das dez identidades com agrupamento por
  família em ``app.css``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from django.utils import timezone

from apps.cases.models import Case, CaseProcedure
from apps.cases.procedures import set_declared_procedures
from apps.doctor.reporting import prepare_doctor_case_report

pytestmark = pytest.mark.django_db

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DECISION_TEMPLATE = PROJECT_ROOT / "templates" / "doctor" / "decision.html"
APP_CSS = PROJECT_ROOT / "static" / "css" / "app.css"

EDA_FAMILY_CODES = ("eda", "eda_gastrostomy", "eda_capsule", "eda_dilation")
COLON_FAMILY_CODES = (
    "colonoscopy",
    "rectosigmoidoscopy",
    "rectosigmoidoscopy_dilation",
    "rectosigmoidoscopy_argon",
)
OWN_BLOCK_CODES = ("eda_colonoscopy", "echoendoscopy", "cpre")


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


def _procedure_item(procedure_type: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": procedure_type,
        "name": procedure_type,
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito o procedimento"}],
    }
    item.update(extra or {})
    return item


def _structured_data(
    *, procedure_types: tuple[str, ...], extra_by_type: dict[str, Any] | None = None
) -> dict[str, Any]:
    extra_by_type = extra_by_type or {}
    return {
        "schema_version": "4.0",
        "language": "pt-BR",
        "agency_record_number": "12345",
        "patient": {"name": "Paciente", "age": 35, "sex": "M", "document_id": None},
        "common_preop": _common_preop(),
        "requested_procedures": [
            _procedure_item(procedure_type, extra_by_type.get(procedure_type)) for procedure_type in procedure_types
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
        "summary": {"one_liner": "Procedimento indicado.", "bullet_points": ["a", "b", "c"]},
        "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
        "transfusion": {"had_transfusion": "no"},
        "tracked_exams": [],
    }


def _recommendation(procedure_type: str, *, dilation_detail: dict[str, Any] | None = None) -> dict[str, Any]:
    recommendation: dict[str, Any] = {
        "procedure_type": procedure_type,
        "suggestion": "accept",
        "support_recommendation": "none",
        "preop_decision": {"decision": "accept", "reason_code": "criteria_met", "failed_requirements": []},
    }
    if dilation_detail is not None:
        recommendation["dilation_detail"] = dilation_detail
    return recommendation


def _package_case(
    user,
    *,
    procedure_types: tuple[str, ...],
    extra_by_type: dict[str, Any] | None = None,
    dilation_detail: dict[str, Any] | None = None,
    precedence: dict[str, Any] | None = None,
) -> Case:
    suggested: dict[str, Any] = {
        "schema_version": "4.0",
        "procedure_recommendations": [
            _recommendation(
                procedure_type,
                dilation_detail=dilation_detail if procedure_type == "eda_dilation" else None,
            )
            for procedure_type in procedure_types
        ],
        "global_support_recommendation": "none",
    }
    if precedence is not None:
        suggested["procedure_precedence"] = precedence
    case = Case.objects.create(
        created_by=user,
        agency_record_number="12345",
        extracted_text="Solicito EDA com dilatação de piloro por estenose.",
        structured_data=_structured_data(procedure_types=procedure_types, extra_by_type=extra_by_type),
        suggested_action=suggested,
    )
    set_declared_procedures(case=case, procedure_types=list(procedure_types), actor=user)
    return Case.objects.get(case_id=case.case_id)


def _report(case: Case) -> dict[str, Any]:
    return prepare_doctor_case_report(case).presenter.build_report()


# ── R6: uma seção por pacote ───────────────────────────────────────────────


class TestPackageProcedureSections:
    def test_capsule_is_one_section_with_the_catalog_label(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-capsule")
        case = _package_case(user, procedure_types=("eda_capsule",))

        report = _report(case)

        assert report["context"]["procedure"] == "procedimento solicitado: EDA + Cápsula"
        assert report["procedure_sections"] == [{"procedure_type": "eda_capsule", "label": "EDA + Cápsula"}]

    def test_dilation_section_carries_only_the_translated_site_label(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-dilation")
        case = _package_case(
            user,
            procedure_types=("eda_dilation",),
            dilation_detail={"anatomical_site": "pylorus", "reason_code": ""},
        )

        report = _report(case)

        assert report["context"]["procedure"] == "procedimento solicitado: EDA + Dilatação"
        assert report["procedure_sections"] == [
            {
                "procedure_type": "eda_dilation",
                "label": "EDA + Dilatação",
                "dilation_site_label": "Piloro",
            }
        ]

    def test_unknown_site_is_neutral_and_creates_no_pendency(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-unknown-site")
        case = _package_case(
            user,
            procedure_types=("eda_dilation",),
            dilation_detail={"anatomical_site": "unknown", "reason_code": "dilation_excerpt_not_anchored"},
        )
        without_detail = _package_case(user, procedure_types=("eda_dilation",))

        report = _report(case)

        assert report["procedure_sections"][0]["dilation_site_label"] == "não informado no laudo"
        # R5/R6: o local informativo nunca cria pendência nem muda o relatório.
        assert report["blocks"] == _report(without_detail)["blocks"]

    def test_known_site_does_not_change_the_report_blocks(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-known-site")
        case = _package_case(
            user,
            procedure_types=("eda_dilation",),
            dilation_detail={"anatomical_site": "pylorus", "reason_code": ""},
        )
        without_detail = _package_case(user, procedure_types=("eda_dilation",))

        assert _report(case)["blocks"] == _report(without_detail)["blocks"]

    def test_paired_case_keeps_two_sections_without_dilation_detail(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-paired")
        case = _package_case(user, procedure_types=("eda", "colonoscopy"))

        report = _report(case)

        assert report["context"]["procedure"] == "procedimento solicitado: EDA + Colonoscopia"
        assert [section["label"] for section in report["procedure_sections"]] == ["EDA", "Colonoscopia"]
        assert all("dilation_site_label" not in section for section in report["procedure_sections"])

    def test_capsule_section_never_shows_a_dilation_label(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-capsule-site")
        case = _package_case(
            user,
            procedure_types=("eda_capsule",),
            extra_by_type={"eda_capsule": {"dilation_detail": {"anatomical_site": "pylorus", "evidence_excerpt": "x"}}},
        )

        report = _report(case)

        assert "dilation_site_label" not in report["procedure_sections"][0]


# ── R4: histórico pelo código exato do pacote ──────────────────────────────


class TestPackageHistoryUsesTheExactCode:
    def _prior_case(self, user, *, rows: list[tuple[str, str]]) -> Case:
        prior = Case.objects.create(
            created_by=user,
            agency_record_number="12345",
            structured_data=_structured_data(procedure_types=("eda",)),
            doctor_decision="deny",
            doctor_reason="Negativa registrada na row.",
            doctor_decided_at=timezone.now(),
        )
        for procedure_type, disposition in rows:
            CaseProcedure.objects.create(
                case=prior,
                procedure_type=procedure_type,
                declared_by_nir=True,
                doctor_disposition=disposition,
            )
        return prior

    def test_prior_eda_denial_does_not_feed_the_package_section(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-hist-eda")
        self._prior_case(user, rows=[("eda", "denied")])
        case = _package_case(user, procedure_types=("eda_dilation",))

        assert _report(case)["prior_sections"] == []

    def test_prior_package_denial_appears_in_the_package_section(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-hist-package")
        self._prior_case(user, rows=[("eda_dilation", "denied")])
        case = _package_case(user, procedure_types=("eda_dilation",))

        sections = _report(case)["prior_sections"]
        assert [section["procedure_label"] for section in sections] == ["EDA + Dilatação"]
        assert sections[0]["decision_display"] == "Regulação Negada"


# ── R6: copy da supressão por variação ─────────────────────────────────────


class TestVariationPrecedenceNotice:
    def test_variation_suppression_uses_its_own_copy(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-precedence")
        case = _package_case(
            user,
            procedure_types=("eda_capsule",),
            precedence={"rule": "variation_over_base", "selected": "eda_capsule", "suppressed": ["eda"]},
        )

        notices = " ".join(_report(case)["notices"])

        assert "EDA + Cápsula" in notices
        assert "especializado" not in notices

    def test_specialized_suppression_keeps_the_existing_copy(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-precedence-echo")
        case = _package_case(
            user,
            procedure_types=("echoendoscopy",),
            precedence={"rule": "specialized_over_conventional", "selected": "echoendoscopy", "suppressed": ["eda"]},
        )

        notices = " ".join(_report(case)["notices"])

        assert "precedência de procedimento especializado" in notices


# ── R6: página de decisão médica renderiza as seções do pacote ─────────────


@pytest.mark.django_db
class TestPackageDecisionPage:
    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username=f"{role_name}@package.test", password="testpass123")
        user.roles.add(self._role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _claim_lock(self, case_id, doctor) -> str:
        from apps.cases.models import CaseStatus
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

    def _case_at_wait_doctor(
        self, user, *, procedure_types: tuple[str, ...], dilation_detail: dict[str, Any] | None
    ) -> Case:
        case = _package_case(
            user,
            procedure_types=procedure_types,
            dilation_detail=dilation_detail,
        )
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

    def test_decision_page_shows_the_dilation_section(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._case_at_wait_doctor(
            nir,
            procedure_types=("eda_dilation",),
            dilation_detail={"anatomical_site": "pylorus", "reason_code": ""},
        )
        doctor = self._login_as(client, "doctor")
        self._claim_lock(case.case_id, doctor)

        response = client.get(f"/doctor/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Procedimentos analisados" in content
        assert "exam-type-eda_dilation" in content
        assert "EDA + Dilatação" in content
        assert "Local da dilatação: Piloro" in content

    def test_decision_page_shows_the_capsule_section_without_a_site(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._case_at_wait_doctor(nir, procedure_types=("eda_capsule",), dilation_detail=None)
        doctor = self._login_as(client, "doctor")
        self._claim_lock(case.case_id, doctor)

        response = client.get(f"/doctor/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "exam-type-eda_capsule" in content
        assert "Local da dilatação" not in content


# ── R6: template e vocabulário CSS das dez identidades ────────────────────


class TestPackageTemplateAndCss:
    def test_decision_template_renders_the_procedure_sections(self) -> None:
        template = DECISION_TEMPLATE.read_text(encoding="utf-8")
        assert "report.procedure_sections" in template
        assert "exam-type-{{ section.procedure_type }}" in template
        assert "section.dilation_site_label" in template

    def _selector_groups(self, css: str) -> list[list[str]]:
        without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        return [
            [selector.strip() for selector in match.group(1).split(",")]
            for match in re.finditer(r"(?m)^([^{}]+)\{", without_comments)
        ]

    def _group_for(self, css: str, selector: str) -> list[str]:
        for group in self._selector_groups(css):
            if selector in group:
                return group
        raise AssertionError(f"Bloco CSS de {selector} ausente em app.css")

    def test_eda_family_shares_one_visual_block(self) -> None:
        css = APP_CSS.read_text(encoding="utf-8")
        group = self._group_for(css, ".exam-type-eda")
        for code in EDA_FAMILY_CODES:
            assert f".exam-type-{code}" in group, code

    def test_colonoscopy_family_shares_one_visual_block(self) -> None:
        css = APP_CSS.read_text(encoding="utf-8")
        group = self._group_for(css, ".exam-type-colonoscopy")
        for code in COLON_FAMILY_CODES:
            assert f".exam-type-{code}" in group, code

    def test_combined_and_specialized_keep_their_own_blocks(self) -> None:
        css = APP_CSS.read_text(encoding="utf-8")
        for code in OWN_BLOCK_CODES:
            group = self._group_for(css, f".exam-type-{code}")
            assert group == [f".exam-type-{code}"], code
