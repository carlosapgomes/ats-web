<!-- markdownlint-disable MD013 -->

# Tasks: Lease de 1 hora para a reserva de caso pelo médico

## Slice vertical

- [x] Slice 001 — Resolução de lease por contexto end-to-end (`slices/slice-001-context-lease.md`)

## Definition of Done do change

- [x] `_get_lease_seconds` resolve override explícito > setting por contexto > global.
- [x] Claim e renew aplicam a resolução por contexto sem mudar assinaturas públicas.
- [x] `doctor_decision` usa `CASE_LOCK_LEASE_SECONDS_DOCTOR = 3600`; `nir_receipt` e `scheduler_confirm` seguem em 300s.
- [x] GET da página de decisão médica estabelece `locked_until ≈ now + 1h`.
- [x] Heartbeat médico renova para `≈ now + 1h`; renew de lock expirado continua falhando.
- [x] Nenhum JS, template, FSM, migration, URL, permissão ou evento de auditoria alterado.
- [x] Testes existentes com `lease_seconds=0` continuam passando (precedência do override).
- [x] TDD RED → GREEN → REFACTOR comprovado no relatório.
- [x] Quality gate completo passou:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline` (3191 vs 3185).
- [x] Relatório `/tmp/doctor-decision-lock-lease-1h-slice-001-report.md` criado com RED/GREEN, snippets antes/depois, gates e rerun (consolidado pelo parent a partir do report inline do worker).
- [x] Commit rastreável criado pelo parent (loop parent-controlled); push da branch `change/doctor-decision-lock-lease-1h` pendente de instrução explícita do usuário.

## Regra de atualização

Marque o slice e cada item da Definition of Done somente depois que todos os critérios, inspeções e gates do arquivo do slice tiverem evidência. Qualquer falha mantém o change incompleto. Não marque parcialmente para representar intenção ou progresso.
