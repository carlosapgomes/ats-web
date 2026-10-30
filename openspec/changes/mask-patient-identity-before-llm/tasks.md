# Tasks: Mascaramento de identidade do paciente antes do LLM

## 0. Precondições

- [x] 0.1 Branch `feature/pii-mask-patient-identity` a partir de `main`.
- [x] 0.2 Probe somente-leitura em `tmp/sample-pdfs/` (5 PDFs): nome do
  arquivo = cabeçalho em 5/5; CNS numérico 3/5, `não cadastrado` 2/5;
  Nome Social vazio em 5/5. Sem identidade reproduzida em artefatos.

## 1. Slices

- [x] 1. Slice 1 — parser + máscara puros (TDD)
- [x] 2. Slice 2 — persistência da identidade local (TDD)
- [x] 3. Slice 3 — fronteira LLM mascarada fail-closed (TDD)
- [x] 4. Slice 4 — verificação com amostras + gate completo + relatório

## 2. Gates

- [x] `ruff check . && ruff format --check .` — verdes (307 arquivos).
- [x] `mypy .` — verde (338 arquivos).
- [x] `pytest` — neste ambiente via SQLite `--no-migrations` (Postgres de
  teste indisponível no sandbox): 4679 passed, 52 failed + 5 errors, todos
  pré-existentes no baseline `main` (54 failed + 5 errors; diff de falhas
  novas = zero). Gate oficial executado em seguida no Postgres de teste
  (`ats-web-test`, flags de intake em `false` como no baseline):
  **4736 passed, 1 failed** — a falha
  (`TestBackfillD3Table::test_forward_and_reverse_are_deterministic`)
  reproduz no `main` limpo (pré-existente, sem relação com a change).
  Com o `.env` local vazando flags `true`, 18 testes de flag falham nos
  dois ramos (ambiental, resolvido pinando as flags em `false`).
- [x] `openspec validate mask-patient-identity-before-llm` — válido
  (delta em `procedure-neutral-analysis`).
