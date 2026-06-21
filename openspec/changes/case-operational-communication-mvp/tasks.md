# Tasks: Comunicação operacional por caso — MVP

## Slices verticais

- [x] Slice 001 — Thread operacional NIR ↔ Médico (`slices/slice-001-nir-doctor-case-thread.md`)
- [x] Slice 002 — Extensão para agendamento e hardening (`slices/slice-002-scheduler-communication-hardening.md`)

## Definition of Done do change

- [ ] Modelo `CaseCommunicationMessage` criado ou nome equivalente aprovado.
- [ ] Mensagens sempre vinculadas a exatamente um `Case`.
- [ ] Mensagens têm autor, papel ativo no momento do post, corpo e data/hora.
- [ ] Migration criada.
- [ ] Serviço de domínio valida e cria mensagens, sem lógica pesada em views/templates.
- [ ] Mensagem vazia/apenas espaços é rejeitada.
- [ ] Mensagem acima do limite definido é rejeitada.
- [ ] Usuário sem papel operacional permitido não consegue postar.
- [ ] Post em caso `CLEANED` é bloqueado no MVP, salvo decisão explícita documentada no relatório.
- [ ] Cada post gera evento `CASE_COMMUNICATION_MESSAGE_POSTED` ou nome equivalente aprovado.
- [ ] Payload do evento inclui `message_id`, `author_role` e `body_preview`.
- [ ] Corpo completo da mensagem não é duplicado integralmente em `CaseEvent.payload`.
- [ ] NIR vê e posta mensagens no detalhe operacional do caso.
- [ ] Médico vê e posta mensagens na tela de decisão do caso.
- [x] Agendador vê e posta mensagens na tela de agendamento/intercorrência prevista.
- [x] Mensagens aparecem em ordem cronológica.
- [x] UI mostra autor, papel e data/hora.
- [x] UI informa que decisões formais continuam nos workflows estruturados.
- [x] Partial/template compartilhado evita duplicação visual desnecessária.
- [x] Labels/dots de timeline incluem `CASE_COMMUNICATION_MESSAGE_POSTED`.
- [x] Nenhum estado FSM é criado ou alterado.
- [ ] `doctor_reason`, `doctor_observation`, `appointment_reason` e `correction_reason` não são redefinidos.
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
