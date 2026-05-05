"""Utilitários de extração de texto de PDF."""

import fitz  # type: ignore[import-untyped]  # PyMuPDF


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
