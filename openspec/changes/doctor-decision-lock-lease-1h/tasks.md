<!-- markdownlint-disable MD013 -->

# Tasks: Lease de 1 hora para a reserva de caso pelo médico

## Slice vertical

- [ ] Slice 001 — Resolução de lease por contexto end-to-end (`slices/slice-001-context-lease.md`)

## Definition of Done do change

- [ ] `_get_lease_seconds` resolve override explícito > setting por contexto > global.
- [ ] Claim e renew aplicam a resolução por contexto sem mudar assinaturas públicas.
- [ ] `doctor_decision` usa `CASE_LOCK_LEASE_SECONDS_DOCTOR = 3600`; `nir_receipt` e `scheduler_confirm` seguem em 300s.
- [ ] GET da página de decisão médica estabelece `locked_until ≈ now + 1h`.
- [ ] Heartbeat médico renova para `≈ now + 1h`; renew de lock expirado continua falhando.
- [ ] Nenhum JS, template, FSM, migration, URL, permissão ou evento de auditoria alterado.
- [ ] Testes existentes com `lease_seconds=0` continuam passando (precedência do override).
- [ ] TDD RED → GREEN → REFACTOR comprovado no relatório.
- [ ] Quality gate completo passou:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] Relatório `/tmp/doctor-decision-lock-lease-1h-slice-001-report.md` criado com RED/GREEN, snippets antes/depois, gates e rerun.
- [ ] Commit rastreável e push da branch `change/doctor-decision-lock-lease-1h` realizados.

## Regra de atualização

Marque o slice e cada item da Definition of Done somente depois que todos os critérios, inspeções e gates do arquivo do slice tiverem evidência. Qualquer falha mantém o change incompleto. Não marque parcialmente para representar intenção ou progresso.
