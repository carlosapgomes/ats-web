# Tasks: Alinhar Contrato LLM e Roteamento NIR → Médico

## Status

Change criado para corrigir divergências críticas identificadas na investigação NIR → médico.

## Slices

- [x] Slice 001 — Prompts canônicos legados (`slices/slice-001-canonical-prompts.md`) — commit `a2e9b23`, report `/tmp/ats-web-slice-001-canonical-prompts-report.md`
- [ ] Slice 002 — Contrato Pydantic LLM1 (`slices/slice-002-llm1-pydantic-contract.md`)
- [ ] Slice 003 — Contrato Pydantic LLM2 (`slices/slice-003-llm2-pydantic-contract.md`)
- [ ] Slice 004 — Scope gate direto para resultado NIR (`slices/slice-004-scope-gate-nir-final.md`)
- [ ] Slice 005 — Presenter médico em 7 blocos (`slices/slice-005-doctor-report-presenter.md`)
- [ ] Slice 006 — Role guard médico (`slices/slice-006-doctor-role-guard.md`)
- [ ] Slice 007 — Quality gate e closeout (`slices/slice-007-quality-docs-closeout.md`)

## Definition of Done do Change

- [ ] Pipeline usa nomes canônicos de prompts do legado.
- [ ] Defaults e fallbacks de prompts são compatíveis com o legado.
- [ ] LLM1 valida schema Pydantic legado.
- [ ] LLM2 valida schema Pydantic legado.
- [ ] `non_eda` e `unknown` não entram na fila médica.
- [ ] NIR recebe resultado de revisão manual obrigatória para scope gate.
- [ ] Tela médica exibe relatório equivalente aos 7 blocos do legado.
- [ ] Views médicas exigem papel ativo `doctor`.
- [ ] Quality gate completo executado.
- [ ] Relatórios dos slices gerados.
