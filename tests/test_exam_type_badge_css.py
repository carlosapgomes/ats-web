"""Guarda de CSS dos badges de tipo de exame (fix-forward do rollout v0.8.0).

O Slice 007 projetou os badges especializados (echoendoscopia/cpre) com a
chave de CSS ``declared_type_key``, mas nenhuma fatia incluiu
``static/css/app.css`` no blast radius — em produção o span renderizava sem
variante de cor (Bootstrap 5 ``.badge`` sem fundo = quase invisível).
Este teste pina a existência das seis variantes do vocabulário completo.
"""

from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static" / "css" / "app.css").read_text()

VARIANTES = (
    "eda",
    "colonoscopy",
    "eda_colonoscopy",
    "echoendoscopy",
    "cpre",
)


def test_todas_as_variantes_de_badge_existem() -> None:
    for variante in VARIANTES:
        assert f".exam-type-{variante} {{" in CSS, f"Falta regra .exam-type-{variante} em app.css"


def test_variantes_especializadas_definem_fundo_texto_e_borda() -> None:
    """Cada variante especializada precisa do trio acessível bg/texto/borda."""
    for variante in ("echoendoscopy", "cpre"):
        inicio = CSS.index(f".exam-type-{variante} {{")
        bloco = CSS[inicio : CSS.index("}", inicio)]
        assert "background-color" in bloco, f"{variante}: sem background-color"
        assert "color" in bloco, f"{variante}: sem color (contraste do texto)"
        assert "border" in bloco, f"{variante}: sem border"
