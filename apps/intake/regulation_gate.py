"""Deterministic gate detector for regulation report documents.

Evaluates whether extracted PDF text corresponds to a regulation report
from the Bahia state health system (Central Estadual de Regulação).

This is a pure, testable function with no dependencies on the database or LLM.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings


@dataclass(frozen=True)
class RegulationReportGateResult:
    """Result of evaluating a text against the regulation report gate."""

    accepted: bool
    reason_code: str
    reason_text: str
    matched_header: bool
    matched_institutional_signals: list[str] = field(default_factory=list)
    matched_operational_sections: list[str] = field(default_factory=list)
    text_length: int = 0


# ── Normalization helper ───────────────────────────────────────────────────


def _normalize_text(text: str) -> str:
    """Normalize text for matching: strip accents, lowercase, collapse whitespace.

    Steps:
    1. Strip leading/trailing whitespace.
    2. Collapse all whitespace runs (including newlines) into single spaces.
    3. Decompose unicode and strip combining marks (accents).
    4. Lowercase.
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    return text


# ── Matching constants ─────────────────────────────────────────────────────

_HEADER_PATTERN: str = _normalize_text("RELATÓRIO DE OCORRÊNCIAS")

# Original display labels and their normalized equivalents for matching
_INSTITUTIONAL_SIGNALS: list[tuple[str, str]] = [
    ("Central Estadual de Regulação", _normalize_text("Central Estadual de Regulação")),
    ("Secretaria da Saúde do Estado", _normalize_text("Secretaria da Saúde do Estado")),
    ("Governo do Estado da Bahia", _normalize_text("Governo do Estado da Bahia")),
]

_OPERATIONAL_SECTIONS: list[tuple[str, str]] = [
    ("Código:", _normalize_text("Código:")),
    ("Abertura:", _normalize_text("Abertura:")),
    ("Unid. Origem", _normalize_text("Unid. Origem")),
    ("Unidade de Origem", _normalize_text("Unidade de Origem")),
    ("Motivo da Solicitação", _normalize_text("Motivo da Solicitação")),
    ("Complemento da Solicitação", _normalize_text("Complemento da Solicitação")),
    ("Resumo Clínico", _normalize_text("Resumo Clínico")),
    ("Dias em tela", _normalize_text("Dias em tela")),
    ("Data Adm. Unid.", _normalize_text("Data Adm. Unid.")),
]


# ── Matching helpers ───────────────────────────────────────────────────────


def _check_header_present(normalized_text: str) -> bool:
    """Check if the normalized text contains the regulation report header."""
    return _HEADER_PATTERN in normalized_text


def _find_institutional_signals(normalized_text: str) -> list[str]:
    """Find which institutional signals are present in the normalized text.

    Returns the original (display) labels for matched signals.
    """
    return [original for original, norm in _INSTITUTIONAL_SIGNALS if norm in normalized_text]


def _find_operational_sections(normalized_text: str) -> list[str]:
    """Find which operational sections are present in the normalized text.

    Returns the original section labels that were matched.
    """
    return [original for original, norm in _OPERATIONAL_SECTIONS if norm in normalized_text]


# ── Public API ─────────────────────────────────────────────────────────────


def evaluate_regulation_report_text(text: str) -> RegulationReportGateResult:
    """Evaluate whether the given text is a valid regulation report.

    Criteria (all must be true):
    1. Cleaned text length >= ``settings.INTAKE_REGULATION_MIN_TEXT_CHARS`` (default 500).
    2. Contains ``RELATÓRIO DE OCORRÊNCIAS`` (accent/case insensitive).
    3. Contains at least 1 institutional signal.
    4. Contains at least ``settings.INTAKE_REGULATION_MIN_OPERATIONAL_SECTIONS``
       (default 3) of the known operational section labels.

    Args:
        text: Raw extracted PDF text.

    Returns:
        A ``RegulationReportGateResult`` with match evidence.
    """
    # ── Normalize ──────────────────────────────────────────────────────────
    raw_text = text.strip()
    text_length = len(raw_text)
    normalized = _normalize_text(text)

    # ── Thresholds from settings ───────────────────────────────────────────
    min_chars = getattr(settings, "INTAKE_REGULATION_MIN_TEXT_CHARS", 500)
    min_sections = getattr(settings, "INTAKE_REGULATION_MIN_OPERATIONAL_SECTIONS", 3)

    # ── Check 1: minimum text length ───────────────────────────────────────
    if text_length < min_chars:
        return RegulationReportGateResult(
            accepted=False,
            reason_code="invalid_regulation_report",
            reason_text=(
                f"Texto extraído insuficiente para avaliação (mínimo de {min_chars} caracteres, obtido {text_length})."
            ),
            matched_header=False,
            matched_institutional_signals=[],
            matched_operational_sections=[],
            text_length=text_length,
        )

    # ── Check 2: header ────────────────────────────────────────────────────
    matched_header = _check_header_present(normalized)

    # ── Check 3: institutional signals ─────────────────────────────────────
    matched_institutional_signals = _find_institutional_signals(normalized)

    # ── Check 4: operational sections ──────────────────────────────────────
    matched_operational_sections = _find_operational_sections(normalized)

    accepted = (
        matched_header and len(matched_institutional_signals) >= 1 and len(matched_operational_sections) >= min_sections
    )

    if accepted:
        return RegulationReportGateResult(
            accepted=True,
            reason_code="accepted",
            reason_text="Documento identificado como relatório de regulação.",
            matched_header=matched_header,
            matched_institutional_signals=matched_institutional_signals,
            matched_operational_sections=matched_operational_sections,
            text_length=text_length,
        )

    # ── Build rejection reasons for diagnostics ────────────────────────────
    reasons: list[str] = []
    if not matched_header:
        reasons.append("header 'RELATÓRIO DE OCORRÊNCIAS' não encontrado")
    if len(matched_institutional_signals) < 1:
        reasons.append("nenhum sinal institucional encontrado")
    if len(matched_operational_sections) < min_sections:
        reasons.append(
            f"seções operacionais insuficientes (mínimo {min_sections}, encontrado {len(matched_operational_sections)})"
        )

    reason_text = "O PDF não apresenta os sinais mínimos de relatório de regulação. " + "; ".join(reasons) + "."

    return RegulationReportGateResult(
        accepted=False,
        reason_code="invalid_regulation_report",
        reason_text=reason_text,
        matched_header=matched_header,
        matched_institutional_signals=matched_institutional_signals,
        matched_operational_sections=matched_operational_sections,
        text_length=text_length,
    )
