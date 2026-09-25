"""Guarda de CSS das affordances visuais do combobox de procedimento (D7).

O Slice 001 introduziu vocabulário novo no bloco ``.procedure-combobox*``
(``.procedure-combobox__hint``, ``.procedure-combobox__option--selected`` e o
chevron ligado à expansão). AGENTS §8: fatia de UI com vocabulário CSS novo
mantém ``static/css/app.css`` no blast radius e pina o vocabulário em teste —
este arquivo é essa guarda (padrão de ``tests/test_exam_type_badge_css.py``).

Regras pinadas sem comentários; os seletores são os exatos do bloco.
"""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static" / "css" / "app.css").read_text()

HINT_SELECTOR = ".procedure-combobox__hint"
SELECTED_OPTION_SELECTOR = ".procedure-combobox__option--selected"
CHEVRON_SELECTOR = ".procedure-combobox--enhanced::after"
CHEVRON_EXPANDED_SELECTOR = '.procedure-combobox--enhanced:has(.procedure-combobox__input[aria-expanded="true"])::after'
INPUT_SELECTOR = ".procedure-combobox__input"
# Borda de repouso (D5): o seletor vencedor precisa carregar o token de controle.
# Só ``.procedure-combobox__input`` (0,1,0) perde para ``.hospital-shell
# .form-control`` (0,2,0) — pinar o seletor baixo deixaria a regra como no-op.
RESTING_INPUT_SELECTOR = ".hospital-shell .procedure-combobox__input"


def _sem_comentarios(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _bloco_de(selector: str) -> str:
    """Declarações do bloco cujo seletor é exatamente ``selector``."""
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", _sem_comentarios(CSS))
    assert match is not None, f"Falta bloco CSS de {selector} em app.css"
    return match.group(1)


def test_hint_class_is_defined() -> None:
    assert _bloco_de(HINT_SELECTOR).strip(), "hint persistente de busca sem bloco CSS"


def test_selected_option_has_a_marker_beyond_color() -> None:
    bloco = _bloco_de(SELECTED_OPTION_SELECTOR)
    assert "font-weight" in bloco, "selecionada sem peso de fonte (marcador além de cor)"
    assert "--hospital-accent" in bloco, "selecionada sem barra à esquerda no accent"


def test_chevron_is_non_interactive_and_bound_to_the_expansion() -> None:
    assert re.search(r"pointer-events:\s*none", _bloco_de(CHEVRON_SELECTOR)), "chevron decorativo interceptando clique"
    assert "transform" in _bloco_de(CHEVRON_EXPANDED_SELECTOR), "chevron sem estado de expansão (rotação por :has())"


def test_input_resting_border_uses_the_stronger_token_on_the_winning_selector() -> None:
    # O helper falha se o seletor vencedor não existir: só a regra baixa
    # (``.procedure-combobox__input``) deixaria a borda como no-op no shell.
    repouso = _bloco_de(RESTING_INPUT_SELECTOR)
    assert re.search(r"border-color:\s*var\(--hospital-control-border\)", repouso), (
        "borda de repouso do input sem o token de controle no seletor vencedor"
    )
    assert "--hospital-border" not in repouso, "borda de repouso ainda com o token claro"


def test_input_hover_changes_the_border() -> None:
    hover = _bloco_de(INPUT_SELECTOR + ":hover")
    assert "border-color" in hover, "hover sem mudança de borda"


def test_input_meets_the_touch_target() -> None:
    assert re.search(r"min-height:\s*44px", _bloco_de(INPUT_SELECTOR)), "alvo de toque do input abaixo de 44 px"
