# Tasks: LLM2 v4 echo-mismatch observability + retry

## 0. Preflight (uma vez por change)

- [x] 0.1 Tree limpa, branch a partir de `BASE_REF=e0f03aa2e7970a36a1adfbf07c0a5cffeab4a45f`;
  branch real: `fix/llm2-v4-echo-mismatch-fix` (HEAD == BASE_REF, só untracked do próprio change).
- [x] 0.2 Baseline: `main` em `e0f03aa` = gate verde do RC6 (deploy prod 2026-09-28).
  Suíte completa NÃO reexecutada no preflight; focados por slice + gate final cobrem o risco
  (mudança restrita a 1 módulo + 1 arquivo novo de teste, sem migração/FSM/schema).
  Banco de teste `ats-web-test-db-1` Up (healthy).

## 1. Slices verticais (ordem executável)

- [ ] Slice 001 — Erro de echo mismatch passa a expor `got` + metadados do raw
  (`slices/slice-001-echo-mismatch-observability.md`)
- [ ] Slice 002 — Retry one-shot para echo mismatch com instrução corretiva
  (`slices/slice-002-echo-mismatch-retry.md`)

## 2. Gate final (uma vez após todos os slices)

- [ ] 2.1 Quality gate do `AGENTS.md` com banco de teste isolado:
  `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`
  (subir `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d` antes do pytest).
- [ ] 2.2 `openspec change validate llm2-v4-echo-mismatch-fix --strict` (ou `openspec validate` conforme CLI).
- [ ] 2.3 Commit + push da branch; relatório de cada slice em markdown temporário com `REPORT_PATH`.
