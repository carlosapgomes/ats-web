# Design: Menções e notificações in-app da comunicação por caso

## Estado atual

O change `case-operational-communication-mvp` entregou:

- `CaseCommunicationMessage` em `apps/cases/models.py`;
- serviço `post_case_communication_message` em `apps/cases/services.py`;
- endpoint SSR `/cases/<case_id>/communication/`;
- partial `templates/cases/_communication_thread.html`;
- thread visível para NIR, médico e agendador;
- evento `CASE_COMMUNICATION_MESSAGE_POSTED`;
- sem notificações, polling ou read state.

O header global está em `templates/base.html`. Já existe CSS para badge em `static/css/app.css` (`.notif-badge`). O projeto já carrega HTMX globalmente, mas este change **não deve usar HTMX para notificações**; usar Vanilla JS no polling.

## Decisões

### D1. Notificação é user-scoped e in-app

Criar `UserNotification` como notificação persistente para usuário específico.

Não criar notificações por papel como entidade abstrata. Menções por papel resolvem para usuários concretos no momento do post.

Motivos:

- facilita badge por usuário;
- facilita marcação individual como lida;
- preserva snapshot de destinatários;
- evita recalcular notificações antigas quando papéis mudam.

### D2. Modelo em `apps/accounts.models`

Adicionar `UserNotification` em `apps/accounts/models.py`, usando FKs string para evitar ciclos:

```python
class UserNotification(models.Model):
    notification_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    case = models.ForeignKey(
        "cases.Case",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
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

    class Meta:
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

Se o banco tratar `NULL` em unique constraint de forma permissiva, tudo bem: no MVP as notificações criadas por comunicação sempre têm `communication_message`.

### D3. Menções explícitas apenas

Criar notificações somente quando o corpo da mensagem contém menções explícitas.

Não notificar todos os participantes do caso automaticamente no MVP.

Motivos:

- evita ruído;
- mantém semântica clara;
- reduz risco de spam operacional;
- preserva simplicidade.

### D4. Parser simples de menções

Implementar parser pequeno, preferencialmente em `apps/cases/services.py` ou helper coeso:

```python
MENTION_TOKEN_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_\.\-]{2,50})")
COMMUNICATION_MENTION_ROLES = {"nir", "doctor", "scheduler", "manager", "admin"}
```

Regras:

- normalizar role tokens para lowercase;
- usernames podem ser tratados case-insensitive para resolução, mas preservar username real no payload;
- tokens desconhecidos são ignorados;
- deduplicar tokens repetidos;
- não tentar parser markdown complexo;
- não implementar autocomplete.

### D5. Resolução de destinatários

Ao postar mensagem:

1. identificar `mentioned_roles`;
2. identificar `mentioned_usernames`;
3. buscar usuários ativos:
   - `is_active=True`;
   - `account_status="active"`;
4. roles: `User.objects.filter(roles__name__in=mentioned_roles)`;
5. usernames: `User.objects.filter(username__iexact=token)`;
6. unir e deduplicar por `pk`;
7. excluir `author`;
8. criar uma notificação por destinatário.

Usuário mencionado por papel e username recebe uma única notificação para a mensagem.

### D6. Serviço de criação de notificações

Criar serviço, por exemplo em `apps/accounts/services.py`:

```python
def create_case_communication_notifications(*, message: CaseCommunicationMessage) -> NotificationCreationResult:
    ...
```

Ou manter helper em `apps/cases/services.py` se ficar mais enxuto. Preferência: `apps/accounts/services.py` para responsabilidades de notificação, chamado pelo serviço de comunicação.

Resultado recomendado:

```python
@dataclass(frozen=True)
class NotificationCreationResult:
    mentioned_roles: tuple[str, ...]
    mentioned_usernames: tuple[str, ...]
    notification_count: int
