# Tasks: Substituição do rótulo "follow-up" por "Pós-Procedimento" na UI

## Slices verticais (ordem executável)

- [x] Slice 001 — Rename completo na UI (templates + flash) com varredura anti-regresso (`slices/slice-001-ui-rename.md`)
- [x] Slice 002 — Manual §6 reescrito: Pós-Procedimento + sub-aba Histórico & Exportação + acesso CHD (`slices/slice-002-manual-section.md`)

## Preflight (uma vez por change)

- [ ] **Dependência**: `followup-chd-access-guard` executado E arquivado (deltas encadeados + manual §6 dependem do guard; ordem inversa quebra os MODIFIED)
- [ ] Working tree limpa em `main` (BASE_REF = HEAD do fechamento de `followup-chd-access-guard`)
- [ ] Baseline verde conhecida do último gate — não repetir por slice
- [ ] `openspec validate followup-pos-procedimento-ui` OK


## Registro de execução

### Slice 001
- Worker: RED (varredura 3 + labels 1 falhando) → GREEN; 10 arquivos previstos + 2 da expansão aprovada (P1 do review: Http404 e 3 ValueErrors de `apps/cases/followup.py` eram strings visíveis renderizadas como erro de formulário/404) = 12 arquivos; 440 dashboard + 634 intake + cases verdes; grep D5 classificado sem hit visível.
- Review r1: BLOCK — P1 strings visíveis fora do inventário (Http404 `views.py:1963`; ValueErrors `followup.py:85,92,97`); fix round converteu + novo teste `test_mensagens_de_validacao_usam_pos_procedimento` no seam do serviço.
- Review r2: `Merge verdict: OK` (sem achados).
- Desvios: comentário do partial e aria-label do tablist atualizados (rótulo); glob do grep ajustado para `!**/tests/**`; linhas do inventário defasadas — conversão por conteúdo.


### Slice 002
- Worker: RED (3 asserts de manual falhando) → GREEN; 2 arquivos previstos; §6 + intro reescritos; manual sem anglicismo; 202 passed em tests/.
- Review r1: BLOCK — P1: CSV emitia header "Case ID" (inglês) contra a spec aplicada (header em português) que o manual §6.2 recém-documenta; P2: regex do teste anti-anglicismo mais estreita que o gate. Decisão do controller: enforçar a spec existente (não decisão nova) — "Case ID"→"ID do caso" (expansão mínima +views.py +test_followup_history.py); regex → `follow.?up`.
- Review r2: `Merge verdict: OK` (sem achados; 642 passed confirmado pelo parent).

## Gate final (uma vez após todos os slices)

- [ ] `uv run ruff check . && uv run ruff format --check .` (exit 0)
- [ ] `uv run mypy .` (exit 0)
- [ ] `uv run pytest` (exit 0, sem regressões vs baseline)
- [ ] `openspec validate followup-pos-procedimento-ui` OK; specs/archive conforme ADR-0005 no fechamento

## Definition of Done

- [ ] Nenhum "follow-up" visível ao usuário (grep em templates/flash/manual — case-insensitive)
- [ ] Código, URLs e filename CSV inalterados (verificado no review)
- [ ] Manual §6 documenta Registrar + Histórico & Exportação com acesso CHD
- [ ] Commits atômicos por slice (parent, pós-review) + archive ADR-0005 + push
