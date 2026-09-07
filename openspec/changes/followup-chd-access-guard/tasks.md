# Tasks: Acesso à aba Follow-up restrito a supervisores do CHD

## Slices verticais (ordem executável)

- [x] Slice 001 — Política de acesso CHD em accounts: helper `can_access_followup` + decorator `followup_access_required` + variável de contexto (`slices/slice-001-chd-policy.md`)
- [x] Slice 002 — Aplicação no dashboard: guard nas 4 views + pill condicional na nav + matriz de acesso (`slices/slice-002-dashboard-guard.md`)

## Preflight (uma vez por change)

- [ ] Working tree limpa em `main` @ `1382bdb` (BASE_REF; rc.3 deployada em produção)
- [ ] Baseline verde conhecida: gate da rc.3 (ruff/format/mypy OK · 3351 passed) — não repetir por slice
- [ ] `openspec validate followup-chd-access-guard` OK


## Registro de execução

### Slice 001
- Worker: RED (ImportError) → GREEN; 4 arquivos exatamente no blast radius; +24 testes em `test_access_policy.py` (235 passed no app); ruff/format/mypy direcionados OK.
- Review r1: BLOCK — P1: política concedia acesso a anônimo com `active_role="admin"` e a inativos (guard de identidade ausente); P2: processor reimplementava False de anônimo. Fix round aplicou guard `is_authenticated`+`is_active` primeiro e delegation incondicional; +casos anônimo(incl. admin)/inativos parametrizados.
- Review r2: `Merge verdict: OK with notes` (nota: gates confirmados pelo parent — 235 passed, ruff/format/mypy OK).


### Slice 002
- Worker: RED (5 failed em `-k chd`) → GREEN; 5 arquivos exatamente no blast radius (+14 testes; 436 no dashboard, 235 no accounts); ruff/format/mypy direcionados OK. Helpers `_login_as("manager")` → manager+scheduler; `_login_as_plain_manager` novo; pill via dashboard:index.
- Reabertura mínima do Slice 001 (descoberta no full-suite do worker): `StubUser` em `tests/test_base_header_navbar.py`/`test_page_title.py` sem `is_active` → AttributeError via `role_context` (15 falhas). Fix: +`is_active: bool = True` nos 2 doubles; suíte completa 3389 passed/0 failed.
- Review: 1 rodada — `Merge verdict: OK with notes`; P2 diferida: caso admin+scheduler com ativo manager também na rota de EXPORT (`TestHistoryExportAccess`) e assert de flash no bloqueio de export.

## Gate final (uma vez após todos os slices)

- [x] `uv run ruff check . && uv run ruff format --check .` (exit 0 — All checks passed! / 240 files)
- [x] `uv run mypy .` (exit 0 — 266 files)
- [x] `uv run pytest` (exit 0 — 3389 passed vs baseline 3351; +38 testes: 24 do slice 001, 14 do slice 002)
- [x] `openspec validate followup-chd-access-guard` OK; archive ADR-0005 fica para o fechamento pós-revisão humana

## Definition of Done

- [ ] Matriz de acesso (design D6) demonstrada por testes em todos os cenários
- [ ] Nenhuma migration; guard de intranet intacto; URLs inalteradas
- [ ] Commits atômicos por slice (parent, pós-review) + archive ADR-0005 + push
- [ ] Registro no change de renomeação (`followup-pos-procedimento-ui`): manual §6 refletirá o acesso CHD após ambos mergeados
