"""Tests for the official user manual artifact and PDF generation script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANUAL_PATH = PROJECT_ROOT / "docs" / "manual" / "manual-usuarios.md"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_user_manual_pdf.py"


# ── R1: Official manual exists ────────────────────────────────────────────


class TestOfficialManualExists:
    def test_official_user_manual_exists(self) -> None:
        """Verifies that docs/manual/manual-usuarios.md exists."""
        assert MANUAL_PATH.is_file(), f"Official manual not found at {MANUAL_PATH}"

    def test_official_user_manual_has_required_sections(self) -> None:
        """Verifies presence of essential sections/terms."""
        content = MANUAL_PATH.read_text(encoding="utf-8")
        content_lower = content.lower()

        required_terms = [
            "Ações do usuário NIR",
            "Ações do usuário Médico",
            # Accept either variant
            "Ações do usuário CHD",
            "CHD/Agendador",
            "Comunicação operacional",
            "Intercorrência Pós-Agendamento",
            "Buscar histórico",
            "Comunicar NIR",
        ]

        # First try exact match for non-accented/standard terms
        missing_exact = [t for t in required_terms if t not in content]

        # For intercurrence terms, use case-insensitive matching
        intercurrence_variants = [
            "intercorrência pós-agendamento",
            "intercorrência após agendamento",
        ]
        intercurrence_found = any(v.lower() in content_lower for v in intercurrence_variants)

        missing = [
            t
            for t in missing_exact
            if t not in intercurrence_variants  # handled separately
        ]
        if not intercurrence_found:
            missing.append("Intercorrência (pós-agendamento / após agendamento)")

        assert not missing, f"Required terms not found in manual: {missing}"

    def test_official_user_manual_documents_file_limits(self) -> None:
        """Verifies the manual mentions file types and size/count limits."""
        content = MANUAL_PATH.read_text(encoding="utf-8")

        required_terms = [
            "PDF",
            "JPEG",
            "JPG",
            "PNG",
            "20 MB",
            "10 arquivos",
            "200 MB",
        ]

        missing = [term for term in required_terms if term not in content]
        assert not missing, f"File/limit terms not found in manual: {missing}"


# ── R2: PDF generation script ─────────────────────────────────────────────


class TestBuildUserManualPdf:
    """Tests for scripts/build_user_manual_pdf.py."""

    def test_build_user_manual_pdf_script_generates_valid_pdf(  # noqa: PLR6301
        self,
        tmp_path: Path,
    ) -> None:
        """Executes the script and validates the generated PDF."""
        assert SCRIPT_PATH.is_file(), f"PDF generation script not found at {SCRIPT_PATH}"

        output_pdf = tmp_path / "test-output.pdf"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--input",
                str(MANUAL_PATH),
                "--output",
                str(output_pdf),
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        # Validate PDF header
        assert output_pdf.is_file(), "PDF file was not created"
        header = output_pdf.read_bytes()[:4]
        assert header == b"%PDF", f"File does not start with %PDF header, got {header!r}"

        # Validate PDF opens with fitz (pymupdf)
        import fitz  # type: ignore[import-untyped]

        doc = fitz.open(str(output_pdf))
        try:
            assert doc.page_count >= 1, "PDF has no pages"
        finally:
            doc.close()

    def test_build_user_manual_pdf_missing_input_fails_clearly(  # noqa: PLR6301
        self,
        tmp_path: Path,
    ) -> None:
        """Calling script with non-existent input must fail with clear error."""
        nonexistent = tmp_path / "nonexistent.md"
        output_pdf = tmp_path / "should-not-exist.pdf"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--input",
                str(nonexistent),
                "--output",
                str(output_pdf),
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode != 0, "Script should have failed with non-existent input"

        error_msg = (result.stderr + result.stdout).lower()
        assert "not found" in error_msg or "does not exist" in error_msg or "não encontrado" in error_msg, (
            f"Error message does not clearly explain missing input:\n{result.stderr}"
        )
