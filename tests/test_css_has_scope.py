"""Tests for CSS :has() selector scoping in app.css.

Ensures the global .d-flex.gap-2:has(> .btn) rule that forces flex-direction: column
is scoped to case cards (and a utility class), preventing accidental matches on
header navbars and other element stacks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSS = PROJECT_ROOT / "static" / "css" / "app.css"


def test_scoped_has_rule_exists() -> None:
    """A regra escopada .case-card .d-flex.gap-2:has(> .btn) deve estar presente."""
    content = CSS.read_text()
    assert ".case-card .d-flex.gap-2:has(> .btn)" in content, (
        "Regra escopada .case-card .d-flex.gap-2:has(> .btn) não encontrada em app.css"
    )


def test_global_has_rule_is_removed() -> None:
    """A regra global .d-flex.gap-2:has(> .btn) sem prefixo .case-card não deve existir."""
    content = CSS.read_text()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(".d-flex.gap-2:has(> .btn)") and ".case-card" not in stripped:
            pytest.fail(f"Seletor global não-escopado ainda presente: {stripped!r}")


def test_btn_stack_mobile_utility_exists() -> None:
    """A classe utilitária .btn-stack-mobile deve estar presente."""
    content = CSS.read_text()
    assert ".btn-stack-mobile" in content, "Classe utilitária .btn-stack-mobile não encontrada em app.css"
