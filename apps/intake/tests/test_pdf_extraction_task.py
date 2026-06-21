"""Tests for async PDF extraction task — Slice 002."""

from __future__ import annotations

import uuid

import pytest

from apps.cases.models import Case, CaseEvent, CaseStatus

# ── Shared helpers ───────────────────────────────────────────────────────


_GATE_PASSING_TEXT = (
    "RELATORIO DE OCORRENCIAS\n"
    "Governo do Estado da Bahia\n"
    "Secretaria da Saude do Estado\n"
    "Codigo: 12345\n"
    "Abertura: 01/01/2025\n"
    "Unid. Origem: Hospital Central\n"
    "Motivo da Solicitacao: EDA diagnostica\n"
    "Resumo Clinico: Paciente de 45 anos, sem comorbidades, exames de rotina.\n"
    + "Texto de preenchimento para atingir o minimo de caracteres exigido. "
    * 20
)
"""Texto sintético que passa na regulation gate (≥500 chars, header, sinal institucional, ≥3 seções)."""


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


def _make_case_at_llm_struct(user, *, with_text: bool = True, extracted_text: str | None = None) -> Case:
    """Create a Case in LLM_STRUCT, optionally with extracted_text."""
    case = _make_case_at_extracting(user, with_pdf=True)
    if with_text:
        case.extracted_text = extracted_text or _GATE_PASSING_TEXT
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
            lambda _path: _GATE_PASSING_TEXT,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: (_GATE_PASSING_TEXT, "12345"),
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
        assert "Codigo: 12345" in case.extracted_text
        assert case.agency_record_number == "12345"
        assert case.agency_record_extracted_at is not None

    def test_enqueues_pipeline_once(self, user, monkeypatch) -> None:
        """Após sucesso, enqueue_pipeline é chamado uma vez."""
        from apps.intake.tasks import execute_pdf_extraction

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: _GATE_PASSING_TEXT,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: (_GATE_PASSING_TEXT, "12345"),
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
            lambda _path: _GATE_PASSING_TEXT,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: (_GATE_PASSING_TEXT, "12345"),
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
            lambda _path: _GATE_PASSING_TEXT,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: (_GATE_PASSING_TEXT, "12345"),
        )
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_extracting(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.LLM_STRUCT
        assert "Codigo: 12345" in case.extracted_text
        assert case.agency_record_number == "12345"


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
        case.extracted_text = _GATE_PASSING_TEXT
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

    def test_llm_struct_recovery_blocks_non_regulation_text(self, user, monkeypatch) -> None:
        """LLM_STRUCT recovery reavalia gate e bloqueia documento não-regulatório."""
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

        non_regulation_text = (
            "ELETROCARDIOGRAMA\n\n"
            "Paciente: Jose Silva\n"
            "Ritmo: Sinusal\n"
            "Conclusao: ECG dentro da normalidade.\n" + "Texto extra para atingir o tamanho minimo. " * 20
        )
        case = _make_case_at_llm_struct(user, extracted_text=non_regulation_text)

        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert len(extract_called) == 0, "extract_pdf_text should NOT be called for LLM_STRUCT recovery"
        assert len(pipeline_calls) == 0
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.suggested_action is not None
        assert case.suggested_action["decision"] == "manual_review_required"
        assert case.suggested_action["reason_code"] == "invalid_regulation_report"

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
            lambda _path: _GATE_PASSING_TEXT,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: (_GATE_PASSING_TEXT, "12345"),
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
        assert "Codigo: 12345" in case.extracted_text

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
            lambda _path: _GATE_PASSING_TEXT,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: (_GATE_PASSING_TEXT, "12345"),
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
        assert case.agency_record_number == "12345"
        assert "Codigo: 12345" in case.extracted_text
        assert len(pipeline_calls) == 1


# ── Test: execute_pdf_extraction — regulation gate integration ────────────


class TestExecutePdfExtractionRegulationGate:
    """Regulation gate integration in extraction flow."""

    @staticmethod
    def _regulation_text() -> str:
        """Build synthetic regulation text that passes the gate."""
        return (
            "RELATORIO DE OCORRENCIAS\n\n"
            "Governo do Estado da Bahia\n"
            "Secretaria da Saude do Estado\n"
            "Central Estadual de Regulacao\n\n"
            "Codigo: 123456\n"
            "Abertura: 01/01/2025\n"
            "Unid. Origem: Hospital Central\n"
            "Motivo da Solicitacao: EDA diagnostica\n"
            "Complemento da Solicitacao: Exame de rotina.\n"
            "Resumo Clinico: Paciente de 45 anos, assintomatico, "
            "encaminhado para EDA de rastreamento.\n"
            "Dias em tela: 3\n"
            "Data Adm. Unid.: 01/01/2025\n" + "Mais texto para atingir o tamanho minimo exigido " * 15
        )

    @staticmethod
    def _non_regulation_text() -> str:
        """Build synthetic non-regulation text that fails the gate."""
        return (
            "ELETROCARDIOGRAMA\n\n"
            "Paciente: Jose Silva\n"
            "Idade: 60 anos\n"
            "Data: 10/01/2025\n\n"
            "Frequencia cardiaca: 72 bpm\n"
            "Ritmo: Sinusal\n"
            "Conclusao: ECG dentro da normalidade.\n\n"
            "Medico responsavel: Dr. Carlos Andrade\n"
            "CRM: 12345-BA\n" + "Mais texto para atingir o tamanho minimo. " * 15
        )

    @pytest.mark.django_db
    def test_gate_accept_preserves_enqueue_pipeline(self, user, monkeypatch) -> None:
        """Gate aceita → enqueue_pipeline chamado, case LLM_STRUCT."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._regulation_text()
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "123456"),
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
        assert len(pipeline_calls) == 1
        assert pipeline_calls[0][0] == case.case_id

    @pytest.mark.django_db
    def test_gate_reject_blocks_enqueue_pipeline(self, user, monkeypatch) -> None:
        """Gate rejeita → enqueue_pipeline NÃO chamado."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._non_regulation_text()
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "1745000000000"),
        )

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        assert len(pipeline_calls) == 0

    @pytest.mark.django_db
    def test_gate_reject_goes_to_wait_r1_cleanup_thumbs(self, user, monkeypatch) -> None:
        """Gate rejeita → status final WAIT_R1_CLEANUP_THUMBS."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._non_regulation_text()
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "1745000000000"),
        )
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    @pytest.mark.django_db
    def test_gate_reject_sets_suggested_action_manual_review(self, user, monkeypatch) -> None:
        """Gate rejeita → suggested_action com manual_review_required."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._non_regulation_text()
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "1745000000000"),
        )
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.suggested_action is not None
        assert case.suggested_action["decision"] == "manual_review_required"
        assert case.suggested_action["reason_code"] == "invalid_regulation_report"

    @pytest.mark.django_db
    def test_gate_reject_records_expected_events(self, user, monkeypatch) -> None:
        """Gate rejeita → 3 eventos: REGULATION_REPORT_GATE_FAILED, SCOPE_GATE_BYPASS, FINAL_REPLY_POSTED."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._non_regulation_text()
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "1745000000000"),
        )
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        events = CaseEvent.objects.filter(case=case).order_by("timestamp")
        event_types = [e.event_type for e in events]
        assert "REGULATION_REPORT_GATE_FAILED" in event_types, f"Eventos encontrados: {event_types}"
        assert "SCOPE_GATE_BYPASS" in event_types
        assert "FINAL_REPLY_POSTED" in event_types

    @pytest.mark.django_db
    def test_gate_reject_preserves_extracted_text(self, user, monkeypatch) -> None:
        """Gate rejeita → extracted_text preservado para auditoria."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._non_regulation_text()
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "1745000000000"),
        )
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.extracted_text is not None
        assert "ELETROCARDIOGRAMA" in case.extracted_text

    @pytest.mark.django_db
    def test_gate_reject_clears_fallback_record_number(self, user, monkeypatch) -> None:
        """Gate rejeita sem registro explícito → agency_record_number vazio."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._non_regulation_text()  # sem Codigo:
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        # strip_watermark retorna timestamp como fallback
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "1745000000000"),
        )
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: None,
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        # Deve estar vazio — sem registro explícito, barreira falhou
        assert case.agency_record_number == "" or case.agency_record_number is None

    @pytest.mark.django_db
    def test_gate_accept_keeps_explicit_record_number(self, user, monkeypatch) -> None:
        """Gate aceita com registro explícito → agency_record_number preservado."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._regulation_text()  # contem "Codigo: 123456"
        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "123456"),
        )

        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.agency_record_number == "123456"
        assert len(pipeline_calls) == 1

    @pytest.mark.django_db
    def test_persists_regulation_days_on_screen(self, user, monkeypatch) -> None:
        """Extrai "Dias em tela: N" do texto e persiste no Case."""
        from apps.intake.tasks import execute_pdf_extraction

        # Texto com Dias em tela: 9
        text_with_days = (
            "RELATORIO DE OCORRENCIAS\n"
            "Governo do Estado da Bahia\n"
            "Codigo: 12345\n"
            "Dias em tela: 9\n"
            "Resumo Clinico: Paciente de 45 anos.\n" + "Texto extra para atingir o tamanho minimo. " * 20
        )

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text_with_days,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: (text, "12345"),
        )
        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.regulation_days_on_screen == 9

    @pytest.mark.django_db
    def test_persists_max_when_multiple_days_on_screen(self, user, monkeypatch) -> None:
        """Quando múltiplos "Dias em tela", persiste o maior valor."""
        from apps.intake.tasks import execute_pdf_extraction

        # Texto com Dias em tela em múltiplas páginas
        text_with_multiple = (
            "RELATORIO DE OCORRENCIAS\n"
            "Governo do Estado da Bahia\n"
            "Codigo: 12345\n"
            "Dias em tela: 3\n"
            "(page break)\n"
            "Dias em tela: 7\n"
            "(page break)\n"
            "Dias em tela: 5\n"
            "Resumo Clinico: Paciente de 45 anos.\n" + "Texto extra para atingir o tamanho minimo. " * 20
        )

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text_with_multiple,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda text: (text, "12345"),
        )
        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.regulation_days_on_screen == 7

    @pytest.mark.django_db
    def test_sets_null_when_no_days_on_screen(self, user, monkeypatch) -> None:
        """Quando não há "Dias em tela", o campo fica None."""
        from apps.intake.tasks import execute_pdf_extraction

        text = self._regulation_text()  # contém Dias em tela: 3
        # Remove a linha Dias em tela para simular ausência
        text = text.replace("Dias em tela: 3\n", "")

        monkeypatch.setattr(
            "apps.intake.pdf_utils.extract_pdf_text",
            lambda _path: text,
        )
        monkeypatch.setattr(
            "apps.intake.pdf_utils.strip_watermark_and_extract_record",
            lambda t: (t, "123456"),
        )
        pipeline_calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append((case_id,)),
        )

        case = _make_case_at_r1_ack(user)
        execute_pdf_extraction(str(case.case_id))

        case = Case.objects.get(case_id=case.case_id)
        assert case.regulation_days_on_screen is None
