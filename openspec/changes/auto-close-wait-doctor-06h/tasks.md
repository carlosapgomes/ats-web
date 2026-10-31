# Tasks: Encerramento administrativo automático diário (06:00) de casos não avaliados

## 0. Preflight (uma vez por change)

- [ ] 0.1 Tree limpa (só untracked do próprio change), branch
  `feat/auto-close-wait-doctor-06h` a partir de
  `BASE_REF=08f94789e9c53a50369ee6fa9a26a05516ffdf08`.
  Banco `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d`.
- [ ] 0.2 Baseline: `uv run ruff check . && uv run ruff format --check .`,
  `uv run mypy .`, `uv run pytest -q` verdes em `main` (ou registrar delta
  pré-existente antes de começar o slice 001).

## 1. Slices verticais (ordem executável)

- [x] Slice 001 — Motivo "não avaliado" + razão na Linha do Tempo
  (`slices/slice-001-reason-code-timeline.md`) — implementado e revisado OK
  (reviewer pi/zai-glm-5.3/max, `task_42d5f7dac471`/`ctx_9e72ad22d766`,
  veredito OK 2026-10-31: R1–R4 verdes, diff +75/-0 em 3 arquivos, 39 testes
  focused + vizinhas verdes, ruff/mypy limpos; 3 MINOR + 2 OBSERVATIONS não
  bloqueantes). Gates full-repo: ruff 307 files OK, mypy 338 files OK,
  pytest 4721 passed + 19 failed pré-existentes (comprovado via stash que
  falham sem a mudança — flags de intake/catálogo).
- [x] Slice 002 — Batch de encerramento + management command, ator sistema
  (`slices/slice-002-batch-close-command.md`) — implementado e revisado OK
  (reviewer pi/zai-glm-5.3/max, `task_9cc3a9888cfd`/`ctx_cd7ccb7f5d35`,
  veredito OK 2026-10-31: R1–R6 verdes, diff em 3 arquivos, 10 testes novos
  + 472 regressão verdes, ruff/mypy limpos; 3 MINOR + 1 INFO não
  bloqueantes). Full `pytest`: 4731 passed + 19 failed pré-existentes
  (zero no escopo do slice).
- [x] Slice 003 — Agendamento diário 06:00 America/Bahia
  (`slices/slice-003-daily-schedule.md`) — implementado; revisão 1 apontou
  BLOCKER (migration sem dep `django_q`, fix `59bb8db`); re-revisão
  (`task_c2aa76b2fc4f`/`ctx_baa2caf64395`) LIFTED o BLOCKER original mas
  apontou DoD: implementação do slice 003 estava uncommitted (só a migration
  tinha subido). Corrigido neste commit: helper + command + testes + migration
  committed e pushed; veredito final do revisor pendente.

## 2. Gate final (uma vez após o slice 003)

- [ ] 2.1 Quality gate do `AGENTS.md`: ruff + mypy + pytest verdes.
- [ ] 2.2 Validar o change (`openspec change validate auto-close-wait-doctor-06h --strict`, se a CLI estiver disponível).
- [ ] 2.3 Push/merge/release/deploy: AGUARDANDO instrução explícita.
  (Stop rule: PARAR após cada slice e pedir confirmação explícita do próximo.)
