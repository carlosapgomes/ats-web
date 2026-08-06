"""Slice 002 — reconciliação D7, projeção de detecção e policy por componente.

RED 4 (R3): matriz D7 completa.
RED 5 (R3): histórico/negação não combina.
RED 6 (R4): upgrade cria row detectada não declarada + evento, sem ACK NIR.
RED 8 (R5): policy executa uma vez por componente; foreign-body não vaza.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, DetectionStatus
from apps.pipeline.llm import RecordingLlmClient

# ── Helpers ──────────────────────────────────────────────────────────────────


def _procedure_row(case: Case, procedure_type: str, *, declared: bool = True) -> CaseProcedure:
    row, _ = CaseProcedure.objects.get_or_create(case=case, procedure_type=procedure_type)
    if declared and not row.declared_by_nir:
        row.declared_by_nir = True
        row.save(update_fields=["declared_by_nir"])
    return row


def _make_case(user, *, agency_record_number: str = "12345") -> Case:
    return Case.objects.create(created_by=user, agency_record_number=agency_record_number)


# ── RED 4: matriz D7 completa ───────────────────────────────────────────────


class TestReconcileD7Matrix:
    def _reconcile(self, *, declared, strong, any_evidence):
        from apps.pipeline.procedure_reconciliation import reconcile_detected_procedures

        return reconcile_detected_procedures(
            declared=declared,
            strong=strong,
            any_evidence=any_evidence,
        )

    def test_eda_declared_eda_detected_proceeds(self) -> None:
        result = self._reconcile(declared=("eda",), strong=("eda",), any_evidence=("eda",))
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("eda",)

    def test_colon_declared_colon_detected_proceeds(self) -> None:
        result = self._reconcile(declared=("colonoscopy",), strong=("colonoscopy",), any_evidence=("colonoscopy",))
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("colonoscopy",)

    def test_both_declared_both_detected_proceeds(self) -> None:
        result = self._reconcile(
            declared=("eda", "colonoscopy"),
            strong=("eda", "colonoscopy"),
            any_evidence=("eda", "colonoscopy"),
        )
        assert result.action == "proceed"
        assert result.detected_procedure_types == ("eda", "colonoscopy")

    def test_eda_declared_both_detected_strong_upgrades(self) -> None:
        result = self._reconcile(
            declared=("eda",),
            strong=("eda", "colonoscopy"),
            any_evidence=("eda", "colonoscopy"),
        )
        assert result.action == "auto_upgrade"
        assert result.upgraded is True
        assert result.detected_procedure_types == ("eda", "colonoscopy")

    def test_colon_declared_both_detected_strong_upgrades(self) -> None:
        result = self._reconcile(
            declared=("colonoscopy",),
            strong=("eda", "colonoscopy"),
            any_evidence=("eda", "colonoscopy"),
        )
        assert result.action == "auto_upgrade"
        assert result.detected_procedure_types == ("eda", "colonoscopy")

    def test_single_declared_both_any_without_strong_returns_to_nir(self) -> None:
        """D7: upgrade exige evidência forte; sem ela, revisão NIR."""
        result = self._reconcile(
            declared=("eda",),
            strong=("eda",),
            any_evidence=("eda", "colonoscopy"),
        )
        assert result.action == "nir_review"
        assert result.reason_code == "mixed_exam_request"

    def test_both_declared_single_detected_returns_to_nir(self) -> None:
        result = self._reconcile(
            declared=("eda", "colonoscopy"),
            strong=("eda",),
            any_evidence=("eda",),
        )
        assert result.action == "nir_review"
        assert result.reason_code == "exam_type_mismatch"

    def test_eda_declared_colon_detected_returns_to_nir(self) -> None:
        result = self._reconcile(
            declared=("eda",),
            strong=("colonoscopy",),
            any_evidence=("colonoscopy",),
        )
        assert result.action == "nir_review"
        assert result.reason_code == "exam_type_mismatch"

    def test_colon_declared_eda_detected_returns_to_nir(self) -> None:
        result = self._reconcile(
            declared=("colonoscopy",),
            strong=("eda",),
            any_evidence=("eda",),
        )
        assert result.action == "nir_review"
        assert result.reason_code == "exam_type_mismatch"

    def test_nothing_detected_returns_unknown_review(self) -> None:
        result = self._reconcile(declared=("eda",), strong=(), any_evidence=())
        assert result.action == "nir_review"
        assert result.reason_code == "unknown_exam_type"


# ── RED 5: histórico/negação não combina ────────────────────────────────────


class TestV2DetectionHistoryNegation:
    def _detect(self, *, structured_data: dict[str, object], cleaned_text: str) -> dict[str, dict[str, bool]]:
        from apps.pipeline.scope_detection import detect_requested_procedures_v2

        return detect_requested_procedures_v2(
            llm1_structured_data=structured_data,
            cleaned_text=cleaned_text,
        )

    def test_eda_historical_colon_current_only_colon(self) -> None:
        llm1: dict[str, object] = {
            "requested_procedures": [
                {
                    "procedure_type": "colonoscopy",
                    "evidence_spans": [{"field_path": "x", "excerpt": "Solicito colonoscopia"}],
                }
            ]
        }
        result = self._detect(
            structured_data=llm1,
            cleaned_text="EDA realizada em 2024. Solicito colonoscopia.",
        )
        assert result["eda"]["any"] is False
        assert result["colonoscopy"]["any"] is True

    def test_eda_current_colon_negated_only_eda(self) -> None:
        llm1: dict[str, object] = {
            "requested_procedures": [
                {"procedure_type": "eda", "evidence_spans": [{"field_path": "x", "excerpt": "Solicito EDA"}]}
            ]
        }
        result = self._detect(
            structured_data=llm1,
            cleaned_text="Solicito EDA. Nega indicacao de colonoscopia.",
        )
        assert result["eda"]["any"] is True
        assert result["colonoscopy"]["any"] is False

    def test_strong_evidence_from_v2_structured_list(self) -> None:
        llm1: dict[str, object] = {
            "requested_procedures": [
                {"procedure_type": "eda", "evidence_spans": [{"field_path": "x", "excerpt": "Solicito EDA"}]},
                {
                    "procedure_type": "colonoscopy",
                    "evidence_spans": [{"field_path": "y", "excerpt": "Solicito colonoscopia"}],
                },
            ]
        }
        result = self._detect(structured_data=llm1, cleaned_text="")
        assert result["eda"]["strong"] is True
        assert result["colonoscopy"]["strong"] is True

    def test_motive_mentions_count_as_strong(self) -> None:
        llm1: dict[str, object] = {"requested_procedures": []}
        result = self._detect(
            structured_data=llm1,
            cleaned_text="Motivo da Solicitacao: EDA e colonoscopia para rastreamento. Unid. Origem: HSA",
        )
        assert result["eda"]["strong"] is True
        assert result["colonoscopy"]["strong"] is True


# ── RED 6/8: projeção atômica + policy por componente ──────────────────────


@pytest.mark.django_db
class TestDetectedProjection:
    def test_upgrade_creates_non_declared_detected_row_and_event(self, django_user_model) -> None:
        from apps.cases.procedures import set_detected_procedures

        user = django_user_model.objects.create_user(username="nir_up1", password="pw")
        case = _make_case(user)
        _procedure_row(case, "eda", declared=True)

        set_detected_procedures(case=case, detected_types=("eda", "colonoscopy"), actor=user)

        eda_row = CaseProcedure.objects.get(case=case, procedure_type="eda")
        colon_row = CaseProcedure.objects.get(case=case, procedure_type="colonoscopy")
        assert eda_row.detection_status == DetectionStatus.DETECTED
        assert colon_row.detection_status == DetectionStatus.DETECTED
        # LLM nunca altera declared_by_nir
        assert colon_row.declared_by_nir is False
        assert eda_row.declared_by_nir is True

    def test_non_detected_existing_rows_marked_not_detected(self, django_user_model) -> None:
        from apps.cases.procedures import set_detected_procedures

        user = django_user_model.objects.create_user(username="nir_up2", password="pw")
        case = _make_case(user)
        _procedure_row(case, "eda", declared=True)
        _procedure_row(case, "colonoscopy", declared=True)

        set_detected_procedures(case=case, detected_types=("eda",), actor=user)

        colon_row = CaseProcedure.objects.get(case=case, procedure_type="colonoscopy")
        assert colon_row.detection_status == DetectionStatus.NOT_DETECTED

    def test_projection_failure_leaves_no_partial_set(self, django_user_model, monkeypatch) -> None:
        from apps.cases.procedures import set_detected_procedures

        user = django_user_model.objects.create_user(username="nir_up3", password="pw")
        case = _make_case(user)
        _procedure_row(case, "eda", declared=True)

        def boom(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("falha na segunda row")

        monkeypatch.setattr("apps.cases.procedures.CaseProcedure.objects.get_or_create", boom)
        with pytest.raises(RuntimeError):
            set_detected_procedures(case=case, detected_types=("eda", "colonoscopy"), actor=user)

        # Falha atômica: nada persiste.
        rows = CaseProcedure.objects.filter(case=case)
        assert rows.count() == 1
        assert rows.get(procedure_type="eda").detection_status == DetectionStatus.PENDING


@pytest.mark.django_db
class TestPolicyPerComponent:
    def test_policy_runs_once_per_detected_component_and_foreign_body_does_not_leak(self, django_user_model) -> None:
        """R5/R8: EDA corpo estranho aceita; Colonoscopia não herda a exceção."""
        from apps.cases.procedures import set_detected_procedures
        from apps.pipeline.policy.eda_preop_policy import evaluate_preop_policy
        from apps.pipeline.schemas.adapters import project_v2_to_llm1_shape

        user = django_user_model.objects.create_user(username="nir_pol", password="pw")
        case = _make_case(user)
        _procedure_row(case, "eda", declared=True)
        _procedure_row(case, "colonoscopy", declared=True)
        set_detected_procedures(case=case, detected_types=("eda", "colonoscopy"), actor=user)

        v2_data: dict[str, object] = {
            "patient": {"age": 35},
            "common_preop": {
                "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0},
                "ecg": {"report_present": "unknown", "abnormal_flag": "unknown"},
                "rulebook_signals": {
                    "eda_subtype": "foreign_body",
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
            },
            "requested_procedures": [
                {
                    "procedure_type": "eda",
                    "indication_category": "foreign_body",
                    "subtype": "foreign_body",
                    "evidence_spans": [{"field_path": "x", "excerpt": "Corpo estranho"}],
                },
                {
                    "procedure_type": "colonoscopy",
                    "indication_category": "screening",
                    "subtype": "standard",
                    "evidence_spans": [{"field_path": "y", "excerpt": "Colonoscopia"}],
                },
            ],
        }

        eda_projection = project_v2_to_llm1_shape(v2_data=v2_data, procedure_type="eda")
        colon_projection = project_v2_to_llm1_shape(v2_data=v2_data, procedure_type="colonoscopy")

        eda_decision = evaluate_preop_policy(structured_data=eda_projection, exam_type="eda")
        colon_decision = evaluate_preop_policy(structured_data=colon_projection, exam_type="colonoscopy")

        assert eda_decision["decision"] == "accept"
        assert eda_decision["reason_code"] == "foreign_body_exception"
        # Colonoscopia não herda exceção de corpo estranho (policy normal).
        assert colon_decision["reason_code"] != "foreign_body_exception"

    def test_projection_never_touches_declared_by_nir(self, django_user_model) -> None:
        from apps.cases.procedures import set_detected_procedures

        user = django_user_model.objects.create_user(username="nir_dec", password="pw")
        case = _make_case(user)
        _procedure_row(case, "eda", declared=True)
        _procedure_row(case, "colonoscopy", declared=False)

        set_detected_procedures(case=case, detected_types=("colonoscopy",), actor=user)

        colon_row = CaseProcedure.objects.get(case=case, procedure_type="colonoscopy")
        eda_row = CaseProcedure.objects.get(case=case, procedure_type="eda")
        assert colon_row.declared_by_nir is False
        assert eda_row.declared_by_nir is True


# ── Pipeline v2 end-to-end: chegada ao médico, gates e regressão ──────────
#
# RED 6/7 (R3/R7): upgrade chega ao médico sem ACK; combined→single e mismatch
# não chegam ao médico nem executam LLM2.
# RED 13 (R7): combinado chega WAIT_DOCTOR com duas recomendações.
# RED 14 (R9): EDA/Colon simples continuam.
# RED 15 (R8): invalid v2 não persiste parcial.
# RED 16 (R9): schema 1.1 ainda renderiza.
# RED 17 (D15): flag falsa após criação não bloqueia pipeline.


# ── Sample builders (v2) ─────────────────────────────────────────────────────


def _evidence_span(field_path: str = "p.0", excerpt: str = "Solicito EDA") -> dict[str, str]:
    return {"field_path": field_path, "excerpt": excerpt}


def _eda_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "eda",
        "name": "EDA",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "subtype": "standard",
        "evidence_spans": [_evidence_span(excerpt="Solicito EDA")],
    }
    item.update(overrides)
    return item


def _colon_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "colonoscopy",
        "name": "Colonoscopia",
        "urgency": "eletivo",
        "indication_category": "screening",
        "subtype": "standard",
        "evidence_spans": [_evidence_span(excerpt="Solicito colonoscopia")],
    }
    item.update(overrides)
    return item


def _llm1_v2_json(*, procedures: list[dict[str, Any]], one_liner: str = "EDA e Colonoscopia indicadas.") -> str:
    payload: dict[str, Any] = {
        "schema_version": "2.0",
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
            "medications_described": [
                {
                    "name": "Varfarina",
                    "normalized_name": "varfarina",
                    "medication_class": "anticoagulant",
                    "use_status": "current",
                    "last_dose_or_schedule": None,
                    "source_text_hint": "faz uso de varfarina",
                }
            ],
            "evidence_spans": [],
        },
        "requested_procedures": procedures,
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
        "summary": {"one_liner": one_liner, "bullet_points": ["P1", "P2", "P3"]},
        "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
        "origin_context": {"city": None, "hospital": None, "unit": None, "state_uf": None, "source_text_hint": None},
        "transfusion": {"had_transfusion": "no"},
        "tracked_exams": [],
    }
    return json.dumps(payload)


def _llm2_v2_json(
    case_id: str, *, recommendations: list[dict[str, Any]] | None = None, global_support: str = "none"
) -> str:
    if recommendations is None:
        recommendations = [
            {
                "procedure_type": "eda",
                "suggestion": "accept",
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
            },
            {
                "procedure_type": "colonoscopy",
                "suggestion": "accept",
                "support_recommendation": "anesthesist",
                "rationale": {
                    "short_reason": "Aprovado.",
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
            },
        ]
    return json.dumps(
        {
            "schema_version": "2.0",
            "language": "pt-BR",
            "case_id": case_id,
            "agency_record_number": "12345",
            "procedure_recommendations": recommendations,
            "global_support_recommendation": global_support,
            "summary": None,
        }
    )


def _make_v2_case(user, *, exam_type: str = "eda", extracted_text: str = "Solicito EDA.") -> Case:
    """Cria um Case com projeção declarada (novo intake) pronto para o pipeline."""
    from apps.cases.procedures import set_declared_procedures

    case = Case.objects.create(created_by=user, agency_record_number="12345", extracted_text=extracted_text)
    if exam_type == "eda_colonoscopy":
        types = ("eda", "colonoscopy")
    else:
        types = (exam_type,)
    set_declared_procedures(case=case, procedure_types=types, actor=user)
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()
    return case


def _reload(case: Case) -> Case:
    return Case.objects.get(case_id=case.case_id)


# ── RED 13: combinado chega WAIT_DOCTOR com duas recomendações ─────────────


@pytest.mark.django_db
class TestCombinedHappyPath:
    def test_combined_declared_reaches_wait_doctor_with_two_recommendations(self, django_user_model) -> None:
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_c1", password="pw"),
            exam_type="eda_colonoscopy",
            extracted_text="Motivo da Solicitacao: EDA e colonoscopia para rastreamento",
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_v2_json(procedures=[_eda_procedure(), _colon_procedure()]),
                _llm2_v2_json(str(case.case_id)),
            ]
        )
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="SP1",
            llm1_user_template="ut1",
            llm2_system_prompt="SP2",
            llm2_user_template="ut2",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        # Uma chamada por estágio.
        assert len(client.calls) == 2
        assert case.suggested_action is not None
        recs = case.suggested_action["procedure_recommendations"]
        assert {r["procedure_type"] for r in recs} == {"eda", "colonoscopy"}
        # Suporte global mais restritivo: colon → anesthesist > eda none.
        assert case.suggested_action is not None
        assert case.suggested_action["global_support_recommendation"] == "anesthesist"
        # Rows detectadas (declaradas).
        for t in ("eda", "colonoscopy"):
            row = CaseProcedure.objects.get(case=case, procedure_type=t)
            assert row.detection_status == DetectionStatus.DETECTED
        assert CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").exists()

    def test_single_eda_upgraded_to_combined_reaches_doctor_with_event(self, django_user_model) -> None:
        """RED 6: single→combined com evidência forte → upgrade auditado, sem ACK."""
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_c1b", password="pw"),
            exam_type="eda",
            extracted_text="Motivo da Solicitacao: EDA e colonoscopia para rastreamento",
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_v2_json(procedures=[_eda_procedure(), _colon_procedure()]),
                _llm2_v2_json(str(case.case_id)),
            ]
        )
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="SP1",
            llm1_user_template="ut1",
            llm2_system_prompt="SP2",
            llm2_user_template="ut2",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        # Row não declarada criada e detectada; declaração imutável.
        colon_row = CaseProcedure.objects.get(case=case, procedure_type="colonoscopy")
        assert colon_row.declared_by_nir is False
        assert colon_row.detection_status == DetectionStatus.DETECTED
        # Eventos de detecção e upgrade auditados.
        assert CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").exists()
        assert CaseEvent.objects.filter(case=case, event_type="PROCEDURE_SELECTION_AUTO_UPGRADED").exists()

    def test_combined_uses_neutral_prompts(self, django_user_model) -> None:
        from apps.llm.models import PromptTemplate

        for name, content in (
            ("exam_llm1_system", "NEUTRAL_SYS_1"),
            ("exam_llm1_user", "NEUTRAL_USR_1"),
            ("exam_llm2_system", "NEUTRAL_SYS_2"),
            ("exam_llm2_user", "NEUTRAL_USR_2"),
        ):
            PromptTemplate.objects.create(name=name, version=1, content=content, is_active=True)

        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_c2", password="pw"),
            exam_type="eda_colonoscopy",
            extracted_text="Motivo da Solicitacao: EDA e colonoscopia para rastreamento",
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_v2_json(procedures=[_eda_procedure(), _colon_procedure()]),
                _llm2_v2_json(str(case.case_id)),
            ]
        )
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(case.case_id, llm_client=client)

        assert client.calls[0]["system_prompt"] == "NEUTRAL_SYS_1"
        assert client.calls[1]["system_prompt"] == "NEUTRAL_SYS_2"

    def test_events_carry_schema_version_and_sets_without_full_clinical_text(self, django_user_model) -> None:
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_c3", password="pw"),
            exam_type="eda_colonoscopy",
            extracted_text="Motivo da Solicitacao: EDA e colonoscopia para rastreamento",
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_v2_json(procedures=[_eda_procedure(), _colon_procedure()]),
                _llm2_v2_json(str(case.case_id)),
            ]
        )
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(case.case_id, llm_client=client)

        detected_event = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")
        payload: dict[str, Any] = detected_event.payload or {}
        assert payload.get("schema_version") == "2.0"
        assert payload.get("detected_procedures") == ["eda", "colonoscopy"]
        serialized = json.dumps(payload)
        assert "Motivo da Solicitacao" not in serialized


# ── RED 7: combined→single e mismatch não chegam médico/LLM2 ───────────────


@pytest.mark.django_db
class TestReviewGates:
    def test_combined_declared_single_detected_returns_to_nir(self, django_user_model) -> None:
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_g1", password="pw"),
            exam_type="eda_colonoscopy",
            extracted_text="Solicito EDA para avaliacao de dispepsia.",
        )
        client = RecordingLlmClient(responses=[_llm1_v2_json(procedures=[_eda_procedure()])])
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert len(client.calls) == 1  # LLM2 nunca roda
        assert case.suggested_action is not None
        assert case.suggested_action["decision"] == "manual_review_required"
        assert case.suggested_action is not None
        assert case.suggested_action["reason_code"] == "exam_type_mismatch"
        assert case.suggested_action is not None
        assert case.suggested_action["detected_procedures"] == ["eda"]

    def test_single_declared_other_detected_returns_to_nir(self, django_user_model) -> None:
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_g2", password="pw"),
            exam_type="eda",
            extracted_text="Solicito colonoscopia para rastreamento.",
        )
        client = RecordingLlmClient(responses=[_llm1_v2_json(procedures=[_colon_procedure()])])
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert len(client.calls) == 1
        assert case.suggested_action is not None
        assert case.suggested_action["reason_code"] == "exam_type_mismatch"

    def test_single_declared_both_without_strong_evidence_returns_to_nir(self, django_user_model) -> None:
        """D7: duas solicitações textuais atuais, mas o segundo procedimento sem
        proveniência forte (LLM não o afirmou estruturado) → revisão NIR."""
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_g3", password="pw"),
            exam_type="eda",
            extracted_text="Solicito EDA e colonoscopia para avaliacao.",
        )
        # LLM1 afirma apenas EDA (sem structured claim de colonoscopia).
        client = RecordingLlmClient(responses=[_llm1_v2_json(procedures=[_eda_procedure()])])
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert len(client.calls) == 1
        assert case.suggested_action is not None
        assert case.suggested_action["reason_code"] == "mixed_exam_request"


# ── RED 14/15/17: simples continuam, invalid não persiste, flag irrelevante ──


@pytest.mark.django_db
class TestSimpleAndFailurePaths:
    def test_simple_eda_reaches_wait_doctor(self, django_user_model) -> None:
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_s1", password="pw"),
            exam_type="eda",
            extracted_text="Solicito EDA para dispepsia.",
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_v2_json(procedures=[_eda_procedure()], one_liner="EDA indicada."),
                _llm2_v2_json(
                    str(case.case_id),
                    recommendations=[
                        {
                            "procedure_type": "eda",
                            "suggestion": "accept",
                            "support_recommendation": "none",
                            "rationale": {
                                "short_reason": "OK.",
                                "details": ["1", "2"],
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
                ),
            ]
        )
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
            llm2_system_prompt="sp2",
            llm2_user_template="ut2",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2

    def test_simple_colonoscopy_reaches_wait_doctor(self, django_user_model) -> None:
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_s2", password="pw"),
            exam_type="colonoscopy",
            extracted_text="Solicito colonoscopia para rastreamento.",
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_v2_json(procedures=[_colon_procedure()], one_liner="Colonoscopia indicada."),
                _llm2_v2_json(
                    str(case.case_id),
                    recommendations=[
                        {
                            "procedure_type": "colonoscopy",
                            "suggestion": "accept",
                            "support_recommendation": "none",
                            "rationale": {
                                "short_reason": "OK.",
                                "details": ["1", "2"],
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
                ),
            ]
        )
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
            llm2_system_prompt="sp2",
            llm2_user_template="ut2",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2

    def test_invalid_llm1_v2_fails_without_partial_artifact(self, django_user_model) -> None:
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_f1", password="pw"),
            exam_type="eda",
            extracted_text="Solicito EDA.",
        )
        # Resposta inválida: requested_procedures vazio.
        client = RecordingLlmClient(responses=['{"schema_version": "2.0", "requested_procedures": []}'])
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        assert case.structured_data is None
        assert case.suggested_action is None

    def test_invalid_llm2_set_fails_without_partial_suggestion(self, django_user_model) -> None:
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_f2", password="pw"),
            exam_type="eda",
            extracted_text="Solicito EDA.",
        )
        responses = [
            _llm1_v2_json(procedures=[_eda_procedure()]),
            # LLM2 devolve dois itens para um único detectado → inválido.
            _llm2_v2_json(str(case.case_id)),
        ]
        client = RecordingLlmClient(responses=responses)
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
            llm2_system_prompt="sp2",
            llm2_user_template="ut2",
        )

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        assert case.suggested_action is None

    def test_flag_off_after_creation_does_not_block_pipeline(self, django_user_model, settings) -> None:
        settings.COLONOSCOPY_INTAKE_ENABLED = False
        case = _make_v2_case(
            django_user_model.objects.create_user(username="nir_fl", password="pw"),
            exam_type="colonoscopy",
            extracted_text="Solicito colonoscopia.",
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_v2_json(procedures=[_colon_procedure()], one_liner="Colonoscopia indicada."),
                _llm2_v2_json(
                    str(case.case_id),
                    recommendations=[
                        {
                            "procedure_type": "colonoscopy",
                            "suggestion": "accept",
                            "support_recommendation": "none",
                            "rationale": {
                                "short_reason": "OK.",
                                "details": ["1", "2"],
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
                ),
            ]
        )
        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
            llm2_system_prompt="sp2",
            llm2_user_template="ut2",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR


# ── RED 16: schema 1.1 ainda renderiza (presenter legado) ──────────────────


class TestLegacy11Render:
    def test_presenter_renders_legacy_11(self) -> None:
        from apps.doctor.presenters import DoctorReportPresenter

        structured_11: dict[str, Any] = {
            "schema_version": "1.1",
            "patient": {"name": "Paciente", "age": 35, "sex": "M"},
            "preop_screening": {
                "exam_type": "eda",
                "comorbidities_described": [],
                "medications_described": [
                    {
                        "name": "Varfarina",
                        "medication_class": "anticoagulant",
                        "use_status": "current",
                        "source_text_hint": "faz uso",
                    }
                ],
                "rulebook_signals": {"eda_subtype": "standard"},
            },
            "eda": {
                "indication_category": "dyspepsia",
                "requested_procedure": {"name": "EDA", "subtype": "standard"},
                "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0},
                "ecg": {"report_present": "unknown", "abnormal_flag": "unknown"},
            },
            "policy_precheck": {
                "excluded_from_eda_flow": False,
                "labs_required": False,
                "labs_pass": "unknown",
                "ecg_required": False,
                "ecg_present": "unknown",
                "pediatric_flag": False,
                "notes": None,
            },
            "summary": {"one_liner": "EDA indicada.", "bullet_points": ["P1", "P2", "P3"]},
            "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
        }
        presenter = DoctorReportPresenter(
            structured_data=structured_11,
            summary_text="EDA indicada.",
            suggested_action={"suggestion": "accept", "support_recommendation": "none"},
            exam_type="eda",
        )
        report = presenter.build_report()
        assert "EDA" in report["context"]["procedure"]
        assert any("Varfarina" in line for line in report["blocks"]["achados_criticos"])
        assert any("aceitar" in line for line in report["blocks"]["decisao_sugerida"])

    def test_presenter_renders_v2_combined_with_two_recommendations(self) -> None:
        from apps.doctor.presenters import DoctorReportPresenter

        v2_data = json.loads(
            _llm1_v2_json(procedures=[_eda_procedure(), _colon_procedure()], one_liner="EDA e Colonoscopia indicadas.")
        )
        suggested: dict[str, Any] = {
            "schema_version": "2.0",
            "procedure_recommendations": [
                {"procedure_type": "eda", "suggestion": "accept", "support_recommendation": "none"},
                {"procedure_type": "colonoscopy", "suggestion": "deny", "support_recommendation": "anesthesist"},
            ],
            "global_support_recommendation": "anesthesist",
        }
        presenter = DoctorReportPresenter(
            structured_data=v2_data,
            summary_text="EDA e Colonoscopia indicadas.",
            suggested_action=suggested,
            exam_type="eda_colonoscopy",
        )
        report = presenter.build_report()
        assert "EDA + Colonoscopia" in report["context"]["procedure"]
        decision_lines = report["blocks"]["decisao_sugerida"]
        assert any("EDA" in line and "aceitar" in line for line in decision_lines)
        assert any("Colonoscopia" in line and "negar" in line for line in decision_lines)
        # Alerta medicamentoso existente (comum no v2).
        assert any("Varfarina" in line for line in report["blocks"]["achados_criticos"])
