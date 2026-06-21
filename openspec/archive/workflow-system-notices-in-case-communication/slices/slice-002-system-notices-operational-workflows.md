# Slice 002: Avisos de intercorrência/encerramento + hardening

## Contexto zero para implementador

O Slice 001 deste change deve ter criado infraestrutura para mensagens sistêmicas:

- `CaseCommunicationMessage.message_type` (`user`/`system`);
- `source_event` idempotente;
- serviço `create_system_communication_notice_for_event` ou equivalente;
- signal `post_save` de `CaseEvent`;
- renderização “Sistema” na thread;
- suporte inicial para eventos de anexos/correção.

Este slice amplia a projeção para workflows estruturados operacionais e reforça que mensagens sistêmicas aparecem **somente no caso**, sem notificação individual.

Fluxo alvo:

```text
NIR abre intercorrência / scheduler responde / admin encerra caso
→ serviço existente cria CaseEvent
→ signal cria mensagem sistêmica na thread
→ nenhum UserNotification é criado
→ badge do usuário não muda por causa da sistêmica
```

## Objetivo do slice

Entregar verticalmente:

```text
Eventos de intercorrência/encerramento → mensagens sistêmicas legíveis → sem notificação/badge → workflows existentes intactos
```

Eventos deste slice:

- `POST_SCHEDULE_ISSUE_OPENED`
- `POST_SCHEDULE_ISSUE_RESPONDED`
- `CASE_ADMINISTRATIVELY_CLOSED`
- `POST_SCHEDULE_ISSUE_ACKNOWLEDGED`, incluir se for útil e já tiver payload suficiente; caso contrário justificar omissão no relatório.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/cases/services.py`
2. testes em `apps/cases/tests/...`, `apps/intake/tests/...`, `apps/scheduler/tests/...` ou equivalentes
3. `openspec/changes/workflow-system-notices-in-case-communication/tasks.md` ao concluir

Possível tocar `templates/cases/_communication_thread.html` apenas se o Slice 001 deixou algum ajuste pendente. Não criar migration neste slice, salvo correção justificada de bug do Slice 001.

## Requisitos funcionais

### R1. Ampliar eventos suportados

Adicionar ao conjunto de eventos projetados:

```python
POST_SCHEDULE_ISSUE_OPENED
POST_SCHEDULE_ISSUE_RESPONDED
CASE_ADMINISTRATIVELY_CLOSED
```

Avaliar `POST_SCHEDULE_ISSUE_ACKNOWLEDGED`:

- incluir se o evento já for gerado e útil na thread;
- se a mensagem ficar ruidosa ou sem payload, omitir e justificar no relatório.

### R2. Formatação de intercorrência aberta

Para `POST_SCHEDULE_ISSUE_OPENED`, mensagem sugerida:

```text
Intercorrência pós-agendamento aberta pelo NIR — <motivo amigável>. Mensagem: <mensagem>, se houver.
```

Usar label amigável do motivo quando disponível, por exemplo via `get_post_schedule_issue_reason_label`.

### R3. Formatação de intercorrência respondida

Para `POST_SCHEDULE_ISSUE_RESPONDED`, mensagem sugerida:

```text
Intercorrência respondida pelo agendador — <ação amigável>. <detalhes relevantes>.
```

Ações sugeridas:

```text
cancel → Cancelado
reschedule → Reagendado
maintain → Mantido
 deny → Solicitação negada
