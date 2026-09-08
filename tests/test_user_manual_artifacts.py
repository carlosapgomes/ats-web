"""Tests for the official user manual artifact and PDF generation script."""

from __future__ import annotations

import re
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
            "Intercorrência Pós-Aceitação",
            "Buscar histórico",
            "Comunicar NIR",
        ]

        # First try exact match for non-accented/standard terms
        missing_exact = [t for t in required_terms if t not in content]

        # For intercurrence terms, use case-insensitive matching
        intercurrence_variants = [
            "intercorrência pós-aceitação",
            "intercorrência após agendamento",
        ]
        intercurrence_found = any(v.lower() in content_lower for v in intercurrence_variants)

        missing = [
            t
            for t in missing_exact
            if t not in intercurrence_variants  # handled separately
        ]
        if not intercurrence_found:
            missing.append("Intercorrência (pós-aceitação / após agendamento)")

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

    def test_build_user_manual_pdf_contains_toc_section(  # noqa: PLR6301
        self,
        tmp_path: Path,
    ) -> None:
        """Generated PDF must include an 'Índice' section listing manual sections."""
        import fitz

        output_pdf = tmp_path / "toc-output.pdf"
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
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        doc = fitz.open(str(output_pdf))
        try:
            text = "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()

        assert "Índice" in text, "PDF does not contain an 'Índice' section"
        # At least one known section title should be listed in the TOC
        assert "Ações do usuário NIR" in text


# ── R3: Manual §6 Supervisor (Slice 002 — Pós-Procedimento) ──────────────


class TestUserManualSection6Supervisor:
    """Slice 002: §6 documenta a aba Pós-Procedimento (CHD) e Histórico & Exportação."""

    @staticmethod
    def _manual() -> str:
        return MANUAL_PATH.read_text(encoding="utf-8")

    def _section6(self) -> str:
        content = self._manual()
        start = content.index("# 6. Ações do usuário Supervisor")
        end = content.index("# 7. ", start)
        return content[start:end]

    def test_section6_documents_pos_procedimento_tab_and_subtabs(self) -> None:
        """§6 usa o rótulo novo e documenta as duas sub-abas (Registrar e Histórico & Exportação)."""
        section = self._section6()
        assert "Pós-Procedimento" in section
        assert "Histórico & Exportação" in section
        assert "Registrar pós-procedimento" in section
        assert "Exportar CSV" in section

    def test_section6_documents_chd_access_rule(self) -> None:
        """§6 documenta o acesso restrito: supervisores do CHD e Administradores."""
        section = self._section6()
        assert "CHD/Agendador" in section
        assert "Administrador" in section
        # Supervisores sem vínculo com o CHD (ex.: Médico/NIR) não veem a aba
        assert "não veem a aba" in section

    def test_manual_is_free_of_followup_anglicism(self) -> None:
        """O manual inteiro não usa 'follow-up'/'follow up' (case-insensitive)."""
        content = self._manual()
        assert re.search(r"follow.?up", content, flags=re.IGNORECASE) is None, (
            "Manual ainda contém o anglicismo 'follow-up'"
        )

    def test_manual_documenta_preparo_inadequado(self) -> None:
        """§6 lista a causa 'Preparo inadequado' entre as causas de não realização."""
        section = self._section6()
        assert "**Preparo inadequado**" in section
        assert "não foi realizado ou foi interrompido" in section
