<!-- markdownlint-disable MD013 -->

# Design: Data e intervalo personalizados para métricas do dashboard

## Estado atual

O dashboard usa `metrics_period=today|7d|30d|all`.

Arquivos relevantes:

- `apps/dashboard/views.py`
  - `_period_bounds(period)` calcula bounds dos presets;
  - `_compute_summary(period=...)`, `_compute_admission_flow(period=...)` e `_compute_average_times(period=...)` aplicam o período;
  - `dashboard_index()` normaliza `metrics_period` para a página completa;
  - `_dashboard_case_list_context()` preserva `metrics_period` na lista/partial.
- `templates/dashboard/index.html`
  - renderiza botões para `Hoje`, `7 dias`, `30 dias`, `Tudo`;
  - form de filtros da lista preserva `metrics_period` em hidden input.
- `templates/dashboard/_case_list.html`
  - paginação preserva `metrics_period`.
- `static/js/dashboard_search.js`
  - busca dinâmica parcial preserva `metrics_period`, mas ainda não conhece os novos campos customizados.

## Decisões

### D1. Um slice vertical único

Implementar em **1 slice vertical**.

Justificativa:

- a feature é pequena e localizada no dashboard;
- não requer migration, modelo, permissão ou workflow;
- separar em slice de backend e slice de UI seria horizontal e deixaria valor incompleto;
- separar `custom_date` e `custom_range` faria os mesmos 4–5 arquivos serem tocados duas vezes, aumentando retrabalho.

O slice deve tocar idealmente só:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html`
4. `static/js/dashboard_search.js`
5. `apps/dashboard/tests/test_dashboard.py`

### D2. Query params canônicos

Presets existentes permanecem:

```text
metrics_period=today
metrics_period=7d
metrics_period=30d
metrics_period=all
```

Novos modos:

```text
metrics_period=custom_date&metrics_date=YYYY-MM-DD
metrics_period=custom_range&metrics_start=YYYY-MM-DD&metrics_end=YYYY-MM-DD
```

Não reutilizar `date_from`/`date_to`, pois esses são filtros da **lista de casos**, não das métricas.

### D3. Representação interna do período

Para evitar duplicação entre `dashboard_index()` e `_dashboard_case_list_context()`, criar uma representação pequena em `apps/dashboard/views.py`.

Sugestão:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class MetricsPeriodSelection:
    period: str
    start: datetime | None
    end: datetime | None
    label: str
    total_label: str
    metrics_date: str = ""
    metrics_start: str = ""
    metrics_end: str = ""
    custom_active: bool = False
    error: str = ""
```

Funções sugeridas:

```python
def _parse_iso_date(raw: str) -> date | None:
    ...


def _resolve_metrics_period(params: QueryDict) -> MetricsPeriodSelection:
    ...
```

YAGNI: não criar app/service global. Esse helper pertence apenas ao dashboard.

### D4. Bounds locais

Reaproveitar `local_day_bounds(day)` de `apps.cases.services`.

Semântica:

| Período | start | end |
| --- | --- | --- |
| `today` | início local de hoje | início local de amanhã |
| `7d` | início local de hoje - 6 dias | início local de amanhã |
| `30d` | início local de hoje - 29 dias | início local de amanhã |
| `all` | `None` | `None` |
| `custom_date` | início local de `metrics_date` | início local do dia seguinte |
| `custom_range` | início local de `metrics_start` | início local do dia seguinte a `metrics_end` |

`metrics_start > metrics_end`, data inválida ou campo obrigatório ausente: fallback para `today` com `error` preenchido.

### D5. Filtragem DRY

Evitar múltiplos `if start is None` espalhados. Se possível, criar helper local:

```python
def _filter_between(qs: QuerySet[Case], field_name: str, start: datetime | None, end: datetime | None) -> QuerySet[Case]:
    if start is not None:
        qs = qs.filter(**{f"{field_name}__gte": start})
    if end is not None:
        qs = qs.filter(**{f"{field_name}__lt": end})
    return qs
```

Os helpers de métrica podem aceitar `selection` ou `start/end`. Preferir a menor mudança segura sobre reescrever tudo.

### D6. Labels

Expor no contexto:

