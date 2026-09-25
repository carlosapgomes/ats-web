"""Guarda de CSS dos badges de tipo de exame (fix-forward do rollout v0.8.0).

O Slice 007 projetou os badges especializados (echoendoscopia/cpre) com a
chave de CSS ``declared_type_key``, mas nenhuma fatia incluiu
``static/css/app.css`` no blast radius — em produção o span renderizava sem
variante de cor (Bootstrap 5 ``.badge`` sem fundo = quase invisível).
Este teste pina a existência das variantes do vocabulário completo.

Design D12 (catálogo ampliado): as dez identidades atômicas compartilham bloco
visual POR FAMÍLIA — os quatro códigos de EDA num bloco, os quatro da família
Colonoscopia noutro — e somente ``eda_colonoscopy``/Ecoendoscopia/CPRE mantêm
bloco próprio. Nenhuma variação ganha cor própria.
"""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static" / "css" / "app.css").read_text()

FAMILIA_EDA = (
    "eda",
    "eda_gastrostomy",
    "eda_capsule",
    "eda_dilation",
)
FAMILIA_COLONOSCOPIA = (
    "colonoscopy",
    "rectosigmoidoscopy",
    "rectosigmoidoscopy_dilation",
    "rectosigmoidoscopy_argon",
)
BLOCO_PROPRIO = (
    "eda_colonoscopy",
    "echoendoscopy",
    "cpre",
)


def _sem_comentarios(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _grupo_de_seletores(selector: str) -> list[str]:
    """Lista de seletores do bloco que contém ``selector`` (nunca vazio)."""
    for match in re.finditer(r"(?m)^([^{}]+)\{", _sem_comentarios(CSS)):
        grupo = [item.strip() for item in match.group(1).split(",")]
        if selector in grupo:
            return grupo
    raise AssertionError(f"Falta bloco CSS de {selector} em app.css")


def _bloco_de(selector: str) -> str:
    css = _sem_comentarios(CSS)
    inicio = css.index(selector)
    return css[inicio : css.index("}", inicio)]


def test_todas_as_variantes_de_badge_existem() -> None:
    for variante in (*FAMILIA_EDA, *FAMILIA_COLONOSCOPIA, *BLOCO_PROPRIO):
        assert f".exam-type-{variante}" in _grupo_de_seletores(f".exam-type-{variante}")


def test_familias_agrupam_os_dez_codigos_por_bloco_visual() -> None:
    assert _grupo_de_seletores(".exam-type-eda") == [f".exam-type-{code}" for code in FAMILIA_EDA]
    assert _grupo_de_seletores(".exam-type-colonoscopy") == [f".exam-type-{code}" for code in FAMILIA_COLONOSCOPIA]


def test_variantes_sem_familia_mantem_bloco_proprio() -> None:
    for variante in BLOCO_PROPRIO:
        assert _grupo_de_seletores(f".exam-type-{variante}") == [f".exam-type-{variante}"]


def test_variantes_definem_fundo_texto_e_borda() -> None:
    """Cada bloco precisa do trio acessível bg/texto/borda."""
    for variante in ("eda", "colonoscopy", "eda_colonoscopy", "echoendoscopy", "cpre"):
        bloco = _bloco_de(f".exam-type-{variante}")
        assert "background-color" in bloco, f"{variante}: sem background-color"
        assert "color" in bloco, f"{variante}: sem color (contraste do texto)"
        assert "border" in bloco, f"{variante}: sem border"
