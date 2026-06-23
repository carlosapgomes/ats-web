# Slice 001: Header com sino, perfil limpo e inbox com voltar

## Handoff para implementador com contexto zero

Leia primeiro:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/header-notifications-queue-badges/proposal.md`
4. `openspec/changes/header-notifications-queue-badges/design.md`
5. `openspec/changes/header-notifications-queue-badges/tasks.md`
6. Este arquivo

O ATS é um monolito Django SSR. O header global está em `templates/base.html`. As notificações in-app já existem, com:

- `UserNotification`;
- context processor `notification_unread_count`;
- endpoint `notifications_unread_count`;
- polling Vanilla JS em `static/js/notifications.js`, que procura `[data-notifications-badge]`.

Hoje o header mistura notificações e fila operacional:

- há um botão textual `Notificações`;
- há um contador de notificações dentro do botão;
- há também um `queue_count` vermelho ao lado do nome/papel do usuário, mas esse número representa fila operacional para médico/agendador, não notificação pessoal.

A página `templates/accounts/notifications.html` não tem botão de retorno sempre visível.

## Objetivo do slice

Entregar verticalmente:

```text
Usuário autenticado vê sino de notificações no header → clica → abre Minhas Notificações → consegue voltar ao início mesmo se a lista estiver vazia
```

E remover ambiguidade no perfil:

```text
Avatar + Nome · Papel ativo
```

sem `queue_count` grudado.

## Arquivos esperados

Idealmente tocar apenas:

1. `templates/base.html`
2. `templates/accounts/notifications.html`
3. `static/css/app.css` — somente se necessário para o sino/badge
4. `apps/accounts/tests/test_notifications.py`
5. `apps/accounts/tests/test_context_processors.py`

Se precisar tocar outros arquivos, justifique no relatório do slice.

## Requisitos funcionais

### R1. Header usa sino para notificações

Em `templates/base.html`, substituir o botão textual grande `Notificações` por um link/botão compacto com ícone de sino.

Requisitos obrigatórios do elemento:

- manter `href="{% url 'notifications' %}"`;
- manter `id="notification-badge"`;
- manter `data-notifications-badge`;
- manter `data-unread-count-url="{% url 'notifications_unread_count' %}"`;
- manter `data-count="{{ notification_unread_count|default:0 }}"`;
- manter `aria-label` informando quantidade de não lidas;
- incluir texto acessível com `visually-hidden`, por exemplo `Notificações`;
- não exibir texto visível grande `Notificações` no header.

Use SVG inline de Bootstrap Icon `bell` ou `bell-fill`. Não adicionar CDN/dependência global de Bootstrap Icons.

### R2. Não duplicar contador visual

O contador de notificações deve aparecer uma única vez.

Aceitável:

- pseudo-elemento CSS baseado em `data-count`; **ou**
- `<span class="badge ...">` interno.

Não aceitável:

- pseudo-elemento + `<span>` ao mesmo tempo criando número duplicado.

### R3. Polling existente continua funcionando

Não alterar `static/js/notifications.js` salvo se estritamente necessário.

O script deve continuar encontrando o elemento por:

```js
[data-notifications-badge]
```

E deve continuar podendo atualizar `data-count` e `aria-label`.

Se a implementação remover o `<span class="badge">` interno, avalie se o JS precisa ou não de ajuste. Preferência: manter o JS funcionando sem ampliar escopo; se tocar o JS, justificar no relatório.

### R4. Remover `queue_count` do perfil no header

Em `templates/base.html`, remover somente a renderização do badge:

```django
{% if queue_count %}
<span class="badge bg-danger ms-1">{{ queue_count }}</span>
{% endif %}
```

Não remover o context processor neste slice.

### R5. Página de notificações tem botão voltar

Em `templates/accounts/notifications.html`, adicionar botão/link sempre visível:

```django
<a href="{% url 'home' %}" class="btn btn-outline-secondary btn-sm">Voltar ao início</a>
```

O botão deve aparecer:

- quando há notificações;
- quando não há notificações;
- quando não há não lidas.

Manter `Marcar todas como lidas` apenas quando `unread_count` for positivo.

## TDD obrigatório

Antes de implementar, adicione/ajuste testes que falhem.

### Testes mínimos sugeridos

Em `apps/accounts/tests/test_notifications.py`:

1. `test_header_renders_notification_bell_with_polling_attributes`
   - autenticar usuário;
   - GET de página que herda `base.html`, por exemplo `reverse("notifications")`;
   - assert contém `id="notification-badge"`;
   - assert contém `data-notifications-badge`;
   - assert contém `data-unread-count-url`;
   - assert contém `aria-label="Notificações:`;
   - assert contém `<svg` e/ou classe/atributo identificável do sino;
   - assert contém `visually-hidden` + `Notificações`;
   - assert **não** contém padrão de botão textual antigo, por exemplo `>Notificações\n` dentro do link.

