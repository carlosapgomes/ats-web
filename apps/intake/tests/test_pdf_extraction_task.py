"""Tests for async PDF extraction task — Slice 002."""

from __future__ import annotations

import uuid

import pytest

from apps.cases.models import Case, CaseEvent, CaseStatus

# ── Test: enqueue_pdf_extraction ────────────────────────────────────────


class TestEnqueuePdfExtraction:
    """enqueue_pdf_extraction deve chamar async_task com cluster 'pdf'."""

    def test_enqueue_calls_async_task_with_pdf_cluster(self, monkeypatch) -> None:
        """Verifica enqueue_pdf_extraction envia task para cluster 'pdf'."""
        from apps.intake.tasks import enqueue_pdf_extraction

        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def _fake_async_task(*args: object, **kwargs: object) -> None:
            calls.append((args, kwargs))

        monkeypatch.setattr("apps.intake.tasks.async_task", _fake_async_task)

        case_id = uuid.uuid4()
        enqueue_pdf_extraction(case_id)

        assert len(calls) == 1
        args, kwargs = calls[0]
        assert args[0] == "apps.intake.tasks.execute_pdf_extraction"
        assert args[1] == str(case_id)

        q_options = kwargs.get("q_options", {})
        assert isinstance(q_options, dict)
        assert q_options.get("cluster") == "pdf", f"Expected cluster='pdf', got {q_options.get('cluster')}"
        assert q_options.get("task_name") == f"pdf:{case_id}"


# ── Test: execute_pdf_extraction — helpers ──────────────────────────────


def _make_case_at_r1_ack(user, *, with_pdf: bool = True) -> Case:
    """Create a Case in R1_ACK_PROCESSING, optionally with pdf_file path set."""
    case = Case.objects.create(created_by=user)
    if with_pdf:
        case.pdf_file = "pdfs/2026/05/test.pdf"
    case.start_processing(user=user)
    case.save()
    return Case.objects.get(case_id=case.case_id)


def _make_case_at_extracting(user, *, with_pdf: bool = True) -> Case:
    """Create a Case in EXTRACTING, optionally with pdf_file path set."""
    case = _make_case_at_r1_ack(user, with_pdf=with_pdf)
    case.start_extraction(user=user)
    case.save()
    return Case.objects.get(case_id=case.case_id)


def _make_case_at_llm_struct(user, *, with_text: bool = True) -> Case:
    """Create a Case in LLM_STRUCT, optionally with extracted_text."""
    case = _make_case_at_extracting(user, with_pdf=True)
    if with_text:
        case.extracted_text = "Paciente já processado."
    case.extraction_complete(success=True, user=user)
    case.save()
    return Case.objects.get(case_id=case.case_id)


# ── Test: execute_pdf_extraction — success ──────────────────────────────


