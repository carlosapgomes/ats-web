# Tasks: Substituição do rótulo "follow-up" por "Pós-Procedimento" na UI

## Slices verticais (ordem executável)

- [ ] Slice 001 — Rename completo na UI (templates + flash) com varredura anti-regresso (`slices/slice-001-ui-rename.md`)
- [ ] Slice 002 — Manual §6 reescrito: Pós-Procedimento + sub-aba Histórico & Exportação + acesso CHD (`slices/slice-002-manual-section.md`)

## Preflight (uma vez por change)

- [ ] Working tree limpa em `main` (BASE_REF = HEAD do fechamento de `followup-chd-access-guard` se já executado; senão `1382bdb`)
- [ ] Baseline verde conhecida do último gate — não repetir por slice
- [ ] `openspec validate followup-pos-procedimento-ui` OK

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
