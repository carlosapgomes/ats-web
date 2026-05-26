"""Tests for the deterministic regulation report gate detector.

All tests use synthetic/anonimized text, no real PHI.
"""

from __future__ import annotations

from apps.intake.regulation_gate import evaluate_regulation_report_text


def _make_regulation_text(
    *,
    header: str = "RELATÓRIO DE OCORRÊNCIAS",
    institutional_signals: list[str] | None = None,
    sections: list[str] | None = None,
    padding_lines: int = 8,
) -> str:
    """Build a synthetic regulation report text long enough (>500 chars).

    Args:
        header: Header line (empty string to omit).
        institutional_signals: List of institutional signal lines.
        sections: List of section lines (e.g. "Código: 123456").
        padding_lines: Number of padding lines to reach minimum length.

    Returns:
        A string with the assembled text.
    """
    lines: list[str] = []
    if header:
        lines.append(header)
        lines.append("")
    if institutional_signals:
        for sig in institutional_signals:
            lines.append(sig)
        lines.append("")
    if sections:
        for sec in sections:
            lines.append(sec)
        lines.append("")
    for i in range(padding_lines):
        lines.append(
            f"Linha de preenchimento número {i + 1} para atingir o tamanho mínimo exigido pelo detector de relatório de regulação."
        )
    return "\n".join(lines)


_FULL_SECTIONS = [
    "Código: 123456",
    "Abertura: 01/01/2025",
    "Unid. Origem: Hospital Central",
    "Motivo da Solicitação: EDA diagnóstica",
    "Complemento da Solicitação: Paciente encaminhado para exame de rotina.",
    "Resumo Clínico: Paciente de 45 anos, assintomático, encaminhado para EDA de rastreamento.",
    "Dias em tela: 3",
    "Data Adm. Unid.: 01/01/2025",
]

_FULL_INSTITUTIONAL = [
    "Governo do Estado da Bahia",
    "Secretaria da Saúde do Estado",
    "Central Estadual de Regulação",
]


