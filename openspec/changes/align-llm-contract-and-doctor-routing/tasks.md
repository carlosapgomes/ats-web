# Tasks: Alinhar Contrato LLM e Roteamento NIR → Médico

## Status

Change criado para corrigir divergências críticas identificadas na investigação NIR → médico.

## Slices

- [x] Slice 001 — Prompts canônicos legados (`slices/slice-001-canonical-prompts.md`) — commit `a2e9b23`, report `/tmp/ats-web-slice-001-canonical-prompts-report.md`
- [x] Slice 002 — Contrato Pydantic LLM1 (`slices/slice-002-llm1-pydantic-contract.md`) — commit `9a0f0e8`, report `/tmp/ats-web-slice-002-llm1-pydantic-report.md`
- [x] Slice 003 — Contrato Pydantic LLM2 (`slices/slice-003-llm2-pydantic-contract.md`) — commit `37c0144`, report `/tmp/ats-web-slice-003-llm2-pydantic-report.md`
- [x] Slice 004 — Scope gate direto para resultado NIR (`slices/slice-004-scope-gate-nir-final.md`) — commit `ab5d5dd`, report `/tmp/ats-web-slice-004-scope-gate-nir-final-report.md`
- [x] Slice 005 — Presenter médico em 7 blocos (`slices/slice-005-doctor-report-presenter.md`) — commit `d6c5fff`, report `/tmp/ats-web-slice-005-doctor-report-presenter-report.md`
- [x] Slice 006 — Role guard médico (`slices/slice-006-doctor-role-guard.md`) — commit `0835256`, report `/tmp/ats-web-slice-006-doctor-role-guard-report.md`
- [x] Slice 007 — Quality gate e closeout (`slices/slice-007-quality-docs-closeout.md`) — commit `a426f8d`, report `/tmp/ats-web-slice-007-quality-docs-closeout-report.md`
- [x] Slice 008 — OpenAI strict schema e language retry (`slices/slice-008-openai-strict-schema-and-language-retry.md`) — commit `4423f18`, report `/tmp/ats-web-slice-008-openai-strict-schema-language-retry-report.md`

## Definition of Done do Change

- [x] Pipeline usa nomes canônicos de prompts do legado.
- [x] Defaults e fallbacks de prompts são compatíveis com o legado.
- [x] LLM1 valida schema Pydantic legado.
- [x] LLM2 valida schema Pydantic legado.
- [x] `non_eda` e `unknown` não entram na fila médica.
- [x] NIR recebe resultado de revisão manual obrigatória para scope gate.
- [x] Tela médica exibe relatório equivalente aos 7 blocos do legado.
- [x] Views médicas exigem papel ativo `doctor`.
- [x] Quality gate completo executado.
- [x] Relatórios dos slices gerados.
- [x] Runtime OpenAI usa `response_format=json_schema` strict com schemas específicos LLM1/LLM2.
- [x] Language retry legado portado para LLM1/LLM2.
