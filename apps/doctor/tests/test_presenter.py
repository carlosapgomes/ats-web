"""Tests for the DoctorReportPresenter — 7-block medical report."""

from __future__ import annotations

from typing import Any

import pytest

from apps.doctor.presenters import DoctorReportPresenter

# ── Fixture helpers ─────────────────────────────────────────────────────


def _make_complete_payload() -> dict[str, Any]:
    """Full structured payload covering all supported fields."""
    return {
        "origin_context": {
            "city": "Salvador",
            "state_uf": "BA",
            "hospital": "Hospital Geral",
            "unit": "Centro Cirúrgico",
        },
        "transfusion": {
            "had_transfusion": "yes",
            "total_units": 3,
            "hemocomponent": "concentrado de hemácias",
        },
        "tracked_exams": [
            {
                "exam_label": "Hb",
                "result_value": "8.5 g/dL",
                "is_most_recent": True,
                "exam_datetime_iso": "2025-12-01T10:00:00",
            },
            {
                "exam_label": "Plaquetas",
                "result_value": "120000/mm³",
                "is_most_recent": False,
            },
        ],
        "eda": {
            "requested_procedure": {"subtype": "gastrostomy"},
            "labs": {
                "hb_g_dl": 8.5,
                "platelets_per_mm3": 120000,
                "inr": 1.1,
            },
            "ecg": {
                "report_present": True,
                "abnormal_flag": False,
            },
            "indication_category": "bleeding",
            "is_pediatric": False,
        },
        "policy_precheck": {
            "labs_required": True,
            "labs_pass": "yes",
            "ecg_required": False,
            "ecg_present": True,
            "labs_failed_items": [],
            "excluded_from_eda_flow": False,
        },
        "patient": {
            "age": 45,
            "name": "João Pereira",
        },
    }


def _make_minimal_payload() -> dict[str, Any]:
    """Minimal payload — mostly empty/absent data."""
    return {
        "patient": {"age": 30},
    }


def _make_suggested_action_accept() -> dict[str, Any]:
    return {
        "suggestion": "accept",
        "support_recommendation": "none",
        "asa": {"display_text": "ASA II"},
    }


def _make_suggested_action_deny() -> dict[str, Any]:
    return {
        "suggestion": "deny",
        "support_recommendation": "none",
        "asa": {"display_text": "ASA I"},
        "reason_code": "hb_below_threshold",
        "reason_text": "Hb abaixo do limiar: 8.5 g/dL.",
    }


def _make_recent_denial_context() -> dict[str, Any]:
    return {
        "decision": "deny_triage",
        "reason": "Contorno clínico elevado",
        "decided_at": "2025-12-01T14:00:00+00:00",
        "prior_denial_count_7d": 2,
    }


