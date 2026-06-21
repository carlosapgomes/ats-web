# Tasks: Mensagens sistêmicas de workflow na comunicação do caso

## Slices verticais

- [x] Slice 001 — Infraestrutura + avisos de anexos/correção (`slices/slice-001-system-notices-attachments-corrections.md`)
- [x] Slice 002 — Avisos de intercorrência/encerramento + hardening (`slices/slice-002-system-notices-operational-workflows.md`)

## Definition of Done do change

- [x] `CaseCommunicationMessage` suporta mensagem manual e sistêmica.
- [x] Mensagem sistêmica pode ter `author=None` sem quebrar UI.
- [x] Mensagem sistêmica referencia o `CaseEvent` de origem ou mecanismo equivalente idempotente.
- [x] Cada evento suportado gera no máximo uma mensagem sistêmica.
- [x] Evento não suportado não gera mensagem sistêmica.
- [x] Mensagens manuais continuam funcionando como antes.
- [x] Mensagens manuais com `@menção` continuam gerando `UserNotification`.
- [x] Mensagens sistêmicas não geram `UserNotification`.
- [x] Mensagens sistêmicas não alteram badge de notificações.
- [x] Mensagens sistêmicas aparecem apenas na thread do caso.
- [x] Thread renderiza mensagens sistêmicas com identificação visual de “Sistema”.
- [x] `CASE_ATTACHMENT_SUPPRESSED` gera mensagem sistêmica.
- [x] `CASE_ATTACHMENT_SUPPLEMENT_ADDED` gera mensagem sistêmica.
- [x] `CASE_CORRECTION_CREATED` gera mensagem sistêmica.
- [x] `CASE_MARKED_SUPERSEDED` gera mensagem sistêmica.
- [x] `POST_SCHEDULE_ISSUE_OPENED` gera mensagem sistêmica.
- [x] `POST_SCHEDULE_ISSUE_RESPONDED` gera mensagem sistêmica.
- [x] `CASE_ADMINISTRATIVELY_CLOSED` gera mensagem sistêmica.
- [x] `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` é incluído ou explicitamente justificado como omitido no relatório.
- [x] `CASE_COMMUNICATION_MESSAGE_POSTED` não gera mensagem sistêmica para evitar ruído/loop.
- [x] Nenhum novo estado FSM é criado ou alterado.
- [x] Não há backfill de eventos históricos neste change.
- [x] Não há inbox/lista de mensagens sistêmicas fora do caso.
- [x] Não há notificação automática para eventos sistêmicos.
- [x] Não há polling/refresh da thread.
- [x] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [x] Clean code aplicado: nomes claros, funções pequenas, coesão, baixo acoplamento, sem dead code.
- [x] DRY aplicado: formatadores/serviço centralizados, sem espalhar lógica em views/templates.
- [x] YAGNI aplicado: sem features futuras antecipadas.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado por cada slice com snippets antes/depois e evidências.
- [x] Cada slice atualiza este `tasks.md` ao concluir.
- [x] Commit e push realizados após cada slice.

## Notas para implementadores

- Mensagens sistêmicas são contexto no caso, não notificação individual.
- Não criar `UserNotification` para mensagens sistêmicas.
- Não mexer no badge/inbox de notificações para eventos sistêmicos.
- Não criar mecanismo de “lida/resolvida” para mensagem sistêmica.
- Não usar menções em mensagens sistêmicas.
- Não alterar FSM.
- Não fazer backfill de eventos antigos.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório antes de ampliar escopo.

## Status final do change

Change concluído e arquivado. 2 slices verticais + 2 hardening pós-revisão.

### Commits

