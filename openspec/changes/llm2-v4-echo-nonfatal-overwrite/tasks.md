# Tasks: LLM2 v4 echo não-fatal (warning + overwrite)

## 0. Preflight (uma vez por change)

- [x] 0.1 Tree limpa, branch a partir de `BASE_REF=5661fea7425bfbb93898c377610612aa3c9be658`; banco de teste `ats-web-test-db-1` Up healthy.
- [x] 0.2 Baseline: gate verde em `main` verificado no gate final (ruff 295 files, mypy 325 files, pytest 4624 passed); worker executou RED/GREEN com focados antes do gate completo.

## 1. Slices verticais (ordem executável)

- [x] Slice 001 — Echo mismatch vira warning + overwrite sem retry
  Contract: `slices/slice-001-echo-nonfatal-overwrite.md`
  *(worker `READY_FOR_REVIEW` 2026-10-05: RED 4 failed/1 passed → GREEN 5 passed + schema 2 passed, ruff/mypy ok, diff restrito aos 2 arquivos; parent revisou diff + reexecutou focados 5 passed e gate completo 4624 passed.)*

## 2. Gate final (uma vez após o slice)

- [x] 2.1 Quality gate do `AGENTS.md`: ruff check ok, ruff format ok (295 files), mypy ok (325 files), pytest **4624 passed** (140s, test-db via compose.test).
- [x] 2.2 `openspec validate --changes` → 5 passed incl. `llm2-v4-echo-nonfatal-overwrite` (`--strict` legado: `valid`).
- [ ] 2.3 Push da branch + relatório consolidado: AGUARDANDO revisão humana final (não fazer push sem instrução).