@pytest.mark.django_db
class TestDoctorReportPresenter:
    """Tests for the DoctorReportPresenter — 7-block report generation."""

    # ── Block coverage ────────────────────────────────────────────────

    def test_full_payload_generates_all_seven_blocks(self):
        """Presenter with complete payload generates all 7 report blocks."""
        payload = _make_complete_payload()
        suggested = _make_suggested_action_accept()
        presenter = DoctorReportPresenter(
            structured_data=payload,
            summary_text="Paciente com HDA. Hb 8.5.",
            suggested_action=suggested,
        )
        report = presenter.build_report()

        block_names = set(report["blocks"].keys())
        expected = {
            "resumo_clinico",
            "achados_criticos",
            "pendencias_criticas",
            "decisao_sugerida",
            "suporte_recomendado",
            "asa_estimado",
            "motivo_objetivo",
        }
        assert block_names == expected

    def test_minimal_payload_still_generates_all_blocks(self):
        """Presenter with minimal payload still generates all 7 blocks (with fallbacks)."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert len(report["blocks"]) == 7
        for block_name, block_lines in report["blocks"].items():
            assert isinstance(block_lines, list), f"Block {block_name} should be a list"
            assert len(block_lines) >= 1, f"Block {block_name} should have at least one line"

    # ── Canonical procedure ──────────────────────────────────────────

    def test_procedure_standard_resolves_to_eda(self):
        """standard subtype resolves to 'EDA'."""
        presenter = DoctorReportPresenter(
            structured_data={"eda": {"requested_procedure": {"subtype": "standard"}}},
            summary_text="",
            suggested_action={},
        )
        assert "EDA" in presenter._resolve_canonical_procedure_name()

    def test_procedure_gastrostomy(self):
        """gastrostomy subtype resolves to 'EDA para gastrostomia'."""
        presenter = DoctorReportPresenter(
            structured_data={"eda": {"requested_procedure": {"subtype": "gastrostomy"}}},
            summary_text="",
            suggested_action={},
        )
        assert "EDA para gastrostomia" in presenter._resolve_canonical_procedure_name()

    def test_procedure_esophageal_dilation(self):
        """esophageal_dilation subtype resolves to 'EDA para dilatação esofágica'."""
        presenter = DoctorReportPresenter(
            structured_data={"eda": {"requested_procedure": {"subtype": "esophageal_dilation"}}},
            summary_text="",
            suggested_action={},
        )
        assert "EDA para dilatação esofágica" in presenter._resolve_canonical_procedure_name()

    def test_procedure_foreign_body(self):
        """foreign_body subtype resolves to 'EDA para retirada de corpo estranho'."""
        presenter = DoctorReportPresenter(
            structured_data={"eda": {"requested_procedure": {"subtype": "foreign_body"}}},
            summary_text="",
            suggested_action={},
        )
        assert "EDA para retirada de corpo estranho" in presenter._resolve_canonical_procedure_name()

    def test_procedure_echoendoscopy(self):
        """echoendoscopy subtype resolves to 'EDA com ecoendoscopia'."""
        presenter = DoctorReportPresenter(
            structured_data={"eda": {"requested_procedure": {"subtype": "echoendoscopy"}}},
            summary_text="",
            suggested_action={},
        )
        assert "EDA com ecoendoscopia" in presenter._resolve_canonical_procedure_name()

    def test_procedure_echoendoscopy_rulebook_fallback(self):
        """echoendoscopy via rulebook_signals resolves to 'EDA com ecoendoscopia'."""
        presenter = DoctorReportPresenter(
            structured_data={
                "preop_screening": {"rulebook_signals": {"eda_subtype": "echoendoscopy"}},
            },
            summary_text="",
            suggested_action={},
        )
        assert "EDA com ecoendoscopia" in presenter._resolve_canonical_procedure_name()

    def test_context_procedure_shows_echoendoscopy(self):
        """O contexto do relatório exibe 'EDA com ecoendoscopia' no topo."""
        presenter = DoctorReportPresenter(
            structured_data={"eda": {"requested_procedure": {"subtype": "echoendoscopy"}}},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert "EDA com ecoendoscopia" in report["context"]["procedure"]

    def test_procedure_falls_back_to_rulebook(self):
        """When eda.requested_procedure.subtype is absent, falls back to rulebook."""
        presenter = DoctorReportPresenter(
            structured_data={
                "preop_screening": {"rulebook_signals": {"eda_subtype": "gastrostomy"}},
            },
            summary_text="",
            suggested_action={},
        )
        assert "EDA para gastrostomia" in presenter._resolve_canonical_procedure_name()

    # ── Context lines ─────────────────────────────────────────────────

    def test_origin_appears_when_present(self):
        """Origin line includes city, state, hospital, unit when present."""
        presenter = DoctorReportPresenter(
            structured_data={
                "origin_context": {
                    "city": "Salvador",
                    "state_uf": "BA",
                    "hospital": "Hospital Geral",
                    "unit": "UTI",
                }
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        origin = report["context"]["origin"]
        assert "Salvador" in origin
        assert "BA" in origin
        assert "Hospital Geral" in origin
        assert "UTI" in origin

    def test_origin_fallback_when_missing(self):
        """Origin fallback when no evidence."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert "sem evidência" in report["context"]["origin"]

    def test_transfusion_appears_when_present(self):
        """Transfusion lines show 'sim', units, and hemocomponent."""
        presenter = DoctorReportPresenter(
            structured_data={
                "transfusion": {
                    "had_transfusion": "yes",
                    "total_units": 5,
                    "hemocomponent": "plasma",
                }
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        transf_lines = report["context"]["transfusion_lines"]
        assert any("sim" in line for line in transf_lines)
        assert any("5" in line for line in transf_lines)
        assert any("plasma" in line for line in transf_lines)

    def test_transfusion_shows_no_by_default(self):
        """Transfusion defaults to 'não' when absent."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert any("não" in line for line in report["context"]["transfusion_lines"])

    def test_tracked_exams_appear_when_present(self):
        """Tracked exams with recency markers appear."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "Hb",
                        "result_value": "10.0 g/dL",
                        "is_most_recent": True,
                        "exam_datetime_iso": "2025-12-01T10:00:00",
                    },
                    {
                        "exam_label": "Creatinina",
                        "result_value": "1.2 mg/dL",
                        "is_most_recent": False,
                    },
                ]
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        tracked = report["context"]["tracked_exam_lines"]
        assert any("Hb: 10.0 g/dL" in line for line in tracked)
        assert any("Creatinina" in line for line in tracked)
        assert any("mais recente" in line for line in tracked)

    def test_pediatric_marker_when_true(self):
        """Pediatric marker appears when patient is pediatric."""
        presenter = DoctorReportPresenter(
            structured_data={"patient": {"age": 10}},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert "paciente pediátrico" in report["context"]["pediatric"]

    def test_pediatric_marker_from_eda_flag(self):
        """Pediatric marker from eda.is_pediatric flag."""
        presenter = DoctorReportPresenter(
            structured_data={
                "patient": {"age": 30},
                "eda": {"is_pediatric": True},
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert "paciente pediátrico" in report["context"]["pediatric"]

    def test_pediatric_marker_hidden_when_not_pediatric(self):
        """Pediatric marker absent when not pediatric."""
        presenter = DoctorReportPresenter(
            structured_data={"patient": {"age": 45}},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert "pediátrico" not in report["context"]["pediatric"]

    # ── Critical findings ─────────────────────────────────────────────

    def test_critical_findings_show_lab_values(self):
        """Critical findings show Hb, platelets, INR, ECG status."""
        presenter = DoctorReportPresenter(
            structured_data={
                "eda": {
                    "labs": {
                        "hb_g_dl": 10.5,
                        "platelets_per_mm3": 200000,
                        "inr": 1.0,
                    },
                    "ecg": {
                        "report_present": True,
                        "abnormal_flag": False,
                    },
                }
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        findings = "\n".join(report["blocks"]["achados_criticos"])
        assert "Hb" in findings
        assert "10.5" in findings
        assert "Plaquetas" in findings
        assert "200000" in findings
        assert "INR" in findings
        assert "1.0" in findings
        assert "ECG" in findings

    # ── Critical pending ──────────────────────────────────────────────

    def test_critical_pending_shows_lab_and_ecg_status(self):
        """Critical pending shows lab pass/fail and ECG presence."""
        presenter = DoctorReportPresenter(
            structured_data={
                "policy_precheck": {
                    "labs_required": True,
                    "labs_pass": "yes",
                    "ecg_required": False,
                    "ecg_present": True,
                    "labs_failed_items": [],
                },
                "eda": {
                    "labs": {
                        "hb_g_dl": 10.0,
                        "platelets_per_mm3": 200000,
                        "inr": 1.0,
                    },
                },
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        pending = "\n".join(report["blocks"]["pendencias_criticas"])
        assert "Laboratório" in pending
        assert "ECG" in pending

    # ── Decision suggested ───────────────────────────────────────────

    def test_decision_accept_shows_aceitar(self):
        """Accept suggestion maps to 'aceitar'."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={"suggestion": "accept"},
        )
        report = presenter.build_report()
        decision = "\n".join(report["blocks"]["decisao_sugerida"])
        assert "aceitar" in decision

    def test_decision_deny_shows_negar(self):
        """Deny suggestion maps to 'negar'."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={"suggestion": "deny"},
        )
        report = presenter.build_report()
        decision = "\n".join(report["blocks"]["decisao_sugerida"])
        assert "negar" in decision

    # ── Support recommended ──────────────────────────────────────────

    def test_support_anesthesist(self):
        """Support recommendation maps to Portuguese."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={"support_recommendation": "anesthesist"},
        )
        report = presenter.build_report()
        support = "\n".join(report["blocks"]["suporte_recomendado"])
        assert "anestesista" in support

    # ── ASA estimated ────────────────────────────────────────────────

    def test_asa_shows_display_text(self):
        """ASA block shows display_text from suggested_action."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={"asa": {"display_text": "ASA III"}},
        )
        report = presenter.build_report()
        asa = "\n".join(report["blocks"]["asa_estimado"])
        assert "ASA III" in asa

    def test_asa_fallback_to_bucket(self):
        """ASA falls back to bucket mapping when no display_text."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={"asa": {"bucket": "insufficient_data"}},
        )
        report = presenter.build_report()
        asa = "\n".join(report["blocks"]["asa_estimado"])
        assert "não foi possível estimar" in asa

    # ── Objective reason ─────────────────────────────────────────────

    def test_objective_reason_accept(self):
        """Accept objective reason shows 'Aceito com suporte'."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={
                "suggestion": "accept",
                "support_recommendation": "anesthesist",
            },
        )
        report = presenter.build_report()
        reason = "\n".join(report["blocks"]["motivo_objetivo"])
        assert "Aceito" in reason

    def test_objective_reason_deny(self):
        """Deny objective reason shows 'Negado por'."""
        presenter = DoctorReportPresenter(
            structured_data={
                "policy_precheck": {
                    "labs_required": True,
                    "labs_pass": "no",
                    "labs_failed_items": ["Hb"],
                    "ecg_required": False,
                    "excluded_from_eda_flow": False,
                },
                "eda": {
                    "labs": {},
                },
            },
            summary_text="",
            suggested_action={
                "suggestion": "deny",
                "reason_code": "hb_below_threshold",
                "reason_text": "Hb abaixo do limiar: 8.5 g/dL.",
            },
        )
        report = presenter.build_report()
        reason = "\n".join(report["blocks"]["motivo_objetivo"])
        assert "Negado por" in reason

    # ── Recent denial ───────────────────────────────────────────────

    def test_recent_denial_appears_when_provided(self):
        """Recent denial context appears when provided."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={},
            recent_denial_context=_make_recent_denial_context(),
        )
        report = presenter.build_report()
        assert report["recent_denial"] is not None
        denial_lines = report["recent_denial"]["lines"]
        assert any("negado na regulação" in line for line in denial_lines)
        assert any("Contorno clínico elevado" in line for line in denial_lines)
        assert any("2" in line and "últimos 7 dias" in line for line in denial_lines)

    def test_recent_denial_none_when_not_provided(self):
        """Recent denial is None when not provided."""
        presenter = DoctorReportPresenter(
            structured_data=_make_minimal_payload(),
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert report["recent_denial"] is None

    # ── Text report for audit ────────────────────────────────────────

    def test_text_report_includes_all_blocks(self):
        """Text report (for audit) includes all 7 block titles."""
        presenter = DoctorReportPresenter(
            structured_data=_make_complete_payload(),
            summary_text="Paciente com HDA. Hb 8.5.",
            suggested_action=_make_suggested_action_accept(),
            recent_denial_context=_make_recent_denial_context(),
        )
        text = presenter.build_text_report()
        assert "Resumo técnico da regulação" in text
        assert "## Resumo clínico" in text
        assert "## Achados críticos" in text
        assert "## Pendências críticas" in text
        assert "## Decisão sugerida" in text
        assert "## Suporte recomendado" in text
        assert "## ASA estimado" in text
        assert "## Motivo objetivo" in text

    # ── Tracked exam date formatting ───────────────────────────────────────

    def test_tracked_exam_recent_with_datetime_shows_date_and_time(self):
        """Recent tracked exam with datetime shows formatted date and time."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "Hb",
                        "result_value": "10.0 g/dL",
                        "is_most_recent": True,
                        "exam_datetime_iso": "2025-12-01T10:00:00",
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        tracked = report["context"]["tracked_exam_lines"]
        assert len(tracked) == 1
        line = tracked[0]
        assert "Hb" in line
        assert "10.0 g/dL" in line
        assert "mais recente" in line
        assert "01/12/2025" in line
        assert "10:00" in line

    def test_tracked_exam_recent_with_date_only_shows_date(self):
        """Recent tracked exam with date-only ISO shows date without time."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "Hb",
                        "result_value": "10.0 g/dL",
                        "is_most_recent": True,
                        "exam_datetime_iso": "2025-12-01",
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        tracked = report["context"]["tracked_exam_lines"]
        assert len(tracked) == 1
        line = tracked[0]
        assert "01/12/2025" in line
        assert "00:00" not in line

    def test_tracked_exam_recent_without_datetime_keeps_no_date_fallback(self):
        """Recent tracked exam without exam_datetime_iso uses fallback."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "Hb",
                        "result_value": "10.0 g/dL",
                        "is_most_recent": True,
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        tracked = report["context"]["tracked_exam_lines"]
        assert len(tracked) == 1
        line = tracked[0]
        assert "sem data" in line

    def test_tracked_exam_recent_with_invalid_datetime_does_not_crash_and_uses_fallback(self):
        """Invalid exam_datetime_iso does not crash and falls back."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "Hb",
                        "result_value": "10.0 g/dL",
                        "is_most_recent": True,
                        "exam_datetime_iso": "data inválida",
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()  # should not raise
        tracked = report["context"]["tracked_exam_lines"]
        assert len(tracked) == 1
        line = tracked[0]
        assert "sem data" in line

    def test_tracked_exam_not_recent_shows_date_without_recent_marker(self):
        """Non-recent exam with datetime shows date but no 'mais recente' marker."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "Hb",
                        "result_value": "10.0 g/dL",
                        "is_most_recent": False,
                        "exam_datetime_iso": "2025-12-01T10:00:00",
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        tracked = report["context"]["tracked_exam_lines"]
        assert len(tracked) == 1
        line = tracked[0]
        assert "mais recente" not in line
        assert "01/12/2025" in line
        assert "10:00" in line

    # ── Absent exam filtering ────────────────────────────────────────────

    def test_tracked_exam_absent_result_is_not_rendered(self):
        """Tracked exam with 'Sem exame' result is not rendered."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "ECG",
                        "result_value": "Sem exame",
                        "is_most_recent": True,
                        "exam_datetime_iso": "2026-06-06T07:00:00",
                    },
                    {
                        "exam_label": "Hb",
                        "result_value": "12.5 g/dL",
                        "is_most_recent": True,
                        "exam_datetime_iso": "2026-06-06T07:00:00",
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        tracked = report["context"]["tracked_exam_lines"]
        # Only Hb should appear
        assert len(tracked) == 1
        line = tracked[0]
        assert "Hb" in line
        assert "12.5 g/dL" in line
        assert "ECG" not in line
        assert "Sem exame" not in line

    def test_tracked_exam_absent_result_variants_are_not_rendered(self):
        """Various absence result values are filtered out."""
        variants = [
            "Não realizado",
            "Nao realizado",
            "Não consta",
            "Nao consta",
            "Ausente",
            "Sem laudo",
            "Sem resultado",
        ]
        for variant in variants:
            presenter = DoctorReportPresenter(
                structured_data={
                    "tracked_exams": [
                        {
                            "exam_label": "ECG",
                            "result_value": variant,
                            "is_most_recent": False,
                        },
                    ],
                },
                summary_text="",
                suggested_action={},
            )
            report = presenter.build_report()
            tracked = report["context"]["tracked_exam_lines"]
            assert len(tracked) == 0, f"Variant '{variant}' should be filtered out, got: {tracked}"

    def test_tracked_exam_valid_not_recent_shows_date_without_recent_marker(self):
        """Valid non-recent exam with datetime shows date but no recent marker."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "LAB externo",
                        "result_value": "HB 12,1; HT 38,3",
                        "exam_datetime_iso": "2026-05-28T08:30:00",
                        "is_most_recent": False,
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        tracked = report["context"]["tracked_exam_lines"]
        assert len(tracked) == 1
        line = tracked[0]
        assert "LAB externo" in line
        assert "HB 12,1" in line
        assert "28/05/2026" in line
        assert "08:30" in line
        assert "mais recente" not in line

    def test_tracked_exam_valid_recent_shows_date_and_recent_marker(self):
        """Valid recent exam with datetime shows date and recent marker."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "LAB interno",
                        "result_value": "HB 12,9; HT 34,1",
                        "exam_datetime_iso": "2026-06-01T00:00:00",
                        "is_most_recent": True,
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        tracked = report["context"]["tracked_exam_lines"]
        assert len(tracked) == 1
        line = tracked[0]
        assert "LAB interno" in line
        assert "HB 12,9" in line
        assert "01/06/2026" in line
        assert "mais recente" in line

    def test_tracked_exam_valid_invalid_datetime_keeps_exam_without_crashing(self):
        """Valid exam with invalid datetime keeps exam value and does not crash."""
        presenter = DoctorReportPresenter(
            structured_data={
                "tracked_exams": [
                    {
                        "exam_label": "Hb",
                        "result_value": "12.0 g/dL",
                        "exam_datetime_iso": "data inválida",
                        "is_most_recent": True,
                    },
                ],
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()  # should not raise
        tracked = report["context"]["tracked_exam_lines"]
        assert len(tracked) == 1
        line = tracked[0]
        assert "Hb" in line
        assert "12.0 g/dL" in line


# ── Comorbidities line (Slice 001) ─────────────────────────────────────────


class TestComorbiditiesLine:
    """Tests for DoctorReportPresenter comorbidities_line (Slice 001)."""

    def test_comorbidities_line_lists_names_separated_by_comma(self) -> None:
        presenter = DoctorReportPresenter(
            structured_data={
                "preop_screening": {
                    "comorbidities_described": [
                        {"name": "hipertensão arterial sistêmica", "source_text_hint": "HAS"},
                        {"name": "diabetes mellitus tipo 2", "source_text_hint": "DM2"},
                    ]
                }
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert report["context"]["comorbidities_line"] == (
            "Comorbidades descritas: hipertensão arterial sistêmica, diabetes mellitus tipo 2"
        )

    def test_comorbidities_line_empty_list_uses_no_comorbidities_text(self) -> None:
        presenter = DoctorReportPresenter(
            structured_data={"preop_screening": {"comorbidities_described": []}},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert report["context"]["comorbidities_line"] == (
            "Comorbidades descritas: sem comorbidades descritas no relatório"
        )

    def test_comorbidities_line_missing_field_uses_unavailable_text_for_old_cases(self) -> None:
        presenter = DoctorReportPresenter(
            structured_data={"preop_screening": {}},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert report["context"]["comorbidities_line"] == (
            "Comorbidades descritas: extração de comorbidades não disponível neste caso"
        )

    def test_comorbidities_line_missing_preop_screening_uses_unavailable_text(self) -> None:
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert report["context"]["comorbidities_line"] == (
            "Comorbidades descritas: extração de comorbidades não disponível neste caso"
        )

    def test_comorbidities_line_deduplicates_and_ignores_blank_items(self) -> None:
        presenter = DoctorReportPresenter(
            structured_data={
                "preop_screening": {
                    "comorbidities_described": [
                        {"name": "hipertensão arterial sistêmica"},
                        {"name": "diabetes mellitus tipo 2"},
                        {"name": "hipertensão arterial sistêmica"},
                        {"name": ""},
                        {"name": "  "},
                    ]
                }
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert report["context"]["comorbidities_line"] == (
            "Comorbidades descritas: hipertensão arterial sistêmica, diabetes mellitus tipo 2"
        )

    def test_comorbidities_line_all_invalid_items_falls_back_to_empty(self) -> None:
        presenter = DoctorReportPresenter(
            structured_data={
                "preop_screening": {
                    "comorbidities_described": [
                        {"name": ""},
                        {"name": "  "},
                    ]
                }
            },
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert report["context"]["comorbidities_line"] == (
            "Comorbidades descritas: sem comorbidades descritas no relatório"
        )


# ── Priority signals (Slice 003) ────────────────────────────────────────────


def _signal(code: str, detail: str = "") -> dict[str, Any]:
    """Build a persisted v1 priority signal dict."""
    return {
        "code": code,
        "category": {
            "foreign_body": "clinical_alert",
            "caustic_ingestion": "clinical_alert",
            "pediatric": "special_population",
            "echoendoscopy": "special_procedure",
            "esophageal_dilation": "special_procedure",
            "gastrostomy": "special_procedure",
        }[code],
        "detail": detail,
        "version": 1,
    }


class TestDoctorReportPrioritySignals:
    """Slice 003: o relatório médico consome os sinais persistidos."""

    def test_report_exposes_priority_signal_badges(self):
        """build_report expõe badges projetados do valor persistido."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("foreign_body"), _signal("echoendoscopy")],
        )
        report = presenter.build_report()
        badges = report["priority_signal_badges"]
        assert [b["code"] for b in badges] == ["foreign_body", "echoendoscopy"]

    def test_presenter_uses_persisted_signals_without_source_text(self):
        """Badge e alerta vêm do valor persistido, não do texto bruto."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("foreign_body")],
            source_text="",  # texto vazio — nada deve ser redetectado
        )
        report = presenter.build_report()
        assert [b["code"] for b in report["priority_signal_badges"]] == ["foreign_body"]
        findings = "\n".join(report["blocks"]["achados_criticos"])
        assert "corpo estranho" in findings.lower()

    def test_persisted_signal_present_without_raw_text(self):
        """Sinal persistido aparece mesmo com texto bruto vazio."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("caustic_ingestion", "há 3 semanas")],
            source_text="",
        )
        report = presenter.build_report()
        findings = "\n".join(report["blocks"]["achados_criticos"])
        assert "ingestão cáustica" in findings.lower()
        assert "há 3 semanas" in findings

    def test_presenter_without_signals_defaults_safely(self):
        """Sem priority_signals o presenter funciona com default seguro."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
        )
        report = presenter.build_report()
        assert report["priority_signal_badges"] == []

    def test_context_prioritarios_appear_once_before_summary(self):
        """Linha de contextos aparece uma vez, antes do resumo LLM."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="Paciente com HDA.",
            suggested_action={},
            priority_signals=[
                _signal("echoendoscopy"),
                _signal("pediatric", "10 anos"),
                _signal("esophageal_dilation"),
            ],
        )
        report = presenter.build_report()
        summary = report["blocks"]["resumo_clinico"]
        assert len(summary) >= 2
        context_line = summary[0]
        assert context_line.startswith("Contextos prioritários:")
        assert "Pediatria — 10 anos" in context_line
        assert "Ecoendoscopia" in context_line
        assert "Dilatação esofágica" in context_line
        context_lines = [line for line in summary if line.startswith("Contextos prioritários:")]
        assert len(context_lines) == 1
        assert "Paciente com HDA." in "\n".join(summary[1:])

    def test_context_order_canonical(self):
        """Ordem canônica: Pediatria → Ecoendoscopia → Dilatação → Gastrostomia."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[
                _signal("gastrostomy"),
                _signal("echoendoscopy"),
                _signal("pediatric"),
                _signal("esophageal_dilation"),
            ],
        )
        report = presenter.build_report()
        context_line = report["blocks"]["resumo_clinico"][0]
        assert context_line.index("Pediatria") < context_line.index("Ecoendoscopia")
        assert context_line.index("Ecoendoscopia") < context_line.index("Dilatação esofágica")
        assert context_line.index("Dilatação esofágica") < context_line.index("Gastrostomia")

    def test_no_context_line_without_context_signals(self):
        """Sem sinais de contexto, nenhuma linha de contextos é criada."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="Paciente com HDA.",
            suggested_action={},
            priority_signals=[_signal("foreign_body")],
        )
        report = presenter.build_report()
        summary = "\n".join(report["blocks"]["resumo_clinico"])
        assert "Contextos prioritários" not in summary

    def test_fallback_when_summary_empty_keeps_context_line(self):
        """Fallback atual com summary vazio mantém a linha de contextos no início."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("pediatric", "8 anos")],
        )
        report = presenter.build_report()
        summary = report["blocks"]["resumo_clinico"]
        assert summary[0].startswith("Contextos prioritários:")
        assert "Pediatria — 8 anos" in summary[0]
        assert any("Resumo clínico não informado" in line for line in summary)

    def test_foreign_body_alert_before_labs(self):
        """Corpo estranho aparece antes de Hb/Plaquetas/INR/ECG."""
        presenter = DoctorReportPresenter(
            structured_data={"eda": {"labs": {"hb_g_dl": 8.5, "platelets_per_mm3": 120000, "inr": 1.1}}},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("foreign_body")],
        )
        report = presenter.build_report()
        findings = report["blocks"]["achados_criticos"]
        fb_idx = next(i for i, line in enumerate(findings) if "corpo estranho" in line.lower())
        hb_idx = next(i for i, line in enumerate(findings) if line.startswith("- Hb:"))
        assert fb_idx < hb_idx

    def test_caustic_alert_with_time_before_labs(self):
        """Cáustico persistido com detail de tempo aparece antes de Hb."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("caustic_ingestion", "há 2 dias")],
        )
        report = presenter.build_report()
        findings = report["blocks"]["achados_criticos"]
        ci_idx = next(i for i, line in enumerate(findings) if "ingestão cáustica" in line.lower())
        hb_idx = next(i for i, line in enumerate(findings) if line.startswith("- Hb:"))
        assert ci_idx < hb_idx
        assert "há 2 dias" in findings[ci_idx]

    def test_caustic_not_duplicated(self):
        """Cáustico não aparece duplicado entre context e achados."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("caustic_ingestion", "há 2 dias")],
            source_text="Paciente ingeriu soda cáustica há 2 dias.",
        )
        report = presenter.build_report()
        all_lines: list[str] = list(report["blocks"]["achados_criticos"])
        all_lines.extend(report["context"].get("clinical_alert_lines", []))
        count = sum(1 for line in all_lines if "ingestão cáustica" in line.lower())
        assert count == 1

    def test_raw_text_alone_does_not_create_canonical_highlight(self):
        """Sem sinal persistido, texto bruto sozinho não cria destaque canônico."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[],
            source_text="Paciente ingeriu soda cáustica há 3 semanas. Suspeita de corpo estranho.",
        )
        report = presenter.build_report()
        findings = "\n".join(report["blocks"]["achados_criticos"])
        assert "ingestão cáustica" not in findings.lower()
        assert "corpo estranho" not in findings.lower()
        assert report["priority_signal_badges"] == []

    def test_procedure_name_combination_ordered(self):
        """Coexistência eco+dilatação+gastro → nome combinado com ordem estável."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[
                _signal("gastrostomy"),
                _signal("echoendoscopy"),
                _signal("esophageal_dilation"),
            ],
        )
        report = presenter.build_report()
        assert report["context"]["procedure"] == (
            "procedimento solicitado: EDA com ecoendoscopia, dilatação esofágica e gastrostomia"
        )

    def test_procedure_name_two_signal_combination(self):
        """Eco + dilatação → 'EDA com ecoendoscopia e dilatação esofágica'."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("echoendoscopy"), _signal("esophageal_dilation")],
        )
        report = presenter.build_report()
        assert report["context"]["procedure"] == (
            "procedimento solicitado: EDA com ecoendoscopia e dilatação esofágica"
        )

    def test_procedure_single_signal_preserves_existing_names(self):
        """Sinal único preserva os nomes existentes."""
        cases = [
            ([_signal("gastrostomy")], "EDA para gastrostomia"),
            ([_signal("esophageal_dilation")], "EDA para dilatação esofágica"),
            ([_signal("echoendoscopy")], "EDA com ecoendoscopia"),
            ([_signal("foreign_body")], "EDA para retirada de corpo estranho"),
        ]
        for signals, expected in cases:
            presenter = DoctorReportPresenter(
                structured_data={},
                summary_text="",
                suggested_action={},
                priority_signals=signals,
            )
            assert presenter._resolve_canonical_procedure_name() == expected

    def test_text_report_contains_contexts_and_alerts(self):
        """build_text_report contém as mesmas linhas determinísticas da tela."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="Paciente com HDA.",
            suggested_action={},
            priority_signals=[
                _signal("pediatric", "10 anos"),
                _signal("foreign_body"),
                _signal("caustic_ingestion", "há 1 semana"),
            ],
        )
        text = presenter.build_text_report()
        assert "Contextos prioritários:" in text
        assert "Pediatria — 10 anos" in text
        assert "corpo estranho" in text.lower()
        assert "ingestão cáustica" in text.lower()
        assert "há 1 semana" in text
        assert "## Resumo clínico" in text
        assert "## Achados críticos" in text


class TestCausticIngestionAlertInReport:
    """Slice 003: representação canônica de cáustico em Achados críticos.

    O caminho antigo (detecção no source_text → clinical_alert_lines no meta)
    foi removido: o detector vive apenas em apps/cases/priority_signals.py e a
    apresentação canônica é a linha documental no início de Achados críticos,
    construída exclusivamente do valor persistido.
    """

    def test_persisted_caustic_with_relative_time(self):
        """Cáustico persistido com tempo aparece em Achados críticos."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("caustic_ingestion", "há 3 semanas")],
        )
        report = presenter.build_report()
        findings = "\n".join(report["blocks"]["achados_criticos"]).lower()
        assert "ingestão cáustica/corrosiva" in findings
        assert "há 3 semanas" in findings
        assert "clinical_alert_lines" not in report["context"]

    def test_persisted_caustic_without_time(self):
        """Cáustico persistido sem detail ainda gera linha documental."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("caustic_ingestion")],
        )
        report = presenter.build_report()
        findings = "\n".join(report["blocks"]["achados_criticos"]).lower()
        assert "ingestão cáustica/corrosiva" in findings

    def test_source_text_no_longer_triggers_caustic_alert(self):
        """Compatibilidade: texto bruto sozinho não cria destaque canônico."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[],
            source_text="Paciente ingeriu soda cáustica há 3 semanas.",
        )
        report = presenter.build_report()
        findings = "\n".join(report["blocks"]["achados_criticos"]).lower()
        assert "ingestão cáustica" not in findings.lower()
        assert report["priority_signal_badges"] == []

    def test_negated_text_not_signaled(self):
        """Negação textual continua sem gerar sinal (sem persistência)."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[],
            source_text="Paciente nega ingestão de cáustico.",
        )
        report = presenter.build_report()
        findings = "\n".join(report["blocks"]["achados_criticos"]).lower()
        assert "ingestão cáustica" not in findings.lower()

    def test_text_report_includes_caustic_from_persisted_signal(self):
        """build_text_report inclui a linha canônica do cáustico persistido."""
        presenter = DoctorReportPresenter(
            structured_data={},
            summary_text="",
            suggested_action={},
            priority_signals=[_signal("caustic_ingestion", "há 3 semanas")],
        )
        text = presenter.build_text_report()
        assert "ingestão cáustica/corrosiva" in text.lower()
        assert "há 3 semanas" in text
