# Slice 001: Menções criam notificações e inbox SSR

## Contexto zero para implementador

O ATS é um monolito Django SSR. A comunicação operacional por caso já existe via `CaseCommunicationMessage` e serviço `post_case_communication_message`.

Hoje, quando alguém posta uma mensagem em um caso, outros usuários só veem se abrirem o caso manualmente. Este slice adiciona menções e notificações in-app persistentes, ainda sem polling ativo.

Fluxo alvo:

```text
NIR/médico/agendador posta mensagem: "@doctor favor revisar"
→ sistema identifica @doctor
→ cria UserNotification para usuários ativos com papel doctor
→ destinatário vê badge no header no próximo render SSR
→ destinatário abre “Minhas notificações”
→ clica na notificação
→ notificação é marcada como lida e redireciona ao caso/fila segura
```

O Slice 002 adicionará polling Vanilla JS do badge. Não implemente polling neste slice.

## Objetivo do slice

Entregar verticalmente:

```text
Parser de menções + modelo UserNotification + criação no post da mensagem + badge SSR + inbox SSR + marcar lida
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/accounts/models.py`
2. `apps/accounts/migrations/<nova_migration>.py`
3. `apps/accounts/services.py` ou helper equivalente
4. `apps/accounts/context_processors.py`
5. `apps/accounts/views.py`
6. `apps/accounts/urls.py`
7. `apps/cases/services.py`
8. `templates/base.html`
9. `templates/accounts/notifications.html`
10. testes em `apps/accounts/tests/...` e/ou `apps/cases/tests/...`
11. `openspec/changes/case-communication-mentions-notifications/tasks.md` ao concluir

Este slice toca mais de 5 arquivos porque é o menor fluxo vertical real: menção → notificação → UI → leitura. Não separar modelo/serviço/UI em fatias horizontais.

## Requisitos funcionais

### R1. Modelo `UserNotification`

Adicionar em `apps/accounts/models.py`:

```python
class UserNotification(models.Model):
    notification_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    case = models.ForeignKey("cases.Case", on_delete=models.CASCADE, related_name="notifications")
    communication_message = models.ForeignKey(
        "cases.CaseCommunicationMessage",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications_triggered",
    )
    notification_type = models.CharField(max_length=60, default="case_communication_mention")
    title = models.CharField(max_length=160)
    body_preview = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
```

Meta recomendada:

```python
ordering = ["-created_at"]
indexes = [
    models.Index(fields=["recipient", "read_at", "created_at"]),
    models.Index(fields=["case", "created_at"]),
]
constraints = [
    models.UniqueConstraint(
        fields=["recipient", "communication_message"],
        name="unique_notification_per_recipient_message",
    )
]
```

Criar migration.

### R2. Parser de menções

Suportar:

```text
@nir
@doctor
@scheduler
@manager
@admin
@username
```

Regras:

- tokens de papel são case-insensitive e normalizados para lowercase;
- token de username deve resolver usuário ativo (`is_active=True`, `account_status="active"`);
- tokens desconhecidos são ignorados;
- tokens repetidos são deduplicados;
- parser deve ser simples, sem markdown/autocomplete.

Regex sugerida:

```python
MENTION_TOKEN_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_\.\-]{2,50})")
```

### R3. Resolução de destinatários

Criar serviço/helper, por exemplo em `apps/accounts/services.py`:

```python
COMMUNICATION_MENTION_ROLES = {"nir", "doctor", "scheduler", "manager", "admin"}

@dataclass(frozen=True)
class NotificationCreationResult:
    mentioned_roles: tuple[str, ...]
    mentioned_usernames: tuple[str, ...]
    notification_count: int


def create_case_communication_notifications(*, message: CaseCommunicationMessage) -> NotificationCreationResult:
    ...
```

Regras:

- roles → usuários ativos com aquele papel;
- usernames → usuários ativos com username correspondente;
- deduplicar destinatários;
- excluir `message.author`;
- criar no máximo uma notificação por destinatário por mensagem;
- se não houver menção, retornar `notification_count=0`.

