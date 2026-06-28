# Slice 3: Migrar módulo `scheduler` para `{% block page_title %}`

## Objetivo

Converter os 6 templates do módulo `scheduler` para o novo `{% block page_title %}`. Atenção especial aos que usam variáveis e `|truncatechars` dentro do título.

## Arquivos (6 templates + 1 teste)

- `templates/scheduler/confirm.html` — `subtitle` contém variáveis: `"Caso {{ case.agency_record_number|default:case.case_id|truncatechars:16 }} · {{ patient_name }}"`.
- `templates/scheduler/confirm_post_schedule_issue.html` — idem.
- `templates/scheduler/historical_search.html` — `"Buscar casos processados/agendados"`.
- `templates/scheduler/context_detail.html` — `"Contexto do caso"`.
- `templates/scheduler/queue.html` — `"Solicitações de agendamento aguardando confirmação"`.
- `tests/test_page_title.py` — extensão.

**Nota:** `confirm.html` e `confirm_post_schedule_issue.html` são páginas de confirmação (fluxo crítico). Validar que o `<h1>` não interfere no layout do card de decisão (Slice 001b adicionou `btn-stack-mobile` ali).

## Handoff / prompt para implementador (contexto zero)

> Para cada um dos templates abaixo, substitua `{% block subtitle %}TEXTO{% endblock %}` por `{% block page_title %}<h1 class="page-title">TEXTO</h1>{% endblock %}`, preservando `TEXTO` exatamente (incluindo `{{ ... }}` e `|truncatechars:16`).
>
> - `confirm.html`: `"Caso {{ case.agency_record_number|default:case.case_id|truncatechars:16 }} · {{ patient_name }}"`
> - `confirm_post_schedule_issue.html`: idem
> - `historical_search.html`: `"Buscar casos processados/agendados"`
> - `context_detail.html`: `"Contexto do caso"`
> - `queue.html`: `"Solicitações de agendamento aguardando confirmação"`
>
> Não altere mais nada.

## TDD

### RED

Estender `tests/test_page_title.py`:

```python
SCHEDULER_TEMPLATES = [
    "templates/scheduler/confirm.html",
    "templates/scheduler/confirm_post_schedule_issue.html",
    "templates/scheduler/historical_search.html",
    "templates/scheduler/context_detail.html",
    "templates/scheduler/queue.html",
]

@pytest.mark.parametrize("template_rel", SCHEDULER_TEMPLATES)
def test_scheduler_template_uses_page_title_block(template_rel):
    content = Path(template_rel).read_text()
    assert '{% block page_title %}<h1 class="page-title">' in content
    assert "{% block subtitle %}" not in content

def test_scheduler_confirm_preserves_case_variables():
    content = Path("templates/scheduler/confirm.html").read_text()
    assert "{{ case.agency_record_number|default:case.case_id|truncatechars:16 }}" in content
    assert "{{ patient_name }}" in content
```

### GREEN

Migrar os 5 templates.

### REFACTOR

Confirmar que variáveis/filtros estão intactos dentro do `<h1>`.

## Critérios de sucesso

- [ ] 5 templates migrados; nenhum `{% block subtitle %}` restante em `scheduler`.
- [ ] Variáveis `{{ case... }}` e `{{ patient_name }}` preservadas.
- [ ] Testes passam; `uv run pytest` verde.
- [ ] Quality gate completo.

## Gates de autoavaliação

- [ ] Verifiquei que `confirm.html` renderiza `<h1>` com o número do caso sem quebrar layout.
- [ ] Commit rastreável (`refactor(scheduler): migrate page titles to h1`).
