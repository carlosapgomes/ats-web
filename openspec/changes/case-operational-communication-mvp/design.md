# Design: Comunicação operacional por caso — MVP

## Estado atual

O sistema já possui:

- `Case` como entidade central em `apps/cases/models.py`;
- `CaseEvent` append-only para auditoria;
- telas operacionais SSR para NIR, médico e agendador;
- campos estruturados para decisões e exceções:
  - `doctor_reason`;
  - `doctor_observation`;
  - `appointment_reason`;
  - campos de intercorrência pós-agendamento;
  - `correction_reason` para reenvio corrigido;
- eventos de anexos, supressão, complemento e reenvio corrigido.

Não existe ainda uma thread textual por caso para esclarecimentos operacionais.

## Decisões

### D1. Comunicação sempre vinculada a `Case`

Não criar chat global, sala geral ou conversa desvinculada.

Cada mensagem pertence a exatamente um caso:

```python
case = ForeignKey(Case, related_name="communication_messages")
```

Motivos:

- reduz risco de PHI fora de contexto;
- mantém rastreabilidade;
- evita substituir WhatsApp por outro chat global;
- facilita auditoria por caso.

### D2. Modelo append-only simples

Modelo proposto em `apps/cases/models.py`:

```python
class CaseCommunicationMessage(models.Model):
    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="communication_messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_communication_messages")
    author_role = models.CharField(max_length=30)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["case", "created_at"])]
```

`author_role` é snapshot do papel ativo na sessão no momento do post. Isso preserva o contexto mesmo se o usuário trocar papel ativo depois.

No MVP:

- sem edição;
- sem deleção;
- sem supressão;
- sem anexos;
- sem mensagem sistêmica;
- sem read state.

### D3. Serviço de domínio em `apps/cases/services.py`

Adicionar serviço pequeno:

```python
ALLOWED_COMMUNICATION_ROLES = {"nir", "doctor", "scheduler", "manager", "admin"}
CASE_COMMUNICATION_MAX_LENGTH = 2000

class CaseCommunicationError(ValueError):
    pass


def post_case_communication_message(*, case: Case, author: User, author_role: str, body: str) -> CaseCommunicationMessage:
    ...
```

Responsabilidades:

1. validar `author_role` permitido;
2. rejeitar mensagem vazia/apenas espaços;
3. normalizar `body.strip()`;
4. rejeitar mensagem acima de `CASE_COMMUNICATION_MAX_LENGTH`;
5. criar `CaseCommunicationMessage`;
6. criar `CaseEvent` `CASE_COMMUNICATION_MESSAGE_POSTED`.

Manter regras de negócio fora de views/templates.

### D4. Evento de auditoria enxuto

Criar evento a cada post:

```text
CASE_COMMUNICATION_MESSAGE_POSTED
```

Payload:

```json
{
  "message_id": "...",
  "author_role": "nir",
  "body_preview": "primeiros 120 caracteres"
}
```

Não duplicar o corpo inteiro no evento. A fonte completa da mensagem é `CaseCommunicationMessage`.

### D5. Permissões básicas por papel

MVP deve permitir post para papéis operacionais:

```python
{"nir", "doctor", "scheduler", "manager", "admin"}
```

Regras iniciais recomendadas:

- usuário autenticado obrigatório;
- `active_role` da sessão deve estar em `ALLOWED_COMMUNICATION_ROLES`;
- `Case.status != CLEANED` para post no MVP;
- leitura ocorre nas telas onde o usuário já tem acesso ao caso;
- a rota POST deve também validar papel para não depender apenas de esconder formulário.

Não criar matriz complexa de permissão por status neste MVP. O controle principal de acesso continua sendo a tela operacional existente.

Se for necessário restringir por status/papel no futuro, criar change separado.

### D6. UI SSR simples e reutilizável

Criar partial compartilhado, por exemplo:

```text
templates/cases/_communication_thread.html
```

Entrada de contexto sugerida:

```python
communication_messages
can_post_communication
communication_post_url
communication_next_url
communication_max_length
```

A partial deve renderizar:

- título “Comunicação operacional”;
- alerta conceitual curto:

```text
Use para esclarecimentos e coordenação. Decisões formais continuam nos fluxos estruturados.
```

- lista cronológica de mensagens;
- autor e papel;
- data/hora;
- corpo com quebra de linha preservada;
- textarea e botão quando `can_post_communication=True`.

Não criar JS para polling. O post SSR recarrega/redireciona a página.

### D7. Endpoint POST único

Adicionar rota sob `/cases/` porque `apps.intake.urls` já está incluído em `path("cases/", ...)`:

```python
path("<uuid:case_id>/communication/", views.post_case_communication, name="post_case_communication")
```

A view pode ficar inicialmente em `apps/intake/views.py` para reduzir criação de novas URLs/apps, mas a lógica deve chamar serviço de `apps/cases/services.py`.

