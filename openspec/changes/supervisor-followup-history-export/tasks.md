# Tasks: Histórico e exportação de follow-ups

## Slices verticais (ordem executável)

- [x] Slice 001 — Página Histórico: sub-abas, janela de datas, versão corrente, cards, tabela e busca (`slices/slice-001-history-page.md`)
- [x] Slice 002 — Exportação CSV da mesma população e filtros (`slices/slice-002-csv-export.md`)
- [ ] Slice 003 — Filtros de linha (desfecho/causa/internação) na tabela e no CSV (`slices/slice-003-table-filters.md`)

## Preflight (uma vez por change)

- [x] Working tree limpa em `main` @ `36b0383` (BASE_REF; rc.1+rc.2 deployadas em produção)
- [x] Baseline verde conhecida: gate da rc.2 (ruff/format/mypy OK · 3285 passed) — não repetir por slice
- [x] `openspec validate supervisor-followup-history-export` OK

## Justificativa de blast radius ampliado (stop rule §6)

Slice 001 declara 8 arquivos (> heurística ≤5): 3 são templates de dimensionamento
trivial (partial novo de sub-abas, include de 1 linha na listagem atual, página
nova) e os demais são service-helper + view/urls + testes; a página é um
comportamento único end-to-end e quebrá-la em mais slices criaria estados
parciais não observáveis. Slices 002/003 retornam ao padrão (≤4 arquivos).


## Registro de execução

### Slice 001
- Worker: RED confirmado (ImportError `current_follow_ups`/NoReverseMatch rota) → GREEN; 8 arquivos exatamente no blast radius; gates focados verdes (47 passed nos testes focados; `apps/dashboard/tests` verde).
- Review: 1 rodada — `Merge verdict: OK`, sem achados.
- Nota de borda aceita (design D3, fonte única): caso gravado que perde elegibilidade atual sai do Histórico (eixo = data de grupo via `is_followup_eligible`) — mesmo predicado da aba Registrar.


### Slice 002
- Worker: RED (NoReverseMatch da rota) → GREEN; 4 arquivos exatamente no blast radius; 43 passed no arquivo focado; ruff/format OK.
- Decisão do controller em execução (semânticas de célula CSV, dentro de D5): Case ID=UUID completo; Ocorrência=ARN (vazio se ausente); Versão=numérica; Causa vazia quando realizado; Submotivo só em resource_shortage; Outra causa (texto)=other_reason.
- Review: 1 rodada — `Merge verdict: OK with notes`; P2 diferida: teste anônimo do export criar dados e afirmar ausência de conteúdo (ARN/paciente) no corpo.

## Gate final (uma vez após todos os slices)

- [ ] `uv run ruff check . && uv run ruff format --check .` (exit 0)
- [ ] `uv run mypy .` (exit 0)
- [ ] `uv run pytest` (exit 0, sem regressões vs baseline 3285)
- [x] `openspec validate supervisor-followup-history-export` OK; specs/archive conforme ADR-0005 no fechamento

## Definition of Done

- [ ] Requisitos da spec `supervisor-followup-history` demonstrados pelos testes (cada scenario tem cobertura direta ou análoga)
- [ ] Supervisor navega: sub-aba Histórico → janela/busca → cards+tabela → filtros de linha → export CSV fiel (manual em dev com fixtures)
- [ ] Sem migrations/FSM/JS novo; `manager`/`admin` only; versões correntes only
- [ ] Commits atômicos por slice (parent, pós-review) + archive ADR-0005 + push
- [ ] Mini-change posterior registrado no fechamento: manual do usuário §6 (sub-aba Histórico) — fora do escopo deste change