- `7a6697e` — Slice 001: infraestrutura de mensagens sistêmicas (campos `message_type`/`source_event`/`system_event_type` + migration `0009` + serviço de projeção `create_system_communication_notice_for_event` + signal `CaseEvent.post_save` + render “Sistema” + 4 eventos de anexos/correção)
- `ee70618` — Hardening Slice 001 (pós-revisão): `CaseCommunicationMessage.clean()` passa a levantar `ValidationError` (idiomático Django) em vez de `ValueError`, preservando integração com `ModelForm`/admin
- `9cf57a0` — Slice 002: 3 eventos operacionais (`POST_SCHEDULE_ISSUE_OPENED`/`POST_SCHEDULE_ISSUE_RESPONDED`/`CASE_ADMINISTRATIVELY_CLOSED`) + 6 testes de hardening (sem `UserNotification`/badge, `@` em sistêmicas não aciona menção, idempotência, regressão de menções manuais, campos estruturais intactos)
- `8468f16` — Hardening Slice 002 (pós-revisão): remover código morto `FORMAT_ACTIONS_WITH_APPT` + parametrizar teste de action labels nas 4 ações (cancel/reschedule/maintain/deny) + decisão D10 no `design.md` (projeção pura do payload em `_format_post_schedule_issue_responded`)

### Hardening pós-slices

Cada slice recebeu revisão antes do arquivamento. Os 4 achados foram corrigidos imediatamente sem deixar débito, conforme decisão do planner:

- **Slice 001**: 1 desvio de idioma Django (`ValueError` → `ValidationError` em `clean()`) que quebraria integração com `ModelForm`/admin.
- **Slice 002**: 1 violação YAGNI/dead code (`FORMAT_ACTIONS_WITH_APPT` nunca referenciado) + 1 lacuna de cobertura (teste de action labels só validava `reschedule`) + 1 decisão de design não registrada (nova data/hora não aparece inline no reagendamento — projeção pura do payload, registrada como D10).

### Resumo do entregue

- `CaseCommunicationMessage`: novos campos `message_type` (`user`/`system`), `source_event` (`OneToOneField` idempotente), `system_event_type`; `author`/`author_role` agora nullable/blank para mensagens sistêmicas + migration `0009_system_notices`
- Serviço de projeção centralizado `create_system_communication_notice_for_event` + `build_system_notice_body` + formatadores por `event_type` (DRY, dispatch dict) + `SUPPORTED_SYSTEM_NOTICE_EVENT_TYPES`
- Signal `create_case_event_system_notice` (`CaseEvent.post_save`) fino, com import tardio evitando circular
- Template `_communication_thread.html`: condicional `message_type == "system"` → “Sistema” + badge SISTEMA (reutilizado em 4 telas)
- 7 eventos projetados: `CASE_ATTACHMENT_SUPPRESSED`, `CASE_ATTACHMENT_SUPPLEMENT_ADDED`, `CASE_CORRECTION_CREATED`, `CASE_MARKED_SUPERSEDED`, `POST_SCHEDULE_ISSUE_OPENED`, `POST_SCHEDULE_ISSUE_RESPONDED`, `CASE_ADMINISTRATIVELY_CLOSED`
- `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` omitido (payload vazio — ruído na thread; teste documenta omissão)
- `CASE_COMMUNICATION_MESSAGE_POSTED` guardado contra loop/ruído
- 1473 testes passando (+31 neste change); ruff/mypy/format verdes; FSM, badge/inbox de notificações e workflows estruturados inalterados

### Limitações aceitas

- Sem notificação/badge/read-resolved para mensagens sistêmicas (by design — contexto no caso, não chamada para ação individual).
- Sem backfill de eventos históricos (apenas eventos criados após a implementação geram sistêmicas).
- Sem inbox/filtro/edição/deleção de mensagens sistêmicas fora da thread do caso.
- `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` omitido (payload vazio, ruído).
- Formatador de `POST_SCHEDULE_ISSUE_RESPONDED` não mostra nova data/hora do reagendamento inline — projeção pura do payload do evento (`{action, response_message}`); a fonte de verdade da nova data permanece `case.appointment_at` + `CaseEvent` (decisão D10).
