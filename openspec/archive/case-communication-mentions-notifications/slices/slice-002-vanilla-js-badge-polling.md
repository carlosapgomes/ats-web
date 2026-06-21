# Slice 002: Polling Vanilla JS e hardening do badge

## Contexto zero para implementador

O Slice 001 deste change deve ter criado:

- `UserNotification`;
- menções por papel e username;
- criação de notificações ao postar `CaseCommunicationMessage`;
- badge SSR no header;
- tela “Minhas notificações”;
- abrir/marcar notificações como lidas.

Este slice adiciona atualização periódica leve do badge de notificações **sem transformar a comunicação em chat em tempo real**.

Fluxo alvo:

```text
Usuário está logado em qualquer tela
→ outro usuário menciona esse usuário/papel em mensagem de caso
→ badge do header atualiza após polling leve
→ usuário abre Minhas notificações quando quiser
```

O polling deve atualizar somente a contagem/badge. Não deve buscar mensagens do caso nem atualizar a thread.

## Objetivo do slice

Entregar verticalmente:

```text
endpoint JSON unread-count + JS Vanilla no header + acessibilidade/backoff + testes de hardening
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/accounts/views.py`
2. `apps/accounts/urls.py`
3. `templates/base.html`
4. `static/js/notifications.js`
5. testes em `apps/accounts/tests/...`
6. `openspec/changes/case-communication-mentions-notifications/tasks.md` ao concluir

Não criar migration neste slice, salvo correção justificada de bug do Slice 001.

## Requisitos funcionais

### R1. Endpoint unread count

Adicionar rota em `apps/accounts/urls.py`:

```python
path("notifications/unread-count/", views.notifications_unread_count, name="notifications_unread_count")
```

View:

- `@login_required`;
- aceitar GET;
- retornar JSON:

```json
{"unread_count": 3}
```

- contar apenas notificações do `request.user` com `read_at__isnull=True`;
- não expor dados de outros usuários;
- não retornar lista de notificações ou PHI;
- para usuário não autenticado, comportamento padrão do `login_required`.

### R2. Header preparado para JS

Em `templates/base.html`, garantir que o link/badge criado no Slice 001 tenha atributos suficientes:

```html
<a id="notification-badge"
   href="..."
   data-notifications-badge
   data-unread-count-url="{% url 'notifications_unread_count' %}"
   data-count="{{ notification_unread_count|default:0 }}"
   aria-label="Notificações: {{ notification_unread_count|default:0 }} não lidas">
  Notificações
</a>
```

Se o Slice 001 já criou estrutura semelhante, apenas ajustar minimamente.

### R3. JavaScript Vanilla

Criar:

```text
static/js/notifications.js
```

Comportamento:

1. ao carregar, procurar `[data-notifications-badge]`;
2. se não existir, sair sem erro;
3. ler URL de `data-unread-count-url`;
4. fazer `fetch()` com `credentials: "same-origin"`;
5. atualizar `data-count` com o número retornado;
6. atualizar texto/aria-label acessível;
7. executar polling a cada 45s ou 60s;
8. só consultar quando `document.visibilityState === "visible"`;
9. aplicar backoff simples em erro, por exemplo dobrar intervalo até limite razoável;
10. resetar intervalo em sucesso.

Não usar:

- HTMX (`hx-get`, `hx-trigger`);
- WebSocket;
- SSE;
- bibliotecas externas.

### R4. Inclusão do script

Incluir em `templates/base.html`:

```django
<script src="{% static 'js/notifications.js' %}"></script>
```

Preferência: após `app.js` ou antes de `{% block extra_js %}`.

O script deve ser seguro em páginas anônimas/login: se não há badge, não faz nada.

### R5. Não atualizar thread de mensagens

Este slice não deve:

- buscar `/cases/<case_id>/communication/`;
- inserir mensagens no DOM;
- recarregar partial de comunicação;
- criar UX tipo chat.

O usuário vê mensagens ao abrir a notificação ou recarregar/abrir o caso.

### R6. Hardening de leitura

Quando o usuário marca/abre notificações na tela SSR, o próximo polling deve refletir o novo count.

Não precisa implementar chamada AJAX para marcar lida no MVP; marcação continua SSR/POST do Slice 001.

## TDD obrigatório

Antes da implementação, criar testes falhando.

### Testes mínimos endpoint

1. `test_unread_count_requires_login`
   - usuário anônimo não recebe JSON de count.

2. `test_unread_count_returns_only_current_user_unread_notifications`
   - conta só notificações não lidas do usuário autenticado.

3. `test_unread_count_excludes_read_notifications`
   - `read_at` preenchido não conta.

4. `test_unread_count_response_contains_no_phi_or_notification_list`
   - resposta contém apenas `unread_count` ou campos técnicos mínimos.

### Testes mínimos template/JS

5. `test_base_template_exposes_notification_badge_polling_url`
   - render de página autenticada contém `data-notifications-badge` e `data-unread-count-url`.

