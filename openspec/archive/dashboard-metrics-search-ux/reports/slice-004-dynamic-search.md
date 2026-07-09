<!-- markdownlint-disable MD013 MD014 MD022 MD031 MD040 -->

# Relatório do Slice 004 — Busca Dinâmica Progressiva

> **Atualização pós-verificação (eficiência do partial).** A verificação
> constatou que a view computava todas as métricas (summary, fluxo, tempos
> médios, resumo de supervisão) mesmo em requests parciais
> (`X-ATS-Partial: case-list`), descartando o resultado — ~20 queries por
> busca dinâmica. O check do header foi movido para o topo, retornando o
> partial antes das métricas: partial caiu de 20 para 7 queries. Detalhes na
> seção "Correção de eficiência" abaixo.

## Arquivos tocados

1. `apps/dashboard/views.py` — Extração do contexto da lista de casos para `_dashboard_case_list_context()`; detecção do header `X-ATS-Partial: case-list` para renderização parcial
2. `templates/dashboard/index.html` — Substituição da lista inline por container `id="dashboard-case-list"` com include do partial; adição do bloco `extra_js` para o script JS
3. `templates/dashboard/_case_list.html` — **Novo**: partial SSR com cards, estado vazio e paginação DRY
4. `static/js/dashboard_search.js` — **Novo**: Vanilla JS com debounce, AbortController, mínimo de 3 caracteres
5. `apps/dashboard/tests/test_dashboard.py` — 7 novos testes na classe `TestDashboardDynamicSearch`

## Resumo das mudanças

### 1. Partial SSR extraído (`_case_list.html`)

**Antes:** O markup de lista de casos, estado vazio e paginação estava inline em `index.html`, duplicando a lógica entre renderização normal e parcial.

**Depois:** `templates/dashboard/_case_list.html` contém o markup extraído. `index.html` inclui via:

```html
<div id="dashboard-case-list" data-dashboard-search-target>
  {% include "dashboard/_case_list.html" %}
</div>
```

### 2. View com suporte a partial

**Antes:** `dashboard_index` computava tudo inline.

**Depois:** Extraída função `_dashboard_case_list_context(request)` que monta o contexto da lista. `dashboard_index` detecta o header e renderiza apenas o partial:

```python
if request.headers.get("X-ATS-Partial") == "case-list":
    return render(request, "dashboard/_case_list.html", case_list_context)
```

### 3. JavaScript Vanilla com debounce

**Novo arquivo** `static/js/dashboard_search.js`:

- IIFE com escopo restrito ao dashboard
- Debounce de 400ms entre digitação e requisição
- Mínimo de 3 caracteres para disparar fetch
- Campo vazio dispara fetch imediato para limpar a busca
- `AbortController` para cancelar requisições anteriores (evita race condition)
- Preserva outros filtros (status, date_from, date_to, attention, metrics_date)
- `history.replaceState` para refletir `search` na URL
- Erro silencioso sem quebrar submit tradicional

## Autoavaliação

### 1. Qual teste prova que o partial não renderiza a página completa?

`test_partial_header_returns_only_partial` — verifica que com `X-ATS-Partial: case-list` a resposta contém o caso mas NÃO contém `base.html`, `Dashboard`, `Visão geral`.

### 2. Onde está o container atualizado pelo JS?

Em `templates/dashboard/index.html`:

```html
<div id="dashboard-case-list" data-dashboard-search-target>
  {% include "dashboard/_case_list.html" %}
</div>
```

O JS seleciona via `document.querySelector('[data-dashboard-search-target]')` e substitui `innerHTML`.

### 3. Qual mecanismo evita respostas antigas?

`AbortController`: cada nova requisição cria um novo controller e aborta o anterior via `currentController.abort()`. Se a resposta chegar após o abort, o `signal.aborted` é verificado antes de atualizar o DOM.

### 4. Qual regra impede fetch com 1 ou 2 caracteres?

No JS:

```javascript
if (termLength < DASHBOARD_SEARCH_MIN_CHARS) {
  cancelPreviousRequest();
  updateUrl(term);
  return; // não dispara fetch
}
```

E no backend: `if len(search_term) >= 3:` em `_dashboard_case_list_context`.

### 5. O formulário continua funcionando sem JS?

Sim. O botão `Filtrar` e o form `method="get"` permanecem intactos no template. O JS é melhoria progressiva — se falhar, o submit tradicional redireciona a página normalmente.

### 6. A paginação preserva `search`?

Sim. Os links de paginação no partial `_case_list.html` incluem `&search={{ search|urlencode }}%` conditionally.

### 7. Foi criado JSON ou API REST?

**Não.** Tudo é SSR puro: o JS faz fetch para `/dashboard/` com header `X-ATS-Partial: case-list` e o servidor retorna HTML parcial.

### 8. O relatório contém snippets antes/depois?

Sim, descritos acima.

## Critérios de sucesso

- [x] Testes foram escritos antes da implementação e falharam inicialmente.
- [x] Lista e paginação estão em partial DRY.
- [x] View retorna partial HTML com header explícito.
- [x] JS dispara fetch apenas com 3 ou mais caracteres, ou campo vazio.
- [x] JS usa debounce.
- [x] JS cancela ou ignora resposta antiga (AbortController).
- [x] Sem JavaScript, submit tradicional continua funcional.
- [x] Sem JSON, DRF, SPA, WebSocket ou SSE.
- [x] Quality gate do `AGENTS.md` passa (ruff, mypy, pytest).

## Correção de eficiência (pós-verificação)

### Problema

Em `dashboard_index`, as métricas eram computadas **antes** do check do
header `X-ATS-Partial`. O partial usa apenas `_dashboard_case_list_context`,
então summary/fluxo/tempos médios/`latest_summary` (~10 queries) eram
computados e descartados a cada busca dinâmica (uma por debounce).

Medido com `CaptureQueriesContext` (helper real `_login_as`):

| Request | Queries (antes) | Queries (depois) |
| --- | --- | --- |
| Página completa | 21 | 21 |
| Partial | 20 | **7** |

### Correção

O check do header foi movido para o início de `dashboard_index`, retornando o
partial antes de qualquer métrica:

```python
if request.headers.get("X-ATS-Partial") == "case-list":
    return render(
        request,
        "dashboard/_case_list.html",
        _dashboard_case_list_context(request),
    )
# ...métricas só para a página completa...
```

`AVG` (de `_compute_average_times`) e a tabela `cases_supervisorsummary`
(de `latest_summary`) não aparecem mais no log de queries do partial.

### Teste de regressão

`test_partial_does_not_compute_metrics` usa `CaptureQueriesContext` sobre o
partial e afirma que `AVG` e `supervisorsummary` **não** estão presentes no
SQL — guarda-contrato direto contra regressão da otimização.

## Quality Gate (após correção)

```text
ruff check .          -> All checks passed
ruff format --check . -> 175 files already formatted
mypy .                -> Success: no issues (195 arquivos)
pytest                -> 1754 passed
```
