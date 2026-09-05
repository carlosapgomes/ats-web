# Tasks: Follow-up de agendamentos pelo Supervisor

## Slices verticais (ordem executável)

- [x] Slice 001 — Domínio: models versionados + service de registro + `CaseEvent` (`slices/slice-001-followup-domain-model.md`)
- [x] Slice 002 — Aba de listagem do supervisor (`slices/slice-002-followup-tab-list.md`) — inclui `is_followup_eligible` (R7)
- [x] Slice 003 — Formulário de follow-up (`slices/slice-003-followup-form.md`) — inclui revalidação de elegibilidade e link na listagem (R6)

## Ciclo de review

- [x] Review independente (reviewer, contexto fresco) do change + Slice 001 — verdict inicial: BLOCK
- [x] Correções P1/P2 incorporadas (ver `design.md` § Registro de review)
- [x] Re-review (ciclo 2, reviewer contexto fresco): 6/6 findings RESOLVIDOS, nenhum finding novo — **Merge verdict: OK**

## Preflight (uma vez, antes do Slice 001)

- [x] Working tree limpa em `main`
- [x] `BASE_REF`: `main` @ `d1d6e4d`
- [x] Baseline: `uv run pytest -q` → 3197 passed (verde)

## Definition of Done do change

- [x] `CaseFollowUp`/`ProcedureFollowUp` versionados, append-only, com constraints e `CaseEvent` espelho.
- [x] `/dashboard/follow-ups/` lista elegíveis (agendados confirmados + vinda imediata) de hoje+ontem, com seletor de data e busca por ocorrência/nome, ordenação data→nome.
- [x] Formulário registra desfecho por procedimento + internação por caso; atualização cria nova versão; histórico visível na página.
- [x] Acesso restrito a `manager`/`admin`; FSM, filas e fluxos operacionais inalterados.
- [x] Testes novos cobrindo os requisitos; suite existente sem regressão (baseline 3197 → final 3283 passed).
- [x] Quality gate final do AGENTS.md (executado uma vez pelo controller após todos os slices):
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
  - [x] `openspec validate supervisor-appointment-follow-up`
- [x] Relatório por slice em markdown temporário (`REPORT_PATH` para o planner).
- [x] Commit por slice com mensagem rastreável (push: apenas Slices 001–002 anteriores ao comando slice-loop; `8ece663` e `bc07f99` ficam SEM push até instrução explícita).
- [ ] `openspec archive` após aprovação humana do change.
