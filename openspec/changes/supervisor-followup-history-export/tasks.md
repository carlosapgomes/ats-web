# Tasks: Histórico e exportação de follow-ups

## Slices verticais (ordem executável)

- [x] Slice 001 — Página Histórico: sub-abas, janela de datas, versão corrente, cards, tabela e busca (`slices/slice-001-history-page.md`)
- [x] Slice 002 — Exportação CSV da mesma população e filtros (`slices/slice-002-csv-export.md`)
- [x] Slice 003 — Filtros de linha (desfecho/causa/internação) na tabela e no CSV (`slices/slice-003-table-filters.md`)

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


### Slice 003
- Worker: RED (18 failed em `-k filter`) → GREEN; 3 arquivos exatamente no blast radius; +21 testes (64 no arquivo, 422 no app); ruff/format/mypy direcionados OK. 1 teste pré-existente ajustado (select "Causa" agora sempre renderiza options; intenção v1-fora-da-população preservada via count==1 + option).
- Nota: `rows_total` ("N desfechos no período") passa a refletir a tabela FILTRADA (coerente com D4: contador acompanha a tabela; cards não mudam).
- Review: 1 rodada — `Merge verdict: OK with notes`; P2 diferida: teste de concordância tabela↔CSV comparar chaves canônicas completas como conjuntos (Counter/sets), não só ARNs ordenados.

## Gate final (uma vez após todos os slices)

- [x] `uv run ruff check . && uv run ruff format --check .` (exit 0 — All checks passed! / 239 files formatted)
- [x] `uv run mypy .` (exit 0 — 265 files; 1 erro de tipagem em teste do Slice 001 corrigido na reabertura mínima do gate, commit `b414891`)
- [x] `uv run pytest` (exit 0 — 3351 passed vs baseline 3285; +54 testes do change)
- [x] `openspec validate supervisor-followup-history-export` OK; specs/archive conforme ADR-0005 no fechamento

## Definition of Done

- [x] Requisitos da spec `supervisor-followup-history` demonstrados pelos testes (cada scenario com cobertura direta/análoga; 3 reviews de implementação + 2 rodadas de review do plano)
- [x] Fluxo end-to-end coberto por testes (+54); smoke manual do supervisor fica no checklist de rollout do release v0.6.0-rc.3 (evidence pack)
- [x] Sem migrations/FSM/JS novo; `manager`/`admin` only; versões correntes only (confirmado em review)
- [x] Commits atômicos por slice (parent, pós-review) + archive ADR-0005 + push
- [x] Follow-up registrado: mini-change do manual do usuário §6 (sub-aba Histórico) antes do estável v0.6.0
