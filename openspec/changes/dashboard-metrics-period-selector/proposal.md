<!-- markdownlint-disable MD013 -->

# Proposal: Seletor de período para métricas do dashboard

**Change ID**: `dashboard-metrics-period-selector`  
**Risco**: PROFISSIONAL  
**Dependências**: `dashboard-metrics-search-ux`, `apps/dashboard`, `apps/cases`

## Problema

O dashboard gerencial já mostra o card `Tempo Médio`, mas a semântica temporal está pouco clara:

1. Sem `metrics_date`, os cards principais usam o dia local atual, enquanto `Tempo Médio` historicamente podia considerar todos os dados.
2. Com `metrics_date`, as médias ficam presas a um único dia de criação do caso, o que pode produzir valores vazios ou pouco representativos quando poucos ciclos terminaram naquele dia.
3. Supervisores precisam alternar rapidamente entre janelas operacionais comuns: hoje, últimos 7 dias, últimos 30 dias e todo o histórico.

## Objetivo

Substituir o seletor de data única das métricas por um seletor simples de período:

- `Hoje`
- `7 dias`
- `30 dias`
- `Tudo`

O dashboard deve continuar SSR puro e sem API/SPA, preservando filtros de lista, busca dinâmica e permissões existentes.

## Escopo

- `apps/dashboard/views.py`
  - parsing/validação do novo query param `metrics_period`;
  - helper de bounds locais por período;
  - ajuste de summary, fluxo de admissão e tempo médio para receber período;
  - tempo médio filtrado por timestamp de conclusão da etapa.
- `templates/dashboard/index.html`
  - trocar o form `metrics_date` por seletor/pills de período;
  - preservar `metrics_period` nos filtros da lista e no link de atenção.
- `static/js/dashboard_search.js` somente se necessário para preservar o novo parâmetro na busca dinâmica.
- `apps/dashboard/tests/test_dashboard.py`
  - regressões de período, labels e preservação de query string.

## Fora de escopo

- Gráficos, séries temporais ou comparação entre períodos.
- Exportação CSV/PDF ou relatórios BI.
- Reconstrução histórica do card `Aguardando por etapa`.
- Mudanças nas permissões do dashboard.
- Alterações em FSM, filas operacionais, modelo de domínio ou migrations.
- API JSON, Django REST Framework, SPA, WebSocket ou SSE.

## Decisões de escopo

### Período por query string simples

Usar `metrics_period=today|7d|30d|all`. Valores inválidos caem silenciosamente para `today`.

### `Aguardando por etapa` permanece snapshot atual

A fila atual não deve ser reconstruída historicamente. O card mantém badge `ATUAL`.

### Médias por etapa concluída no período

Para evitar distorção em casos criados recentemente e ainda não concluídos:

- `Upload → Decisão Médica`: filtrar por `doctor_decided_at` no período.
- `Decisão → Agendamento`: filtrar por `appointment_decided_at` no período.
- `Ciclo Total`: filtrar por `cleanup_completed_at` ou fallback para evento `CLEANUP_COMPLETED` no período.

### Cards principais continuam baseados em recebimento

`Total`, `Aceitos`, `Negados`, `Encerrados admin.` e `Em Andamento` continuam avaliando casos recebidos/criados no período selecionado. Para `Tudo`, consideram todo o histórico.

## Critérios de sucesso globais

- Dashboard continua acessível apenas para `manager`/`admin`.
- O seletor mostra `Hoje`, `7 dias`, `30 dias` e `Tudo`.
- Query string inválida de `metrics_period` não quebra a página.
- Cards principais usam casos criados no período selecionado.
- `Tempo Médio` usa timestamps de conclusão de cada etapa no período selecionado.
- `Ciclo Total` continua compatível com casos antigos via evento `CLEANUP_COMPLETED`.
- Filtros, busca e link de atenção preservam `metrics_period`.
- `Aguardando por etapa` continua indicado como snapshot atual.
- Sem DRF/SPA/endpoint JSON novo.
- Quality gate do `AGENTS.md` passa.
