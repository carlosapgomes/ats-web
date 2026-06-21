# Tasks: Mensagens sistêmicas de workflow na comunicação do caso

## Slices verticais

- [x] Slice 001 — Infraestrutura + avisos de anexos/correção (`slices/slice-001-system-notices-attachments-corrections.md`)
- [x] Slice 002 — Avisos de intercorrência/encerramento + hardening (`slices/slice-002-system-notices-operational-workflows.md`)

## Definition of Done do change

- [ ] `CaseCommunicationMessage` suporta mensagem manual e sistêmica.
- [ ] Mensagem sistêmica pode ter `author=None` sem quebrar UI.
- [ ] Mensagem sistêmica referencia o `CaseEvent` de origem ou mecanismo equivalente idempotente.
- [ ] Cada evento suportado gera no máximo uma mensagem sistêmica.
- [ ] Evento não suportado não gera mensagem sistêmica.
- [ ] Mensagens manuais continuam funcionando como antes.
- [ ] Mensagens manuais com `@menção` continuam gerando `UserNotification`.
- [ ] Mensagens sistêmicas não geram `UserNotification`.
- [ ] Mensagens sistêmicas não alteram badge de notificações.
- [ ] Mensagens sistêmicas aparecem apenas na thread do caso.
- [ ] Thread renderiza mensagens sistêmicas com identificação visual de “Sistema”.
- [ ] `CASE_ATTACHMENT_SUPPRESSED` gera mensagem sistêmica.
- [ ] `CASE_ATTACHMENT_SUPPLEMENT_ADDED` gera mensagem sistêmica.
- [ ] `CASE_CORRECTION_CREATED` gera mensagem sistêmica.
- [ ] `CASE_MARKED_SUPERSEDED` gera mensagem sistêmica.
- [ ] `POST_SCHEDULE_ISSUE_OPENED` gera mensagem sistêmica.
- [ ] `POST_SCHEDULE_ISSUE_RESPONDED` gera mensagem sistêmica.
- [ ] `CASE_ADMINISTRATIVELY_CLOSED` gera mensagem sistêmica.
- [ ] `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` é incluído ou explicitamente justificado como omitido no relatório.
- [ ] `CASE_COMMUNICATION_MESSAGE_POSTED` não gera mensagem sistêmica para evitar ruído/loop.
- [ ] Nenhum novo estado FSM é criado ou alterado.
- [ ] Não há backfill de eventos históricos neste change.
- [ ] Não há inbox/lista de mensagens sistêmicas fora do caso.
- [ ] Não há notificação automática para eventos sistêmicos.
- [ ] Não há polling/refresh da thread.
- [ ] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [ ] Clean code aplicado: nomes claros, funções pequenas, coesão, baixo acoplamento, sem dead code.
- [ ] DRY aplicado: formatadores/serviço centralizados, sem espalhar lógica em views/templates.
- [ ] YAGNI aplicado: sem features futuras antecipadas.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório markdown temporário criado por cada slice com snippets antes/depois e evidências.
- [ ] Cada slice atualiza este `tasks.md` ao concluir.
- [ ] Commit e push realizados após cada slice.

## Notas para implementadores

- Mensagens sistêmicas são contexto no caso, não notificação individual.
- Não criar `UserNotification` para mensagens sistêmicas.
- Não mexer no badge/inbox de notificações para eventos sistêmicos.
- Não criar mecanismo de “lida/resolvida” para mensagem sistêmica.
- Não usar menções em mensagens sistêmicas.
- Não alterar FSM.
- Não fazer backfill de eventos antigos.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório antes de ampliar escopo.