```

Incluir detalhes disponíveis sem exagero:

- nova data/hora, se reagendado;
- mensagem de resposta, se houver;
- status de agendamento, se relevante.

### R4. Formatação de encerramento administrativo

Para `CASE_ADMINISTRATIVELY_CLOSED`, mensagem sugerida:

```text
Caso encerrado administrativamente — motivo: <motivo>. Status anterior: <status>, se disponível.
```

Usar labels já existentes quando possível.

### R5. Não criar notificação/badge

Para todos os eventos deste slice:

- não criar `UserNotification`;
- não incrementar badge;
- não aparecer em “Minhas notificações”;
- não interpretar `@` no corpo da mensagem sistêmica.

Se o texto da mensagem sistêmica contiver `@` por algum motivo, isso não deve acionar parser de menções porque o serviço manual não deve ser chamado.

### R6. Workflows estruturados intactos

Os serviços existentes devem continuar alterando os campos estruturados e eventos como antes:

- `open_post_schedule_issue`;
- `respond_post_schedule_issue`;
- confirmação/ack da intercorrência, se aplicável;
- `administratively_close_case`.

A mensagem sistêmica é uma projeção adicional, não uma mudança de regra de negócio.

### R7. Sem backfill

Não criar mensagens sistêmicas para eventos antigos existentes antes da implementação.

Testes devem focar eventos criados após o código novo.

## TDD obrigatório

Antes da implementação, criar testes falhando.

### Testes mínimos de integração com workflows

1. `test_post_schedule_issue_opened_creates_system_notice`
   - chamar `open_post_schedule_issue`;
   - verificar mensagem sistêmica na thread/case.

2. `test_post_schedule_issue_opened_notice_uses_reason_label_and_message`
   - payload/mensagem contém motivo amigável e mensagem NIR quando houver.

3. `test_post_schedule_issue_responded_creates_system_notice`
   - chamar `respond_post_schedule_issue`;
   - verificar mensagem sistêmica.

4. `test_post_schedule_issue_responded_notice_includes_action_details`
   - reschedule/cancel/maintain/deny mostra ação amigável e detalhes relevantes.

5. `test_administrative_closure_creates_system_notice`
   - chamar `administratively_close_case`;
   - verificar mensagem sistêmica.

6. `test_administrative_closure_notice_includes_reason`
   - motivo/status anterior aparecem, quando disponíveis.

7. `test_post_schedule_issue_acknowledged_notice_behavior_is_documented`
   - se incluído: testar criação;
   - se omitido: testar que não cria e registrar justificativa no relatório.

### Testes mínimos de hardening

8. `test_operational_system_notices_do_not_create_user_notifications`
   - criar eventos do slice e verificar count de `UserNotification` inalterado.

9. `test_operational_system_notices_do_not_change_unread_badge_count`
   - contagem de não lidas permanece igual.

10. `test_system_notice_with_at_symbol_does_not_trigger_mention_notifications`
    - usar payload/mensagem com `@nir` e garantir zero notificações.

11. `test_system_notice_source_event_idempotency_for_operational_events`
    - chamar serviço duas vezes para mesmo evento não duplica.

12. `test_manual_mentions_still_create_notifications_after_system_notice_changes`
    - regressão: mensagem manual com `@nir` ainda cria notificação.

13. `test_workflow_structured_fields_are_unchanged_by_system_notice`
    - campos de intercorrência/admin closure continuam corretos.

### RED esperado

Antes da implementação, os testes devem falhar porque eventos operacionais ainda não geram mensagens sistêmicas.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- Apenas ampliar formatadores/mapeamento central do Slice 001.
- Não colocar lógica de mensagem em views.
- Não duplicar código de criação de `CaseCommunicationMessage`.
- Formatadores pequenos, fáceis de testar.

### DRY

- Reusar `create_system_communication_notice_for_event`.
- Reusar helpers/labels existentes para motivos de intercorrência.
- Reusar truncamento/preview do Slice 001, se houver.

### YAGNI

Não implementar neste slice:

- novas migrations;
- notificações para sistêmicas;
- marcação como resolvida;
- inbox de sistêmicas;
- polling da thread;
- backfill;
- filtros de thread;
- edição/deleção de mensagens sistêmicas;
- novos workflows.

## Critérios de sucesso

- [ ] `POST_SCHEDULE_ISSUE_OPENED` gera mensagem sistêmica legível.
- [ ] `POST_SCHEDULE_ISSUE_RESPONDED` gera mensagem sistêmica legível.
- [ ] `CASE_ADMINISTRATIVELY_CLOSED` gera mensagem sistêmica legível.
- [ ] `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` é implementado ou omitido com justificativa clara.
- [ ] Eventos operacionais não geram `UserNotification`.
- [ ] Badge de notificações não muda por mensagens sistêmicas.
- [ ] Mensagens sistêmicas com `@` não disparam menções.
- [ ] Serviços estruturados continuam atualizando campos/eventos corretamente.
- [ ] Idempotência por `source_event` mantida.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Quais eventos operacionais foram adicionados ao mapeamento?
2. `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` foi incluído ou omitido? Por quê?
3. Qual teste prova que intercorrência aberta cria mensagem sistêmica?
4. Qual teste prova que encerramento administrativo cria mensagem sistêmica?
5. Qual teste prova que sistêmicas não criam `UserNotification`?
6. Qual teste prova que badge/unread count não muda?
7. Qual teste prova que uma sistêmica contendo `@` não aciona menções?
8. Algum workflow estruturado mudou de comportamento? Se sim, justificar; idealmente não.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/workflow-system-notices-in-case-communication-slice-002-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois;
- resultados do quality gate;
- evidência de ausência de notificações/badge para sistêmicas;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/workflow-system-notices-in-case-communication-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/workflow-system-notices-in-case-communication/proposal.md, design.md, tasks.md and slices/slice-002-system-notices-operational-workflows.md.
Implement ONLY Slice 002. Assume Slice 001 is complete.
Use TDD: first add failing tests for system notices from post-schedule intercurrence and administrative closure events, then implement minimal code.
Extend the central system notice mapping/formatters to support POST_SCHEDULE_ISSUE_OPENED, POST_SCHEDULE_ISSUE_RESPONDED and CASE_ADMINISTRATIVELY_CLOSED. Decide whether POST_SCHEDULE_ISSUE_ACKNOWLEDGED should be included; either implement it with tests or explicitly justify omission in the report.
Do not create UserNotification, badge changes, inbox entries, polling, read/resolved state, backfill, new FSM states or new workflows for system messages. System notices appear only in the case communication thread. Manual @mention notifications must keep working.
Apply clean code, DRY and YAGNI. Reuse the service/signal infrastructure from Slice 001.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/workflow-system-notices-in-case-communication/tasks.md when complete.
Create /tmp/workflow-system-notices-in-case-communication-slice-002-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
