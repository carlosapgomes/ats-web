<!-- markdownlint-disable MD013 -->

# Design: Ocultar notificações lidas há mais de 48h

## D1. Ocultar vs. apagar

**Decisão: ocultar da UI.** A demanda original mencionava "apagar", mas a motivação declarada é apresentacional ("a lista está ficando muito longa"). Apagar `UserNotification`:

- tornaria a ação irreversível sem ganho presente;
- conflitaria com o princípio de auditoria do projeto (ainda que `UserNotification` não seja a trilha de auditoria canônica, o projeto não tem política de deleção de dados operacionais);
- exigiria task django-q2, idempotência e mais superfície de teste.

Ocultar entrega o valor com queryset puro, reversível e sem migrations.

## D2. Semântica da janela

- Visível: `read_at IS NULL` **ou** `read_at >= now - 48h`.
- Oculta: `read_at IS NOT NULL AND read_at < now - 48h`.
- Implementação com um único `exclude`: `qs.exclude(read_at__lt=cutoff)` — em SQL, `read_at < cutoff` avalia `NULL` para não lidas, portanto **não lidas nunca são excluídas** pelo `exclude`. Esse detalhe semântico do ORM deve ser coberto por teste explícito.
- A janela usa `read_at` (momento da leitura), decisão registrada no proposal. `created_at` não participa do predicado.

## D3. Onde vive o filtro

`UserNotification` hoje é um `models.Model` simples com `Meta.ordering = ["-created_at"]`. O filtro de visibilidade entra como **QuerySet customizado**:

- `UserNotificationQuerySet.visible_for_list(now=None)` — recebe `now` injetável para testes determinísticos; default `timezone.now()`.
- Manager `UserNotification.objects` passa a expor o QuerySet (`UserNotificationManager.from_queryset`), preservando a API existente (`objects.filter`, `objects.create` etc. usados em `apps/accounts/services.py` e views).

Alternativa considerada e rejeitada: filtrar inline na view (`UserNotification.objects.filter(...).exclude(...)`). Rejeitada porque o `AGENTS.md` manda centralizar queries em QuerySets customizados, e o predicado NULL-safe merece nome próprio e teste unitário direto.

## D4. Constante de configuração

`NOTIFICATION_READ_RETENTION_HOURS = 48` em `config/settings/base.py`, lida no QuerySet via `settings.NOTIFICATION_READ_RETENTION_HOURS` com `getattr(..., 48)` de fallback defensivo (mesmo padrão de `_get_lease_seconds` em `apps/cases/services.py`). Sem env var neste change (fora de escopo).

## D5. Superfícies não afetadas (verificação de não-regressão)

- Badge/contador de não lidas (`get_unread_notification_count`, polling `notifications_unread_count`): conta apenas `read_at IS NULL` — invisível ao predicado de leitura.
- `notification_open`, `notification_mark_read`, `notifications_mark_all_read`: resolvem por PK; notificação oculta continua acessível por URL direta (comportamento inalterado e aceito; o caso de origem continua navegável).
- Criação de notificações por menção (`apps/accounts/services.py`): inalterada.
- Template `accounts/notifications.html`: inalterado — a lista simplesmente encurta; estado vazio existente continua válido.

## D6. Testes

- Unitários do QuerySet (`visible_for_list`): os 4 casos de D2, com `now` injetado e sem freezegun.
- Integração da view: notificação lida há 49h não aparece no HTML; lida há 1h aparece; não lida antiga aparece.
- Estilo do arquivo de testes: seguir `apps/accounts/tests/test_notifications.py` (fixtures `db`/`client`, `timezone.now()`, escrita direta de `read_at`).