```

O serviço de comunicação deve usar esse resultado para enriquecer o payload do `CASE_COMMUNICATION_MESSAGE_POSTED`.

### D7. Ordem de criação do evento

Hoje o serviço de comunicação cria mensagem e evento. Para incluir `notification_count` no evento, a ordem recomendada é:

```text
validar body
criar CaseCommunicationMessage
criar UserNotifications
criar CaseEvent com payload incluindo mentions/notification_count
```

Se a implementação atual cria o evento antes, ajustar com cuidado e teste.

### D8. UI de notificações em `apps/accounts`

Adicionar rotas em `apps/accounts/urls.py`:

```python
path("notifications/", views.notifications_list, name="notifications")
path("notifications/<uuid:notification_id>/open/", views.notification_open, name="notification_open")
path("notifications/<uuid:notification_id>/read/", views.notification_mark_read, name="notification_mark_read")
path("notifications/mark-all-read/", views.notifications_mark_all_read, name="notifications_mark_all_read")
```

Templates sugeridos:

```text
templates/accounts/notifications.html
```

Comportamento:

- listar apenas notificações de `request.user`;
- não expor notificações de outros usuários;
- `notification_open` marca como lida e redireciona para o caso;
- `notification_mark_read` é POST e marca uma como lida;
- `notifications_mark_all_read` é POST;
- usar `messages.success` quando adequado.

### D9. Link para caso por papel ativo

`notification_open` deve redirecionar conforme `active_role` atual:

| active_role | destino sugerido |
| --- | --- |
| `nir` | `intake:case_detail` |
| `doctor` | `doctor:decision` se caso em `WAIT_DOCTOR`; senão `doctor:decided_detail` quando o usuário for o médico que decidiu; fallback `doctor:queue` |
| `scheduler` | `scheduler:confirm` se caso em `WAIT_APPT`; fallback `scheduler:queue` |
| `manager`/`admin` | fallback `dashboard:index` ou detalhe disponível se existir |

Manter simples. Se não houver rota segura para o papel/status, redirecionar para a home/fila do papel com mensagem informativa.

Não criar detalhe universal novo neste change.

### D10. Badge SSR no header

Adicionar contagem de não lidas ao contexto global, preferencialmente em `apps/accounts/context_processors.py`, reaproveitando contexto existente:

```python
notification_unread_count = UserNotification.objects.filter(recipient=request.user, read_at__isnull=True).count()
```

Em `templates/base.html`, adicionar link:

```django
<a href="{% url 'notifications' %}" id="notification-badge" data-count="{{ notification_unread_count }}">Notificações</a>
```

Usar `.notif-badge` já existente em CSS.

### D11. Polling leve com Vanilla JS no Slice 002

Adicionar endpoint:

```python
GET /notifications/unread-count/
```

Resposta:

```json
{"unread_count": 3}
```

Adicionar `static/js/notifications.js`:

- ler elemento `#notification-badge`;
- se não existir, não fazer nada;
- intervalo inicial: 45s ou 60s;
- só fazer request quando `document.visibilityState === "visible"`;
- em erro, backoff simples;
- atualizar `data-count` e texto acessível;
- não buscar mensagens;
- não tocar na thread do caso;
- não usar HTMX.

Incluir script em `base.html`.

### D12. Slices verticais

Este change terá **2 slices verticais**.

#### Slice 001 — Menções criam notificações e inbox SSR

Entrega:

```text
Mensagem com @role/@username → UserNotification → badge SSR → página Minhas notificações → abrir/marcar lida
```

Inclui modelo/migration, parser/resolução, criação de notificações, views/templates de inbox e header SSR.

#### Slice 002 — Polling Vanilla JS e hardening de entrega

Entrega:

```text
Badge de notificações atualiza periodicamente sem reload usando endpoint JSON e Vanilla JS
```

Inclui endpoint unread-count, JS, acessibilidade do badge, testes de polling e regressões para não usar HTMX/WebSocket/SSE.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Notificar demais | Só menções explícitas no MVP |
| Duplicar notificação | Deduplicação por destinatário + unique constraint |
| Autor receber autopings | Excluir autor |
| Link para rota sem acesso | Redirecionamento por active_role com fallback seguro |
| Polling virar chat | Polling atualiza apenas badge, nunca thread |
| Aumentar dependência de HTMX | Usar Vanilla JS; não criar hx-get/hx-trigger para notificações |
| Parser complexo demais | Regex simples; sem autocomplete/aliases avançados |

## Futuro fora deste change

- Autocomplete de menções.
- Aliases como `@chd`, `@nir_lideranca`, `@medicos_chd`.
- Preferências de notificação por usuário.
- Notificar participantes de um caso sem menção explícita.
- Mensagens sistêmicas em comunicação por caso (`workflow-system-notices-in-case-communication`).
- Push/SMS/email operacional, se algum dia for aprovado por ADR específica.