- `metrics_period`: código normalizado (`today`, `7d`, `30d`, `all`, `custom_date`, `custom_range`);
- `metrics_period_label`: label legível;
- `total_label`: label do card total;
- valores dos campos (`metrics_date`, `metrics_start`, `metrics_end`);
- `metrics_period_error` se houver fallback.

Labels esperados:

| Período | `metrics_period_label` | `total_label` |
| --- | --- | --- |
| `today` | `Métricas de hoje` | `Total Hoje` |
| `7d` | `Métricas dos últimos 7 dias` | `Total 7 dias` |
| `30d` | `Métricas dos últimos 30 dias` | `Total 30 dias` |
| `all` | `Métricas de todo o histórico` | `Total geral` |
| `custom_date` | `Métricas de DD/MM/AAAA` | `Total DD/MM/AAAA` |
| `custom_range` | `Métricas de DD/MM/AAAA a DD/MM/AAAA` | `Total período` |

### D7. UI SSR sem framework JS

Manter os presets atuais como botões/pills.

Adicionar uma área `Personalizado` abaixo dos presets. Para manter SSR puro e evitar dependência de JS, usar uma destas abordagens simples:

1. `<details>` nativo aberto quando `custom_active` ou quando há erro; ou
2. seção sempre visível, compacta, com título `Personalizado`.

Preferência: `<details>` para reduzir ruído visual.

Dentro de `Personalizado`, usar **dois mini-forms independentes**, ambos `method="get"`:

- `Data específica`
  - hidden `metrics_period=custom_date`
  - input `type="date" name="metrics_date"`
  - botão `Aplicar`
- `Intervalo`
  - hidden `metrics_period=custom_range`
  - inputs `type="date" name="metrics_start"` e `metrics_end`
  - botão `Aplicar`

Cada mini-form deve preservar filtros da lista (`status`, `date_from`, `date_to`, `attention`, `search`) via hidden inputs, como a UI atual já faz para presets.

Não usar React/Vue/HTMX/DRF/JSON. JavaScript customizado só é necessário para a busca dinâmica preservar os novos query params.

### D8. Preservação de query string

Preservar `metrics_period`, `metrics_date`, `metrics_start`, `metrics_end` em:

- form de filtros da lista;
- link `Atenção necessária`;
- paginação do partial `_case_list.html`;
- `static/js/dashboard_search.js` (`getFilterParams()`);
- fallback SSR de submit tradicional.

Ao selecionar um preset (`today`, `7d`, `30d`, `all`), não carregar campos customizados antigos na URL.

### D9. Fallback e mensagens

A query inválida deve retornar HTTP 200 e usar `today`.

Exemplos inválidos:

```text
?metrics_period=custom_date
?metrics_period=custom_date&metrics_date=abc
?metrics_period=custom_range&metrics_start=2026-07-10
?metrics_period=custom_range&metrics_start=2026-07-12&metrics_end=2026-07-01
?metrics_period=banana
```

O template pode mostrar alerta discreto:

```text
Período personalizado inválido. Exibindo métricas de hoje.
```

### D10. Testes

Adicionar testes antes de implementar (RED):

- bounds e contagens para `custom_date`;
- bounds e contagens para `custom_range` inclusivo;
- fallback para inválido/missing/invertido;
- template exibe `Personalizado`, `Data específica`, `Intervalo`;
- label do período ativo;
- preservação em hidden inputs/link atenção/paginação;
- busca dinâmica preserva parâmetros customizados (teste pode validar HTML gerado; JS pode ser coberto por inspeção de string se o padrão do projeto já fizer isso).

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Confundir filtro da lista com período das métricas | Usar nomes `metrics_*`, labels claros e manter seções separadas |
| Custom range inválido gerar 500 | Parser defensivo + fallback para `today` |
| Perder parâmetro na busca dinâmica | Testar/preservar hidden inputs e atualizar `dashboard_search.js` |
| Template ficar poluído | Usar `<details>` ou seção compacta; presets continuam na primeira linha |
| Reescrita excessiva dos helpers | Preferir refactor mínimo e coeso; sem abstrações globais |

## Rollback

Reverter mudanças em:

- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- `templates/dashboard/_case_list.html`
- `static/js/dashboard_search.js`
- `apps/dashboard/tests/test_dashboard.py`

Sem migration prevista.
