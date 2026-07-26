# Tasks: Restaurar baseline de testes isolado e determinístico

## Status

**COMPLETED — ambos os ciclos (original + corretivo) concluídos.**

## Slice

- [x] Slice 001 — Isolar settings de teste e eliminar regressão temporal flakey (`slices/slice-001-repair-test-baseline.md`)

## Definition of Done

- [x] `config.settings.test` ignora `DATABASE_URL` e `DB_*` genéricos.
- [x] `TEST_DATABASE_URL` é o único override URL explícito do banco de teste.
- [x] Default continua `localhost:${POSTGRES_TEST_HOST_PORT:-5433}/ats_web_test`, usuário `ats_web`.
- [x] Testes subprocess provam default isolado e override `TEST_DATABASE_URL`.
- [x] Nenhum teste/log imprime senha ou URL completa.
- [x] Teste de dashboard usa instante fixo na fronteira UTC/local.
- [x] Expectativa usa `timezone.localtime()` e valida `25/07/2026 21:37`.
- [x] Nenhum `xfail`, `skip` ou tolerância a failure foi adicionado.
- [x] `config/settings/base.py`, `dev.py`, `prod.py`, `db.py`, templates e views permanecem inalterados.
- [x] RED A e RED B registrados.
- [x] Testes alvo passam.
- [x] Inspeção efetiva sem segredo confirma `ats_web_test`/5433 com comando canônico.
- [x] `uv run ruff check .` passa.
- [x] `uv run ruff format --check .` passa.
- [x] `uv run mypy .` passa.
- [x] `uv run pytest` sem prefixo/workaround passa com exit code 0 e zero failures/errors.
- [x] Relatório `/tmp/restore-isolated-deterministic-test-baseline-slice-001-report.md` criado.
- [x] Commit e push realizados.

## Regra de parada

Após este slice, retornar o `REPORT_PATH` e parar. O workflow GHCR só pode ser retomado após revisão do relatório e baseline verde confirmado por terceiro LLM.
