# Slice 2: Migrar módulo `intake` para `{% block page_title %}`

## Objetivo

Converter os 7 templates do módulo `intake` para o novo `{% block page_title %}`.

## Arquivos (7 templates + 1 teste)

- `templates/intake/corrected_resubmission.html`
- `templates/intake/my_cases.html`
- `templates/intake/closed_cases_search.html`
- `templates/intake/case_detail.html`
- `templates/intake/closed_case_detail.html`
- `templates/intake/post_schedule_issue_form.html`
- `templates/intake/intake_home.html`
- `tests/test_page_title.py` — extensão.

## Handoff / prompt para implementador (contexto zero)

> Para cada um dos 7 templates abaixo, substitua:
>
> ```html
> {% block subtitle %}TEXTO{% endblock %}
> ```
> por:
> ```html
> {% block page_title %}<h1 class="page-title">TEXTO</h1>{% endblock %}
> ```
>
> Preservando `TEXTO` exatamente. Os textos são:
>
> - `corrected_resubmission.html`: `"Novo encaminhamento corrigido a partir de caso anterior"`
> - `my_cases.html`: `"Todos os seus encaminhamentos"`
> - `closed_cases_search.html`: `"Localize casos encerrados para registrar intercorrência"`
> - `case_detail.html`: `"Detalhes do encaminhamento e linha do tempo"`
> - `closed_case_detail.html`: `"Detalhes do caso encerrado"`
> - `post_schedule_issue_form.html`: `"Registrar intercorrência pós-agendamento"`
> - `intake_home.html`: `"Upload de encaminhamentos e acompanhamento de casos"`
>
> Não altere mais nada.

## TDD

### RED

Estender `tests/test_page_title.py` com teste parametrizado:

```python
import pytest
from pathlib import Path

INTAKE_TEMPLATES = [
    "templates/intake/corrected_resubmission.html",
    "templates/intake/my_cases.html",
    "templates/intake/closed_cases_search.html",
    "templates/intake/case_detail.html",
    "templates/intake/closed_case_detail.html",
    "templates/intake/post_schedule_issue_form.html",
    "templates/intake/intake_home.html",
]

@pytest.mark.parametrize("template_rel", INTAKE_TEMPLATES)
def test_intake_template_uses_page_title_block(template_rel):
    content = Path(template_rel).read_text()
    assert '{% block page_title %}<h1 class="page-title">' in content, (
        f"{template_rel} deve usar {{% block page_title %}} com <h1 class='page-title'>"
    )
    assert "{% block subtitle %}" not in content, (
        f"{template_rel} ainda contém {{% block subtitle %}}"
    )
```

### GREEN

Migrar os 7 templates.

### REFACTOR

Nenhum — migração mecânica.

## Critérios de sucesso

- [ ] 7 templates migrados; nenhum `{% block subtitle %}` restante em `intake`.
- [ ] Teste parametrizado passa (7 casos).
- [ ] `uv run pytest` verde.
- [ ] Quality gate completo.

## Gates de autoavaliação

- [ ] Confirmei que cada `<h1>` renderiza o texto esperado (verificação visual em 1 template representativo, ex.: `my_cases`).
- [ ] Commit rastreável (`refactor(intake): migrate page titles to h1`).
