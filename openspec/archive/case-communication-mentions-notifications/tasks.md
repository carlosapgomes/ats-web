# Tasks: Menções e notificações in-app da comunicação por caso

## Slices verticais

- [x] Slice 001 — Menções criam notificações e inbox SSR (`slices/slice-001-mentions-create-in-app-notifications.md`)
- [x] Slice 002 — Polling Vanilla JS e hardening do badge (`slices/slice-002-vanilla-js-badge-polling.md`)

## Definition of Done do change

- [x] Modelo `UserNotification` criado ou nome equivalente aprovado.
- [x] Notificação é vinculada a usuário destinatário e a `Case`.
- [x] Notificação de comunicação referencia `CaseCommunicationMessage`.
- [x] Migration criada.
- [x] Menções por papel funcionam para `@nir`, `@doctor`, `@scheduler`, `@manager`, `@admin`.
- [x] Menções por username funcionam para usuários ativos.
- [x] Tokens desconhecidos são ignorados sem quebrar o post da mensagem.
- [x] Usuários inativos/bloqueados não recebem notificações.
- [x] Autor da mensagem não recebe notificação da própria mensagem.
- [x] Destinatário mencionado por papel e username recebe no máximo uma notificação por mensagem.
- [x] Mensagem sem menção continua funcionando e não cria notificação.
- [x] Evento `CASE_COMMUNICATION_MESSAGE_POSTED` inclui resumo de menções e quantidade de notificações criadas.
- [x] Header mostra badge SSR com contagem de não lidas.
- [x] Tela “Minhas notificações” lista apenas notificações do usuário autenticado.
- [x] Usuário não acessa/marca notificação de outro usuário.
- [x] Abrir notificação marca `read_at` e redireciona com fallback seguro por papel/status.
- [x] Marcar uma notificação como lida funciona.
- [x] Marcar todas como lidas funciona.
- [x] Endpoint `GET /notifications/unread-count/` retorna JSON só para usuário autenticado.
- [x] Polling do badge usa Vanilla JS.
- [x] Polling só atualiza badge/contagem, não a thread do caso.
- [x] Polling respeita `document.visibilityState === "visible"` ou estratégia equivalente.
- [x] Não é usado HTMX para notificações.
- [x] WebSocket/SSE não são introduzidos.
- [x] SMS/push/email operacional não são introduzidos.
- [x] Chat global não é introduzido.
- [x] Autocomplete de menções não é introduzido.
- [x] Aliases avançados (`@chd`, `@nir_lideranca`, etc.) não são introduzidos.
- [x] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [x] Clean code aplicado: nomes claros, funções pequenas, coesão, baixo acoplamento, sem dead code.
- [x] DRY aplicado: parser/serviço único, sem duplicar lógica de notificação em views.
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

- Notificações são in-app apenas.
- Não criar SMS, push ou email operacional.
- Não usar HTMX para notificações, apesar de HTMX já existir no projeto.
- Não criar chat em tempo real.
- Não atualizar thread de mensagens por polling neste change.
- Não criar tela global de chat.
- Notificações só devem nascer de menções explícitas neste MVP.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório antes de ampliar escopo.

## Status final do change

Change concluído e arquivado. 2 slices verticais + 2 hardening pós-revisão.

### Commits

- `aede364` — Slice 001: menções criam notificações e inbox SSR
- `4b3ad7c` — Hardening Slice 001 (pós-revisão): `decided_detail` em redirect de médico decidido por si, `username__iexact` (case-insensitive), URLs via `reverse()`, `notification_count` preciso (diff), teste do badge endurecido, cobertura de username desconhecido
- `eb0358d` — Slice 002: polling Vanilla JS e hardening do badge
- `f6b5d4c` — Hardening Slice 002 (pós-revisão): helper DRY `get_unread_notification_count()`, `@require_GET`, teste tautológico de thread corrigido, imports top-of-module, migration corretiva `0005` de drift de índices do Slice 001

### Hardening pós-slices

Cada slice recebeu revisão de par antes do arquivamento. Os 12 achados (6 por slice) foram corrigidos imediatamente sem deixar débito, conforme decisão do planner:

- **Slice 001**: 1 desvio funcional (R7/D9 `decided_detail`) + 1 desvio de spec (D5 `username__iexact`) + 4 melhorias de qualidade/cobertura/processo.
- **Slice 002**: 1 violação DRY explícita no spec + 1 teste tautológico que dava falsa confiança + 4 melhorias cosméticas/cobertura/processo + 1 drift de migration latente do Slice 001.

### Resumo do entregue

- Modelo `UserNotification` (UUID PK, indexes, unique constraint) + migration `0004` (+ corretiva `0005`)
- Parser de menções (`@role`/`@username`) + serviço `create_case_communication_notifications` (exclui autor, deduplica, `bulk_create` com unique constraint)
- Integração em `post_case_communication_message` enriquecendo o payload do evento `CASE_COMMUNICATION_MESSAGE_POSTED` com `mentioned_roles`/`mentioned_usernames`/`notification_count`
- Badge SSR no header (`context_processors.notification_unread_count` via helper `get_unread_notification_count()`)
- Página “Minhas notificações” com abrir/marcar lida/marcar todas, redirecionamento seguro por `active_role` + status (`resolve_notification_redirect_url`)
- Endpoint `GET /notifications/unread-count/` (`@require_GET`) + `static/js/notifications.js` (Vanilla JS, `fetch()`, polling 45s, `document.visibilityState`, backoff exponencial)
- 1442 testes passando (+47 neste change); ruff/mypy/format verdes

### Limitações aceitas

- Sem autocomplete de menções (fora de escopo).
- Sem aliases avançados (`@chd`, etc.) (fora de escopo).
- Sem marcação AJAX de lida (continua SSR/POST).
- Sem polling da thread de comunicação (somente badge).
- Polling comportamental (intervalo/backoff) validado apenas por checks estáticos — sem runner JS no stack.
