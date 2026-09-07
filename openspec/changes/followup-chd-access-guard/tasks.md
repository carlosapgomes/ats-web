# Tasks: Acesso à aba Follow-up restrito a supervisores do CHD

## Slices verticais (ordem executável)

- [ ] Slice 001 — Política de acesso CHD em accounts: helper `can_access_followup` + decorator `followup_access_required` + variável de contexto (`slices/slice-001-chd-policy.md`)
- [ ] Slice 002 — Aplicação no dashboard: guard nas 4 views + pill condicional na nav + matriz de acesso (`slices/slice-002-dashboard-guard.md`)

## Preflight (uma vez por change)

- [ ] Working tree limpa em `main` @ `1382bdb` (BASE_REF; rc.3 deployada em produção)
- [ ] Baseline verde conhecida: gate da rc.3 (ruff/format/mypy OK · 3351 passed) — não repetir por slice
- [ ] `openspec validate followup-chd-access-guard` OK

## Gate final (uma vez após todos os slices)

- [ ] `uv run ruff check . && uv run ruff format --check .` (exit 0)
- [ ] `uv run mypy .` (exit 0)
- [ ] `uv run pytest` (exit 0, sem regressões vs baseline 3351)
- [ ] `openspec validate followup-chd-access-guard` OK; specs/archive conforme ADR-0005 no fechamento

## Definition of Done

- [ ] Matriz de acesso (design D6) demonstrada por testes em todos os cenários
- [ ] Nenhuma migration; guard de intranet intacto; URLs inalteradas
- [ ] Commits atômicos por slice (parent, pós-review) + archive ADR-0005 + push
- [ ] Registro no change de renomeação (`followup-pos-procedimento-ui`): manual §6 refletirá o acesso CHD após ambos mergeados
