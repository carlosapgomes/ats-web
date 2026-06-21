# Design: Mensagens sistêmicas de workflow na comunicação do caso

## Estado atual

O sistema já possui:

- `CaseEvent` append-only como trilha auditável;
- `CaseCommunicationMessage` para mensagens manuais por caso;
- notificações individuais (`UserNotification`) criadas por menções manuais;
- partial compartilhado `templates/cases/_communication_thread.html`;
- labels de timeline em `apps/intake/views.py`.

Atualmente `CaseCommunicationMessage` tem `author` obrigatório e representa apenas mensagens manuais. Mensagens com `@menção` criam notificações individuais. Isso deve continuar inalterado para mensagens manuais.

## Decisões

### D1. Mensagem sistêmica é contexto no caso, não notificação

Mensagem sistêmica automática aparece somente na thread do caso.

Ela não deve:

- criar `UserNotification`;
- aparecer no badge;
- aparecer em “Minhas notificações”;
- exigir leitura/resolução;
- acionar polling;
- mencionar usuários/papéis.

Motivo: eventos automáticos podem ser frequentes. Se todos gerassem inbox individual, notificações acumulariam sem representar chamada explícita para ação.

### D2. Fonte de verdade continua sendo `CaseEvent`

A mensagem sistêmica é uma projeção legível de um `CaseEvent` suportado.

```text
CaseEvent → CaseCommunicationMessage(message_type="system")
```

A fonte de verdade continua sendo o evento e os campos estruturados. A mensagem não substitui auditoria, FSM ou serviços.

### D3. Adaptar `CaseCommunicationMessage`

Adicionar campos:

```python
message_type = models.CharField(max_length=20, default="user")  # user | system
author = models.ForeignKey(..., null=True, blank=True, on_delete=models.PROTECT, ...)
author_role = models.CharField(max_length=30, blank=True)
source_event = models.OneToOneField(
    CaseEvent,
    null=True,
    blank=True,
    on_delete=models.CASCADE,
    related_name="communication_notice",
)
system_event_type = models.CharField(max_length=80, blank=True)
```

Notas:

- `author` precisa ficar nullable para mensagens do sistema.
- O serviço manual deve continuar exigindo `author` e `author_role` válidos.
- `source_event` com `OneToOneField` garante idempotência por evento.
- `system_event_type` facilita filtros/debug sem precisar seguir FK.

### D4. Serviço de projeção de eventos

Criar serviço em `apps/cases/services.py` ou módulo pequeno equivalente:

```python
SUPPORTED_SYSTEM_NOTICE_EVENT_TYPES = {...}


def build_system_notice_body(event: CaseEvent) -> str | None:
    ...


def create_system_communication_notice_for_event(event: CaseEvent) -> CaseCommunicationMessage | None:
    ...
```

Regras:

- retorna `None` para evento não suportado;
- retorna mensagem existente se `event.communication_notice` já existir;
- cria `CaseCommunicationMessage` com:
  - `case=event.case`;
  - `message_type="system"`;
  - `author=None`;
  - `author_role="system"` ou vazio;
  - `source_event=event`;
  - `system_event_type=event.event_type`;
  - `body` formatado.
- não chama `post_case_communication_message`;
- não cria `CaseEvent`;
- não cria `UserNotification`.

### D5. Signal em `CaseEvent`

Adicionar/estender signal em `apps/cases/signals.py`:

```python
@receiver(post_save, sender=CaseEvent)
def create_case_event_system_notice(...):
    if created:
        create_system_communication_notice_for_event(instance)
```

Motivos:

- evita espalhar chamadas manuais em vários serviços;
- qualquer workflow que crie `CaseEvent` suportado passa a projetar mensagem;
- reduz risco de esquecer integração em uma view.

Cuidados:

- signal deve ignorar `CASE_COMMUNICATION_MESSAGE_POSTED`;
- signal deve ser idempotente;
- signal não pode criar outro `CaseEvent` para evitar loops.

### D6. Formatação enxuta

Mensagens devem ser curtas, objetivas e seguras.

Exemplos:

```text
Anexo suprimido pelo NIR: exame-antigo.pdf — motivo: Enviado no caso errado.
Anexo complementar adicionado pelo NIR: laudo-cardio.pdf — observação: Complemento recebido da origem.
Reenvio corrigido criado pelo NIR para substituir/corrigir o caso anterior. Motivo: PDF incompleto.
Este caso foi corrigido por novo envio. Motivo: Anexo incorreto no envio anterior.
Intercorrência aberta pelo NIR — Transporte indisponível pela unidade de origem.
Intercorrência respondida pelo agendador — Reagendado para 22/06/2026 08:00.
Caso encerrado administrativamente — motivo: Duplicado/reapresentação manual.
```

Regras:

