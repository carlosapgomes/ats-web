# Slice 001: Corrigir bug CSS do seletor `:has()` global

## Objetivo

A regra `.d-flex.gap-2:has(> .btn) { flex-direction: column }` (em `static/css/app.css`, dentro de `@media (max-width: 767.98px)`) foi criada para empilhar ações de *case cards* no mobile, mas casa acidentalmente com qualquer `.d-flex.gap-2` contendo um botão direto — incluindo o header. Escopá-la ao contexto correto elimina o efeito colateral que verticaliza o header (e outras fileiras) indevidamente.

## Arquivos

- `static/css/app.css` (único arquivo).
- `tests/test_css_has_scope.py` (novo — teste de regressão determinístico).

## Handoff / prompt para implementador (contexto zero)

> No arquivo `static/css/app.css`, dentro do bloco `@media (max-width: 767.98px)`, localize a regra:
>
> ```css
> /* Action button rows: stack vertically */
> .d-flex.gap-2:has(> .btn) {
>   flex-direction: column;
> }
> ```
>
> Substitua por uma versão escopada que só aplique a fileiras de ação dentro de cards de caso, expondo também uma classe utilitária explícita para reuso intencional:
>
> ```css
> /* Action button rows: stack vertically (only inside case cards or explicit utility) */
> .case-card .d-flex.gap-2:has(> .btn),
> .btn-stack-mobile {
>   flex-direction: column;
> }
> ```
>
> Não altere mais nada. Rode `uv run ruff check . && uv run ruff format --check .` (CSS não é coberto por ruff, mas garanta que nada no repo quebrou) e `uv run pytest`.

## TDD

### RED (teste primeiro)

Como CSS não roda em `pytest`, o teste de regressão é de **comportamento observável via template**: renderizar um snippet contendo `<div class="d-flex gap-2">` com um `.btn` **fora** de `.case-card` e assegurar que o HTML/CSS resultante **não** inclui a regra global que força coluna. Implementação prática: teste de string no CSS compilado/referenciado — ou, mais robusto, um teste que verifica que a regra `.d-flex.gap-2:has(> .btn)` sem prefixo de `.case-card` **não existe mais** em `app.css`.

`tests/test_css_has_scope.py`:

```python
from pathlib import Path

CSS = Path("static/css/app.css").read_text()

def test_global_has_rule_is_removed():
    """A regra global que forçava coluna em qualquer d-flex.gap-2 com botão deve ter sumido."""
    # a regra problema não pode aparecer sem qualificação de contexto
    assert ".case-card .d-flex.gap-2:has(> .btn)" in CSS  # nova regra escopada existe
    # garante que não há o seletor solto (sem prefixo .case-card)
    for line in CSS.splitlines():
        stripped = line.strip()
        if stripped.startswith(".d-flex.gap-2:has(> .btn)"):
            pytest.fail(f"Seletor global não-escopado ainda presente: {stripped!r}")

def test_btn_stack_mobile_utility_exists():
    assert ".btn-stack-mobile" in CSS

import pytest  # noqa: E402
```

(Ajustar imports conforme convenção do projeto.)

### GREEN

Aplicar a substituição acima.

### REFACTOR

Confirmar que nenhum outro seletor dependia do comportamento global (busca por `.d-flex.gap-2` nos templates).

## Critérios de sucesso

- [ ] Seletor global `.d-flex.gap-2:has(> .btn)` removido de `app.css`.
- [ ] Nova regra escopada `.case-card .d-flex.gap-2:has(> .btn)` + utilitária `.btn-stack-mobile` presentes.
- [ ] Teste `tests/test_css_has_scope.py` passa (2 testes).
- [ ] `uv run pytest` verde (sem regressões).
- [ ] Quality gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.

## Gates de autoavaliação

- [ ] Confirmei que nenhuma fileira de ações de cards quebra (busca por `.d-flex.gap-2` + `.btn` em `templates/`).
- [ ] Header não é mais afetado (verificação visual registrada no relatório).
- [ ] Commit com mensagem rastreável (`refactor(css): scope :has() button-stacking to case cards`).
