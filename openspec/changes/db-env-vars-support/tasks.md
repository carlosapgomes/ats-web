# Tasks: Suporte a variáveis individuais de banco de dados

## Slices verticais

- [x] Slice 001 — Helper `get_db_config()` + aplicação em dev/test/prod (`slices/slice-001-individual-db-env-vars.md`)

Apenas 1 slice porque o change é pequeno e coeso — não há como entregar valor parcial sem o helper + uso nos 3 settings simultaneamente.

## Definition of Done do change

- [ ] `config/settings/db.py` criado com `_required_environment`, `_environment_or_file` e `get_db_config()`.
- [ ] Caminho `DATABASE_URL`: usa `dj_database_url.parse()`, retorna dict com `conn_max_age`/`conn_health_checks` aplicados.
- [ ] Caminho vars individuais: monta dict Django **direto** (sem construir URL intermediária).
- [ ] `DB_PASSWORD_FILE` suportado via `_environment_or_file` com precedência sobre `DB_PASSWORD`.
- [ ] `DB_CONN_MAX_AGE` como env var opcional, sobrescrevendo o default do ambiente.
- [ ] `DB_APPLICATION_NAME` como env var opcional, aparece em `OPTIONS["application_name"]`.
- [ ] `config/settings/prod.py` atualizado — sem default de senha (fail fast).
- [ ] `config/settings/dev.py` atualizado — defaults locais preservados.
- [ ] `config/settings/test.py` atualizado — defaults de teste preservados.
- [ ] `import dj_database_url` removido dos 3 settings modules (só `db.py` importa).
- [ ] Testes unitários em `config/settings/tests/test_db.py` (14 casos).
- [ ] `DATABASE_URL` permanece com precedência (retrocompatível).
- [ ] Senhas com caracteres especiais (`@:;/%`) preservadas intactas.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Commit e push realizados.

## Observações para implementadores

- Implementar o slice único.
- Seguir TDD: RED → GREEN → REFACTOR.
- Não alterar docker-compose files — eles continuam usando `DATABASE_URL`.
- Gerar relatório temporário com evidências RED/GREEN.
