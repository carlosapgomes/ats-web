"""Integration tests for pipeline orchestrator (procedure-neutral v2, Slice 007).

Slice 007: o orchestrator é exclusivamente v2. Casos com projeção declarada
(``CaseProcedure``) percorrem o contrato 2.0; casos sem rows declarados falham
de modo explícito/auditável (R1), sem cair em perfil singular/EDA nem em
prompt 1.1. Fixtures criam ``CaseProcedure`` explicitamente (R5).
"""

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


def _to_llm_struct(case: Case, user: Any) -> Case:
    """Transition: NEW → R1_ACK_PROCESSING → EXTRACTING → LLM_STRUCT."""
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()
    return case


def _make_case(
    user: Any,
    *,
    extracted_text: str = "Paciente com dispepsia. Solicito EDA.",
    declared: tuple[str, ...] = ("eda",),
) -> Case:
    """Create a Case with declared CaseProcedure rows ready for v2 pipeline."""
    from apps.cases.procedures import set_declared_procedures

    case = Case.objects.create(
        created_by=user,
        agency_record_number="12345",
        extracted_text=extracted_text,
    )
    set_declared_procedures(case=case, procedure_types=declared, actor=user)
    return _to_llm_struct(case, user)


def _make_bare_case(user: Any, *, extracted_text: str = "Paciente com dispepsia.") -> Case:
    """Create a Case WITHOUT declared projection (R1 fail-closed scenario)."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number="12345",
        extracted_text=extracted_text,
    )
    return _to_llm_struct(case, user)


def _min_exam_ok() -> dict[str, str]:
    return {
        "hb_numeric_present": "yes",
        "platelets_numeric_present": "yes",
        "tp_inr_rni_numeric_present": "yes",
        "ttpa_present": "yes",
        "urea_present": "yes",
        "creatinine_present": "yes",
    }


def _llm1_v2(
    *,
    procedures: list[dict[str, Any]],
    one_liner: str = "EDA eletiva indicada.",
    hb_g_dl: float = 13.0,
    age: int = 35,
) -> str:
    """LLM1 procedure-neutral v2 response."""
    return json.dumps(
        {
            "schema_version": "2.0",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": "Paciente", "age": age, "sex": "F", "document_id": None},
            "common_preop": {
                "labs": {"hb_g_dl": hb_g_dl, "platelets_per_mm3": 200000, "inr": 1.0, "source_text_hint": None},
                "ecg": {"report_present": "unknown", "abnormal_flag": "unknown", "source_text_hint": None},
                "asa": {"bucket": "I-II", "source_text_hint": None},
                "cardiovascular_risk": {"level": "low", "source_text_hint": None},
                "rulebook_signals": {
                    "eda_subtype": "standard",
                    "minimum_exam_evidence": _min_exam_ok(),
                    "conditional_exam_requirements": {},
                    "clinical_flags": {},
                },
                "comorbidities_described": [],
                "medications_described": [],
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
            "summary": {"one_liner": one_liner, "bullet_points": ["Ponto 1", "Ponto 2", "Ponto 3"]},
            "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
            "origin_context": {
                "city": None,
                "hospital": None,
                "unit": None,
                "state_uf": None,
                "source_text_hint": None,
            },
            "transfusion": {"had_transfusion": "no"},
            "tracked_exams": [],
        }
    )


def _eda_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "eda",
        "name": "EDA",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "subtype": "standard",
        "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito EDA"}],
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
        "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito colonoscopia"}],
    }
    item.update(overrides)
    return item


def _eda_llm1_response() -> str:
    return _llm1_v2(procedures=[_eda_procedure()])


def _low_hb_llm1_response() -> str:
    return _llm1_v2(procedures=[_eda_procedure()], one_liner="EDA eletiva.", hb_g_dl=5.0)


def _priority_signals_llm1_response() -> str:
    """EDA foreign-body + pediatric + echoendoscopy (from text)."""
    return _llm1_v2(
        procedures=[
            _eda_procedure(
                name="EDA com ecoendoscopia",
                indication_category="foreign_body",
                subtype="foreign_body",
            )
        ],
        one_liner="Criança com corpo estranho; EDA com ecoendoscopia indicada.",
        age=10,
    )


def _llm2_v2(case_id: str, *, suggestion: str = "accept", procedure_type: str = "eda") -> str:
    return json.dumps(
        {
            "schema_version": "2.0",
            "language": "pt-BR",
            "case_id": case_id,
            "agency_record_number": "12345",
            "procedure_recommendations": [
                {
                    "procedure_type": procedure_type,
                    "suggestion": suggestion,
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
            ],
            "global_support_recommendation": "none",
            "summary": None,
        }
    )


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPipelineFullRun:
    """Fluxo completo v2: EDA → LLM1 + LLM2 + policy → WAIT_DOCTOR."""

    def test_pipeline_full_run(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir1", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

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
        recs = case.suggested_action["procedure_recommendations"]
        assert recs[0]["suggestion"] == "accept"

    def test_pipeline_persist_structured_data(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir2", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert isinstance(case.structured_data, dict)
        assert case.structured_data["schema_version"] == "2.0"

    def test_pipeline_persist_summary_text(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir3", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.summary_text == "EDA eletiva indicada."

    def test_pipeline_persist_suggested_action(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert isinstance(case.suggested_action, dict)
        rec = case.suggested_action["procedure_recommendations"][0]
        assert rec["suggestion"] == "accept"
        assert "preop_decision" in rec
        assert "support_recommendation" in rec
        assert "policy_alignment" in rec


@pytest.mark.django_db
class TestPipelineGeneratesEvents:
    """Orchestrator deve gerar eventos de auditoria em cada etapa (v2)."""

    def test_pipeline_generates_events(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir5", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        events = CaseEvent.objects.filter(case=case).order_by("timestamp")
        event_types = [e.event_type for e in events]

        assert "CASE_CREATED" in event_types
        assert "CASE_START_PROCESSING" in event_types
        assert "CASE_START_EXTRACTION" in event_types
        assert "CASE_EXTRACTION_OK" in event_types
        assert "CASE_PROCEDURES_DECLARED" in event_types
        assert "CASE_PROCEDURES_DETECTED" in event_types
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

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.FAILED

        events = CaseEvent.objects.filter(case=case).order_by("timestamp")
        event_types = [e.event_type for e in events]
        assert "PIPELINE_FAILED" in event_types
        assert "LLM1_FAILED" in event_types


@pytest.mark.django_db
class TestPipelineFailClosed:
    """R1: caso sem procedimentos declarados válidos falha de modo explícito/auditável."""

    def test_case_without_declared_procedures_fails_without_llm_call(self, django_user_model) -> None:
        """Sem rows declaradas → FAILED, PIPELINE_FAILED, ZERO chamadas LLM."""
        user = django_user_model.objects.create_user(username="nir_fc1", password="pw")
        case = _make_bare_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        # Nenhuma chamada LLM: a validação da projeção falha antes do LLM1.
        assert client.calls == []
        failed = CaseEvent.objects.filter(case=case, event_type="PIPELINE_FAILED").latest("timestamp")
        assert (
            "declarados" in str(failed.payload.get("error", "")).lower()
            or "declared" in str(failed.payload.get("error", "")).lower()
        )
        # Nunca cai em WAIT_DOCTOR nem em scope-gate.
        assert case.suggested_action is None
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_READY_FOR_DOCTOR").exists()

    def test_case_without_declared_procedures_never_enters_legacy_branch(self, django_user_model) -> None:
        """R2: o branch 1.1 não existe mais no orchestrator."""
        from apps.pipeline import orchestrator

        assert not hasattr(orchestrator, "_uses_v2_pipeline")
        assert not hasattr(orchestrator, "_run_llm1_step")
        assert not hasattr(orchestrator, "_run_scope_and_llm2")
        # Serviços 1.1 não são importados pelo módulo do orchestrator.
        assert "Llm1Service" not in dir(orchestrator)
        assert "Llm2Service" not in dir(orchestrator)
        assert "classify_exam_scope" not in dir(orchestrator)

    def test_neutral_fallback_does_not_resolve_legacy_prompt_names(self) -> None:
        """R3: fallback do orchestrator contém somente os quatro nomes neutros."""
        from apps.pipeline.orchestrator import _get_prompt_content

        for neutral in ("exam_llm1_system", "exam_llm1_user", "exam_llm2_system", "exam_llm2_user"):
            assert _get_prompt_content(neutral).strip()
        # Nomes antigos não têm fallback dedicado: retornam o genérico "{case_id}".
        for legacy in (
            "llm1_system",
            "llm1_user",
            "llm2_system",
            "llm2_user",
            "colonoscopy_llm1_system",
            "colonoscopy_llm1_user",
            "colonoscopy_llm2_system",
            "colonoscopy_llm2_user",
        ):
            assert _get_prompt_content(legacy) == "{case_id}", f"{legacy} must not have a dedicated fallback"


@pytest.mark.django_db
class TestPipelineReviewGate:
    """v2 review gate (mismatch/unknown) → WAIT_R1_CLEANUP_THUMBS sem LLM2."""

    def test_declared_eda_detected_colonoscopy_returns_to_nir(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir7", password="pw")
        case = _make_case(user, extracted_text="Solicito colonoscopia para rastreamento.")

        client = RecordingLlmClient(responses=[_llm1_v2(procedures=[_colon_procedure()], one_liner="Colonoscopia.")])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert len(client.calls) == 1  # LLM2 nunca roda
        assert case.suggested_action is not None
        assert case.suggested_action["decision"] == "manual_review_required"
        assert case.suggested_action["reason_code"] == "exam_type_mismatch"
        events = [e.event_type for e in CaseEvent.objects.filter(case=case)]
        assert "LLM2_OK" not in events

    def test_review_gated_case_does_not_appear_in_doctor_queue(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir_filter", password="pw")
        case = _make_case(user, extracted_text="Solicito colonoscopia para rastreamento.")

        client = RecordingLlmClient(responses=[_llm1_v2(procedures=[_colon_procedure()], one_liner="Colonoscopia.")])
        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status != CaseStatus.WAIT_DOCTOR
        assert Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count() == 0


@pytest.mark.django_db
class TestPipelinePreopDenyOverridesLlm2Accept:
    """Policy engine deny deve sobrescrever LLM2 accept (invariante legada, v2)."""

    def test_pipeline_preop_deny_overrides_llm2_accept(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir8", password="pw")
        case = _make_case(user)

        # LLM1: low Hb triggers preop deny; LLM2: says accept (overridden).
        client = RecordingLlmClient(
            responses=[_low_hb_llm1_response(), _llm2_v2(str(case.case_id), suggestion="accept")]
        )

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.suggested_action is not None
        rec = case.suggested_action["procedure_recommendations"][0]
        # Policy determinística vence LLM2.
        assert rec["suggestion"] == "deny"
        assert rec["preop_decision"]["decision"] == "deny"


@pytest.mark.django_db
class TestPipelineSupportSynthesisSaved:
    """Suporte/ASA por componente devem ser salvos no suggested_action (v2)."""

    def test_pipeline_support_synthesis_saved(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir9", password="pw")
        case = _make_case(user)

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.suggested_action is not None
        rec = case.suggested_action["procedure_recommendations"][0]
        assert isinstance(rec["support_recommendation"], str)
        assert rec["asa"]["bucket"]
        assert rec["asa"]["display_text"]
        assert case.suggested_action["global_support_recommendation"] == "none"


@pytest.mark.django_db
class TestPipelinePrioritySignals:
    """Persistência de sinais canônicos após LLM1 e antes do gate (v2)."""

    def _run(self, user, *, extracted_text, llm1_response, llm2_response=None, declared=("eda",)) -> Case:
        case = _make_case(user, extracted_text=extracted_text, declared=declared)
        responses = [llm1_response]
        if llm2_response is not None:
            responses.append(llm2_response(str(case.case_id)))
        client = RecordingLlmClient(responses=responses)
        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
        )
        return _reload(case)

    def test_pipeline_persists_multiple_signals_after_llm1(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir_sig1", password="pw")
        case = self._run(
            user,
            extracted_text=(
                "Motivo da Solicitação: EDA com ecoendoscopia para retirada de corpo estranho "
                "em paciente de 10 anos. Unid. Origem: HSA."
            ),
            llm1_response=_priority_signals_llm1_response(),
            llm2_response=_llm2_v2,
        )
        assert case.status == CaseStatus.WAIT_DOCTOR
        codes = {s["code"] for s in case.priority_signals}
        assert codes == {"foreign_body", "pediatric", "echoendoscopy"}
        for signal in case.priority_signals:
            assert signal["version"] == 1
            assert signal["category"] in {"clinical_alert", "special_population", "special_procedure"}

    def test_llm1_ok_payload_contains_priority_signal_codes(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir_sig2", password="pw")
        case = self._run(
            user,
            extracted_text=(
                "Motivo da Solicitação: EDA com ecoendoscopia para retirada de corpo estranho "
                "em paciente de 10 anos. Unid. Origem: HSA."
            ),
            llm1_response=_priority_signals_llm1_response(),
            llm2_response=_llm2_v2,
        )
        llm1_ok = CaseEvent.objects.filter(case=case, event_type="LLM1_OK").latest("timestamp")
        payload: dict[str, Any] = llm1_ok.payload or {}
        codes = set(payload["priority_signal_codes"])
        assert codes == {"foreign_body", "pediatric", "echoendoscopy"}
        # A auditoria não copia texto clínico adicional (apenas resumo + códigos).
        assert "extracted_text" not in payload

    def test_priority_signals_persisted_before_review_gate(self, django_user_model) -> None:
        """Casos em review gate persistem sinais resolvidos após LLM1 (antes do gate)."""
        user = django_user_model.objects.create_user(username="nir_sig3", password="pw")
        # Declarado EDA, detectado colonoscopia + pediátrico → mismatch + pediatric.
        case = self._run(
            user,
            extracted_text="Crianca de 10 anos. Solicito colonoscopia para rastreamento.",
            llm1_response=_llm1_v2(
                procedures=[_colon_procedure()],
                one_liner="Colonoscopia pediátrica.",
                age=10,
            ),
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        codes = {s["code"] for s in case.priority_signals}
        assert codes == {"pediatric"}

    def test_pipeline_failure_does_not_persist_partial_value(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir_sig4", password="pw")
        case = _make_case(user)
        client = StaticLlmClient(response_text="not json at all")
        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")
        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        assert case.priority_signals == []


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
    """Orchestrator resolve os QUATRO nomes neutros do DB (Slice 007)."""

    def test_uses_neutral_llm1_system_from_db(self, django_user_model) -> None:
        from apps.llm.models import PromptTemplate

        user = django_user_model.objects.create_user(username="npr1", password="pw")
        case = _make_case(user)

        PromptTemplate.objects.create(
            name="exam_llm1_system",
            version=1,
            content="DB_NEUTRAL_LLM1_SYS",
            is_active=True,
        )

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

        # Run WITHOUT injecting llm1_system_prompt — must come from DB (neutral).
        run_pipeline(case.case_id, llm_client=client, llm1_user_template="ut1")

        assert client.calls[0]["system_prompt"] == "DB_NEUTRAL_LLM1_SYS"

    def test_uses_neutral_llm2_system_from_db(self, django_user_model) -> None:
        from apps.llm.models import PromptTemplate

        user = django_user_model.objects.create_user(username="npr2", password="pw")
        case = _make_case(user)

        PromptTemplate.objects.create(
            name="exam_llm2_system",
            version=1,
            content="DB_NEUTRAL_LLM2_SYS",
            is_active=True,
        )

        client = RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        assert client.calls[1]["system_prompt"] == "DB_NEUTRAL_LLM2_SYS"

    def test_neutral_fallback_does_not_contain_endoscopy_report(self) -> None:
        """When no prompt in DB, neutral fallbacks must not mention 'relatório de endoscopia'."""
        from apps.pipeline.orchestrator import _get_prompt_content

        for name in ("exam_llm1_system", "exam_llm1_user", "exam_llm2_system", "exam_llm2_user"):
            fallback = _get_prompt_content(name)
            assert "relatório de endoscopia" not in fallback.lower(), (
                f"Fallback for {name} contains 'relatório de endoscopia'"
            )