6. `test_notifications_js_is_loaded_for_authenticated_header`
   - `base.html` inclui `static/js/notifications.js`.

7. `test_notifications_js_uses_fetch_and_visibility_state`
   - arquivo JS contém `fetch` e `document.visibilityState`.

8. `test_notifications_js_does_not_use_htmx_websocket_or_sse`
   - JS não contém `hx-get`, `hx-trigger`, `WebSocket`, `EventSource`.

9. `test_notifications_polling_does_not_target_case_thread`
   - JS não referencia `case-communication`, `communication_thread`, ou endpoint de mensagens.

### RED esperado

Antes da implementação, os testes devem falhar por ausência de endpoint/atributos/JS.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- View JSON pequena e explícita.
- JS encapsulado em IIFE ou função isolada para não poluir global.
- Funções pequenas: `fetchUnreadCount`, `updateBadge`, `scheduleNextPoll`.
- Tratamento defensivo de DOM ausente.

### DRY

- Reusar a mesma contagem de não lidas do contexto/header se houver helper.
- Não duplicar lógica complexa de query em múltiplos lugares; se necessário, criar helper simples.

### YAGNI

Não implementar neste slice:

- lista AJAX de notificações;
- mark-read AJAX;
- toast/pop-up;
- som;
- Service Worker push;
- WebSocket/SSE;
- HTMX;
- polling da thread de comunicação;
- configurações por usuário.

## Critérios de sucesso

- [x] Endpoint `/notifications/unread-count/` retorna JSON correto para usuário autenticado.
- [x] Endpoint conta apenas notificações não lidas do usuário atual.
- [x] Endpoint não expõe PHI/lista de notificações.
- [x] Header expõe badge com URL de polling.
- [x] `static/js/notifications.js` usa Vanilla JS `fetch()`.
- [x] Polling só roda/consulta quando página está visível.
- [x] Badge atualiza `data-count` e acessibilidade.
- [x] JS não usa HTMX/WebSocket/SSE.
- [x] JS não atualiza thread de mensagens.
- [x] Testes novos passam.
- [x] Quality gate completo passa.

### Hardening (follow-up pós-slice)

- [x] DRY: query de unread count extraída para `get_unread_notification_count()` em `apps/accounts/models.py`, reutilizada por context processor, `notifications_list` e endpoint (antes duplicada em 3 lugares).
- [x] Endpoint restrito a GET via `@require_GET` (antes aceitava qualquer método).
- [x] Teste `test_notifications_polling_does_not_target_case_thread` endurecido: `assert "/cases/" not in js_content` (antes era tautológico via `or "unread-count"` que sempre passava).
- [x] Asserções `or` redundantes removidas em `test_notifications_js_is_loaded_for_authenticated_header` e `test_notifications_js_uses_fetch_and_visibility_state`.
- [x] Imports top-of-module (`JsonResponse`, `require_GET`) em vez de inline no corpo da view.
- [x] Migration corretiva `0005_rename_usernotification_indexes.py` alinha nomes de índice do Slice 001 (`0004`) com os determinísticos atuais do Django.

## Gates de autoavaliação

Responder no relatório:

1. Qual endpoint retorna a contagem de não lidas?
2. Qual teste prova que a contagem é por usuário e exclui lidas?
3. Qual teste prova que o endpoint não expõe PHI/lista de notificações?
4. Qual teste prova que o JS usa `fetch()` e respeita visibilidade?
5. Qual teste prova que HTMX/WebSocket/SSE não foram usados?
6. Qual teste prova que a thread de mensagens não é alvo do polling?
7. Foi implementado mark-read AJAX/toast/push? Se sim, está fora de escopo.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/case-communication-mentions-notifications-slice-002-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois;
- resultados do quality gate;
- evidência de ausência de HTMX/WebSocket/SSE/polling de thread;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/case-communication-mentions-notifications-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/case-communication-mentions-notifications/proposal.md, design.md, tasks.md and slices/slice-002-vanilla-js-badge-polling.md.
Implement ONLY Slice 002. Assume Slice 001 is complete.
Use TDD: first add failing tests for unread-count endpoint, badge attributes, JS loading and hardening, then implement minimal code.
Add GET /notifications/unread-count/ returning {"unread_count": N} for the authenticated user only. Add Vanilla JS static/js/notifications.js to poll this endpoint every 45–60s only when document.visibilityState is visible, update only the header notification badge, and use simple backoff on errors. Wire the badge URL/attributes and script in base.html.
Do not use HTMX for notifications. Do not implement WebSocket/SSE, push/SMS/email, AJAX mark-read, toasts, notification list AJAX, or polling/refreshing the case communication thread.
Apply clean code, DRY and YAGNI.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/case-communication-mentions-notifications/tasks.md when complete.
Create /tmp/case-communication-mentions-notifications-slice-002-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
