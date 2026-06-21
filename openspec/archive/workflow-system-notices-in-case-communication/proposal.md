# Proposal: Mensagens sistêmicas de workflow na comunicação do caso

**Change ID**: `workflow-system-notices-in-case-communication`  
**Prioridade**: média/baixa  
**Risco**: PROFISSIONAL (altera representação da thread de comunicação e integra eventos estruturados existentes)  
**Dependências**: `case-operational-communication-mvp`, `case-communication-mentions-notifications`

## Problema

A comunicação operacional por caso já permite mensagens manuais e menções/notificações. Porém, alguns eventos estruturados importantes ficam apenas na timeline/auditoria ou em blocos específicos da tela. Isso dificulta ler a história operacional do caso em uma única thread contextual.

Exemplos de eventos que deveriam aparecer como contexto legível na comunicação do caso:

- anexo suprimido pelo NIR;
- anexo complementar adicionado;
- caso corrigido criado;
- caso anterior marcado como corrigido por novo envio;
- intercorrência pós-agendamento aberta;
- intercorrência respondida pelo agendador;
- encerramento administrativo.

Hoje, para entender a conversa, o usuário precisa correlacionar manualmente mensagens, timeline e blocos estruturados.

## Objetivo

Criar mensagens sistêmicas automáticas na thread de comunicação do caso para eventos estruturados selecionados.

Exemplo:

```text
Sistema · 19/06/2026 10:42
Anexo complementar adicionado pelo NIR: laudo-cardio.pdf — motivo: Complementação recebida da origem.
```

Essas mensagens são apenas apresentação/contexto. A fonte de verdade continua sendo:

- campos estruturados;
- serviços de domínio;
- transições FSM;
- `CaseEvent` append-only.

## Regra central de ciclo de vida

Mensagens sistêmicas automáticas **aparecem somente no caso**.

Elas **não criam notificações individuais**, **não entram no badge**, **não ficam na página “Minhas notificações”** e **não precisam ser lidas/resolvidas**.

Separação planejada:

```text
Evento estruturado automático
→ mensagem sistêmica no caso
→ sem UserNotification
→ sem badge

Mensagem manual com @menção
→ mensagem no caso
→ UserNotification individual
→ badge/notificações do usuário
```

## Escopo

### Modelo

Adaptar `CaseCommunicationMessage` para suportar mensagens sistêmicas:

```python
message_type = CharField(default="user")  # user | system
author = ForeignKey(User, null=True, blank=True, ...)
author_role = CharField(max_length=30, blank=True)
source_event = OneToOneField(CaseEvent, null=True, blank=True, related_name="communication_notice")
system_event_type = CharField(max_length=80, blank=True)
```

Regras:

- mensagens manuais continuam `message_type="user"` com `author` obrigatório pelo serviço manual;
- mensagens sistêmicas usam `message_type="system"`, `author=None`, `author_role="system"` ou vazio;
- cada `CaseEvent` suportado gera no máximo uma mensagem sistêmica;
- mensagens sistêmicas são append-only no MVP.

### Serviço

Criar serviço/helper em `apps/cases/services.py` ou módulo coeso equivalente:

```python
def create_system_communication_notice_for_event(event: CaseEvent) -> CaseCommunicationMessage | None:
    ...
```

Responsabilidades:

- verificar se `event.event_type` é suportado;
- formatar texto curto e seguro a partir do payload/campos estruturados;
- criar `CaseCommunicationMessage(message_type="system")`;
- ser idempotente por `source_event`;
- não chamar serviço de notificação;
- não criar `CaseEvent` adicional.

### Gatilho

Preferência: signal `post_save` de `CaseEvent`, para evitar espalhar chamadas manuais por vários serviços.

Fluxo:

```text
serviço estruturado cria CaseEvent
→ signal de CaseEvent detecta evento suportado
→ cria mensagem sistêmica na thread do caso
```

Isso evita tocar todos os workflows individualmente.

### UI

Atualizar `templates/cases/_communication_thread.html` para renderizar mensagens sistêmicas de forma distinta:

```text
Sistema
badge: SISTEMA
estilo leve/neutro
```

Mensagens manuais devem continuar mostrando autor, papel, data e corpo como hoje.

### Eventos suportados

#### Slice 001 — artefatos clínicos e reenvio corrigido

- `CASE_ATTACHMENT_SUPPRESSED`
- `CASE_ATTACHMENT_SUPPLEMENT_ADDED`
- `CASE_CORRECTION_CREATED`
- `CASE_MARKED_SUPERSEDED`

#### Slice 002 — fluxos operacionais estruturados

- `POST_SCHEDULE_ISSUE_OPENED`
- `POST_SCHEDULE_ISSUE_RESPONDED`
- `POST_SCHEDULE_ISSUE_ACKNOWLEDGED`, se já existir como evento operacional relevante
- `CASE_ADMINISTRATIVELY_CLOSED`

Não duplicar todos os eventos do sistema. Apenas eventos que ajudam a compreender exceções operacionais na thread.

## Fora de escopo

- Criar notificações para mensagens sistêmicas.
- Marcar mensagens sistêmicas como lidas/resolvidas.
- Criar inbox de mensagens sistêmicas.
- Enviar SMS/push/email.
- Usar menções dentro de mensagens sistêmicas.
- Criar polling da thread.
- Criar WebSocket/SSE.
- Alterar FSM.
- Substituir `CaseEvent` por mensagens.
- Backfill de eventos históricos já existentes.
- Mensagens sistêmicas para todos os eventos de pipeline/LLM.
- Edição/deleção/supressão de mensagens sistêmicas.

## Critérios de sucesso

- Eventos estruturados selecionados criam mensagens sistêmicas na thread do caso.
- Cada `CaseEvent` suportado gera no máximo uma mensagem sistêmica.
- Mensagens sistêmicas são visualmente distintas de mensagens manuais.
- Mensagens sistêmicas não criam `UserNotification`.
- Mensagens sistêmicas não alteram badge de notificações.
- Mensagens manuais com menções continuam criando notificações como antes.
- Workflows estruturados continuam fonte de verdade.
- Nenhum estado FSM é alterado.
- Quality gate do AGENTS.md passa.