Comportamento:

- `@login_required`;
- validar `active_role` em view/serviço;
- aceitar apenas POST;
- buscar `Case`;
- chamar `post_case_communication_message`;
- usar `messages.success`/`messages.warning`;
- redirecionar para `next` seguro ou fallback.

`next` deve ser tratado com segurança usando utilitário Django apropriado (`url_has_allowed_host_and_scheme`) ou fallback fixo. Não aceitar redirect aberto.

### D8. Sem notificações/polling neste change

Este change não implementa:

- badge no header;
- tela de notificações;
- polling com `fetch()`;
- HTMX;
- websocket;
- SSE;
- marcação de lido.

Motivo: manter MVP enxuto e não criar uma experiência de chat em tempo real antes de validar necessidade operacional.

### D9. Slices verticais

Este change terá **2 slices verticais**.

#### Slice 001 — Thread operacional NIR ↔ Médico

Entrega:

```text
NIR posta mensagem no detalhe do caso
→ médico vê/posta na tela de decisão
→ mensagem persiste no caso
→ evento auditável é criado
```

Inclui:

- modelo/migration;
- serviço de domínio;
- endpoint POST;
- partial compartilhado;
- inclusão no detalhe NIR;
- inclusão na decisão médica;
- testes de serviço, permissão, NIR e médico.

Justificativa de tocar mais arquivos: é o menor fluxo vertical útil de comunicação bidirecional entre dois papéis centrais. Separar modelo/serviço/UI criaria fatias horizontais sem valor operacional.

#### Slice 002 — Extensão para agendamento e hardening de superfícies compartilhadas

Entrega:

```text
Agendador vê/posta mensagens no contexto de agendamento/intercorrência
→ labels de timeline e regras de não-notificação ficam consistentes
→ partial é reutilizada sem duplicar lógica
```

Inclui:

- tela de confirmação do scheduler;
- tela de resposta de intercorrência, se aplicável;
- labels/dots do evento em timeline;
- testes de scheduler e regressão de não-polling/notificação.

Por que não incluir scheduler no Slice 001: a tela de agendamento tem fluxos/locks próprios; separar mantém o core NIR↔médico menor, sem perder verticalidade.

## Arquivos previstos

### Slice 001

| Arquivo | Mudança |
| --- | --- |
| `apps/cases/models.py` | modelo `CaseCommunicationMessage` |
| `apps/cases/migrations/*` | migration |
| `apps/cases/services.py` | serviço de post e validações |
| `apps/intake/views.py` | endpoint POST + contexto NIR |
| `apps/intake/urls.py` | rota POST |
| `apps/doctor/views.py` | contexto da thread na decisão médica |
| `templates/cases/_communication_thread.html` | partial compartilhado |
| `templates/intake/case_detail.html` | include do partial |
| `templates/doctor/decision.html` | include do partial |
| testes | serviço + NIR + médico |

### Slice 002

| Arquivo | Mudança |
| --- | --- |
| `apps/scheduler/views.py` | contexto da thread para agendamento/intercorrência |
| `templates/scheduler/confirm.html` | include do partial |
| `templates/scheduler/confirm_post_schedule_issue.html` | include do partial, se aplicável |
| `apps/intake/views.py` | label/dot de evento, se ainda não feito |
| testes | scheduler + regressões |

Se o implementador encontrar forma mais enxuta mantendo o valor vertical, pode ajustar e justificar no relatório.

## UX textual sugerida

Título:

```text
💬 Comunicação operacional
```

Texto de ajuda:

```text
Use este espaço para esclarecimentos e coordenação sobre este caso. Decisões formais, agendamento e encerramento continuam nos fluxos estruturados.
```

Estado vazio:

```text
Nenhuma mensagem operacional registrada neste caso.
```

Textarea:

```text
Escreva uma mensagem operacional sobre este caso...
```

Botão:

```text
Enviar mensagem
```

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Virar chat global | Mensagens sempre vinculadas a `Case`; sem tela global no MVP |
| Substituir decisão formal | Texto de ajuda e docs reforçam workflow estruturado |
| Crescer escopo com notificações | Notificações ficam em change futuro |
| Duplicar lógica em templates | Partial compartilhado e contexto padronizado |
| Views com lógica de negócio | Serviço em `apps/cases/services.py` |
| Exposição indevida por URL | Login + active role + acesso pelas telas existentes + redirect seguro |
| Mensagens enormes | limite de tamanho no serviço |

## Futuro fora deste change

- `case-communication-mentions-notifications`:
  - `UserNotification`;
  - menções por papel/usuário;
  - badge no header;
  - polling periódico com Vanilla JS `fetch()`;
  - tela de notificações;
  - marcar como lida.
- `workflow-system-notices-in-case-communication`:
  - mensagens sistêmicas opcionais para eventos estruturados importantes.
- Anexos em mensagens, se houver necessidade real.
