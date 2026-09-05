# Tasks: Follow-up de agendamentos pelo Supervisor

## Slices verticais (ordem executável)

- [x] Slice 001 — Domínio: models versionados + service de registro + `CaseEvent` (`slices/slice-001-followup-domain-model.md`)
- [ ] Slice 002 — Aba de listagem do supervisor (`slices/slice-002-followup-tab-list.md`) — inclui `is_followup_eligible` (R7)
- [ ] Slice 003 — Formulário de follow-up (`slices/slice-003-followup-form.md`) — inclui revalidação de elegibilidade e link na listagem (R6)

## Ciclo de review

- [x] Review independente (reviewer, contexto fresco) do change + Slice 001 — verdict inicial: BLOCK
- [x] Correções P1/P2 incorporadas (ver `design.md` § Registro de review); revalidação pendente de novo ciclo do reviewer

## Preflight (uma vez, antes do Slice 001)

- [x] Working tree limpa em `main`
- [x] `BASE_REF`: `main` @ `d1d6e4d`
- [x] Baseline: `uv run pytest -q` → 3197 passed (verde)

## Definition of Done do change

- [ ] `CaseFollowUp`/`ProcedureFollowUp` versionados, append-only, com constraints e `CaseEvent` espelho.
- [ ] `/dashboard/follow-ups/` lista elegíveis (agendados confirmados + vinda imediata) de hoje+ontem, com seletor de data e busca por ocorrência/nome, ordenação data→nome.
- [ ] Formulário registra desfecho por procedimento + internação por caso; atualização cria nova versão; histórico visível na página.
- [ ] Acesso restrito a `manager`/`admin`; FSM, filas e fluxos operacionais inalterados.
- [ ] Testes novos cobrindo os requisitos; suite existente sem regressão.
- [ ] Quality gate final do AGENTS.md:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório por slice em markdown temporário (`REPORT_PATH` para o planner).
- [ ] Commit (e push) por slice com mensagem rastreável.
- [ ] `openspec archive` após aprovação humana do change.