@pytest.mark.django_db
class TestExecutePdfExtractionSuccess:
    """Fluxo feliz: R1_ACK_PROCESSING → LLM_STRUCT + pipeline enqueued."""

    def test_extracts_text_and_saves_fields(self, user, monkeypatch) -> None:
        """Extrai texto, salva campos e deixa status LLM_STRUCT."""
        from apps.intake.tasks import execute_pdf_extraction

        # Mock PDF utilities
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: "Paciente: João\nCódigo: 12345\nRelatório",
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: ("Paciente: João\nRelatório", "12345"),
        )
        # Mock enqueue_pipeline to avoid side effects
        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.LLM_STRUCT
        assert "Paciente: João" in case.extracted_text
        assert case.agency_record_number == "12345"
        assert case.agency_record_extracted_at is not None

    def test_enqueues_pipeline_once(self, user, monkeypatch) -> None:
        """Após sucesso, enqueue_pipeline é chamado uma vez."""
        from apps.intake.tasks import execute_pdf_extraction

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: "Paciente: João\nCódigo: 12345",
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: ("Paciente: João", "12345"),
        )

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        assert len(pipeline_calls) == 1
        assert pipeline_calls[0][0] == case.case_id

    def test_generates_extraction_events(self, user, monkeypatch) -> None:
        """Deve gerar CASE_START_EXTRACTION e CASE_EXTRACTION_OK."""
        from apps.intake.tasks import execute_pdf_extraction

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: "Paciente: João\nCódigo: 12345",
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: ("Paciente: João", "12345"),
        )
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        events = CaseEvent.objects.filter(case=case).order_by("timestamp")
        event_types = [e.event_type for e in events]
        assert "CASE_START_EXTRACTION" in event_types
        assert "CASE_EXTRACTION_OK" in event_types
        assert "CASE_EXTRACTION_FAILED" not in event_types

    def test_handles_case_in_extracting_state(self, user, monkeypatch) -> None:
        """Task funciona se case já está em EXTRACTING (retry scenario)."""
        from apps.intake.tasks import execute_pdf_extraction

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: "Paciente: Maria\nCódigo: 67890",
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: ("Paciente: Maria", "67890"),
        )
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_extracting(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.LLM_STRUCT
        assert "Paciente: Maria" in case.extracted_text
        assert case.agency_record_number == "67890"


# ── Test: execute_pdf_extraction — idempotency ──────────────────────────


@pytest.mark.django_db
class TestExecutePdfExtractionIdempotency:
    """Task não deve reprocessar se já estiver além de LLM_STRUCT."""

    def test_llm_struct_enqueues_pipeline_without_re_extracting(self, user, monkeypatch) -> None:
        """LLM_STRUCT → chama enqueue_pipeline, não reextrai PDF."""
        from apps.intake.tasks import execute_pdf_extraction

        extract_called: list[bool] = []

        def _extract(_path: str) -> str:
            extract_called.append(True)
            return "NOVO TEXTO"

        monkeypatch.setattr("apps.intake.pdf_utils.extract_pdf_text", _extract)
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: ("NOVO TEXTO", "99999"),
        )

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_llm_struct(user, with_text=True)
        original_text = case.extracted_text
        original_record = case.agency_record_number

        execute_pdf_extraction(str(case.case_id))

        # Não reextraiu
        assert len(extract_called) == 0, "extract_pdf_text should NOT be called for LLM_STRUCT"
        case = Case.objects.get(case_id=case.case_id)
        assert case.extracted_text == original_text
        assert case.agency_record_number == original_record
        # Pipeline enfileirada
        assert len(pipeline_calls) == 1
        assert pipeline_calls[0][0] == case.case_id

    def test_skips_status_after_llm_struct(self, user, monkeypatch) -> None:
        """LLM_STRUCT → enfileira pipeline e não reextrai."""
        from apps.intake.tasks import execute_pdf_extraction

        extract_called: list[bool] = []

        def _extract(_path: str) -> str:
            extract_called.append(True)
            return "NOVO TEXTO"

        monkeypatch.setattr("apps.intake.pdf_utils.extract_pdf_text", _extract)

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = Case.objects.create(created_by=user)
        case.pdf_file = "pdfs/2026/05/test.pdf"
        case.save()
        case.start_processing(user=user)
        case.save()
        case.start_extraction(user=user)
        case.save()
        case.extraction_complete(success=True, user=user)
        case.save()

        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.LLM_STRUCT
        assert len(extract_called) == 0, "extract_pdf_text should NOT be called"
        assert len(pipeline_calls) == 1

    def test_skips_failed_status(self, user, monkeypatch) -> None:
        """Status FAILED → não reextrai."""
        from apps.intake.tasks import execute_pdf_extraction

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        # Create a case in FAILED state via FSM: R1_ACK_PROCESSING → EXTRACTING → FAILED
        case = _make_case_at_r1_ack(user, with_pdf=False)
        case.start_extraction(user=user)
        case.save()
        case.extraction_complete(success=False, user=user)
        case.save()
        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.FAILED

        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.FAILED
        assert len(pipeline_calls) == 0


# ── Test: execute_pdf_extraction — no pdf_file ──────────────────────────


@pytest.mark.django_db
class TestExecutePdfExtractionNoPdf:
    """Caso sem pdf_file → falha controlada."""

    def test_no_pdf_file_marks_as_failed(self, user, monkeypatch) -> None:
        """Caso em R1_ACK_PROCESSING sem pdf_file → estado FAILED."""
        from apps.intake.tasks import execute_pdf_extraction

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user, with_pdf=False)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.FAILED
        assert len(pipeline_calls) == 0

    def test_no_pdf_file_generates_failed_event(self, user, monkeypatch) -> None:
        """Caso sem pdf_file → CASE_EXTRACTION_FAILED registrado."""
        from apps.intake.tasks import execute_pdf_extraction

        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_r1_ack(user, with_pdf=False)
        execute_pdf_extraction(str(case.case_id))

        events = CaseEvent.objects.filter(case=case)
        event_types = [e.event_type for e in events]
        assert "CASE_EXTRACTION_FAILED" in event_types


