"""Slice 001 do cutover 3.0 (migrado no cutover 4.0) — fluxo EDA/Colonoscopia.

Cobre, agora sob o writer 4.0:
- R6: jobs EDA, Colonoscopia e EDA + Colonoscopia usam UMA chamada 4.0 por
  estágio, chegam a ``WAIT_DOCTOR`` e a superfície médica lê o artefato 4.0 sem
  regressão (relatório por componente, não modo legado).
- R7: o seed cria os quatro prompts 4.0 de forma idempotente, sem apagar
  histórico anterior.
- R8 (histórico): as chaves de seleção declaradas derivam do catálogo; a UI do
  intake continua oferecendo somente as opções publicadas.
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.procedures import set_declared_procedures
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.llm1_service_v4 import LLM1_V4_DEFAULT_SYSTEM_PROMPT
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

User = get_user_model()

NEUTRAL_NAMES = ["exam_llm1_system", "exam_llm1_user", "exam_llm2_system", "exam_llm2_user"]


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


# ── R6: writer 4.0 ponta a ponta ────────────────────────────────────────────


class TestV3WriterReachesDoctor:
    def test_eda_reaches_wait_doctor_with_v4_artifacts(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir")
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
        assert reloaded.structured_data is not None
        assert reloaded.structured_data["schema_version"] == "4.0"
        assert reloaded.suggested_action is not None
        assert reloaded.suggested_action["schema_version"] == "4.0"
        assert len(client.calls) == 2  # uma chamada por estágio

    def test_colonoscopy_reaches_wait_doctor(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir")
        case = _make_declared_case(user, procedure_types=("colonoscopy",), extracted_text="Solicito colonoscopia.")
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_colon_procedure()], one_liner="Colonoscopia indicada."),
                _llm2_json(str(case.case_id), recommendations=_single_procedure_recommendation("colonoscopy")),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)
        assert _reload(case).status == CaseStatus.WAIT_DOCTOR

    def test_combined_reaches_wait_doctor_with_two_recommendations(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir")
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
        assert reloaded.suggested_action is not None
        recommendations = reloaded.suggested_action["procedure_recommendations"]
        assert {item["procedure_type"] for item in recommendations} == {"eda", "colonoscopy"}

    def test_events_carry_schema_3_0(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir")
        case = _make_declared_case(user, procedure_types=("eda",), extracted_text="Solicito EDA.")
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_procedure()]),
                _llm2_json(str(case.case_id), recommendations=_single_procedure_recommendation("eda")),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        detection_event = CaseEvent.objects.get(case=case, event_type="CASE_PROCEDURES_DETECTED")
        assert detection_event.payload["schema_version"] == "4.0"
        llm1_event = CaseEvent.objects.get(case=case, event_type="LLM1_OK")
        assert llm1_event.payload["schema_version"] == "4.0"

    def test_doctor_surface_reads_v4_without_regression(self, django_user_model) -> None:
        """R6: o artefato 4.0 entra no modo por componente da UI médica."""
        from apps.doctor.presenters import DoctorReportPresenter
        from apps.doctor.views import _is_v2_case

        user = django_user_model.objects.create_user(username="nir")
        case = _make_declared_case(
            user, procedure_types=("eda", "colonoscopy"), extracted_text="Solicito EDA e colonoscopia."
        )
        client = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_eda_procedure(), _colon_procedure()], one_liner="EDA e Colonoscopia indicadas."
                ),
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


# ── R7: seed 4.0 idempotente preservando histórico ──────────────────────────


class TestSeedPromptsV4:
    def test_seeds_four_active_v4_prompts(self) -> None:
        from apps.llm.models import PromptTemplate

        call_command("seed_prompts")
        for name in NEUTRAL_NAMES:
            active = PromptTemplate.get_active(name)
            assert active is not None
            assert active.is_active is True

    def test_idempotent_second_run_creates_nothing(self) -> None:
        from apps.llm.models import PromptTemplate

        call_command("seed_prompts")
        count = PromptTemplate.objects.count()
        call_command("seed_prompts")
        assert PromptTemplate.objects.count() == count

    def test_upgrades_previous_version_without_deleting_history(self) -> None:
        from apps.llm.models import PromptTemplate

        PromptTemplate.objects.create(
            name="exam_llm1_system",
            version=1,
            content="conteudo 2.0 legado",
            is_active=True,
        )
        call_command("seed_prompts")

        active = PromptTemplate.get_active("exam_llm1_system")
        assert active is not None
        assert active.version == 2
        assert active.content == LLM1_V4_DEFAULT_SYSTEM_PROMPT
        # Histórico preservado e inativado — nunca apagado nem reativado.
        legacy = PromptTemplate.objects.get(name="exam_llm1_system", version=1)
        assert legacy.content == "conteudo 2.0 legado"
        assert legacy.is_active is False
        assert PromptTemplate.objects.filter(name="exam_llm1_system", is_active=True).count() == 1


# ── R8: intake especializado permanece fechado ──────────────────────────────


class TestSpecializedIntakeFlags:
    """Slice 002/004 substituem o R8 do Slice 001: os dois especializados entram sob flag.

    O Slice 001 mantinha TODO intake especializado fechado. O Slice 002 abriu
    Ecoendoscopia atrás de ``ECHOENDOSCOPY_INTAKE_ENABLED`` e o Slice 004 abriu
    CPRE atrás de ``CPRE_INTAKE_ENABLED`` (default false) — o contrato é a flag,
    não a ausência da opção.
    """

    def test_intake_rejects_unknown_procedure_selections(self) -> None:
        """D10: as chaves declaradas derivam do catálogo; alias/texto livre falha."""
        from apps.cases.procedures import SELECTION_KEYS
        from apps.intake.services import _DECLARED_SELECTION_VALUES, validate_exam_type

        assert _DECLARED_SELECTION_VALUES == frozenset(SELECTION_KEYS)
        assert {"eda", "eda_gastrostomy", "rectosigmoidoscopy_argon", "cpre"} <= _DECLARED_SELECTION_VALUES
        for value in ("eda_cpre", "eda_echoendoscopy", "EDA", "Colonoscopia"):
            with pytest.raises(ValueError):
                validate_exam_type(value)

    def test_specialized_flags_absent_or_disabled(self) -> None:
        assert getattr(settings, "ECHOENDOSCOPY_INTAKE_ENABLED", False) is False
        assert getattr(settings, "CPRE_INTAKE_ENABLED", False) is False

    def test_cpre_visual_option_is_flag_gated(self) -> None:
        """Opção visual existe, mas nasce ``disabled`` com a flag desligada.

        Slice 002: no upload as opções vêm do helper de jornada
        (``apps/intake/services.py``), que aplica o gate explícito por código;
        o reenvio corrigido mantém os radios com o gate no template.
        """
        from pathlib import Path

        from django.conf import settings as django_settings

        base = Path(django_settings.BASE_DIR)
        # Gate explícito do helper que publica as opções do upload.
        assert "ProcedureType.CPRE: is_cpre_intake_enabled" in (base / "apps" / "intake" / "services.py").read_text(
            encoding="utf-8"
        )
        assert "exam_type_options" in (base / "templates" / "intake" / "intake_home.html").read_text(encoding="utf-8")
        source = (base / "templates" / "intake" / "corrected_resubmission.html").read_text(encoding="utf-8")
        assert 'value="cpre"' in source
        assert "cpre_intake_enabled" in source

    def test_echoendoscopy_option_is_flag_gated(self) -> None:
        """Opção visual existe, mas nasce ``disabled`` com a flag desligada."""
        from pathlib import Path

        from django.conf import settings as django_settings

        base = Path(django_settings.BASE_DIR)
        assert "ProcedureType.ECHOENDOSCOPY: is_echoendoscopy_intake_enabled" in (
            base / "apps" / "intake" / "services.py"
        ).read_text(encoding="utf-8")
        assert "exam_type_options" in (base / "templates" / "intake" / "intake_home.html").read_text(encoding="utf-8")
        source = (base / "templates" / "intake" / "corrected_resubmission.html").read_text(encoding="utf-8")
        assert 'value="echoendoscopy"' in source
        assert "echoendoscopy_intake_enabled" in source
