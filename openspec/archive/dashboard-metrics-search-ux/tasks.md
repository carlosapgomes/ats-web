<!-- markdownlint-disable MD013 -->

# Tasks: Melhorias de UX e busca do dashboard

## Slices verticais

- [x] Slice 001 — Polimento UX: labels mobile e duração humana
  (`slices/slice-001-dashboard-ux-polish.md`)
- [x] Slice 002 — Métricas do dashboard por data selecionada
  (`slices/slice-002-metrics-date-selector.md`)
- [x] Slice 003 — Busca server-side indexada por nome ou registro
  (`slices/slice-003-server-side-indexed-search.md`)
- [x] Slice 004 — Busca dinâmica progressiva após 3 caracteres
  (`slices/slice-004-dynamic-search-progressive-enhancement.md`)

## Definition of Done global

- [x] Labels visíveis para `date_from` e `date_to` no card "Todos os Casos".
- [x] Tempo médio exibe horas/minutos quando o valor for maior ou igual a
  60 minutos.
- [x] Métricas diárias aceitam `metrics_date` e usam hoje como padrão.
- [x] Card "Aguardando por etapa" deixa claro que é snapshot atual.
- [x] Busca por nome do paciente funciona server-side com `search`.
- [x] Busca por número de ocorrência funciona server-side com `search`.
- [x] Busca só filtra com 3 ou mais caracteres.
- [x] Busca compõe com status, datas, attention e paginação.
- [x] Índices PostgreSQL `pg_trgm` existem para os campos pesquisados.
- [x] Busca dinâmica usa Vanilla JS, debounce e SSR parcial.
- [x] Sem JavaScript, submit tradicional continua funcional.
- [x] Sem Django REST Framework, SPA, WebSocket ou SSE.
- [x] Testes relevantes passam.
- [x] Quality gate executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatórios temporários de cada slice foram criados e informados.
- [x] Commits de implementação foram feitos sem commitar OpenSpec antes do
  arquivamento final.
- [x] Push realizado para a branch remota após cada slice.

## Observação para implementadores

É aceitável marcar checkboxes localmente durante a execução para orientar o
trabalho, mas não incluir arquivos OpenSpec nos commits de implementação. As
especificações só devem ser commitadas quando o change for arquivado ao final.

## Status final do change

Change concluído em 4 slices verticais, todos revisados antes do arquivamento.

### Commits de implementação

- `fb7b881` — Slice 001: polimento UX (duração humana + labels de data).
- `4669476` — Slice 002: seletor de data das métricas (`metrics_date`).
- `c46b34b` — Slice 003: busca server-side indexada.
- `06046db` — Slice 003 (correção pós-revisão): alinha a query aos índices
  trigram (`Lower()` + `__contains`), provado por `EXPLAIN`.
- `c145834` — Slice 004: busca dinâmica progressiva (partial SSR + JS).
- `95fa0ee` — Slice 004 (correção pós-revisão): partial não computa métricas
  (20 → 7 queries).
- `c733eb4` — Micro-fix pré-arquivamento: remove hidden `name="search"`
  duplicado do form da lista.

### Resumo do entregue

- Duração média legível (`N min` ou `X h YY min`) e labels visíveis para
  `date_from`/`date_to`.
- Métricas diárias por data selecionada (`metrics_date=YYYY-MM-DD`, padrão
  hoje; data inválida cai silenciosamente para hoje); card “Aguardando por
  etapa” rotulado como snapshot ATUAL.
- Busca server-side por nome (`structured_data.patient.name`) e registro
  (`agency_record_number`), case-insensitive, mínimo de 3 caracteres,
  compondo com status/datas/attention/metrics_date e paginação.
- Migration `cases.0011` com `pg_trgm` + índices GIN trigram sobre
  `lower(agency_record_number)` e `lower((structured_data #>> '{patient,name}'))`,
  confirmadamente utilizados pela query (Bitmap Index Scan).
- Busca dinâmica progressiva: partial `dashboard/_case_list.html` retornado
  via header `X-ATS-Partial: case-list`, Vanilla JS com debounce 400 ms,
  `AbortController`, mínimo de 3 caracteres e fallback de submit tradicional.

### Limitações aceitas

- L1: busca não é accent-insensitive (`unaccent` exige wrapper imutável fora
  de escopo — ver `design.md`).
- L2: o JS monta a URL a partir de `/dashboard/` (hardcoded) e detecta o
  filtro de atenção via classe CSS `btn-warning`; aceitável como melhoria
  progressiva (o submit tradicional permanece como fallback robusto).