2. `test_notifications_page_has_back_to_home_link_when_empty`
   - usuário sem notificações;
   - GET `reverse("notifications")`;
   - assert contém `Voltar ao início`;
   - assert contém `href="/"` ou `reverse("home")`.

3. `test_notifications_page_has_back_to_home_link_with_notifications`
   - criar notificação para usuário;
   - GET `reverse("notifications")`;
   - assert contém `Voltar ao início`.

Em `apps/accounts/tests/test_context_processors.py`:

4. Ajustar teste legado que esperava badge de `queue_count` no header.
   - Novo comportamento esperado: mesmo com `queue_count > 0`, o header do perfil não renderiza o número grudado no nome/avatar.
   - Não invalidar contadores das abas médica/agendador, pois esses serão tratados no Slice 002.

## Critérios de aceitação

- [ ] TDD seguido: testes novos/ajustados falham antes da implementação e passam após.
- [ ] Header autenticado mostra sino, não botão textual grande `Notificações`.
- [ ] `data-notifications-badge`, `data-unread-count-url`, `data-count` e `aria-label` preservados.
- [ ] Contador visual de notificações não aparece duplicado.
- [ ] `queue_count` não aparece mais junto do nome/avatar.
- [ ] Página `Minhas Notificações` sempre mostra `Voltar ao início`.
- [ ] `Marcar todas como lidas` continua condicionado a `unread_count`.
- [ ] Não houve alteração de modelo, migration, endpoint ou polling além do necessário.
- [ ] Quality gate do AGENTS.md executado.

## Gates de autoavaliação para relatório

Responder no relatório markdown temporário:

1. Qual teste prova que o sino preserva os atributos necessários ao polling?
2. Qual teste prova que a inbox tem botão voltar no estado vazio?
3. Qual teste prova que a inbox tem botão voltar quando há notificações?
4. Como você garantiu que `queue_count` não aparece mais grudado no perfil?
5. O contador de notificações pode duplicar visualmente? Explique a fonte única de renderização.
6. Você tocou em `static/js/notifications.js`? Se sim, por quê?
7. Quantos arquivos foram tocados e por que esse número é necessário?

## Relatório obrigatório

Criar um relatório temporário em markdown, por exemplo:

```text
/tmp/ats-web-header-notifications-queue-badges-slice-001-report.md
```

O relatório deve conter:

- resumo do slice;
- evidência RED: testes falhando antes da implementação;
- evidência GREEN: testes passando após implementação;
- snippets antes/depois dos trechos principais;
- respostas aos gates de autoavaliação;
- comandos de validação executados e resultado;
- arquivos tocados e justificativa;
- riscos residuais, se houver.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/header-notifications-queue-badges/proposal.md, design.md, tasks.md and slices/slice-001-header-notifications-inbox.md.

Implement ONLY Slice 001. Use TDD: first add/adjust failing tests, then implement minimal code. Keep it clean, DRY and YAGNI. Do not add Bootstrap Icons CDN. Use inline SVG for the bell if needed. Preserve notification polling attributes: id="notification-badge", data-notifications-badge, data-unread-count-url, data-count and aria-label. Replace the visible textual Notificações button with a compact bell. Remove only the rendered queue_count badge from avatar/name in templates/base.html; do not remove the context processor. Add a persistent Voltar ao início link to templates/accounts/notifications.html.

Do not implement Slice 002. Do not change models, migrations, notification endpoint, WebSocket/SSE/push/toasts/dropdowns, or queue counters in doctor/scheduler tabs.

Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/header-notifications-queue-badges/tasks.md when complete for Slice 001 only.
Create /tmp/ats-web-header-notifications-queue-badges-slice-001-report.md with RED/GREEN evidence, before/after snippets, quality gate results and self-evaluation answers.
Commit and push. Reply with REPORT_PATH=/tmp/ats-web-header-notifications-queue-badges-slice-001-report.md and stop.
```
