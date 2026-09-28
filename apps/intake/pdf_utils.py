"""Utilitários de extração de texto de PDF."""

from __future__ import annotations

import re
import time
from collections import Counter

import fitz  # type: ignore[import-untyped]  # PyMuPDF

# Patterns for watermark detection
_WATERMARK_DIGIT_TOKEN_PATTERN = re.compile(r"\b([0-9]{3,})\b")
_WATERMARK_MIN_OCCURRENCES = 11

# Patterns to extract agency record number from text
_CODE_LABEL_PATTERN = re.compile(
    r"\bC(?:[oO]|[óÓ])digo\s*:\s*([0-9]{5,})\b",
    flags=re.IGNORECASE,
)
_REPORT_HEADER_PATTERN = re.compile(
    r"RELAT(?:[OÓ])RIO\s+DE\s+OCORR(?:[EÊ])NCIAS"
    r"(?:\s*[:\-])?"
    r"[\s\S]{0,120}?"
    r"\b([0-9]{5,})\b",
    flags=re.IGNORECASE,
)


def extract_pdf_text(pdf_path: str) -> str:
    """Extrai texto de todas as páginas do PDF.

    Args:
        pdf_path: Caminho absoluto para o arquivo PDF.

    Returns:
        Texto concatenado de todas as páginas, sem espaços extras.
    """
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def strip_watermark_and_extract_record(text: str) -> tuple[str, str]:
    """Remove marca d'água do texto e extrai número de registro.

    A marca d'água é um token numérico de 3 ou mais dígitos que aparece
    mais de 10 vezes ao longo do texto extraído.

    Strategy (portado do legado record_number.py):
    1. Detectar padrões explícitos de registro (Código: XXXXX, RELATÓRIO...)
    2. Se encontrado, usar como registro e remover todas as ocorrências
    3. Remover tokens numéricos repetidos mais de 10 vezes no documento
    4. Fallback: usar timestamp se nenhum registro encontrado

    Returns:
        Tupla (texto_limpo, número_do_registro).
    """
    # 1. Extract explicit record number patterns
    record_number = _extract_record_number(text)

    if not record_number:
        record_number = str(_current_epoch_millis())

    # 2. Remove all occurrences of the record number
    cleaned = re.sub(rf"\b{re.escape(record_number)}\b", " ", text)

    # 3. Strip repeated numeric watermark tokens
    cleaned = _strip_repeated_digit_watermarks(cleaned, protected_token=record_number)

    # 4. Normalize whitespace
    cleaned = _normalize_whitespace(cleaned)

    return cleaned, record_number


def _extract_record_number(text: str) -> str:
    """Extract agency record number from explicit patterns in text."""
    for pattern in (_CODE_LABEL_PATTERN, _REPORT_HEADER_PATTERN):
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def _current_epoch_millis() -> int:
    """Return current UNIX epoch in milliseconds."""
    return time.time_ns() // 1_000_000


def _strip_repeated_digit_watermarks(text: str, *, protected_token: str) -> str:
    """Remove 3+ digit tokens repeated more than 10 times in the document."""
    token_counts = Counter(_WATERMARK_DIGIT_TOKEN_PATTERN.findall(text))
    watermark_tokens = {token for token, count in token_counts.items() if count >= _WATERMARK_MIN_OCCURRENCES}
    watermark_tokens.discard(protected_token)

    result = text
    for token in watermark_tokens:
        result = re.sub(rf"\b{re.escape(token)}\b", " ", result)
    return result


def extract_explicit_record_number(text: str) -> str:
    """Extract explicit agency record number from raw PDF text.

    Returns the record number if found via explicit patterns
    (Código:..., RELATÓRIO... header), or empty string if none found
    (would be fallback/timestamp).
    """
    return _extract_record_number(text)


_DAYS_ON_SCREEN_PATTERN = re.compile(
    r"\bDias\s+em\s+tela\s*:\s*(\d+)\b",
    flags=re.IGNORECASE,
)


def extract_regulation_days_on_screen(text: str) -> int | None:
    """Extrai o maior valor de "Dias em tela: N" do texto.

    Procura por ocorrências do padrão "Dias em tela: <número>" (case-insensitive,
    com variações de espaços) e retorna o maior inteiro encontrado.
    Retorna None se nenhuma ocorrência for encontrada.
    """
    matches = [int(value) for value in _DAYS_ON_SCREEN_PATTERN.findall(text)]
    return max(matches) if matches else None


def _normalize_whitespace(text: str) -> str:
    """Normalize spaces while preserving paragraph linebreaks."""
    normalized_lines: list[str] = []
    for raw_line in text.splitlines():
        compact = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not compact:
            if normalized_lines and normalized_lines[-1] != "":
                normalized_lines.append("")
            continue
        normalized_lines.append(compact)
    return "\n".join(normalized_lines).strip()
