# Slice 2: Exibição no dashboard — card + histórico

## Objetivo

Adicionar card de último resumo no dashboard e página de histórico de resumos.

## Arquivos

### 1. `apps/dashboard/views.py` — adicionar

- `dashboard_summaries` — lista paginada de SupervisorSummary
- No `dashboard_index`: adicionar `latest_summary` ao contexto

### 2. `apps/dashboard/urls.py` — adicionar

- `path("summaries/", views.dashboard_summaries, name="summaries")`

### 3. `templates/dashboard/index.html` — adicionar card

Card abaixo dos sub-métricas com último resumo gerado:
- Período (janela em horário local)
- Métricas principais (recebidos, aceitos, recusados)
- Link "Ver todos os resumos"

### 4. `templates/dashboard/summaries.html` — novo

Tabela paginada com histórico de resumos:
- Colunas: Período, Recebidos, Processados, Avaliados, Aceitos, Imediata, Recusados, Em Andamento
- Badge de status (sent/pending)
- Paginação (25 por página)
- Nav pills: Dashboard / Prompts / Usuários / Auditoria

## Critérios de sucesso

- [ ] Card de último resumo aparece no dashboard (se existir)
- [ ] `/dashboard/summaries/` lista resumos com paginação
- [ ] Janelas exibidas em horário local (America/Sao_Paulo)
- [ ] Apenas manager/admin acessam
- [ ] Template estende `base.html`
- [ ] Testes: ~6
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 4