- preferir labels existentes quando houver;
- truncar textos longos para evitar blocos enormes na thread;
- não incluir PHI desnecessária além do que já está no caso;
- não inserir `@mentions` em mensagens sistêmicas.

### D7. Renderização distinta

Atualizar `templates/cases/_communication_thread.html`:

```django
{% if msg.message_type == "system" %}
  Sistema <span class="badge bg-info text-dark">SISTEMA</span>
{% else %}
  {{ msg.author.get_full_name|default:msg.author.username }} <span>{{ msg.author_role|upper }}</span>
{% endif %}
```

Sistema deve ter estilo visual neutro/informativo. Não precisa criar CSS complexo; Bootstrap existente basta.

### D8. Eventos por slice

#### Slice 001

Implementa infraestrutura e projeta eventos ligados a documentos/correção:

- `CASE_ATTACHMENT_SUPPRESSED`
- `CASE_ATTACHMENT_SUPPLEMENT_ADDED`
- `CASE_CORRECTION_CREATED`
- `CASE_MARKED_SUPERSEDED`

Motivo: são os eventos mais diretamente conectados à conversa operacional recente sobre anexos e reenvios.

#### Slice 002

Amplia a tabela de eventos suportados para fluxos estruturados operacionais:

- `POST_SCHEDULE_ISSUE_OPENED`
- `POST_SCHEDULE_ISSUE_RESPONDED`
- `POST_SCHEDULE_ISSUE_ACKNOWLEDGED`, se útil e já gerado
- `CASE_ADMINISTRATIVELY_CLOSED`

Inclui hardening para garantir que mensagens sistêmicas não geram notificações/badge.

### D9. Sem backfill

Não criar mensagens sistêmicas retroativas para eventos antigos neste change.

Motivos:

- evita migração de dados pesada;
- reduz risco de duplicidade visual;
- mantém slice enxuto.

Apenas eventos novos, criados após a implementação, geram mensagens sistêmicas.

### D10. Formatador de `POST_SCHEDULE_ISSUE_RESPONDED` e projeção pura do payload

O formatador `_format_post_schedule_issue_responded` consome apenas o payload
do evento (`{action, response_message}`) e **não consulta campos estruturados do `Case`**
(`appointment_at`, `appointment_location`, etc.), mesmo para `action=reschedule`.

Motivo: o formatador é uma projeção legível do `CaseEvent`. Consultar o `Case`
injetaria acoplamento de leitura na camada de formatação de evento, e a fonte de
verdade para a nova data/hora continua sendo `case.appointment_at` (campo
estrutural) e o próprio `CaseEvent`. Duplicar a nova data na mensagem sistêmica
aumentaria o risco de inconsistência entre thread e dados estruturados.

Trade-off aceito no MVP: a thread não mostra inline a nova data/hora do
reagendamento; ela permanece acessível nos campos estruturais do caso e na
timeline. Se houver demanda futura, enriquecer o payload do evento
`POST_SCHEDULE_ISSUE_RESPONDED` com a nova data mantém o formatador como
projeção pura do payload, sem acoplar leitura de modelo.

## Arquivos previstos

### Slice 001

| Arquivo | Mudança |
| --- | --- |
| `apps/cases/models.py` | campos de mensagem sistêmica em `CaseCommunicationMessage` |
| `apps/cases/migrations/*` | migration |
| `apps/cases/services.py` | serviço de projeção/formatação para eventos suportados |
| `apps/cases/signals.py` | receiver de `CaseEvent` |
| `templates/cases/_communication_thread.html` | render distinto de sistema vs usuário |
| testes | serviço/signal/UI/no-notification |

### Slice 002

| Arquivo | Mudança |
| --- | --- |
| `apps/cases/services.py` | ampliar eventos/formatadores |
| testes | integração com serviços de intercorrência/admin closure + hardening |
| `openspec/.../tasks.md` | atualizar status |

Se o implementador precisar tocar serviços específicos por falta de payload nos eventos, deve justificar no relatório e manter o mínimo necessário.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Inbox virar depósito de eventos | Mensagens sistêmicas não criam `UserNotification` |
| Duplicidade por signal/idempotência | `source_event` OneToOne e get-or-create |
| Perder fonte de verdade | Documentar que `CaseEvent`/campos estruturados continuam fonte oficial |
| Thread ficar ruidosa | Mapear apenas eventos operacionais selecionados |
| Loop de signals | Serviço não cria `CaseEvent`; ignora evento de comunicação |
| Quebrar mensagens manuais | Serviço manual continua exigindo author/role; testes de regressão |

## Futuro fora deste change

- Preferências para ocultar/filtrar mensagens sistêmicas.
- Backfill controlado de eventos históricos.
- Notificação opcional para alguns eventos sistêmicos críticos, com regra explícita.
- Resolução/claim de notificações por grupo.
- Timeline unificada mais rica.
