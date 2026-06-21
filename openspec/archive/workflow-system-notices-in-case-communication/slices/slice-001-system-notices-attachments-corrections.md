# Slice 001: Infraestrutura + avisos de anexos/correção

## Contexto zero para implementador

O ATS é um monolito Django SSR. O caso (`Case`) tem uma thread de comunicação operacional (`CaseCommunicationMessage`) e uma trilha auditável (`CaseEvent`). Mensagens manuais podem conter `@menções`, que geram `UserNotification` individual.

Este slice adiciona mensagens sistêmicas automáticas na thread do caso para eventos estruturados selecionados de anexos e reenvio corrigido.

Regra central:

```text
Mensagem sistêmica automática aparece somente no caso.
Ela NÃO gera notificação individual, badge, inbox ou estado de lida/resolvida.
```

Fluxo alvo:

```text
NIR suprime anexo ou adiciona anexo complementar
→ serviço já cria CaseEvent
→ signal projeta CaseEvent em mensagem sistêmica
→ thread do caso mostra “Sistema: Anexo suprimido...”
→ nenhum UserNotification é criado
```

## Objetivo do slice

Entregar verticalmente:

```text
CaseEvent de anexo/correção → CaseCommunicationMessage sistêmica → aparece na thread → sem notificação
```

Eventos deste slice:

- `CASE_ATTACHMENT_SUPPRESSED`
- `CASE_ATTACHMENT_SUPPLEMENT_ADDED`
- `CASE_CORRECTION_CREATED`
- `CASE_MARKED_SUPERSEDED`

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/cases/models.py`
2. `apps/cases/migrations/<nova_migration>.py`
3. `apps/cases/services.py`
4. `apps/cases/signals.py`
5. `templates/cases/_communication_thread.html`
6. testes em `apps/cases/tests/...` e/ou `apps/intake/tests/...`
7. `openspec/changes/workflow-system-notices-in-case-communication/tasks.md` ao concluir

Este slice toca mais de 5 arquivos porque é o menor fluxo vertical real: modelo + signal + serviço + UI + testes.

## Requisitos funcionais

### R1. Adaptar `CaseCommunicationMessage`

Adicionar campos:

```python
message_type = models.CharField(max_length=20, default="user")  # user | system
source_event = models.OneToOneField(
    CaseEvent,
    null=True,
    blank=True,
    on_delete=models.CASCADE,
    related_name="communication_notice",
)
system_event_type = models.CharField(max_length=80, blank=True)
```

Alterar campos existentes:

```python
author = models.ForeignKey(..., null=True, blank=True, on_delete=models.PROTECT, ...)
author_role = models.CharField(max_length=30, blank=True)
```

Criar migration.

Mensagens manuais existentes devem continuar válidas com `message_type="user"`.

### R2. Preservar serviço manual

`post_case_communication_message` deve continuar exigindo:

- `author` válido;
- `author_role` em papéis permitidos;
- body não vazio;
- limite de tamanho;
- criação de notificações para `@menções`.

Ele deve criar mensagens com:

```python
message_type="user"
source_event=None
system_event_type=""
```

### R3. Serviço de mensagem sistêmica

Adicionar serviço/helper em `apps/cases/services.py`, por exemplo:

```python
SUPPORTED_SYSTEM_NOTICE_EVENT_TYPES = {
    "CASE_ATTACHMENT_SUPPRESSED",
    "CASE_ATTACHMENT_SUPPLEMENT_ADDED",
    "CASE_CORRECTION_CREATED",
    "CASE_MARKED_SUPERSEDED",
}


def create_system_communication_notice_for_event(event: CaseEvent) -> CaseCommunicationMessage | None:
    ...
```

Regras:

- retornar `None` para evento não suportado;
- se já existir `event.communication_notice`, retornar a existente;
- criar `CaseCommunicationMessage` com `message_type="system"`;
- `author=None`;
- `author_role="system"` ou vazio;
- `source_event=event`;
- `system_event_type=event.event_type`;
- corpo formatado e curto;
- não chamar `post_case_communication_message`;
- não criar `CaseEvent`;
- não criar `UserNotification`.

### R4. Signal de `CaseEvent`

Em `apps/cases/signals.py`, adicionar receiver `post_save` para `CaseEvent`:

```python
@receiver(post_save, sender=CaseEvent)
def create_case_event_system_notice(...):
    if created:
        create_system_communication_notice_for_event(instance)