Título sugerido:

```text
Você foi mencionado em um caso
```

Preview:

```text
primeiros 200–240 caracteres da mensagem
```

### R4. Integração com `post_case_communication_message`

Em `apps/cases/services.py`, após criar `CaseCommunicationMessage`, chamar o serviço de notificações.

Atualizar payload do evento `CASE_COMMUNICATION_MESSAGE_POSTED` para incluir:

```json
{
  "message_id": "...",
  "author_role": "nir",
  "body_preview": "...",
  "mentioned_roles": ["doctor"],
  "mentioned_usernames": ["maria"],
  "notification_count": 2
}
```

Não criar evento individual para cada notificação neste MVP.

Mensagem sem menção deve continuar criando `CaseCommunicationMessage` normalmente, com `notification_count=0`.

### R5. Badge SSR no header

Em `apps/accounts/context_processors.py`, expor:

```python
notification_unread_count
```

Contagem:

```python
UserNotification.objects.filter(recipient=request.user, read_at__isnull=True).count()
```

Em `templates/base.html`, adicionar link no header para:

```django
{% url 'notifications' %}
```

Usar classe CSS existente `.notif-badge`, por exemplo:

```django
<a href="{% url 'notifications' %}"
   id="notification-badge"
   class="btn btn-sm btn-light notif-badge"
   data-count="{{ notification_unread_count|default:0 }}">
  Notificações
</a>
```

Não adicionar JS neste slice.

### R6. Tela “Minhas notificações”

Adicionar rotas em `apps/accounts/urls.py`:

```python
path("notifications/", views.notifications_list, name="notifications")
path("notifications/<uuid:notification_id>/open/", views.notification_open, name="notification_open")
path("notifications/<uuid:notification_id>/read/", views.notification_mark_read, name="notification_mark_read")
path("notifications/mark-all-read/", views.notifications_mark_all_read, name="notifications_mark_all_read")
```

Views:

- `notifications_list`: GET, lista apenas notificações de `request.user`.
- `notification_open`: GET, busca notificação do usuário, marca `read_at` se vazio, redireciona conforme papel/status.
- `notification_mark_read`: POST, marca uma como lida.
- `notifications_mark_all_read`: POST, marca todas não lidas do usuário como lidas.

Template:

```text
templates/accounts/notifications.html
```

Mostrar:

- título “Minhas notificações”;
- contagem de não lidas;
- lista com não lidas destacadas;
- título/preview/caso/data/autor;
- botão/link “Abrir caso”;
- botão “Marcar como lida” quando não lida;
- botão “Marcar todas como lidas”.

### R7. Redirecionamento seguro ao abrir notificação

Ao abrir notificação, redirecionar de forma segura conforme `active_role`:

- `nir`: `intake:case_detail` se caso não estiver `CLEANED`; se `CLEANED`, fallback home/fila com mensagem.
- `doctor`: `doctor:decision` se `WAIT_DOCTOR`; se o caso já foi decidido pelo próprio médico, `doctor:decided_detail`; senão fallback `doctor:queue`.
- `scheduler`: `scheduler:confirm` se `WAIT_APPT`; senão fallback `scheduler:queue`.
- `manager`/`admin`: `dashboard:index` como fallback inicial.

Não criar detalhe universal novo neste slice.

## TDD obrigatório

Antes da implementação, criar testes falhando.

### Testes mínimos de parser/serviço

1. `test_extracts_role_mentions_from_message_body`
   - body com `@doctor @nir` retorna papéis normalizados.

2. `test_extracts_username_mentions_from_message_body`
   - body com `@maria` resolve username ativo.

3. `test_unknown_mentions_are_ignored`
   - `@fantasma` não quebra e não cria notificação.

4. `test_role_mention_creates_notifications_for_active_role_users`
   - usuários ativos com role recebem notificação.

5. `test_inactive_or_blocked_users_do_not_receive_notifications`
   - `is_active=False` ou `account_status != active` não recebem.

6. `test_author_does_not_receive_own_mention_notification`
   - autor com role mencionada não recebe.

