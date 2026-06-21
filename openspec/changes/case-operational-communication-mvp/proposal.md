# Proposal: Comunicação operacional por caso — MVP

**Change ID**: `case-operational-communication-mvp`  
**Prioridade**: média/alta  
**Risco**: PROFISSIONAL (novo modelo persistente, novo fluxo de escrita multi-role, impacto em telas operacionais)  
**Dependências**: `case-attachments-initial-upload`, `fix-prior-case-lookup-after-closure`, `corrected-case-resubmission-linkage`

## Problema

O sistema substitui parte de um fluxo operacional que hoje costuma ocorrer por mensagens fora do prontuário/sistema, como WhatsApp. Os workflows estruturados já cobrem decisões formais e estados principais, mas ainda existem situações heterogêneas que exigem esclarecimento assíncrono contextual:

- anexo suspeito ou enviado incorretamente;
- relatório ambíguo;
- unidade de origem precisa esclarecer algo;
- médico precisa avisar o NIR sem transformar isso em decisão formal;
- NIR precisa contextualizar informação para médico ou agendamento;
- casos corrigidos/suprimidos exigem explicação operacional;
- intercorrências e exceções precisam de conversa curta sem alterar FSM.

Hoje essas mensagens tendem a escapar para canais externos, com risco de perda de contexto, baixa auditabilidade e exposição indevida de PHI.

## Objetivo

Criar um MVP de comunicação assíncrona **vinculada ao caso**, sem chat global e sem notificação ativa nesta etapa.

O MVP deve permitir:

```text
Usuário com papel operacional abre um caso
→ lê a thread operacional daquele caso
→ posta uma mensagem curta/contextual
→ mensagem fica persistida no caso
→ evento auditável registra o post
→ outros papéis que acessarem o mesmo caso veem a mensagem
```

## Escopo

### Modelo

Criar modelo sugerido:

```python
CaseCommunicationMessage
```

Campos mínimos:

```python
message_id: UUID primary key
case: ForeignKey(Case, related_name="communication_messages")
author: ForeignKey(User, on_delete=PROTECT)
author_role: CharField  # snapshot do papel ativo no momento do post
body: TextField
created_at: DateTimeField(auto_now_add=True)
```

Regras:

- mensagem sempre pertence a exatamente um `Case`;
- mensagem é append-only no MVP;
- sem edição;
- sem deleção/supressão;
- sem anexos em mensagens;
- sem menções reais;
- sem notificação ativa;
- sem websocket/SSE/HTMX polling.

### Serviço de domínio

Criar serviço pequeno, por exemplo em `apps/cases/services.py`:

```python
def post_case_communication_message(*, case: Case, author: User, author_role: str, body: str) -> CaseCommunicationMessage:
    ...
```

Responsabilidades:

- validar papel permitido;
- validar mensagem não vazia;
- normalizar `body.strip()`;
- validar tamanho máximo;
- criar `CaseCommunicationMessage`;
- criar `CaseEvent` com `event_type="CASE_COMMUNICATION_MESSAGE_POSTED"`.

### UI SSR

Criar área “Comunicação operacional” nas telas operacionais relevantes.

MVP recomendado por fatias:

1. NIR + Médico:
   - detalhe NIR do caso (`templates/intake/case_detail.html`);
   - tela de decisão médica (`templates/doctor/decision.html`).
2. Agendamento:
   - tela de confirmação de agendamento (`templates/scheduler/confirm.html`);
   - tela de resposta de intercorrência, se aplicável (`templates/scheduler/confirm_post_schedule_issue.html`).

A UI deve ser simples:

```text
Comunicação operacional
[lista de mensagens em ordem cronológica]
[textarea]
[Enviar mensagem]
```

### Rota POST

Adicionar endpoint SSR simples, por exemplo:

```text
POST /cases/<case_id>/communication/
```

Comportamento:

- usa sessão/autenticação normal;
- exige papel operacional permitido;
- persiste mensagem;
- usa `messages.success`/`messages.warning`;
- redireciona para `next` seguro ou para detalhe padrão do caso;
- sem JSON/API REST.

### Auditoria

Cada mensagem gera evento:

```text
CASE_COMMUNICATION_MESSAGE_POSTED
```

Payload mínimo:

```json
{
  "message_id": "...",
  "author_role": "doctor",
  "body_preview": "primeiros caracteres..."
}
```

O texto completo fica em `CaseCommunicationMessage`, não precisa ser duplicado inteiro em `CaseEvent.payload`.

## Regra conceitual

```text
Se precisa alterar estado, fila, agendamento, decisão ou responsabilidade formal → workflow estruturado.
Se precisa esclarecer, alertar ou coordenar → comunicação operacional.
```

Comunicação operacional **não substitui**:

- decisão médica;
- motivo formal de negativa (`doctor_reason`);
- observação curta da decisão (`doctor_observation`);
- confirmação/negação de agendamento;
- intercorrência pós-agendamento estruturada;
- supressão auditável de anexo;
- reenvio corrigido explícito.

## Notificações

Notificações ficam fora deste change.

Plano futuro recomendado:

```text
case-communication-mentions-notifications
```

Nesse change futuro:

- `UserNotification`;
- badge no header;
- tela “Minhas notificações”;
- polling periódico com Vanilla JS `fetch()` a cada 30–60s;
- sem HTMX inicialmente;
- sem websocket inicialmente.

Este MVP deve funcionar bem mesmo sem notificação: a thread é lida quando o usuário acessa o caso.

## Fora de escopo

- Chat global.
- Notificações in-app.
- Menções reais.
- Polling periódico.
- HTMX.
- WebSocket/SSE.
- Presença online.
- Marcação de lido/não lido.
- Mensagens sistêmicas espelhando eventos estruturados.
- Anexos em mensagens.
- Edição/deleção/supressão de mensagens.
- Alterar FSM.
- Alterar prior-case lookup.
- Alterar corrected-case linkage.
- Transformar `doctor_observation` em thread.
- Enviar SMS, push ou email operacional.

## Critérios de sucesso

- Mensagens são sempre vinculadas a um `Case`.
- Usuário NIR consegue postar mensagem contextual em caso operacional.
- Médico consegue ver/postar mensagem na tela de decisão do caso.
- Agendador consegue ver/postar mensagem na tela de confirmação/agendamento prevista.
- Mensagens aparecem em ordem cronológica.
- Mensagens mostram autor, papel ativo e data/hora.
- Mensagem vazia é rejeitada.
- Mensagem acima do limite é rejeitada.
- Usuário sem papel permitido não consegue postar.
- Cada post gera `CASE_COMMUNICATION_MESSAGE_POSTED`.
- Nenhum estado FSM é criado/alterado.
- Nenhuma notificação ativa/polling é implementada.
- Workflows estruturados existentes continuam fonte de verdade.
- Quality gate do AGENTS.md passa.
