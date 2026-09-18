# Tasks: Priorizar solicitações de Ecoendoscopia e CPRE

## 0. Precondições do change

- [x] 0.1 Classificar o change como CRÍTICO / HIGH-ARCH e registrar `design.md`, plano de rollback e ADR.
- [x] 0.2 Criar e aceitar `ADR-0008`, com relação de supersessão parcial da ADR-0006 e índice atualizado.
- [x] 0.3 Antes do primeiro código, registrar `BASE_REF`, confirmar branch/worktree adequadas e executar baseline global uma única vez se não houver CI verde confiável do HEAD (`BASE_REF=47206b0`).

## 1. Slice vertical

- [x] 1.1 Implementar o Slice 001 (`slices/slice-001-specialized-precedence-to-doctor.md`) em RED → GREEN → REFACTOR, provar Ecoendoscopia/CPRE até `WAIT_DOCTOR`, auditoria e aviso médico, e obter review independente aceito.

## 2. Gate final e operação

- [x] 2.1 Executar uma única vez o gate final: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.
- [x] 2.2 Executar `openspec validate prioritize-specialized-procedure-requests --strict`, `git diff --check` e inspeção final de escopo.
- [ ] 2.3 Atualizar specs canônicas/`PROJECT_CONTEXT.md` no arquivamento conforme workflow, gerar relatório final, commit/push rastreáveis e parar para aprovação humana antes de deploy/arquivo.
- [ ] 2.4 Após aprovação e deploy, executar smoke de Ecoendoscopia antes de CPRE e monitorar os reason codes/eventos definidos no `proposal.md`.

## Regra de execução

- Implementar exatamente um slice vertical por vez; este change contém apenas o Slice 001.
- Worker não altera `tasks.md`, não faz commit/push e não amplia escopo silenciosamente.
- Parent/orquestrador marca checkboxes somente após evidência e review aceito, cria commit/push e informa `REPORT_PATH`.
- Qualquer necessidade de tocar detector/regex, prompt, schema LLM, model, migration, FSM, permissão, policy clínica ou template exige escalonamento antes da edição.
- O smoke pós-deploy é operacional e não deve ser marcado durante a implementação local.
