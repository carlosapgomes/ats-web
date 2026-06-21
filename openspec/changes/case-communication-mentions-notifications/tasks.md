# Tasks: Menções e notificações in-app da comunicação por caso

## Slices verticais

- [x] Slice 001 — Menções criam notificações e inbox SSR (`slices/slice-001-mentions-create-in-app-notifications.md`)
- [x] Slice 002 — Polling Vanilla JS e hardening do badge (`slices/slice-002-vanilla-js-badge-polling.md`)

## Definition of Done do change

- [ ] Modelo `UserNotification` criado ou nome equivalente aprovado.
- [ ] Notificação é vinculada a usuário destinatário e a `Case`.
- [ ] Notificação de comunicação referencia `CaseCommunicationMessage`.
- [ ] Migration criada.
- [ ] Menções por papel funcionam para `@nir`, `@doctor`, `@scheduler`, `@manager`, `@admin`.
- [ ] Menções por username funcionam para usuários ativos.
- [ ] Tokens desconhecidos são ignorados sem quebrar o post da mensagem.
- [ ] Usuários inativos/bloqueados não recebem notificações.
- [ ] Autor da mensagem não recebe notificação da própria mensagem.
- [ ] Destinatário mencionado por papel e username recebe no máximo uma notificação por mensagem.
- [ ] Mensagem sem menção continua funcionando e não cria notificação.
- [ ] Evento `CASE_COMMUNICATION_MESSAGE_POSTED` inclui resumo de menções e quantidade de notificações criadas.
- [ ] Header mostra badge SSR com contagem de não lidas.
- [ ] Tela “Minhas notificações” lista apenas notificações do usuário autenticado.
- [ ] Usuário não acessa/marca notificação de outro usuário.
- [ ] Abrir notificação marca `read_at` e redireciona com fallback seguro por papel/status.
- [ ] Marcar uma notificação como lida funciona.
- [ ] Marcar todas como lidas funciona.
- [x] Endpoint `GET /notifications/unread-count/` retorna JSON só para usuário autenticado.
- [x] Polling do badge usa Vanilla JS.
- [x] Polling só atualiza badge/contagem, não a thread do caso.
- [x] Polling respeita `document.visibilityState === "visible"` ou estratégia equivalente.
- [x] Não é usado HTMX para notificações.
- [x] WebSocket/SSE não são introduzidos.
- [ ] SMS/push/email operacional não são introduzidos.
- [ ] Chat global não é introduzido.
- [ ] Autocomplete de menções não é introduzido.
- [ ] Aliases avançados (`@chd`, `@nir_lideranca`, etc.) não são introduzidos.
- [ ] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [ ] Clean code aplicado: nomes claros, funções pequenas, coesão, baixo acoplamento, sem dead code.
- [ ] DRY aplicado: parser/serviço único, sem duplicar lógica de notificação em views.
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

- Notificações são in-app apenas.
- Não criar SMS, push ou email operacional.
- Não usar HTMX para notificações, apesar de HTMX já existir no projeto.
- Não criar chat em tempo real.
- Não atualizar thread de mensagens por polling neste change.
- Não criar tela global de chat.
- Notificações só devem nascer de menções explícitas neste MVP.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório antes de ampliar escopo.
