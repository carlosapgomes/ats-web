"""Regression tests for mobile PDF viewer affordances.

Mobile browsers render embedded PDFs inconsistently, so the primary PDF action must
open the protected PDF URL directly instead of expanding the inline viewer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PDF_VIEWER_TEMPLATES = [
    "templates/intake/case_detail.html",
    "templates/intake/closed_case_detail.html",
    "templates/scheduler/context_detail.html",
    "templates/doctor/decision.html",
]


@pytest.mark.parametrize("template_rel", PDF_VIEWER_TEMPLATES)
def test_main_pdf_viewer_has_mobile_direct_open_action(template_rel: str) -> None:
    """Main PDF viewer must expose a mobile-only direct-open action."""
    content = (PROJECT_ROOT / template_rel).read_text()

    assert "d-md-none" in content, f"{template_rel} deve ter ação mobile-only para PDF"
    assert "toque para abrir o PDF" in content, f"{template_rel} deve orientar abertura direta no mobile"
    assert 'target="_blank"' in content, f"{template_rel} deve abrir PDF em nova aba/tela no mobile"


@pytest.mark.parametrize("template_rel", PDF_VIEWER_TEMPLATES)
def test_main_pdf_viewer_keeps_desktop_collapse_action(template_rel: str) -> None:
    """Desktop must keep the existing collapse/embedded PDF experience."""
    content = (PROJECT_ROOT / template_rel).read_text()

    assert "d-none d-md" in content, f"{template_rel} deve manter trigger desktop-only"
    assert "clique para expandir" in content, f"{template_rel} deve manter orientação desktop de expandir"
    assert "pdf-collapse" in content, f"{template_rel} deve manter collapse do PDF"
