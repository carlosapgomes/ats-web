<!-- markdownlint-disable MD013 -->

# Proposal: Data e intervalo personalizados para métricas do dashboard

**Change ID**: `dashboard-metrics-custom-date-range`  
**Risco**: PROFISSIONAL  
**Dependências**: `dashboard-metrics-period-selector`, `apps/dashboard`, `apps/cases`

## Problema

O dashboard gerencial já oferece atalhos úteis em `Período das métricas`:

- `Hoje`
- `7 dias`
- `30 dias`
- `Tudo`

Esses presets atendem bem o uso operacional recorrente, mas não cobrem duas necessidades comuns de supervisão/auditoria:

1. analisar as métricas de uma **data específica** que não seja hoje;
2. analisar um **intervalo personalizado** que não coincide com 7/30 dias ou histórico completo.

Hoje o gestor precisa inferir esses recortes por filtros da lista de casos, mas esses filtros não devem alterar a semântica dos cards de métricas. Isso pode gerar confusão entre "filtro da lista" e "período das métricas".

## Objetivo

Adicionar, no bloco `Período das métricas`, uma opção `Personalizado` que permita escolher:

- uma **data específica**; ou
- um **intervalo de datas**.

A experiência deve manter os presets atuais como caminho principal e preservar a implementação SSR pura do projeto.

## Escopo

- `apps/dashboard/views.py`
  - normalizar os presets existentes e os novos períodos personalizados;
  - calcular bounds locais para data específica e intervalo inclusivo;
  - expor contexto de UI para destacar o período ativo e exibir label legível;
  - manter compatibilidade com busca dinâmica parcial e filtros da lista.
- `templates/dashboard/index.html`
  - manter os botões/pills atuais;
  - adicionar área `Personalizado` com dois fluxos SSR simples: data específica e intervalo;
  - preservar filtros da lista ao aplicar/preservar o período das métricas.
- `templates/dashboard/_case_list.html`
  - preservar os novos query params customizados na paginação.
- `static/js/dashboard_search.js`
  - preservar `metrics_date`, `metrics_start` e `metrics_end` nas requisições parciais.
- `apps/dashboard/tests/test_dashboard.py`
  - cobrir parsing, bounds, fallback, renderização e preservação de query string.

## Fora de escopo

- Alterar modelos, migrations, FSM, filas operacionais ou permissões.
- Criar API JSON, Django REST Framework, SPA, HTMX, WebSocket ou SSE.
- Criar gráficos, séries históricas, comparação entre períodos ou exportações.
- Alterar a semântica dos filtros da lista (`date_from`, `date_to`, `status`, `search`, `attention`).
- Reconstruir historicamente o card `Aguardando por etapa`; ele continua snapshot atual.
- Reintroduzir `metrics_date` antigo como seletor único fora da opção personalizada.

## Decisões de escopo

### D1. Presets continuam principais

Os atalhos `Hoje`, `7 dias`, `30 dias` e `Tudo` continuam visíveis e rápidos. `Personalizado` deve ser complementar, não substituir a UX atual.

### D2. Query string canônica

Manter `metrics_period` como parâmetro principal:

| Caso | Query string |
| --- | --- |
| Hoje | `metrics_period=today` |
| 7 dias | `metrics_period=7d` |
| 30 dias | `metrics_period=30d` |
| Tudo | `metrics_period=all` |
| Data específica | `metrics_period=custom_date&metrics_date=YYYY-MM-DD` |
| Intervalo | `metrics_period=custom_range&metrics_start=YYYY-MM-DD&metrics_end=YYYY-MM-DD` |

Usar nomes `metrics_*` evita colisão com filtros da lista (`date_from`/`date_to`).

### D3. Datas locais e intervalo inclusivo

- Data específica usa o dia local completo (`00:00` local até início do próximo dia local).
- Intervalo usa `metrics_start` e `metrics_end` como datas inclusivas na UI.
- Internamente o bound final deve ser exclusivo no início do dia seguinte a `metrics_end`.

### D4. Fallback seguro

Valores inválidos, ausentes ou intervalo invertido não devem quebrar a página. A implementação deve cair para `today` e sinalizar no contexto/template que o personalizado é inválido, preferencialmente com alerta discreto.

### D5. Métricas mantêm semântica existente

A mudança altera apenas os bounds temporais. As regras atuais permanecem:

- cards principais e fluxo de admissão filtram por `created_at` no período selecionado;
- `Tempo Médio` filtra por timestamp de conclusão da etapa (`doctor_decided_at`, `appointment_decided_at`, `cleanup_completed_at`/evento fallback);
- `Aguardando por etapa` continua snapshot atual e rotulado `ATUAL`.

## Critérios de sucesso globais

- Dashboard continua acessível apenas para `manager`/`admin`.
- Presets atuais continuam funcionando sem regressão.
- Usuário consegue aplicar data específica via query string e UI.
- Usuário consegue aplicar intervalo personalizado via query string e UI.
- Período ativo é visível, com label legível (`Métricas de DD/MM/AAAA` ou `Métricas de DD/MM/AAAA a DD/MM/AAAA`).
- Query inválida não quebra a página e cai para `Hoje`.
- Filtros, link de atenção, paginação e busca dinâmica preservam os novos parâmetros.
- Sem migration/model/FSM/permissão/API nova.
- Quality gate do `AGENTS.md` passa quando o slice for implementado.
