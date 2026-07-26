# Tasks: Restaurar baseline de testes isolado e determinístico

## Status

**COMPLETED — Slice 001 concluído.**

## Slice

- [x] Slice 001 — Isolar settings de teste e eliminar regressão temporal flakey (`slices/slice-001-repair-test-baseline.md`)

## Definition of Done

- [ ] `config.settings.test` ignora `DATABASE_URL` e `DB_*` genéricos.
- [ ] `TEST_DATABASE_URL` é o único override URL explícito do banco de teste.
- [ ] Default continua `localhost:${POSTGRES_TEST_HOST_PORT:-5433}/ats_web_test`, usuário `ats_web`.
- [ ] Testes subprocess provam default isolado e override `TEST_DATABASE_URL`.
- [ ] Nenhum teste/log imprime senha ou URL completa.
- [ ] Teste de dashboard usa instante fixo na fronteira UTC/local.
- [ ] Expectativa usa `timezone.localtime()` e valida `25/07/2026 21:37`.
- [ ] Nenhum `xfail`, `skip` ou tolerância a failure foi adicionado.
- [ ] `config/settings/base.py`, `dev.py`, `prod.py`, `db.py`, templates e views permanecem inalterados.
- [ ] RED A e RED B registrados.
- [ ] Testes alvo passam.
- [ ] Inspeção efetiva sem segredo confirma `ats_web_test`/5433 com comando canônico.
- [ ] `uv run ruff check .` passa.
- [ ] `uv run ruff format --check .` passa.
- [ ] `uv run mypy .` passa.
- [ ] `uv run pytest` sem prefixo/workaround passa com exit code 0 e zero failures/errors.
- [ ] Relatório `/tmp/restore-isolated-deterministic-test-baseline-slice-001-report.md` criado.
- [ ] Commit e push realizados.

## Regra de parada

Após este slice, retornar o `REPORT_PATH` e parar. O workflow GHCR só pode ser retomado após revisão do relatório e baseline verde confirmado por terceiro LLM.