```

Cuidados:

- ignorar evento não suportado;
- ignorar `CASE_COMMUNICATION_MESSAGE_POSTED`;
- não gerar loop;
- idempotência garantida por `source_event`.

### R5. Formatação dos eventos do slice

Formatos sugeridos:

#### `CASE_ATTACHMENT_SUPPRESSED`

```text
Anexo suprimido pelo NIR: <filename> — motivo: <reason>.
```

Payloads podem variar; usar fallback seguro se filename/motivo não existirem.

#### `CASE_ATTACHMENT_SUPPLEMENT_ADDED`

```text
Anexo complementar adicionado pelo NIR: <filename> — observação: <note>.
```

#### `CASE_CORRECTION_CREATED`

```text
Reenvio corrigido criado pelo NIR para este caso. Motivo: <correction_reason>.
```

#### `CASE_MARKED_SUPERSEDED`

```text
Este caso foi corrigido por novo envio. Motivo: <correction_reason>.
```

Regras gerais:

- truncar textos longos;
- não inserir `@menções`;
- não incluir PDF/anexos embutidos;
- não duplicar payload inteiro.

### R6. Template da thread

Atualizar `templates/cases/_communication_thread.html` para renderizar mensagens sistêmicas com “Sistema”.

Exemplo:

```django
{% if msg.message_type == "system" %}
  <span class="fw-semibold small">Sistema <span class="badge bg-info text-dark ms-1">SISTEMA</span></span>
{% else %}
  {{ msg.author.get_full_name|default:msg.author.username }} <span class="badge bg-secondary ms-1">{{ msg.author_role|upper }}</span>
{% endif %}
```

Mensagem manual não deve quebrar.

## TDD obrigatório

Antes da implementação, criar testes falhando.

### Testes mínimos de modelo/serviço/signal

1. `test_case_communication_message_supports_system_message_without_author`
   - cria mensagem sistêmica com `author=None`.

2. `test_manual_communication_message_still_requires_author_via_service`
   - serviço manual continua validando author/role.

3. `test_supported_attachment_suppressed_event_creates_system_notice`
   - criar `CaseEvent` `CASE_ATTACHMENT_SUPPRESSED` gera `CaseCommunicationMessage` sistêmica.

4. `test_supported_supplemental_attachment_event_creates_system_notice`
   - idem para `CASE_ATTACHMENT_SUPPLEMENT_ADDED`.

5. `test_correction_created_event_creates_system_notice`
   - idem para `CASE_CORRECTION_CREATED`.

6. `test_marked_superseded_event_creates_system_notice`
   - idem para `CASE_MARKED_SUPERSEDED`.

7. `test_unsupported_event_does_not_create_system_notice`
   - `LLM1_OK` ou similar não gera mensagem.

8. `test_case_communication_posted_event_does_not_create_system_notice`
   - evita loop/ruído.

9. `test_system_notice_is_idempotent_per_case_event`
   - chamar serviço duas vezes para mesmo evento não duplica.

10. `test_system_notice_does_not_create_user_notification`
    - count de `UserNotification` permanece zero.

### Testes mínimos UI

11. `test_communication_thread_renders_system_notice_as_system`
    - detalhe do caso mostra “Sistema”/“SISTEMA” e corpo.

12. `test_communication_thread_still_renders_manual_message_author`
    - regressão de mensagem manual.

13. `test_manual_message_with_mention_still_creates_notification`
    - regressão do change anterior.

### RED esperado

Antes da implementação, os testes devem falhar por ausência de campos/serviço/signal/render.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- Serviço de projeção centralizado.
- Formatadores pequenos por event_type, se necessário.
- Signal fino, sem lógica de formatação pesada.
- Template com condicional simples.

### DRY

- Não espalhar criação de mensagens sistêmicas em cada view.
- Reusar um único serviço para todos os eventos suportados.
- Não duplicar formatação no template.

### YAGNI

Não implementar neste slice:

- eventos de intercorrência/admin closure;
- notificações para mensagens sistêmicas;
- read/resolved para mensagens sistêmicas;
- backfill;
- polling da thread;
- filtro para ocultar sistêmicas;
- edição/deleção de mensagens sistêmicas.

## Critérios de sucesso

- [ ] Modelo/migration suportam mensagens sistêmicas.
- [ ] Eventos do slice geram mensagens sistêmicas.
- [ ] Eventos não suportados não geram mensagens sistêmicas.
- [ ] `CASE_COMMUNICATION_MESSAGE_POSTED` não gera sistêmica.
- [ ] Uma mensagem sistêmica por `CaseEvent` no máximo.
- [ ] Thread mostra “Sistema”.
- [ ] Mensagens manuais continuam funcionando.
- [ ] Mensagens manuais com menção continuam notificando.
- [ ] Mensagens sistêmicas não criam `UserNotification`.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Onde está a regra que decide quais `CaseEvent` viram mensagem sistêmica?
2. Qual teste prova idempotência por evento?
3. Qual teste prova que mensagem sistêmica não cria `UserNotification`?
4. Qual teste prova que mensagem manual com `@menção` continua notificando?
5. Qual teste prova que `CASE_COMMUNICATION_MESSAGE_POSTED` não gera loop?
6. Foi implementado backfill ou notificação para sistêmica? Se sim, está fora de escopo.
7. Algum estado FSM foi alterado? Se sim, está errado.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/workflow-system-notices-in-case-communication-slice-001-report.md
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
REPORT_PATH=/tmp/workflow-system-notices-in-case-communication-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/workflow-system-notices-in-case-communication/proposal.md, design.md, tasks.md and slices/slice-001-system-notices-attachments-corrections.md.
Implement ONLY Slice 001.
Use TDD: first add failing tests for system communication notices from CaseEvent, then implement minimal code.
Adapt CaseCommunicationMessage to support message_type=user|system, nullable author for system messages, source_event idempotency and system_event_type. Add a central service to project selected CaseEvent types into system CaseCommunicationMessage records, and a CaseEvent post_save signal that calls it. Support only CASE_ATTACHMENT_SUPPRESSED, CASE_ATTACHMENT_SUPPLEMENT_ADDED, CASE_CORRECTION_CREATED and CASE_MARKED_SUPERSEDED in this slice. Update the communication thread partial to render system messages as “Sistema”.
Do not create UserNotification for system messages. Do not alter badge/inbox, FSM, polling, backfill, read/resolved state or notification behavior. Manual messages and @mention notifications must keep working.
Apply clean code, DRY and YAGNI. Keep signal thin and formatting in services/helpers.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/workflow-system-notices-in-case-communication/tasks.md for Slice 001 when complete.
Create /tmp/workflow-system-notices-in-case-communication-slice-001-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
