# Tasks: Filtro por tipo de exame com `<select>` nas filas

## 0. Preflight (uma vez por change)

- [x] 0.1 Tree limpa (só untracked do próprio change), branch
  `fix/queue-exam-type-select-filter` a partir de `BASE_REF=a8d4c75347699639757ea00ddd4cfd5128712ec6`.
- [ ] 0.2 Baseline: gate do RC7 verde em `main` (`ruff`, `mypy` 325 files,
  `pytest` 4613 passed); suíte completa NÃO reexecutada no preflight —
  focados por slice + gate final cobrem o risco (2 templates + 2 JS + 2
  arquivos de teste, sem migração/FSM/schema/backend).
  Banco de teste via `docker compose -f docker-compose.yml -f docker-compose.test.yml`
  (host `55433` se a `5433` estiver ocupada por outro projeto).
  *(preflight: `ats-web-test-db-1` Up healthy; baseline RC7 aceita sem rerun
  global — mudança restrita a templates/JS/testes, sem backend.)*

## 1. Slices verticais (ordem executável)

- [x] Slice 001 — Scheduler: `<select>` com filtro imediato (pending + processed)
  (`slices/slice-001-scheduler-select-filter.md`)
  *(review `OK with notes` 1 rodada; P2: comportamento runtime do JS provado por
  inspeção estática (sem runner JS no projeto — permitido pelo slice); RED 1 failed
  em markup de radios → GREEN 37 passed; 4 arquivos 112 passed; scheduler 347 passed;
  full 4618 passed; ruff/format/mypy ok. Decisão registrada: blast radius estendido a
  3 arquivos de teste legados (só asserts de markup, sem produção) —
  `test_expanded_catalog_scheduler`, `test_slice_004_paired_scheduler_appointment`,
  `test_specialized_scheduler`.)*
- [x] Slice 002 — Médico: `<select>` com filtro imediato, composição tipo+busca
  (`slices/slice-002-doctor-select-filter.md`) — após o slice 001 aceito.
  *(reviewer builtin indisponível: 2 tentativas falharam por limite de uso do
  provider Codex — sem veredito independente; parent verificou diretamente:
  diff restrito aos 4 arquivos (3 do slice + `test_expanded_catalog_queues`
  test-only), sem radios/btn-group restantes, `change` sem botão de ação,
  RED exit 1 em radios → GREEN 34 passed, regressão 17 passed, suite doctor
  557 passed, ruff/format ok. P2 herdado do slice 001: JS provado por inspeção
  estática, sem runner JS no projeto.)*

## 2. Gate final (uma vez após todos os slices)

- [x] 2.1 Quality gate do `AGENTS.md`: ruff check ok, ruff format ok (295 files),
  mypy ok (325 files), pytest **4624 passed** com `POSTGRES_TEST_HOST_PORT=55433`
  (5433 ocupada por `hmd-test-db-1` de outro projeto — workaround local, sem código).
- [x] 2.2 `openspec change validate queue-exam-type-select-filter --strict` → `valid`.
- [ ] 2.3 Push/merge final: AGUARDANDO revisão humana (não fazer push sem instrução).
