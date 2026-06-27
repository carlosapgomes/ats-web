# Relatório Slice 002: `Buscar caso antigo` como terceira aba do agendador

## Resumo da mudança

Transformar o botão discreto `🔍 Buscar histórico` em uma aba/entrada principal `Buscar caso antigo`, no mesmo nível das abas `Pendentes` e `Processados Hoje`.

## Arquivos tocados

| Arquivo | Mudança |
| --- | --- |
| `templates/scheduler/_nav.html` | **CRIADO** — partial de navegação com três abas (Pendentes, Processados Hoje, Buscar caso antigo). Badges condicionais (`data-count` apenas se valor presente). |
| `templates/scheduler/queue.html` | Substituído bloco `nav` inteiro (2 abas + botão standalone) por `{% include "scheduler/_nav.html" %}`. |
| `templates/scheduler/historical_search.html` | Adicionado `{% block nav %}{% include "scheduler/_nav.html" %}{% endblock %}` antes do conteúdo. |
| `apps/scheduler/views.py` | Adicionado `"active_tab": "historical"` ao contexto de `scheduler_historical_search`. |
| `apps/scheduler/tests/test_views.py` | 4 novos testes + 1 ajuste em teste existente de badges. |

## Evidência TDD

### RED — Testes falhando antes da implementação

```
FAILED apps/scheduler/tests/test_views.py::TestSchedulerProcessedTodayTab::test_scheduler_queue_nav_has_historical_search_tab
FAILED apps/scheduler/tests/test_views.py::TestSchedulerQueueRegulationDays::test_queue_nav_uses_action_and_neutral_count_badges
```

### GREEN — Testes passando após implementação

```
apps/scheduler/tests/test_views.py ....                                  [100%]
134 passed
```

### REFACTOR — Ajuste de formato (ruff format) + range de busca no teste de badges

Nenhuma refatoração adicional necessária.

## Snippets antes/depois

### `templates/scheduler/queue.html` — antes

```html
{% block nav %}
<nav class="app-nav mt-3" aria-label="Navegação">
  <ul class="nav nav-pills gap-2">
    <li class="nav-item">
      <a class="nav-link {% if active_tab == 'pending' %}active{% endif %} nav-count-badge nav-count-badge--danger"
         data-count="{{ total_notice_count }}" style="position:relative;"
         href="{% url 'scheduler:queue' %}?tab=pending">Pendentes</a>
    </li>
    <li class="nav-item">
      <a class="nav-link {% if active_tab == 'processed' %}active{% endif %} nav-count-badge nav-count-badge--neutral"
         data-count="{{ processed_today_count }}" style="position:relative;"
         href="{% url 'scheduler:queue' %}?tab=processed">Processados Hoje</a>
    </li>
  </ul>
</nav>
<div class="mt-2 mb-3">
  <a href="{% url 'scheduler:historical_search' %}" class="btn btn-sm btn-hospital-outline">
    🔍 Buscar histórico
  </a>
</div>
{% endblock %}
```

### `templates/scheduler/queue.html` — depois

```html
{% block nav %}
{% include "scheduler/_nav.html" %}
{% endblock %}
```

### `templates/scheduler/historical_search.html` — antes

Sem `{% block nav %}` — página sem navegação do agendador.

### `templates/scheduler/historical_search.html` — depois

```html
{% block nav %}
{% include "scheduler/_nav.html" %}
{% endblock %}
```

Segue antes de `{% block content %}`.

### `templates/scheduler/_nav.html` — criado

```html
{% comment %}
Partial de navegação do agendador com três abas.
...
{% endcomment %}
<nav class="app-nav mt-3" aria-label="Navegação">
  <ul class="nav nav-pills gap-2">
    <li class="nav-item">
      <a class="nav-link {% if active_tab == 'pending' %}active{% endif %} nav-count-badge nav-count-badge--danger"
         {% if total_notice_count is not None %}data-count="{{ total_notice_count }}"{% endif %}
         style="position:relative;"
         href="{% url 'scheduler:queue' %}?tab=pending">Pendentes</a>
    </li>
    <li class="nav-item">
      <a class="nav-link {% if active_tab == 'processed' %}active{% endif %} nav-count-badge nav-count-badge--neutral"
         {% if processed_today_count is not None %}data-count="{{ processed_today_count }}"{% endif %}
         style="position:relative;"
         href="{% url 'scheduler:queue' %}?tab=processed">Processados Hoje</a>
    </li>
    <li class="nav-item">
      <a class="nav-link {% if active_tab == 'historical' %}active{% endif %}"
         style="position:relative;"
         href="{% url 'scheduler:historical_search' %}">Buscar caso antigo</a>
    </li>
  </ul>
</nav>
```

### `apps/scheduler/views.py` — antes

```python
return render(
    request,
    "scheduler/historical_search.html",
    {
        "query": query,
        "results": results,
    },
)
```

### `apps/scheduler/views.py` — depois

```python
return render(
    request,
    "scheduler/historical_search.html",
    {
        "query": query,
        "results": results,
        "active_tab": "historical",
    },
)
```

## Gates de autoavaliação

### 1. A navegação foi extraída para partial ou duplicada? Por quê?

**Extraída para partial** (`templates/scheduler/_nav.html`). Como o partial é usado em duas páginas (`queue.html` e `historical_search.html`), a extração evita duplicação e mantém consistência visual. O partial é pequeno e focado (3 abas, ~30 linhas).

### 2. Que teste prova que `Buscar caso antigo` é aba/link principal?

`test_scheduler_queue_nav_has_historical_search_tab`:
- verifica que "Buscar caso antigo" está no conteúdo
- verifica que "/scheduler/historical/" está no conteúdo (link)
- verifica que as outras duas abas também estão presentes

### 3. Que teste prova que a página histórica marca essa aba como ativa?

`test_scheduler_historical_search_nav_marks_historical_active`:
- GET /scheduler/historical/
- verifica que 'href="/scheduler/historical/"' está no conteúdo
- verifica que a classe "active" está presente em torno desse link

### 4. O botão antigo com lupa foi removido? Que teste ou snippet prova?

`test_scheduler_queue_no_small_standalone_historical_button`:
- verifica que "🔍 Buscar histórico" **não** está no conteúdo
- verifica que "Buscar caso antigo" (nova aba) está presente

### 5. A busca histórica/query/permissão foi alterada? Esperado: não.

Não. Apenas `active_tab` foi adicionado ao contexto. Lógica de query, permissão e resultados permanece intacta.

### 6. Alguma migration/FSM/model foi criado/alterado? Esperado: não.

Não. Nenhum model, FSM ou migration foi criado ou alterado.

### 7. Quais comandos de validação foram executados?

- `uv run ruff check .` → All checks passed
- `uv run ruff format --check .` → 171 files already formatted
- `uv run mypy .` → Success: no issues found in 190 source files
- `uv run pytest` → 1586 passed

## Riscos/observações

- O partial `_nav.html` usa `data-count` condicional (`{% if total_notice_count is not None %}`). Na página histórica, esses valores não são passados, portanto as abas aparecem sem badges — consistente com a decisão D8 do design.
- O partial mantém nomes de variáveis iguais aos usados por `_scheduler_queue_context` (`active_tab`, `total_notice_count`, `processed_today_count`), então `queue.html` funciona sem mapeamento adicional.
- O botão `← Voltar para fila` permanece no conteúdo da `historical_search.html`, mesmo com a navegação em abas no topo. Isso não gera conflito visual — o botão está dentro do card de busca, abaixo da nav.