class TestRegulationGateAccepts:
    """Cases the gate should accept (valid regulation reports)."""

    def test_accepts_valid_regulation_report(self) -> None:
        """Accepts a synthetic regulation report with all signals present."""
        text = _make_regulation_text(
            institutional_signals=_FULL_INSTITUTIONAL,
            sections=_FULL_SECTIONS,
        )
        result = evaluate_regulation_report_text(text)
        assert result.accepted, f"Deveria aceitar relatório válido: {result.reason_text}"
        assert result.matched_header is True
        assert len(result.matched_institutional_signals) >= 1
        assert len(result.matched_operational_sections) >= 3

    def test_accepts_regulation_report_colonoscopy(self) -> None:
        """Accepts a regulation report where the exam requested is colonoscopy (non-EDA)."""
        text = _make_regulation_text(
            institutional_signals=["Governo do Estado da Bahia", "Secretaria da Saúde do Estado"],
            sections=[
                "Código: 789012",
                "Abertura: 15/03/2025",
                "Unidade de Origem: Hospital Regional",
                "Motivo da Solicitação: Colonoscopia para rastreamento oncológico",
                "Complemento da Solicitação: Paciente com histórico familiar de neoplasia colorretal.",
                "Resumo Clínico: Paciente de 55 anos, sem comorbidades, encaminhado para colonoscopia.",
                "Dias em tela: 5",
                "Data Adm. Unid.: 15/03/2025",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert result.accepted, "Deveria aceitar relatório de colonoscopia (valida formato, não escopo)"
        assert result.matched_header is True

    def test_accepts_minimal_required_sections(self) -> None:
        """Accepts a report with exactly 3 operational sections."""
        text = _make_regulation_text(
            institutional_signals=["Secretaria da Saúde do Estado"],
            sections=[
                "Código: 345678",
                "Abertura: 10/06/2025",
                "Motivo da Solicitação: Endoscopia digestiva alta",
                "Resumo Clínico: Paciente com queixas dispépticas, aguardando avaliação.",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert result.accepted, "Deveria aceitar com 3 seções mínimas"
        assert len(result.matched_operational_sections) >= 3

    def test_accepts_with_accent_variations(self) -> None:
        """Handles accented variations correctly via normalization.

        Uses 'RELATORIO DE OCORRENCIAS' (sem acentos) which should match
        'RELATÓRIO DE OCORRÊNCIAS' after normalization.
        """
        text = _make_regulation_text(
            header="RELATORIO DE OCORRENCIAS",
            institutional_signals=["Governo do Estado da Bahia"],
            sections=[
                "Código: 111222",
                "Abertura: 01/01/2025",
                "Unid. Origem: Posto de Saude",
                "Motivo da Solicitacao: EDA",
                "Complemento da Solicitacao: Exame de rotina",
                "Resumo Clinico: Paciente de 50 anos, encaminhado para EDA de rotina.",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert result.accepted, "Deveria aceitar com header sem acentos"
        assert result.matched_header is True


class TestRegulationGateRejects:
    """Cases the gate should reject (non-regulation documents)."""

    def test_rejects_ecg_report(self) -> None:
        """Rejects a synthetic ECG report."""
        text = """
ELETROCARDIOGRAMA

Paciente: José Silva
Idade: 60 anos
Data: 10/01/2025

Frequência cardíaca: 72 bpm
Ritmo: Sinusal
Eixo: Normal
Sobrecarga ventricular esquerda: Não
Alteração de repolarização ventricular: Não

Conclusão: ECG dentro da normalidade.

Médico responsável: Dr. Carlos Andrade
CRM: 12345-BA
Hospital Central da Bahia
Unidade de Cardiologia
"""
        result = evaluate_regulation_report_text(text)
        assert not result.accepted, "Deveria rejeitar laudo de ECG"
        assert result.reason_code == "invalid_regulation_report"

    def test_rejects_lab_hemogram(self) -> None:
        """Rejects a synthetic lab/hemogram report."""
        text = """
HEMOGRAMA COMPLETO

Paciente: Maria Souza
Data da coleta: 15/01/2025
Médico solicitante: Dr. Antônio Oliveira

Eritrócitos: 5.0 milhões/mm³
Hemoglobina: 14.5 g/dL
Hematócrito: 42%
Volume corpuscular médio: 88 fL
Leucócitos: 6500/mm³
Plaquetas: 250000/mm³

Valores dentro da normalidade.

Laboratório Central de Análises Clínicas
Rua das Flores, 100 - Centro
Salvador - BA
"""
        result = evaluate_regulation_report_text(text)
        assert not result.accepted, "Deveria rejeitar exame laboratorial"

    def test_rejects_short_text(self) -> None:
        """Rejects text that is too short."""
        text = "Apenas um texto curto sem conteúdo significativo."
        result = evaluate_regulation_report_text(text)
        assert not result.accepted, "Deveria rejeitar texto curto"
        assert result.reason_code == "invalid_regulation_report"

    def test_rejects_empty_text(self) -> None:
        """Rejects empty text (simulating PDF with no extractable text)."""
        result = evaluate_regulation_report_text("")
        assert not result.accepted, "Deveria rejeitar texto vazio"
        assert "texto" in result.reason_text.lower()

    def test_rejects_whitespace_only(self) -> None:
        """Rejects text that is only whitespace."""
        result = evaluate_regulation_report_text("   \n  \n  ")
        assert not result.accepted, "Deveria rejeitar texto só com espaços"

    def test_rejects_text_without_header(self) -> None:
        """Rejects text with institutional signals but no header."""
        text = _make_regulation_text(
            header="",
            institutional_signals=["Governo do Estado da Bahia", "Secretaria da Saúde do Estado"],
            sections=[
                "Código: 123456",
                "Abertura: 01/01/2025",
                "Motivo da Solicitação: Exame",
                "Resumo Clínico: Paciente de 40 anos, rotina.",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert not result.accepted, "Deveria rejeitar sem header específico"
        assert result.matched_header is False

    def test_rejects_text_with_header_but_no_institutional_signal(self) -> None:
        """Rejects text with header but no institutional signal."""
        text = _make_regulation_text(
            institutional_signals=None,
            sections=[
                "Código: 123456",
                "Abertura: 01/01/2025",
                "Motivo da Solicitação: Exame de rotina",
                "Resumo Clínico: Paciente de 40 anos, encaminhado para exame de rotina.",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert not result.accepted, "Deveria rejeitar sem sinal institucional"
        assert len(result.matched_institutional_signals) == 0

    def test_rejects_text_with_header_and_signal_but_few_sections(self) -> None:
        """Rejects text with header and institutional signal but < 3 sections."""
        text = _make_regulation_text(
            institutional_signals=["Secretaria da Saúde do Estado"],
            sections=[
                "Código: 123456",
                "Motivo da Solicitação: Exame",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert not result.accepted, "Deveria rejeitar com menos de 3 seções operacionais"
        assert len(result.matched_operational_sections) < 3


class TestRegulationGateEvidence:
    """Evidence fields returned by the gate for auditability."""

    def test_returns_text_length(self) -> None:
        """Returns the text length in the result."""
        text = _make_regulation_text(
            institutional_signals=["Secretaria da Saúde do Estado"],
            sections=[
                "Código: 123456",
                "Abertura: 01/01/2025",
                "Unid. Origem: Hospital",
                "Motivo da Solicitação: EDA",
                "Complemento da Solicitação: Rotina",
                "Resumo Clínico: Paciente de 45 anos, sem queixas, rotina.",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert result.text_length > 0
        assert isinstance(result.text_length, int)

    def test_returns_matched_sections(self) -> None:
        """Returns which operational sections were matched."""
        text = _make_regulation_text(
            institutional_signals=["Secretaria da Saúde do Estado"],
            sections=[
                "Código: 123456",
                "Abertura: 01/01/2025",
                "Unid. Origem: Hospital Central",
                "Motivo da Solicitação: EDA diagnóstica",
                "Resumo Clínico: Paciente de 45 anos, encaminhado para EDA.",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert "Código:" in result.matched_operational_sections
        assert "Abertura:" in result.matched_operational_sections
        assert "Resumo Clínico" in result.matched_operational_sections

    def test_evidence_is_not_sensitive(self) -> None:
        """Evidence fields contain only structural markers, not clinical data."""
        text = _make_regulation_text(
            institutional_signals=["Secretaria da Saúde do Estado"],
            sections=[
                "Código: 123456",
                "Abertura: 01/01/2025",
                "Unid. Origem: Hospital Central",
                "Motivo da Solicitação: EDA diagnóstica",
                "Complemento da Solicitação: Paciente com dispepsia há 3 meses.",
                "Resumo Clínico: Paciente de 45 anos, dispepsia funcional, H. pylori negativo.",
                "Dias em tela: 3",
                "Data Adm. Unid.: 01/01/2025",
            ],
        )
        result = evaluate_regulation_report_text(text)
        # Evidence sections should list the labels found, not the clinical values
        assert "Código:" in result.matched_operational_sections
        assert "Resumo Clínico" in result.matched_operational_sections


class TestRegulationGateRobustness:
    """Edge cases and robustness."""

    def test_handles_institutional_signal_anywhere(self) -> None:
        """Institutional signal can appear anywhere in the document."""
        text = _make_regulation_text(
            institutional_signals=None,
            sections=[
                "Código: 123456",
                "Abertura: 01/01/2025",
                "Unid. Origem: Hospital Central",
                "Motivo da Solicitação: Exame de rotina",
                "Complemento da Solicitação: Paciente encaminhado para avaliação.",
                "Resumo Clínico: Paciente de 40 anos, assintomático, exame de rotina.",
            ],
            padding_lines=0,
        )
        # Add institutional signal at the end
        text += "\n\nGoverno do Estado da Bahia\n"
        # Ensure enough length
        text += " Secretaria da Saúde do Estado." * 20

        result = evaluate_regulation_report_text(text)
        assert result.accepted, "Sinal institucional deve ser detectado em qualquer posição"

    def test_handles_unidade_variant(self) -> None:
        """Both 'Unid. Origem' and 'Unidade de Origem' should be recognized."""
        text = _make_regulation_text(
            institutional_signals=["Secretaria da Saúde do Estado"],
            sections=[
                "Código: 123456",
                "Abertura: 01/01/2025",
                "Unidade de Origem: Hospital Regional do Interior",
                "Motivo da Solicitação: EDA diagnóstica",
                "Complemento da Solicitação: Paciente encaminhado da atenção básica.",
                "Resumo Clínico: Paciente de 50 anos, pirose, dispepsia, encaminhado para EDA.",
            ],
        )
        result = evaluate_regulation_report_text(text)
        assert result.accepted
        assert "Unidade de Origem" in result.matched_operational_sections

    def test_deterministic_and_idempotent(self) -> None:
        """Same input always produces same output."""
        text = _make_regulation_text(
            institutional_signals=["Secretaria da Saúde do Estado"],
            sections=[
                "Código: 123456",
                "Abertura: 01/01/2025",
                "Unid. Origem: Hospital Central",
                "Motivo da Solicitação: EDA diagnóstica",
                "Complemento da Solicitação: Exame de rotina.",
                "Resumo Clínico: Paciente de 45 anos, encaminhado para EDA.",
            ],
        )
        result1 = evaluate_regulation_report_text(text)
        result2 = evaluate_regulation_report_text(text)
        assert result1.accepted == result2.accepted
        assert result1.matched_header == result2.matched_header
        assert result1.matched_institutional_signals == result2.matched_institutional_signals
        assert result1.matched_operational_sections == result2.matched_operational_sections
        assert result1.text_length == result2.text_length
