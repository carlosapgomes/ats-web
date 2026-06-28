"""Tests for CSS :has() selector scoping in app.css.

Ensures the global .d-flex.gap-2:has(> .btn) rule that forces flex-direction: column
is scoped to case cards (and a utility class), preventing accidental matches on
header navbars and other element stacks.

Also ensures page-level action rows (Submit + Cancel pairs) opt-in to vertical
stacking on mobile via the explicit .btn-stack-mobile utility class.
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


# Templates onde fileiras de ação (Submit + Cancelar, em alguns casos btn-lg) devem
# opt-in ao empilhamento vertical no mobile via .btn-stack-mobile (regressão do Slice 001).
ACTION_ROW_TEMPLATES = [
    "templates/doctor/decision.html",
    "templates/scheduler/confirm.html",
    "templates/scheduler/confirm_post_schedule_issue.html",
    "templates/intake/closed_case_detail.html",
    "templates/intake/corrected_resubmission.html",
    "templates/admin_ui/prompt_create.html",
    "templates/admin_ui/user_form.html",
]


@pytest.mark.parametrize("template_rel", ACTION_ROW_TEMPLATES)
def test_action_rows_have_btn_stack_mobile(template_rel: str) -> None:
    """Cada fileira de ação de página deve conter .btn-stack-mobile (empilhamento mobile)."""
    content = (PROJECT_ROOT / template_rel).read_text()
    assert "btn-stack-mobile" in content, (
        f"{template_rel} deve usar .btn-stack-mobile na fileira de ação para empilhar no mobile"
    )


def test_closed_case_detail_has_two_action_rows_stacked() -> None:
    """closed_case_detail tem duas fileiras de ação; ambas precisam de .btn-stack-mobile."""
    content = (PROJECT_ROOT / "templates/intake/closed_case_detail.html").read_text()
    assert content.count("btn-stack-mobile") >= 2, (
        "closed_case_detail.html deve ter .btn-stack-mobile em ambas as fileiras de ação"
    )
