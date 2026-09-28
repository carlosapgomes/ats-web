# Tasks: LLM2 v4 echo-mismatch observability + retry

## 0. Preflight (uma vez por change)

- [x] 0.1 Tree limpa, branch a partir de `BASE_REF=e0f03aa2e7970a36a1adfbf07c0a5cffeab4a45f`;
  branch real: `fix/llm2-v4-echo-mismatch-fix` (HEAD == BASE_REF, só untracked do próprio change).
- [x] 0.2 Baseline: `main` em `e0f03aa` = gate verde do RC6 (deploy prod 2026-09-28).
  Suíte completa NÃO reexecutada no preflight; focados por slice + gate final cobrem o risco
  (mudança restrita a 1 módulo + 1 arquivo novo de teste, sem migração/FSM/schema).
  Banco de teste `ats-web-test-db-1` Up (healthy).

## 1. Slices verticais (ordem executável)

- [x] Slice 001 — Erro de echo mismatch passa a expor `got` + metadados do raw
  (`slices/slice-001-echo-mismatch-observability.md`)
  *(review `OK with notes` 1 rodada; P2: sem teste de sucesso direto no arquivo novo —
  coberto por `test_v4_existing_workflow.py`; focados 3 passed + schema 2 passed;
  ruff/format/mypy ok; full 4609 passed com `POSTGRES_TEST_HOST_PORT=55433`.)*
- [x] Slice 002 — Retry one-shot para echo mismatch com instrução corretiva
  (`slices/slice-002-echo-mismatch-retry.md`)
  *(review `OK with notes` 1 rodada; P2: retry reconstrói do prompt base — na rara sequência
  language-retry→echo-mismatch a instrução de idioma é descartada (limitado, revalidado, máx 4 calls);
  asserts R5 do slice 001 atualizados 1→2 calls conforme permitido; focados 7 passed +
  schema 2 passed + orchestrator 28 passed; ruff/format/mypy ok.)*

## 2. Gate final (uma vez após todos os slices)

- [x] 2.1 Quality gate do `AGENTS.md`: ruff check ok, ruff format ok (295 files),
  mypy ok (325 files), pytest **4613 passed** com `POSTGRES_TEST_HOST_PORT=55433`
  (porta 5433 ocupada por `hmd-test-db-1` de outro projeto; `ats-web-test-db-1` remapeado
  para 55433 — workaround local, sem mudança de código).
- [x] 2.2 `openspec change validate llm2-v4-echo-mismatch-fix --strict` → `valid`.
- [ ] 2.3 Push da branch + relatório consolidado: AGUARDANDO revisão humana final (não fazer push sem instrução).
