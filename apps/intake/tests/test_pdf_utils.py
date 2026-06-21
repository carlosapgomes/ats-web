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


class TestExtractRegulationDaysOnScreen:
    """extract_regulation_days_on_screen extrai "Dias em tela: N" do texto."""

    def test_returns_none_when_not_found(self) -> None:
        from apps.intake.pdf_utils import extract_regulation_days_on_screen

        text = "Paciente: João\nRelatório de endoscopia\nCódigo: 12345"
        assert extract_regulation_days_on_screen(text) is None

    def test_returns_zero(self) -> None:
        from apps.intake.pdf_utils import extract_regulation_days_on_screen

        text = "Dias em tela: 0"
        assert extract_regulation_days_on_screen(text) == 0

    def test_returns_positive_integer(self) -> None:
        from apps.intake.pdf_utils import extract_regulation_days_on_screen

        text = "Dias em tela: 12"
        assert extract_regulation_days_on_screen(text) == 12

    def test_case_insensitive(self) -> None:
        from apps.intake.pdf_utils import extract_regulation_days_on_screen

        text = "DIAS EM TELA : 7"
        assert extract_regulation_days_on_screen(text) == 7

    def test_extra_spaces_variations(self) -> None:
        from apps.intake.pdf_utils import extract_regulation_days_on_screen

        text = "Dias  em  tela:  5"
        assert extract_regulation_days_on_screen(text) == 5

    def test_returns_max_when_multiple_occurrences(self) -> None:
        from apps.intake.pdf_utils import extract_regulation_days_on_screen

        text = "Dias em tela: 3\nAlgum texto\nDias em tela: 5\nMais texto\nDias em tela: 4"
        assert extract_regulation_days_on_screen(text) == 5

    def test_returns_max_when_same_value_repeated(self) -> None:
        from apps.intake.pdf_utils import extract_regulation_days_on_screen

        text = "Dias em tela: 3\nDias em tela: 3\nDias em tela: 3"
        assert extract_regulation_days_on_screen(text) == 3

    def test_ignores_numbers_not_after_dias_em_tela(self) -> None:
        from apps.intake.pdf_utils import extract_regulation_days_on_screen

        text = "Paciente: 123\nTelefone: 98765\nDias em tela: 8"
        assert extract_regulation_days_on_screen(text) == 8
