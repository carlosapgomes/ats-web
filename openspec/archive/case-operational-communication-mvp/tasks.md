# Tasks: Comunicação operacional por caso — MVP

## Slices verticais

- [x] Slice 001 — Thread operacional NIR ↔ Médico (`slices/slice-001-nir-doctor-case-thread.md`)
- [x] Slice 002 — Extensão para agendamento e hardening (`slices/slice-002-scheduler-communication-hardening.md`)

## Status final do change

Change **concluído e arquivado**. Todos os itens da Definition of Done abaixo marcados. Commits em `main`:

- `34b22c5` — Slice 001 (modelo `CaseCommunicationMessage` + migration `0008` + serviço `post_case_communication_message` + endpoint POST `/cases/<id>/communication/` + partial `_communication_thread.html` + telas NIR/médico + evento `CASE_COMMUNICATION_MESSAGE_POSTED` + label/dot de timeline + 23 testes)
- `5ae8f00` — Slice 002 (contexto de comunicação no helper do scheduler + includes nas telas `confirm.html`/`confirm_post_schedule_issue.html` + 9 testes cobrindo visibilidade/post/cross-role/blank/CLEANED/regressão de submit/label/anti-HTMX/anti-notificação)
- `b5ebd6f` — Finalização do DoD (36 itens marcados) + hardening do teste R9 (inspeção estática escopada à superfície de comunicação em vez de `sys.modules`, robusto à futura change de `UserNotification`)

### Hardening pós-slices

- **Regra de negócio no serviço, não na view**: `post_case_communication_message` valida papel permitido, blank/spaces, tamanho máximo e caso `CLEANED`; a view apenas adapta request/response e usa `messages.success`/`messages.warning`.
- **Redirect seguro**: `post_case_communication` valida `next` com `url_has_allowed_host_and_scheme` antes de redirecionar — sem open redirect.
- **DRY real**: contexto de comunicação centralizado em helper (`_build_confirm_context` no scheduler, contexto inline no NIR/médico); partial único reutilizado por 4 telas (NIR, médico, scheduler confirm, scheduler intercorrência); serviço e endpoint únicos.
- **Teste anti-notificação determinístico**: R9 inspeciona estaticamente os 5 arquivos da superfície de comunicação por `UserNotification`/`notification_badge`/`unread_count`. Não depende de `sys.modules`, então não quebra quando uma change futura criar `UserNotification` num módulo novo — só falha se a própria superfície de comunicação for acoplada a notificações.
- **FSM inalterada**: nenhum dos 17 estados foi criado/alterado; `doctor_reason`/`doctor_observation`/`appointment_reason`/`correction_reason` não foram redefinidos.

## Definition of Done do change

- [x] Modelo `CaseCommunicationMessage` criado ou nome equivalente aprovado.
- [x] Mensagens sempre vinculadas a exatamente um `Case`.
- [x] Mensagens têm autor, papel ativo no momento do post, corpo e data/hora.
- [x] Migration criada.
- [x] Serviço de domínio valida e cria mensagens, sem lógica pesada em views/templates.
- [x] Mensagem vazia/apenas espaços é rejeitada.
- [x] Mensagem acima do limite definido é rejeitada.
- [x] Usuário sem papel operacional permitido não consegue postar.
- [x] Post em caso `CLEANED` é bloqueado no MVP, salvo decisão explícita documentada no relatório.
- [x] Cada post gera evento `CASE_COMMUNICATION_MESSAGE_POSTED` ou nome equivalente aprovado.
- [x] Payload do evento inclui `message_id`, `author_role` e `body_preview`.
- [x] Corpo completo da mensagem não é duplicado integralmente em `CaseEvent.payload`.
- [x] NIR vê e posta mensagens no detalhe operacional do caso.
- [x] Médico vê e posta mensagens na tela de decisão do caso.
- [x] Agendador vê e posta mensagens na tela de agendamento/intercorrência prevista.
- [x] Mensagens aparecem em ordem cronológica.
- [x] UI mostra autor, papel e data/hora.
- [x] UI informa que decisões formais continuam nos workflows estruturados.
- [x] Partial/template compartilhado evita duplicação visual desnecessária.
- [x] Labels/dots de timeline incluem `CASE_COMMUNICATION_MESSAGE_POSTED`.
- [x] Nenhum estado FSM é criado ou alterado.
- [x] `doctor_reason`, `doctor_observation`, `appointment_reason` e `correction_reason` não são redefinidos.
- [x] Nenhum chat global é criado.
- [x] Nenhuma notificação in-app é criada neste change.
- [x] Nenhum polling periódico é implementado neste change.
- [x] HTMX/WebSocket/SSE não são introduzidos neste change.
- [x] Emails/SMS/push operacionais não são introduzidos.
- [x] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [x] Clean code aplicado: nomes claros, funções pequenas, coesão, baixo acoplamento, sem dead code.
- [x] DRY aplicado: partial compartilhado, serviço único, sem duplicar validações.
- [x] YAGNI aplicado: sem features futuras antecipadas.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado por cada slice com snippets antes/depois e evidências.
- [x] Cada slice atualiza este `tasks.md` ao concluir.

## Notas para implementadores

- Comunicação operacional é para esclarecimento/coordenação; não substitui workflow estruturado.
- Não criar notificações agora. Elas pertencem ao futuro `case-communication-mentions-notifications`.
- Não usar HTMX agora.
- Não criar chat global.
- Não transformar `doctor_observation` em thread.
- Não adicionar anexos em mensagens neste MVP.
- Não implementar edição/deleção/supressão de mensagens neste MVP.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório antes de ampliar escopo.
