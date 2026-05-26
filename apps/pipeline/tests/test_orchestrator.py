"""Integration tests for pipeline orchestrator."""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.orchestrator import run_pipeline


def _reload(case: Case) -> Case:
    """Re-fetch case from DB (refresh_from_db conflicts with FSM protected field)."""
    return Case.objects.get(case_id=case.case_id)


# ── Test fixtures ────────────────────────────────────────────────────────────


def _make_case(user, extracted_text="Paciente com dispepsia. Solicito EDA.") -> Case:
    """Create a minimal Case ready for pipeline execution."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number="12345",
        extracted_text=extracted_text,
    )
    # Transition: NEW → R1_ACK_PROCESSING → EXTRACTING → LLM_STRUCT
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()
    return case


def _eda_llm1_response() -> str:
    """LLM1 structured data for a standard EDA case that passes all checks."""
    return json.dumps(
        {
            "schema_version": "1.1",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": "Paciente", "age": 35, "sex": "F"},
            "summary": {
                "one_liner": "EDA eletiva indicada.",
                "bullet_points": ["Ponto 1", "Ponto 2", "Ponto 3"],
            },
            "extraction_quality": {
                "confidence": "alta",
                "missing_fields": [],
                "notes": None,
            },
            "preop_screening": {
                "exam_type": "eda",
                "has_cardiovascular_disease": "no",
                "has_active_respiratory_symptoms": "no",
                "has_prior_respiratory_disease": "no",
                "has_ecg_report": "unknown",
                "has_chest_xray_report": "unknown",
                "hb_g_dl": 13.0,
                "platelets_per_mm3": 200000,
                "inr": 1.0,
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
            },
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
            "eda": {
                "indication_category": "dyspepsia",
                "exclusion_type": "none",
                "is_pediatric": False,
                "foreign_body_suspected": False,
                "requested_procedure": {
                    "name": "EDA",
                    "urgency": "eletivo",
                    "subtype": "standard",
                },
                "labs": {
                    "hb_g_dl": 13.0,
                    "platelets_per_mm3": 200000,
                    "inr": 1.0,
                    "source_text_hint": None,
                },
                "ecg": {
                    "report_present": "unknown",
                    "abnormal_flag": "unknown",
                    "source_text_hint": None,
                },
            },
        }
    )


def _eda_llm2_accept_response(case_id: str = "case-001") -> str:
    """LLM2 suggestion: accept."""
    return json.dumps(
        {
            "schema_version": "1.1",
            "language": "pt-BR",
            "case_id": case_id,
            "agency_record_number": "12345",
            "suggestion": "accept",
            "support_recommendation": "none",
            "rationale": {
                "short_reason": "Critérios atendidos.",
                "details": ["Sem contraindicação relevante.", "Exames compatíveis."],
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
    )


def _eda_llm2_deny_response() -> str:
    """LLM2 suggestion: deny."""
    return json.dumps(
        {
            "schema_version": "1.1",
            "language": "pt-BR",
            "case_id": "case-001",
            "agency_record_number": "12345",
            "suggestion": "deny",
            "support_recommendation": "none",
            "rationale": {
                "short_reason": "Exames incompletos.",
                "details": ["Há pendências laboratoriais.", "Necessita revisão manual."],
                "missing_info_questions": [],
            },
            "policy_alignment": {
                "excluded_request": False,
                "labs_ok": "no",
                "ecg_ok": "yes",
                "pediatric_flag": False,
                "notes": None,
            },
            "confidence": "media",
        }
    )


def _non_eda_llm1_response() -> str:
    """LLM1 data for a non-EDA exam (should trigger scope gate)."""
    return json.dumps(
        {
            "schema_version": "1.1",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": "Paciente", "age": 50, "sex": "M"},
            "summary": {
                "one_liner": "Colonoscopia solicitada.",
                "bullet_points": ["Ponto 1", "Ponto 2", "Ponto 3"],
            },
            "extraction_quality": {
                "confidence": "alta",
                "missing_fields": [],
                "notes": None,
            },
            "preop_screening": {
                "exam_type": "non_eda",
                "has_cardiovascular_disease": "no",
                "has_active_respiratory_symptoms": "no",
                "has_prior_respiratory_disease": "no",
                "has_ecg_report": "unknown",
                "has_chest_xray_report": "unknown",
                "hb_g_dl": None,
                "platelets_per_mm3": None,
                "inr": None,
                "evidence_spans": [
                    {"field_path": "exam_type", "excerpt": "colonoscopia"},
                ],
                "rulebook_signals": {
                    "eda_subtype": "unknown",
                },
            },
            "policy_precheck": {
                "excluded_from_eda_flow": True,
                "exclusion_reason": "non_eda",
                "labs_required": False,
                "labs_pass": "unknown",
                "labs_failed_items": [],
                "ecg_required": False,
                "ecg_present": "unknown",
                "pediatric_flag": False,
                "notes": None,
            },
            "eda": {
                "indication_category": "unknown",
                "exclusion_type": "unknown",
                "is_pediatric": False,
                "foreign_body_suspected": False,
                "requested_procedure": {
                    "name": "Colonoscopia",
                    "urgency": "eletivo",
                    "subtype": "unknown",
                },
                "labs": {
                    "hb_g_dl": None,
                    "platelets_per_mm3": None,
                    "inr": None,
                    "source_text_hint": None,
                },
                "ecg": {
                    "report_present": "unknown",
                    "abnormal_flag": "unknown",
                    "source_text_hint": None,
                },
            },
        }
    )


def _low_hb_llm1_response() -> str:
    """LLM1 data with critically low Hb (triggers preop deny)."""
    return json.dumps(
        {
            "schema_version": "1.1",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": "Paciente", "age": 45, "sex": "F"},
            "summary": {
                "one_liner": "EDA eletiva.",
                "bullet_points": ["Hb 5.0", "Ponto 2", "Ponto 3"],
            },
            "extraction_quality": {
                "confidence": "alta",
                "missing_fields": [],
                "notes": None,
            },
            "preop_screening": {
                "exam_type": "eda",
                "has_cardiovascular_disease": "no",
                "has_active_respiratory_symptoms": "no",
                "has_prior_respiratory_disease": "no",
                "has_ecg_report": "unknown",
                "has_chest_xray_report": "unknown",
                "hb_g_dl": 5.0,
                "platelets_per_mm3": 200000,
                "inr": 1.0,
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
            },
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
            "eda": {
                "indication_category": "dyspepsia",
                "exclusion_type": "none",
                "is_pediatric": False,
                "foreign_body_suspected": False,
                "requested_procedure": {
                    "name": "EDA",
                    "urgency": "eletivo",
                    "subtype": "standard",
                },
                "labs": {
                    "hb_g_dl": 5.0,
                    "platelets_per_mm3": 200000,
                    "inr": 1.0,
                    "source_text_hint": None,
                },
                "ecg": {
                    "report_present": "unknown",
                    "abnormal_flag": "unknown",
                    "source_text_hint": None,
                },
            },
        }
    )


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPipelineFullRun:
    """Fluxo completo: EDA → LLM1 + LLM2 + policy → WAIT_DOCTOR."""

    def test_pipeline_full_run(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir1", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _eda_llm2_accept_response(str(case.case_id))])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_system_prompt="sp2",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.structured_data is not None
        assert case.summary_text == "EDA eletiva indicada."
        assert case.suggested_action is not None
        assert case.suggested_action.get("suggestion") == "accept"

    def test_pipeline_persist_structured_data(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir2", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _eda_llm2_accept_response(str(case.case_id))])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_system_prompt="sp2",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        case = _reload(case)
        assert isinstance(case.structured_data, dict)

    def test_pipeline_persist_summary_text(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _eda_llm2_accept_response(str(case.case_id))])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_system_prompt="sp2",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        case = _reload(case)
        assert case.summary_text == "EDA eletiva indicada."

    def test_pipeline_persist_suggested_action(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _eda_llm2_accept_response(str(case.case_id))])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_system_prompt="sp2",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        case = _reload(case)
        assert isinstance(case.suggested_action, dict)
        assert case.suggested_action.get("suggestion") == "accept"
        assert "preop_gate" in case.suggested_action
        assert "support_recommendation" in case.suggested_action
        assert "policy_alignment" in case.suggested_action


@pytest.mark.django_db
class TestPipelineGeneratesEvents:
    """Orchestrator deve gerar eventos de auditoria em cada etapa."""

    def test_pipeline_generates_events(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir5", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _eda_llm2_accept_response(str(case.case_id))])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_system_prompt="sp2",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        events = CaseEvent.objects.filter(case=case).order_by("timestamp")
        event_types = [e.event_type for e in events]

        assert "CASE_CREATED" in event_types
        assert "CASE_START_PROCESSING" in event_types
        assert "CASE_START_EXTRACTION" in event_types
        assert "CASE_EXTRACTION_OK" in event_types
        assert "LLM1_OK" in event_types
        assert "EDA_PREOP_POLICY_DECISION" in event_types
        assert "LLM2_OK" in event_types
        assert "CASE_READY_FOR_DOCTOR" in event_types


@pytest.mark.django_db
class TestPipelineLlm1Failure:
    """Falha no LLM1 → estado FAILED."""

    def test_pipeline_llm1_failure(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir6", password="pw")
        case = _make_case(user)

        # LLM1 returns garbage (not valid JSON)
        client = StaticLlmClient(response_text="not json at all")

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
        )

        case = _reload(case)
        assert case.status == CaseStatus.FAILED

        events = CaseEvent.objects.filter(case=case).order_by("timestamp")
        event_types = [e.event_type for e in events]
        assert "PIPELINE_FAILED" in event_types
        assert "LLM1_FAILED" in event_types


@pytest.mark.django_db
class TestPipelineScopeGated:
    """Non-EDA → scope gate ativa → WAIT_R1_CLEANUP_THUMBS sem LLM2."""

    def test_pipeline_scope_gated(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir7", password="pw")
        case = _make_case(user)

        # LLM1 returns non-EDA data; LLM2 won't be called
        client = RecordingLlmClient(responses=[_non_eda_llm1_response()])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        # LLM2 was never called (only 1 call = LLM1)
        assert len(client.calls) == 1

        # suggested_action is the scope gate result
        assert case.suggested_action is not None
        assert case.suggested_action.get("decision") == "manual_review_required"

        # Scope gate events recorded — EDA_SCOPE_GATED_MANUAL_REVIEW, SCOPE_GATE_BYPASS, FINAL_REPLY_POSTED
        events = CaseEvent.objects.filter(case=case).order_by("timestamp")
        event_types = [e.event_type for e in events]
        assert "EDA_SCOPE_GATED_MANUAL_REVIEW" in event_types
        assert "SCOPE_GATE_BYPASS" in event_types
        assert "FINAL_REPLY_POSTED" in event_types
        assert "LLM2_OK" not in event_types

    def test_pipeline_scope_gated_unknown_exam_type(self, django_user_model) -> None:
        """unknown exam_type → WAIT_R1_CLEANUP_THUMBS sem LLM2."""
        user = django_user_model.objects.create_user(username="nir_unk", password="pw")

        # Use NON-EDA response but modify exam_type to 'unknown'
        import json

        unknown_data = json.loads(_non_eda_llm1_response())
        unknown_data["preop_screening"]["exam_type"] = "unknown"

        case = _make_case(user)
        client = RecordingLlmClient(responses=[json.dumps(unknown_data)])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        # LLM2 was never called
        assert len(client.calls) == 1

        # suggested_action is the scope gate result
        assert case.suggested_action is not None
        assert case.suggested_action.get("decision") == "manual_review_required"
        assert case.suggested_action.get("reason_code") == "unknown_exam_type"

        # No LLM2_OK
        event_types = [e.event_type for e in CaseEvent.objects.filter(case=case)]
        assert "LLM2_OK" not in event_types
        assert "EDA_SCOPE_GATED_MANUAL_REVIEW" in event_types
        assert "FINAL_REPLY_POSTED" in event_types

    def test_pipeline_scope_gated_does_not_appear_in_doctor_queue(self, django_user_model) -> None:
        """Scope-gated case (WAIT_R1_CLEANUP_THUMBS) não aparece na fila WAIT_DOCTOR."""
        user = django_user_model.objects.create_user(username="nir_filter", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_non_eda_llm1_response()])
        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
        )

        case = _reload(case)
        # Not in WAIT_DOCTOR
        assert case.status != CaseStatus.WAIT_DOCTOR
        # Doctor queue would filter by WAIT_DOCTOR — this case won't appear
        from apps.cases.models import Case

        wait_doctor_count = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count()
        assert wait_doctor_count == 0


@pytest.mark.django_db
class TestPipelinePreopDenyOverridesLlm2Accept:
    """Policy engine deny deve sobrescrever LLM2 accept via reconciliation."""

    def test_pipeline_preop_deny_overrides_llm2_accept(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir8", password="pw")
        case = _make_case(user)

        # LLM1: low Hb triggers preop deny
        # LLM2: says accept (should be overridden)
        client = RecordingLlmClient(
            responses=[
                _low_hb_llm1_response(),
                _eda_llm2_accept_response(str(case.case_id)),
            ]
        )

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_system_prompt="sp2",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.suggested_action is not None

        # Reconciliation should override suggestion to "deny"
        assert case.suggested_action.get("suggestion") == "deny"

        # Preop decision metadata should reflect the denial
        preop_gate = case.suggested_action.get("preop_gate", {})
        assert isinstance(preop_gate, dict)
        assert preop_gate.get("decision") == "deny"

        # Contradictions are recorded (may be empty — Hb threshold is preop, not reconcile)
        contradictions = case.suggested_action.get("contradictions", [])
        assert isinstance(contradictions, list)


@pytest.mark.django_db
class TestPipelineSupportSynthesisSaved:
    """Support recommendation deve ser salvo no suggested_action."""

    def test_pipeline_support_synthesis_saved(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir9", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _eda_llm2_accept_response(str(case.case_id))])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_system_prompt="sp2",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        case = _reload(case)
        assert case.suggested_action is not None

        assert "support_recommendation" in case.suggested_action
        assert isinstance(case.suggested_action["support_recommendation"], str)

        assert "asa" in case.suggested_action
        asa = case.suggested_action["asa"]
        assert isinstance(asa, dict)
        assert "bucket" in asa
        assert "display_text" in asa


@pytest.mark.django_db
class TestQClusterSettings:
    """Q_CLUSTER deve ter ALT_CLUSTERS com clusters e retry > timeout."""

    @staticmethod
    def _cluster() -> dict[str, Any]:
        from django.conf import settings

        return dict(settings.Q_CLUSTER)

    @staticmethod
    def _alt() -> dict[str, Any]:
        return dict(TestQClusterSettings._cluster().get("ALT_CLUSTERS", {}))

    @staticmethod
    def _sub(name: str) -> dict[str, Any]:
        return dict(TestQClusterSettings._alt().get(name, {}))

    def test_alt_clusters_contains_pdf_and_llm(self) -> None:
        alt_clusters = self._alt()
        assert "pdf" in alt_clusters, "ALT_CLUSTERS must contain 'pdf' cluster"
        assert "llm" in alt_clusters, "ALT_CLUSTERS must contain 'llm' cluster"

    def test_default_cluster_retry_greater_than_timeout(self) -> None:
        c = self._cluster()
        timeout = int(c.get("timeout", 0))
        retry = int(c.get("retry", 0))
        assert retry > timeout, f"Default cluster: retry ({retry}) must be > timeout ({timeout})"

    def test_pdf_cluster_retry_greater_than_timeout(self) -> None:
        pdf = self._sub("pdf")
        timeout = int(pdf.get("timeout", 0))
        retry = int(pdf.get("retry", 0))
        assert retry > timeout, f"PDF cluster: retry ({retry}) must be > timeout ({timeout})"

    def test_llm_cluster_retry_greater_than_timeout(self) -> None:
        llm = self._sub("llm")
        timeout = int(llm.get("timeout", 0))
        retry = int(llm.get("retry", 0))
        assert retry > timeout, f"LLM cluster: retry ({retry}) must be > timeout ({timeout})"

    def test_llm_alt_cluster_has_workers_1(self) -> None:
        llm = self._sub("llm")
        workers = int(llm.get("workers", 0))
        assert workers <= 2, f"LLM cluster workers ({workers}) should be conservative (<=2)"

    def test_pdf_alt_cluster_has_workers_at_least_1(self) -> None:
        pdf = self._sub("pdf")
        workers = int(pdf.get("workers", 0))
        assert workers >= 1, f"PDF cluster must have at least 1 worker, got {workers}"


class TestEnqueuePipeline:
    """enqueue_pipeline deve chamar django-q2 async_task com cluster llm."""

    def test_enqueue_pipeline_creates_task(self, django_user_model, monkeypatch) -> None:
        user = django_user_model.objects.create_user(username="nir10", password="pw")
        case = _make_case(user)

        from apps.pipeline.tasks import enqueue_pipeline

        calls: list[tuple[object, ...]] = []

        def _capture(*args: object, **kwargs: object) -> None:
            calls.append((args, kwargs))

        monkeypatch.setattr("apps.pipeline.tasks.async_task", _capture)

        enqueue_pipeline(case.case_id)

        assert len(calls) == 1
        call_args, call_kwargs = calls[0]
        assert isinstance(call_args, tuple)
        assert isinstance(call_kwargs, dict)
        assert call_args[0] == "apps.pipeline.tasks.execute_pipeline"
        assert call_args[1] == str(case.case_id)

        # Must route to cluster "llm"
        q_options: dict[str, Any] = call_kwargs.get("q_options", {})
        assert q_options.get("cluster") == "llm", f"Expected cluster='llm', got {q_options.get('cluster')}"
        assert q_options.get("task_name") == f"llm:{case.case_id}", (
            f"Expected task_name='llm:{case.case_id}', got {q_options.get('task_name')}"
        )


@pytest.mark.django_db
class TestPromptResolutionFromDB:
    """Orchestrator resolves canonical prompt names from DB."""

    def test_uses_llm1_system_from_db(self, django_user_model) -> None:
        """When l1m1_system exists in DB, orchestrator uses it."""
        from apps.llm.models import PromptTemplate

        user = django_user_model.objects.create_user(username="npr1", password="pw")
        case = _make_case(user)

        # Seed canonical prompt with recognizable content
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="DB_SYSTEM_PROMPT_LLM1",
            is_active=True,
        )

        # Capture what prompts are sent to LLM
        client = RecordingLlmClient(responses=[_eda_llm1_response(), _eda_llm2_accept_response(str(case.case_id))])

        # Run WITHOUT injecting llm1_system_prompt — must come from DB
        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_system_prompt="sp2",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        # Verify the LLM received the DB prompt
        llm1_call = client.calls[0]
        assert llm1_call["system_prompt"] == "DB_SYSTEM_PROMPT_LLM1"

    def test_uses_llm2_system_from_db(self, django_user_model) -> None:
        """When llm2_system exists in DB, orchestrator uses it."""
        from apps.llm.models import PromptTemplate

        user = django_user_model.objects.create_user(username="npr2", password="pw")
        case = _make_case(user)

        PromptTemplate.objects.create(
            name="llm2_system",
            version=1,
            content="DB_SYSTEM_PROMPT_LLM2",
            is_active=True,
        )

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _eda_llm2_accept_response(str(case.case_id))])

        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="{case_id}|{agency_record_number}|{extracted_text}",
            llm2_user_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        llm2_call = client.calls[1]
        assert llm2_call["system_prompt"] == "DB_SYSTEM_PROMPT_LLM2"

    def test_fallback_does_not_contain_endoscopy_report(self) -> None:
        """When no prompt in DB, fallback must not mention 'relatório de endoscopia'."""
        from apps.pipeline.orchestrator import _get_prompt_content

        # Ensure no prompts in DB
        for name in ["llm1_system", "llm1_user", "llm2_system", "llm2_user"]:
            fallback = _get_prompt_content(name)
            assert "relatório de endoscopia" not in fallback.lower(), (
                f"Fallback for {name} contains 'relatório de endoscopia'"
            )
