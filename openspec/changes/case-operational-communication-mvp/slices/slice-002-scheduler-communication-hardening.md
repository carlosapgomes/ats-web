# Slice 002: Extensão para agendamento e hardening

## Contexto zero para implementador

O Slice 001 deste change deve ter criado:

- modelo `CaseCommunicationMessage`;
- serviço `post_case_communication_message` ou equivalente;
- endpoint SSR `/cases/<case_id>/communication/`;
- partial `templates/cases/_communication_thread.html`;
- UI de comunicação para NIR e médico;
- evento `CASE_COMMUNICATION_MESSAGE_POSTED`.

Este slice estende o MVP para o agendador e faz hardening de consistência, mantendo o escopo sem notificações/polling.

Fluxo alvo:

```text
NIR/médico deixam mensagem no caso
→ agendador abre tela de agendamento/intercorrência
→ vê a thread contextual
→ pode postar esclarecimento operacional
→ mensagem fica no mesmo Case
```

A comunicação continua não substituindo confirmação/negação de agendamento.

## Objetivo do slice

Entregar verticalmente:

```text
Agendador lê/posta mensagens no contexto de agendamento
+ labels/timeline consistentes
+ regressões garantindo que não foram introduzidas notificações/polling
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/scheduler/views.py`
2. `templates/scheduler/confirm.html`
3. `templates/scheduler/confirm_post_schedule_issue.html` se essa tela existir no fluxo ativo
4. `apps/intake/views.py` apenas se labels/dots ainda não foram adicionados no Slice 001
5. testes em `apps/scheduler/tests/...` ou equivalentes
6. `openspec/changes/case-operational-communication-mvp/tasks.md` ao concluir

Não criar nova migration neste slice, salvo correção justificada de bug do Slice 001.

## Requisitos funcionais

### R1. Scheduler vê thread na tela de agendamento

Em `apps/scheduler/views.py`, na view que renderiza `templates/scheduler/confirm.html`, adicionar contexto equivalente ao usado no NIR/médico:

```python
communication_messages = case.communication_messages.select_related("author").all()
can_post_communication = case.status != CaseStatus.CLEANED
communication_post_url = reverse("intake:post_case_communication", args=[case.case_id])
communication_next_url = request.get_full_path() + "#case-communication"
communication_max_length = CASE_COMMUNICATION_MAX_LENGTH
```

Em `templates/scheduler/confirm.html`, incluir:

```django
{% include "cases/_communication_thread.html" %}
```

Local sugerido: coluna esquerda abaixo do resumo do caso/decisão médica, ou abaixo do formulário, sem interferir no submit de agendamento.

### R2. Scheduler vê thread na resposta de intercorrência, se aplicável

Se o fluxo ativo de intercorrência pós-agendamento usa `templates/scheduler/confirm_post_schedule_issue.html`, adicionar a mesma partial nessa tela.

A comunicação deve coexistir com o formulário estruturado de resposta de intercorrência.

Não substituir campos estruturados:

- `response_action`;
- `response_message`;
- nova data/local/instruções;
- confirmação/negação formal.

### R3. Scheduler consegue postar mensagem

O endpoint do Slice 001 deve aceitar `author_role="scheduler"`.

Este slice deve garantir por teste que:

- agendador com `active_role="scheduler"` consegue postar em caso operacional de agendamento;
- a mensagem aparece para NIR/médico depois;
- mensagem vazia continua rejeitada;
- caso `CLEANED` continua bloqueado para post.

### R4. Labels de timeline

Se ainda não estiver feito no Slice 001, adicionar em `apps/intake/views.py`:

```python
EVENT_LABELS["CASE_COMMUNICATION_MESSAGE_POSTED"] = "Mensagem operacional registrada"
EVENT_DOT_CSS["CASE_COMMUNICATION_MESSAGE_POSTED"] = "system"
```

O objetivo é que a timeline NIR/médico não mostre o event_type cru.

Se já estiver feito, não duplicar.

### R5. Hardening: sem notificação/polling

Este change não deve introduzir:

- HTMX para mensagens;
- `setInterval`/polling;
- endpoint JSON de unread count;
- badge de notificações;
- `UserNotification`;
- WebSocket/SSE;
- marcação de lido/não lido.

Adicionar teste ou verificação simples quando viável. Exemplo aceitável:

- teste de template garantindo que não há atributos `hx-get`/`hx-trigger` na partial;
- grep/report evidenciando que nenhum arquivo JS novo de polling foi criado.

Não exagerar: o foco é manter YAGNI.

### R6. Regressão de workflows estruturados

A presença da comunicação não deve quebrar:

- submit de confirmação/negação de agendamento;
- submit de resposta de intercorrência;
- locks existentes de scheduler.

