# Tasks: Cache-busting nos JS das filas

## 0. Preflight (uma vez por change)

- [x] 0.1 Tree limpa (só untracked do próprio change), branch
  `fix/queue-filter-cache-busting` a partir de `BASE_REF=cfae1847d74d382eb8ade8c8fe4b0ed3b6f557f7`.
  Banco `ats-web-test-db-1` Up healthy; baseline RC8 aceita sem rerun global.
- [ ] 0.2 Baseline: gate do RC8 verde em `main` (`ruff`, `mypy` 325 files,
  `pytest` 4624 passed); suíte completa NÃO reexecutada no preflight —
  focados do slice + gate final cobrem o risco (2 templates, sem
  backend/migração/FSM).
  Banco de teste via `docker compose -f docker-compose.yml -f docker-compose.test.yml`
  (host `55433` se a `5433` estiver ocupada por outro projeto).

## 1. Slices verticais (ordem executável)

- [x] Slice 001 — Script tags das filas via `{% static %}`
  (`slices/slice-001-static-tag-queue-scripts.md`)
  *(reviewer builtin indisponível: 2 tentativas falharam por limite de uso do
  provider Codex — sem veredito independente; parent verificou diretamente:
  diff restrito aos 4 arquivos permitidos (2 templates + 2 testes, só asserts
  novos), `{% load static %}` + `{% static %}` nos 2 templates, grep de
  hardcoded em templates/ → 0, RED exit 1 → GREEN 73 passed, regressão vizinha
  247 passed, ruff/format ok.)*

## 2. Gate final (uma vez após o slice)

- [ ] 2.1 Quality gate do `AGENTS.md` com banco de teste isolado:
  `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.
- [ ] 2.2 `openspec change validate queue-filter-cache-busting --strict`.
- [ ] 2.3 Commit + push da branch; relatório do slice em markdown temporário
  com `REPORT_PATH`. Push/merge/release/deploy só com instrução explícita.