7. `test_duplicate_role_and_username_mentions_create_single_notification_per_recipient`
   - usuário mencionado por `@doctor @username` recebe uma notificação.

8. `test_message_without_mentions_creates_no_notifications`
   - mensagem normal continua funcionando sem notificar.

9. `test_communication_event_payload_includes_mentions_and_notification_count`
   - evento inclui arrays e count.

### Testes mínimos UI/permissions

10. `test_header_shows_unread_notification_badge`
    - usuário com notificação não lida vê badge/count.

11. `test_notifications_list_shows_only_current_user_notifications`
    - não vaza notificação de outro usuário.

12. `test_open_notification_marks_read_and_redirects`
    - `read_at` preenchido e redirect seguro.

13. `test_user_cannot_open_other_users_notification`
    - 404/redirect/permission, sem marcar lida.

14. `test_mark_notification_read_requires_post`
    - GET não marca.

15. `test_mark_all_notifications_read_marks_only_current_user`
    - não altera notificações de terceiros.

### RED esperado

Antes da implementação, os testes devem falhar por ausência de modelo/serviço/views/UI.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- Parser/resolução em serviço/helper, não em view/template.
- Views de notificação pequenas e coesas.
- Helper claro para resolver URL de destino da notificação.
- Nomes explícitos: `mentioned_roles`, `mentioned_usernames`, `notification_count`.

### DRY

- Um único parser de menções.
- Um único serviço de criação de notificações.
- Não duplicar query de unread count fora de helper/context processor quando possível.

### YAGNI

Não implementar neste slice:

- polling;
- endpoint JSON unread-count;
- JS de notificações;
- HTMX;
- WebSocket/SSE;
- autocomplete de menções;
- aliases avançados;
- preferências de notificação;
- notificações para mensagens sem menção;
- push/SMS/email.

## Critérios de sucesso

- [ ] `UserNotification` criado com migration.
- [ ] Menções por papel criam notificações.
- [ ] Menções por username criam notificações.
- [ ] Autor não recebe notificação própria.
- [ ] Destinatários duplicados são deduplicados.
- [ ] Mensagem sem menção não cria notificação.
- [ ] Evento de comunicação inclui resumo de menções/count.
- [ ] Header mostra badge SSR de não lidas.
- [ ] Tela de notificações lista apenas notificações do usuário.
- [ ] Abrir/marcar notificação atualiza `read_at`.
- [ ] Não há polling/JS/HTMX neste slice.
- [ ] Testes novos passam.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Onde está o parser de menções?
2. Qual teste prova que role mention cria notificações?
3. Qual teste prova que username mention cria notificação?
4. Qual teste prova que o autor não recebe autopings?
5. Qual teste prova que não há vazamento de notificações de outro usuário?
6. Qual teste prova que abrir notificação marca como lida?
7. Foi implementado polling/JS/HTMX neste slice? Se sim, está fora de escopo.
8. Mensagens sem menção continuam funcionando? Qual teste prova?

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/case-communication-mentions-notifications-slice-001-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois;
- resultados do quality gate;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/case-communication-mentions-notifications-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/case-communication-mentions-notifications/proposal.md, design.md, tasks.md and slices/slice-001-mentions-create-in-app-notifications.md.
Implement ONLY Slice 001.
Use TDD: first add failing tests for mention parsing, notification creation, SSR badge and notifications inbox, then implement minimal code.
Add UserNotification, a migration, mention parsing for @nir/@doctor/@scheduler/@manager/@admin and @username, notification creation when CaseCommunicationMessage is posted, SSR unread badge in the header, and a “Minhas notificações” page with open/mark-read/mark-all-read behavior.
Do not implement polling, JS unread-count endpoint, HTMX notifications, WebSocket/SSE, autocomplete, aliases advanced, push/SMS/email, or notifications for messages without explicit mention.
Apply clean code, DRY and YAGNI. Keep parser and notification rules in services/helpers, not views/templates.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/case-communication-mentions-notifications/tasks.md for Slice 001 when complete.
Create /tmp/case-communication-mentions-notifications-slice-001-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
