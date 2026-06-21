# Proposal: Menções e notificações in-app da comunicação por caso

**Change ID**: `case-communication-mentions-notifications`  
**Prioridade**: média  
**Risco**: PROFISSIONAL (novo modelo de notificação, entrega direcionada a usuários, header global e polling leve)  
**Dependências**: `case-operational-communication-mvp`

## Problema

O MVP de comunicação operacional por caso permite registrar mensagens contextualizadas no `Case`, mas ainda exige que usuários abram manualmente cada caso para descobrir se há algo relevante.

Isso limita a substituição de canais externos como WhatsApp quando alguém precisa direcionar atenção para um papel ou usuário específico.

Exemplos:

- NIR precisa chamar médicos para revisar um esclarecimento: `@doctor`.
- Médico precisa pedir ação do NIR: `@nir`.
- NIR ou médico precisa chamar agendamento: `@scheduler`.
- Supervisor precisa ser acionado: `@manager`.
- Um usuário específico precisa ser chamado: `@usuario`.

Sem notificação in-app, essas mensagens podem passar despercebidas.

## Objetivo

Adicionar menções e notificações in-app para mensagens da comunicação operacional por caso.

Fluxo alvo:

```text
Usuário posta mensagem no caso com @doctor ou @maria
→ sistema identifica menções
→ cria notificações in-app para destinatários elegíveis
→ destinatário vê badge no header
→ destinatário abre “Minhas notificações”
→ clica na notificação e vai para o caso
→ notificação é marcada como lida
```

Depois, adicionar atualização leve do badge por polling com Vanilla JS.

## Escopo

### Menções suportadas no MVP

#### Menções por papel

Suportar tokens explícitos:

```text
@nir
@doctor
@scheduler
@manager
@admin
```

Cada token notifica usuários ativos com o papel correspondente.

#### Menções por usuário

Suportar menção direta por username:

```text
@username
```

Regras:

- se o token for um papel conhecido, tratar como papel;
- caso contrário, tentar resolver como `User.username` ativo;
- tokens não reconhecidos são ignorados silenciosamente;
- deduplicar destinatários quando usuário for mencionado por papel e username;
- não notificar o autor da mensagem.

### Modelo de notificação

Criar modelo sugerido em `apps/accounts/models.py`:

```python
UserNotification
```

Campos mínimos:

```python
notification_id = UUID primary key
recipient = ForeignKey(User, related_name="notifications")
case = ForeignKey("cases.Case")
communication_message = ForeignKey("cases.CaseCommunicationMessage", null=True, blank=True)
triggered_by = ForeignKey(User, null=True, blank=True, related_name="notifications_triggered")
notification_type = CharField(default="case_communication_mention")
title = CharField(max_length=160)
body_preview = CharField(max_length=240)
created_at = DateTimeField(auto_now_add=True)
read_at = DateTimeField(null=True, blank=True)
```

Recomendação:

- `UniqueConstraint(recipient, communication_message)` para evitar duplicidade por mensagem;
- índices por `recipient/read_at/created_at`.

### Integração com comunicação existente

Ao postar `CaseCommunicationMessage`, o serviço deve:

1. criar a mensagem como hoje;
2. extrair menções do `body`;
3. resolver destinatários;
4. criar `UserNotification` para cada destinatário elegível;
5. registrar no evento de comunicação um resumo das menções/notificações criadas.

Evento existente:

```text
CASE_COMMUNICATION_MESSAGE_POSTED
```

Payload pode ser estendido com campos enxutos:

```json
{
  "message_id": "...",
  "author_role": "doctor",
  "body_preview": "...",
  "mentioned_roles": ["nir"],
  "mentioned_usernames": ["maria"],
  "notification_count": 2
}
```

Não criar novo evento para cada notificação no MVP.

### UI de notificações

Adicionar:

```text
Minhas notificações
```

Funcionalidades:

- listar notificações do usuário autenticado;
- separar/indicar não lidas;
- mostrar título, preview, caso, autor e data/hora;
- link para abrir caso;
- marcar notificação individual como lida;
- marcar todas como lidas.

### Badge no header

Mostrar badge de não lidas no header global:

```text
Notificações (3)
```

O primeiro slice pode atualizar o badge apenas por render SSR. O segundo slice adiciona polling leve.

### Polling leve com Vanilla JS

Adicionar endpoint:

```text
GET /notifications/unread-count/
→ { "unread_count": 3 }
```

Adicionar JS vanilla:

- intervalo 30–60s;
- somente quando `document.visibilityState === "visible"`;
- backoff simples em erro;
- sem HTMX;
- sem websocket/SSE;
- sem atualizar a thread como chat em tempo real.

## Fora de escopo

- SMS.
- Push notification.
- Email operacional.
- WebSocket.
- SSE.
- HTMX para notificações.
- Chat em tempo real.
- Auto-refresh da thread de mensagens.
- Presença online.
- Autocomplete de menções.
- Menções por aliases avançados como `@chd`, `@nir_lideranca`, `@medicos_chd`.
- Preferências de notificação por usuário.
- Notificações para todos os participantes sem menção explícita.
- Mensagens sistêmicas espelhando workflows estruturados.

## Critérios de sucesso

- Menções por papel criam notificações para usuários ativos com o papel mencionado.
- Menções por username criam notificação para o usuário ativo correspondente.
- Tokens desconhecidos são ignorados sem quebrar o post da mensagem.
- Autor não recebe notificação da própria mensagem.
- Destinatários duplicados recebem no máximo uma notificação por mensagem.
- Header mostra badge SSR com contagem de não lidas.
- Tela “Minhas notificações” lista notificações do usuário autenticado.
- Abrir/marcar notificação atualiza `read_at`.
- Marcar todas como lidas funciona.
- Polling leve atualiza apenas o badge no Slice 002.
- Nenhum HTMX/WebSocket/SSE é usado para notificações.
- Comunicação por caso continua funcionando sem menção.
- Quality gate do AGENTS.md passa.
