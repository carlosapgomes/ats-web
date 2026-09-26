"""Slice 005 — família Retossigmoidoscopia no relatório médico (R4/R5).

Cobre:

- uma única seção por identidade detectada, com a label canônica do catálogo;
- nenhum texto do relatório apresenta a identidade como "Colonoscopia" apesar
  do profile clínico reutilizado (D4);
- a supressão da base por uma variação atual usa a copy da regra de variação;
- o histórico anterior consulta o código exato da identidade;
- a página de decisão médica publica o badge e a seção da identidade.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.utils import timezone

from apps.cases.models import Case, CaseProcedure, ProcedureType
from apps.cases.procedures import PROCEDURE_LABELS, set_declared_procedures
from apps.doctor.reporting import prepare_doctor_case_report

pytestmark = pytest.mark.django_db

RECTOSIGMOIDOSCOPY_TYPES = (
    ProcedureType.RECTOSIGMOIDOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
)

REQUEST_TEXT_BY_TYPE: dict[str, str] = {
    ProcedureType.RECTOSIGMOIDOSCOPY: "Solicito Retossigmoidoscopia para rastreamento.",
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION: "Solicito Retossigmoidoscopia com dilatação de anastomose.",
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON: "Solicito Retossigmoidoscopia com plasma de argônio.",
}


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


def _procedure_item(procedure_type: str) -> dict[str, Any]:
    return {
        "procedure_type": procedure_type,
        "name": PROCEDURE_LABELS[procedure_type],
        "urgency": "eletivo",
        "indication_category": "screening",
        "evidence_spans": [{"field_path": "p.0", "excerpt": REQUEST_TEXT_BY_TYPE[procedure_type]}],
    }


def _structured_data(*, procedure_types: tuple[str, ...]) -> dict[str, Any]:
    return {
        "schema_version": "4.0",
        "language": "pt-BR",
        "agency_record_number": "12345",
        "patient": {"name": "Paciente", "age": 35, "sex": "M", "document_id": None},
        "common_preop": _common_preop(),
        "requested_procedures": [_procedure_item(procedure_type) for procedure_type in procedure_types],
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


def _recommendation(procedure_type: str) -> dict[str, Any]:
    return {
        "procedure_type": procedure_type,
        "suggestion": "accept",
        "support_recommendation": "none",
        "preop_decision": {
            "decision": "accept",
            "reason_code": "criteria_met",
            "reason_text": f"Critérios determinísticos pré-operatórios de {PROCEDURE_LABELS[procedure_type]} atendidos.",
            "failed_requirements": [],
        },
    }


def _recto_case(
    user,
    *,
    procedure_types: tuple[str, ...],
    precedence: dict[str, Any] | None = None,
) -> Case:
    suggested: dict[str, Any] = {
        "schema_version": "4.0",
        "procedure_recommendations": [_recommendation(procedure_type) for procedure_type in procedure_types],
        "global_support_recommendation": "none",
    }
    if precedence is not None:
        suggested["procedure_precedence"] = precedence
    case = Case.objects.create(
        created_by=user,
        agency_record_number="12345",
        extracted_text=REQUEST_TEXT_BY_TYPE[procedure_types[0]],
        structured_data=_structured_data(procedure_types=procedure_types),
        suggested_action=suggested,
    )
    set_declared_procedures(case=case, procedure_types=list(procedure_types), actor=user)
    return Case.objects.get(case_id=case.case_id)


def _report(case: Case) -> dict[str, Any]:
    return prepare_doctor_case_report(case).presenter.build_report()


def _text_report(case: Case) -> str:
    return prepare_doctor_case_report(case).presenter.build_text_report()


# ── R5: uma seção por identidade, label da identidade ──────────────────────


class TestRectosigmoidoscopyProcedureSections:
    @pytest.mark.parametrize("procedure_type", RECTOSIGMOIDOSCOPY_TYPES)
    def test_identity_renders_one_section_with_the_catalog_label(self, django_user_model, procedure_type: str) -> None:
        user = django_user_model.objects.create_user(username=f"doc-{procedure_type}")
        case = _recto_case(user, procedure_types=(procedure_type,))
        identity_label = PROCEDURE_LABELS[procedure_type]

        report = _report(case)

        assert report["context"]["procedure"] == f"procedimento solicitado: {identity_label}"
        assert report["procedure_sections"] == [{"procedure_type": procedure_type, "label": identity_label}]

    @pytest.mark.parametrize("procedure_type", RECTOSIGMOIDOSCOPY_TYPES)
    def test_report_never_labels_the_identity_as_colonoscopy(self, django_user_model, procedure_type: str) -> None:
        """R5/D4: compartilhar profile não troca a identidade apresentada."""
        user = django_user_model.objects.create_user(username=f"doc-label-{procedure_type}")
        case = _recto_case(user, procedure_types=(procedure_type,))
        identity_label = PROCEDURE_LABELS[procedure_type]

        text = _text_report(case)

        assert f"procedimento solicitado: {identity_label}" in text
        assert "Colonoscopia" not in text

    def test_variations_never_inherit_the_dilation_site_section(self, django_user_model) -> None:
        """O local anatômico é exclusivo de EDA + Dilatação (D6/R6)."""
        user = django_user_model.objects.create_user(username="doc-recto-site")
        case = _recto_case(user, procedure_types=(ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,))

        section = _report(case)["procedure_sections"][0]

        assert "dilation_site_label" not in section

    def test_variation_does_not_create_a_base_section(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-recto-single-section")
        case = _recto_case(
            user,
            procedure_types=(ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,),
            precedence={
                "rule": "variation_over_base",
                "selected": ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
                "suppressed": [ProcedureType.RECTOSIGMOIDOSCOPY],
            },
        )

        report = _report(case)

        assert [section["procedure_type"] for section in report["procedure_sections"]] == [
            ProcedureType.RECTOSIGMOIDOSCOPY_DILATION
        ]

    def test_variation_suppression_uses_the_variation_copy(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-recto-precedence")
        case = _recto_case(
            user,
            procedure_types=(ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,),
            precedence={
                "rule": "variation_over_base",
                "selected": ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
                "suppressed": [ProcedureType.RECTOSIGMOIDOSCOPY],
            },
        )

        notices = " ".join(_report(case)["notices"])

        assert "Retossigmoidoscopia + Dilatação" in notices
        assert "especializado" not in notices

    def test_family_umbrella_suppression_uses_the_family_copy(self, django_user_model) -> None:
        """Slice 003/R7: a regra de família tem copy própria (não a de especializado)."""
        user = django_user_model.objects.create_user(username="doc-recto-family-precedence")
        case = _recto_case(
            user,
            procedure_types=(ProcedureType.RECTOSIGMOIDOSCOPY,),
            precedence={
                "rule": "family_umbrella_over_colonoscopy",
                "selected": ProcedureType.RECTOSIGMOIDOSCOPY,
                "suppressed": [ProcedureType.COLONOSCOPY],
            },
        )

        notices = " ".join(_report(case)["notices"])

        assert "Retossigmoidoscopia" in notices
        assert "Colonoscopia" in notices
        assert "descreve o procedimento da família correspondente" in notices
        assert "especializado" not in notices
        assert "pacote atômico" not in notices


# ── R4/D11: histórico anterior pelo código exato ───────────────────────────


class TestRectosigmoidoscopyHistoryUsesTheExactCode:
    def _prior_case(self, user, *, rows: list[tuple[str, str]]) -> Case:
        prior = Case.objects.create(
            created_by=user,
            agency_record_number="12345",
            structured_data=_structured_data(procedure_types=(ProcedureType.RECTOSIGMOIDOSCOPY,)),
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

    def test_prior_colonoscopy_denial_does_not_feed_the_identity_section(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-recto-hist-colon")
        self._prior_case(user, rows=[(ProcedureType.COLONOSCOPY, "denied")])
        case = _recto_case(user, procedure_types=(ProcedureType.RECTOSIGMOIDOSCOPY,))

        assert _report(case)["prior_sections"] == []

    def test_prior_base_denial_does_not_feed_the_variation_section(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-recto-hist-base")
        self._prior_case(user, rows=[(ProcedureType.RECTOSIGMOIDOSCOPY, "denied")])
        case = _recto_case(user, procedure_types=(ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,))

        assert _report(case)["prior_sections"] == []

    def test_prior_identity_denial_appears_under_the_identity_label(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-recto-hist-exact")
        self._prior_case(user, rows=[(ProcedureType.RECTOSIGMOIDOSCOPY_DILATION, "denied")])
        case = _recto_case(user, procedure_types=(ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,))

        sections = _report(case)["prior_sections"]

        assert [section["procedure_label"] for section in sections] == ["Retossigmoidoscopia + Dilatação"]
        assert sections[0]["decision_display"] == "Regulação Negada"


# ── R5: página de decisão médica renderiza a identidade ────────────────────


@pytest.mark.django_db
class TestRectosigmoidoscopyDecisionPage:
    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username=f"{role_name}@recto.test", password="testpass123")
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

    def _case_at_wait_doctor(self, user, *, procedure_type: str) -> Case:
        case = _recto_case(user, procedure_types=(procedure_type,))
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

    @pytest.mark.parametrize("procedure_type", RECTOSIGMOIDOSCOPY_TYPES)
    def test_decision_page_shows_the_identity_badge_and_section(self, client, procedure_type: str) -> None:
        nir = self._login_as(client, "nir")
        case = self._case_at_wait_doctor(nir, procedure_type=procedure_type)
        doctor = self._login_as(client, "doctor")
        self._claim_lock(case.case_id, doctor)

        response = client.get(f"/doctor/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Procedimentos analisados" in content
        assert f"exam-type-{procedure_type}" in content
        assert PROCEDURE_LABELS[procedure_type] in content
