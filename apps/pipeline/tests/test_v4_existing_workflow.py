"""Cutover 4.0 (R5/R6) — fluxo existente preservado sob o writer 4.0.

Cobre:
- R5: EDA, Colonoscopia e EDA + Colonoscopia completam a análise 4.0 com UMA
  extração comum por caso, uma recomendação por row reconciliada e sem
  regressão de policy até ``WAIT_DOCTOR``;
- R6: nenhuma flag/FSM/permissão nova é necessária e sinais históricos
  permanecem legíveis — o writer 4.0 não duplica um sinal legado já coberto por
  identidade atômica (D13).
"""

from __future__ import annotations

import json

import pytest

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.procedures import set_declared_procedures
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.llm1_service_v4 import LLM1_V4_DEFAULT_SYSTEM_PROMPT
from apps.pipeline.llm2_service_v4 import LLM2_V4_DEFAULT_SYSTEM_PROMPT
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.tests.test_slice_002_pipeline import (
    _colon_procedure,
    _eda_procedure,
    _llm1_json,
    _llm2_json,
    _reload,
    _single_procedure_recommendation,
)

pytestmark = pytest.mark.django_db

SCHEMA_VERSION = "4.0"


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


# ── R5: writer 4.0 chega ao médico ──────────────────────────────────────────


class TestV4WriterReachesDoctor:
    def test_eda_reaches_wait_doctor_with_v4_artifacts(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_eda")
        case = _make_declared_case(user, procedure_types=("eda",), extracted_text="Solicito EDA.")
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_procedure()], one_liner="EDA indicada."),
                _llm2_json(str(case.case_id), recommendations=_single_procedure_recommendation("eda")),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2  # uma extração comum + uma análise conjunta
        assert reloaded.structured_data is not None
        assert reloaded.structured_data["schema_version"] == SCHEMA_VERSION
        assert reloaded.suggested_action is not None
        assert reloaded.suggested_action["schema_version"] == SCHEMA_VERSION

    def test_colonoscopy_reaches_wait_doctor(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_colon")
        case = _make_declared_case(user, procedure_types=("colonoscopy",), extracted_text="Solicito colonoscopia.")
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_colon_procedure()], one_liner="Colonoscopia indicada."),
                _llm2_json(str(case.case_id), recommendations=_single_procedure_recommendation("colonoscopy")),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)
        assert _reload(case).status == CaseStatus.WAIT_DOCTOR

    def test_combined_reaches_wait_doctor_with_one_row_per_component(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_both")
        case = _make_declared_case(
            user, procedure_types=("eda", "colonoscopy"), extracted_text="Solicito EDA e colonoscopia."
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_eda_procedure(), _colon_procedure()],
                    one_liner="EDA e Colonoscopia indicadas.",
                ),
                _llm2_json(str(case.case_id)),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        assert reloaded.suggested_action is not None
        recommendations = reloaded.suggested_action["procedure_recommendations"]
        assert [item["procedure_type"] for item in recommendations] == ["eda", "colonoscopy"]
        # Suporte global = nível mais restritivo entre as rows (colonoscopy > eda).
        assert reloaded.suggested_action["global_support_recommendation"] == "anesthesist"

    def test_events_carry_v4_schema_and_sets(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_events")
        case = _make_declared_case(
            user, procedure_types=("eda", "colonoscopy"), extracted_text="Solicito EDA e colonoscopia."
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_procedure(), _colon_procedure()]),
                _llm2_json(str(case.case_id)),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        detected_event = CaseEvent.objects.get(case=case, event_type="CASE_PROCEDURES_DETECTED")
        assert detected_event.payload["schema_version"] == SCHEMA_VERSION
        assert detected_event.payload["detected_procedures"] == ["eda", "colonoscopy"]
        llm1_event = CaseEvent.objects.get(case=case, event_type="LLM1_OK")
        llm2_event = CaseEvent.objects.get(case=case, event_type="LLM2_OK")
        assert llm1_event.payload["schema_version"] == SCHEMA_VERSION
        assert llm2_event.payload["schema_version"] == SCHEMA_VERSION
        assert llm2_event.payload["detected_procedures"] == ["eda", "colonoscopy"]

    def test_doctor_surface_reads_v4_without_regression(self, django_user_model) -> None:
        from apps.doctor.presenters import DoctorReportPresenter
        from apps.doctor.views import _is_v2_case

        user = django_user_model.objects.create_user(username="nir4_presenter")
        case = _make_declared_case(
            user, procedure_types=("eda", "colonoscopy"), extracted_text="Solicito EDA e colonoscopia."
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_procedure(), _colon_procedure()]),
                _llm2_json(str(case.case_id)),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reloaded = _reload(case)
        assert _is_v2_case(reloaded) is True
        presenter = DoctorReportPresenter(
            structured_data=reloaded.structured_data or {},
            summary_text=reloaded.summary_text,
            suggested_action=reloaded.suggested_action or {},
            exam_type="eda_colonoscopy",
        )
        report = presenter.build_report()
        assert "EDA + Colonoscopia" in report["context"]["procedure"]


# ── R5: dispatch de produção usa prompts 4.0 ────────────────────────────────


class TestV4ProductionPrompts:
    def test_fallback_prompts_are_v4(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir4_prompt")
        case = _make_declared_case(user, procedure_types=("eda",), extracted_text="Solicito EDA.")
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_procedure()]),
                _llm2_json(str(case.case_id), recommendations=_single_procedure_recommendation("eda")),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        assert client.calls[0]["system_prompt"] == LLM1_V4_DEFAULT_SYSTEM_PROMPT
        assert client.calls[1]["system_prompt"] == LLM2_V4_DEFAULT_SYSTEM_PROMPT
        assert "schema_version 4.0" in client.calls[0]["system_prompt"]
        assert "schema_version 4.0" in client.calls[1]["system_prompt"]


# ── R6/D13: identidade atômica não duplica sinal legado ─────────────────────


class TestV4AtomicIdentityDoesNotDuplicateLegacySignal:
    def test_declared_gastrostomy_package_does_not_persist_gastrostomy_signal(self, django_user_model) -> None:
        """D13: a identidade ``eda_gastrostomy`` já cobre o sinal equivalente.

        O caso declarado como pacote ainda não é detectado por texto neste slice
        (Slices 003/004/005 habilitam a detecção): ele volta fail-closed para o
        NIR. O ponto verificado aqui é que o writer 4.0 não persiste o sinal
        legado ``gastrostomy`` quando a identidade atômica está presente.
        """
        user = django_user_model.objects.create_user(username="nir4_gtt")
        case = _make_declared_case(
            user,
            procedure_types=("eda_gastrostomy",),
            extracted_text="Solicito EDA com GTT.",
        )
        llm1_payload = json.loads(
            _llm1_json(
                procedures=[
                    {
                        "procedure_type": "eda_gastrostomy",
                        "name": "EDA + Gastrostomia",
                        "urgency": "eletivo",
                        "indication_category": "other",
                        "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito EDA com GTT"}],
                        "infection_evidence": [],
                    }
                ],
                one_liner="EDA com GTT indicada.",
            )
        )
        # Sem a exclusão do D13 o subtype persistido geraria o sinal ``gastrostomy``.
        llm1_payload["common_preop"]["rulebook_signals"]["eda_subtype"] = "gastrostomy"
        client = RecordingLlmClient(responses=[json.dumps(llm1_payload)])
        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        reloaded = _reload(case)
        assert reloaded.structured_data is not None
        assert reloaded.structured_data["schema_version"] == SCHEMA_VERSION
        assert reloaded.priority_signals == []