# ── Test: execute_pdf_extraction — exception handling ───────────────────


@pytest.mark.django_db
class TestExecutePdfExtractionException:
    """Exceção durante extração → estado FAILED + evento de falha."""

    def test_exception_generates_failed_event(self, user, monkeypatch) -> None:
        """Exceção em extract_pdf_text → CASE_EXTRACTION_FAILED e FAILED."""
        from apps.intake.tasks import execute_pdf_extraction

        def _explode(_path: str) -> str:
            raise RuntimeError("Arquivo corrompido")

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            _explode,
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.FAILED

        events = CaseEvent.objects.filter(case=case)
        event_types = [e.event_type for e in events]
        assert "CASE_EXTRACTION_FAILED" in event_types

    def test_exception_does_not_enqueue_pipeline(self, user, monkeypatch) -> None:
        """Exceção → pipeline não é enfileirada."""
        from apps.intake.tasks import execute_pdf_extraction

        def _explode(_path: str) -> str:
            raise RuntimeError("Falha")

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            _explode,
        )

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        assert len(pipeline_calls) == 0

    def test_enqueue_pipeline_failure_after_extraction_propagates(self, user, monkeypatch) -> None:
        """Falha de enqueue_pipeline após extração propaga e case fica LLM_STRUCT."""
        from apps.intake.tasks import execute_pdf_extraction

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: "Paciente: João\nCódigo: 12345",
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: ("Paciente: João", "12345"),
        )

        def _explode_enqueue(_case_id: object) -> None:
            raise RuntimeError("Queue failure")

        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            _explode_enqueue,
        )

        case = _make_case_at_r1_ack(user)

        with pytest.raises(RuntimeError, match="Queue failure"):
            execute_pdf_extraction(str(case.case_id))

        # Case deve permanecer em LLM_STRUCT (não FAILED)
        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.LLM_STRUCT, f"Expected LLM_STRUCT, got {case.status}"
        assert case.extracted_text == "Paciente: João"

    def test_retry_on_llm_struct_calls_enqueue_pipeline_again(self, user, monkeypatch) -> None:
        """Reexecução em LLM_STRUCT chama enqueue_pipeline novamente."""
        from apps.intake.tasks import execute_pdf_extraction

        extract_called: list[bool] = []

        def _extract(_path: str) -> str:
            extract_called.append(True)
            return "NÃO DEVE CHAMAR"

        monkeypatch.setattr("apps.intake.pdf_utils.extract_pdf_text", _extract)

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_llm_struct(user, with_text=True)

        # Primeira chamada (recovery)
        execute_pdf_extraction(str(case.case_id))
        assert len(pipeline_calls) == 1
        assert len(extract_called) == 0

        # Segunda chamada (retry fictício)
        execute_pdf_extraction(str(case.case_id))
        assert len(pipeline_calls) == 2
        assert len(extract_called) == 0


# ── Test: execute_pdf_extraction — case not found ───────────────────────


@pytest.mark.django_db
class TestExecutePdfExtractionCaseNotFound:
    """Case não existente → levanta exceção."""

    def test_raises_when_case_not_found(self, monkeypatch) -> None:
        """Case inexistente → ValueError."""
        from apps.intake.tasks import execute_pdf_extraction

        fake_id = str(uuid.uuid4())
        with pytest.raises(ValueError, match="not found"):
            execute_pdf_extraction(fake_id)


# ── Test: execute_pdf_extraction — integration leve ─────────────────────


@pytest.mark.django_db
class TestExecutePdfExtractionIntegration:
    """Teste de integração leve com mock de strip_watermark."""

    def test_with_mocked_pdf_text_and_strip(self, user, monkeypatch) -> None:
        """Fluxo completo com mocks nas funções de PDF."""
        from apps.intake.tasks import execute_pdf_extraction

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: "RELATÓRIO DE OCORRÊNCIAS\nCódigo: 55555\nPaciente tratado.",
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: ("RELATÓRIO DE OCORRÊNCIAS\nPaciente tratado.", "55555"),
        )

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.LLM_STRUCT
        assert case.agency_record_number == "55555"
        assert "Paciente tratado." in case.extracted_text
        assert len(pipeline_calls) == 1