Adicionar ao menos um teste de regressão para o submit principal de scheduler, se já houver factories/helpers para isso. Se for muito caro, justificar no relatório e manter teste de renderização + post de mensagem.

## TDD obrigatório

Antes da implementação, criar testes falhando.

### Testes mínimos scheduler

1. `test_scheduler_confirm_shows_case_communication_thread`
   - mensagem existente aparece na tela de agendamento.

2. `test_scheduler_posts_case_communication_message`
   - POST como scheduler cria mensagem e redireciona com segurança.

3. `test_scheduler_message_is_visible_to_nir_or_doctor`
   - mensagem do scheduler aparece em tela NIR ou médica já integrada no Slice 001.

4. `test_scheduler_cannot_post_blank_communication_message`
   - mensagem vazia é rejeitada.

5. `test_scheduler_cannot_post_to_cleaned_case`
   - caso `CLEANED` não aceita post.

6. `test_scheduler_confirm_form_still_works_with_communication_thread`
   - regressão do formulário de agendamento, se viável.

### Testes mínimos de hardening

7. `test_case_communication_event_has_human_timeline_label`
   - timeline exibe “Mensagem operacional registrada”.

8. `test_communication_partial_does_not_use_htmx_polling`
   - partial não contém `hx-get`, `hx-trigger="every` ou equivalente.

9. `test_no_notification_badge_required_for_mvp`
   - se houver forma simples, garantir que o MVP não depende de `UserNotification`/badge. Caso não seja prático, registrar verificação manual no relatório.

### RED esperado

Antes da implementação, os testes devem falhar por ausência de contexto/partial no scheduler ou label.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- Reusar contexto/partial criado no Slice 001.
- Evitar lógica complexa em templates.
- Se houver repetição para montar contexto de comunicação, extrair helper pequeno em local apropriado e justificar.

### DRY

- Não duplicar HTML da thread no scheduler.
- Não criar segundo endpoint para scheduler.
- Não criar segundo serviço de post.

### YAGNI

Não implementar neste slice:

- notificações;
- polling;
- HTMX;
- WebSocket/SSE;
- read/unread;
- menções;
- mensagens sistêmicas;
- anexos em mensagens;
- tela global de conversas.

## Critérios de sucesso

- [ ] Agendador vê mensagens do caso na tela de agendamento.
- [ ] Agendador posta mensagem operacional.
- [ ] Mensagem do agendador aparece para NIR/médico.
- [ ] Formulário estruturado de agendamento/intercorrência continua funcionando.
- [ ] Evento `CASE_COMMUNICATION_MESSAGE_POSTED` tem label amigável na timeline.
- [ ] Partial compartilhado é reutilizado.
- [ ] Nenhum endpoint de notificação/unread é criado.
- [ ] Nenhum polling/HTMX/WebSocket/SSE é introduzido.
- [ ] Nenhum estado FSM é alterado.
- [ ] Testes novos passam.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Onde o scheduler vê a thread de comunicação?
2. Qual teste prova que o scheduler consegue postar?
3. Qual teste prova que a mensagem do scheduler aparece para outro papel?
4. Qual teste/regressão prova que o fluxo de agendamento não quebrou?
5. Foi criado algum endpoint de notificação, unread count ou polling? Se sim, está fora de escopo.
6. Foi introduzido HTMX/WebSocket/SSE? Se sim, está fora de escopo.
7. A partial foi reutilizada ou o HTML foi duplicado?
8. Algum estado FSM foi alterado? Se sim, está errado.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/case-operational-communication-mvp-slice-002-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois;
- resultados do quality gate;
- evidência de ausência de polling/notificações/HTMX;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/case-operational-communication-mvp-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/case-operational-communication-mvp/proposal.md, design.md, tasks.md and slices/slice-002-scheduler-communication-hardening.md.
Implement ONLY Slice 002. Assume Slice 001 is complete.
Use TDD: first add failing tests for scheduler visibility/posting and hardening, then implement minimal code.
Reuse the CaseCommunicationMessage model, post_case_communication_message service, /cases/<case_id>/communication/ endpoint, and templates/cases/_communication_thread.html partial from Slice 001. Add the communication context and partial to scheduler agendamento/intercorrência screens so scheduler can read/post messages on the same Case.
Ensure CASE_COMMUNICATION_MESSAGE_POSTED has a human timeline label if not already done. Do not duplicate the thread HTML or create another post endpoint/service.
Do not implement notifications, polling, HTMX, WebSocket/SSE, unread state, mentions, message attachments, global chat, or system notices. Do not alter FSM or structured scheduler workflows.
Apply clean code, DRY and YAGNI.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/case-operational-communication-mvp/tasks.md when complete.
Create /tmp/case-operational-communication-mvp-slice-002-report.md with RED/GREEN evidence, snippets, quality gate results, absence-of-polling evidence and self-evaluation answers.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
