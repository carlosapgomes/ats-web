"""Tests for PDF watermark stripping and record extraction."""

from __future__ import annotations

from apps.intake.pdf_utils import strip_watermark_and_extract_record


class TestWatermarkStripping:
    """strip_watermark_and_extract_record removes watermarks and extracts record."""

    def test_extracts_code_label_pattern(self) -> None:
        text = "Paciente: João\nCódigo: 12345\nRelatório de endoscopia"
        cleaned, record = strip_watermark_and_extract_record(text)
        assert record == "12345"
        assert "12345" not in cleaned
        assert "João" in cleaned

    def test_extracts_relatorio_pattern(self) -> None:
        text = "RELATÓRIO DE OCORRÊNCIAS\nRegistro: 98765\nPaciente: Maria"
        cleaned, record = strip_watermark_and_extract_record(text)
        assert record == "98765"

    def test_strips_repeated_digit_lines(self) -> None:
        text = "Paciente: João\n12345 12345 12345 12345\nRelatório"
        cleaned, record = strip_watermark_and_extract_record(text)
        assert "12345 12345" not in cleaned

    def test_fallback_to_epoch_when_no_record(self) -> None:
        text = "Paciente: João\nRelatório de endoscopia"
        cleaned, record = strip_watermark_and_extract_record(text)
        # Fallback is epoch millis — all digits
        assert record.isdigit()
        assert len(record) >= 10

    def test_removes_record_from_text(self) -> None:
        text = "Código: 55555\nPaciente com registro 55555 e outro 55555"
        cleaned, record = strip_watermark_and_extract_record(text)
        assert record == "55555"
        assert "55555" not in cleaned

    def test_normalizes_whitespace(self) -> None:
        text = "Código: 12345\nPaciente:  João   \n\n\nRelatório"
        cleaned, record = strip_watermark_and_extract_record(text)
        assert "João   " not in cleaned  # extra spaces removed
        assert "João" in cleaned
