# Tasks: Intercorrência pós-agendamento

## Status

Slice 001 concluído. Implementar **um slice por vez**, seguindo TDD e aguardando confirmação explícita antes de iniciar o próximo slice.

## Slices

- [X] Slice 001 — Modelo, FSM e serviços de domínio (`slices/slice-001-domain-fsm-services.md`)
- [X] Slice 002 — NIR busca casos encerrados e abre intercorrência (`slices/slice-002-nir-search-open-issue.md`)
- [X] Slice 003 — Agendador resolve intercorrência (`slices/slice-003-scheduler-resolve-issue.md`)
- [ ] Slice 004 — NIR confirma ciência e encerra ciclo (`slices/slice-004-nir-acknowledge-issue.md`)
- [ ] Slice 005 — Timeline, badges e hardening (`slices/slice-005-timeline-badges-hardening.md`)

## Definition of Done do Change

- [X] `Case` possui metadados mínimos para uma intercorrência ativa/latest.
- [X] FSM possui transição explícita `CLEANED → WAIT_APPT` para abertura de intercorrência elegível.
- [X] Nenhum novo estado FSM foi criado; os 17 estados foram preservados.
- [X] Serviço/helper transacional impede duas intercorrências ativas simultâneas.
- [X] Elegibilidade restringe a casos `CLEANED`, aceitos pelo médico, fluxo `scheduled`, agendamento confirmado e sem intercorrência ativa.
- [X] NIR consegue buscar caso encerrado por ocorrência ou nome do paciente.
- [X] NIR consegue abrir intercorrência com motivo oficial e mensagem condicional.
- [X] Agendador vê intercorrência distinguida de agendamento inicial.
- [X] Agendador consegue cancelar, reagendar, manter ou negar solicitação.
- [X] Cancelamento marca agendamento atual como cancelado sem criar novo fluxo.
- [X] Reagendamento atualiza os campos principais de agendamento.
- [X] Manutenção/negação preservam o agendamento confirmado quando aplicável.
- [ ] Após resposta do agendador, NIR confirma ciência.
- [ ] Após ciência, caso retorna a `CLEANED` e deixa de ter intercorrência ativa.
- [X] Timeline registra abertura, resposta e ciência com payload suficiente.
- [X] Múltiplos ciclos sequenciais são suportados e auditados.
- [X] Locks existentes de agendador/NIR continuam respeitados.
- [X] Quality gate completo executado.
- [X] Cada slice gerou relatório temporário com snippets antes/depois e informou `REPORT_PATH`.
- [X] Cada slice atualizou este `tasks.md` apenas ao final da implementação.
- [ ] Cada slice teve commit e push, conforme `AGENTS.md`.

## Comandos globais de validação

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Notas para implementadores

- Leia sempre `AGENTS.md`, `PROJECT_CONTEXT.md`, `proposal.md`, `design.md`, `tasks.md` e o arquivo do slice atual.
- Use TDD: RED → GREEN → REFACTOR.
- Siga clean code, DRY e YAGNI.
- Evite slices horizontais; cada slice deve entregar comportamento observável end-to-end.
- Toque o mínimo de arquivos necessário; se ampliar escopo, justifique no relatório.
- Não introduza DRF, SPA, framework JS, WebSocket ou dependências novas.
- Preserve `CaseEvent` como fonte append-only de auditoria.
- Não altere os 17 estados da FSM.
