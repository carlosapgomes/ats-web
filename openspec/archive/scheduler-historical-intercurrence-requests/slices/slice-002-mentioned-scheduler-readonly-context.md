# Slice 002: CHD mencionado — detalhe read-only e resposta sem workflow

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR. Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/scheduler-historical-intercurrence-requests/proposal.md`
4. `openspec/changes/scheduler-historical-intercurrence-requests/design.md`
5. `openspec/changes/scheduler-historical-intercurrence-requests/tasks.md`
6. `openspec/changes/scheduler-historical-intercurrence-requests/slices/slice-001-nir-historical-detail-before-intercurrence.md`
7. Este arquivo
8. Código atual em:
   - `apps/accounts/services.py`
   - `apps/accounts/views.py`
   - `apps/accounts/models.py`
   - `apps/scheduler/views.py`
   - `apps/scheduler/urls.py`
   - `apps/cases/services.py`
   - `templates/cases/_communication_thread.html`
   - `templates/scheduler/confirm.html`
   - `templates/intake/case_detail.html`

Assuma que o Slice 001 está completo. Implemente **somente este slice** usando TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Permitir que CHD/agendador mencionado em um caso fora da fila de agendamento consiga abrir contexto e responder sem ganhar permissão de workflow:

```text
NIR/médico posta mensagem com @scheduler/@chd ou @username do agendador
→ UserNotification é criada
→ agendador abre notificação
→ redirect vai para detalhe read-only contextual do caso
→ agendador lê contexto/thread
→ se o caso não está CLEANED, pode responder na comunicação
→ nenhum botão/lock/ação de agendamento aparece
```

## Escopo funcional

### R1. Rota contextual scheduler por menção

Criar rota explícita, por exemplo:

```python
path("context/<uuid:case_id>/", views.scheduler_context_detail, name="context_detail")
```

A view deve:

- exigir login e `@role_required("scheduler")`;
- buscar caso por `case_id`;
- validar que existe `UserNotification` para `recipient=request.user` e `case=case`;
- retornar 404/403 quando não houver notificação para o usuário;
- não adquirir lock;
- não alterar FSM em GET;
- renderizar detalhe read-only.

Neste slice, a autorização por busca histórica scheduler ainda não existe. Só menção/notificação.

### R2. Redirect de notificação scheduler

Atualizar `apps/accounts/services.py::resolve_notification_redirect_url`:

- `active_role="scheduler"` e `case.status == WAIT_APPT` continua indo para `scheduler:confirm`;
- `active_role="scheduler"` e status diferente de `WAIT_APPT` deve ir para `scheduler:context_detail`.

A rota contextual deve validar a notificação; não confiar no redirect.

### R3. Detalhe read-only sem ações de workflow

O detalhe contextual deve mostrar contexto suficiente:

- paciente;
- ocorrência;
- status;
- decisão médica, se houver;
- dados de agendamento, se houver;
- timeline resumida ou eventos;
- thread de comunicação.

Não pode mostrar:

- botão confirmar agendamento;
- botão negar agendamento;
- formulário `SchedulerDecisionForm`;
- formulário `PostScheduleIssueForm` de resposta;
- lock token;
- botões de renovar/liberar lock;
- ações de intercorrência do NIR.

Pode reutilizar `templates/intake/case_detail.html` com flags ou criar `templates/scheduler/context_detail.html`. Se criar template novo, use partials/trechos compartilhados quando possível.

### R4. Resposta na comunicação quando não `CLEANED`

Se `case.status != CaseStatus.CLEANED`, a tela deve renderizar a partial de comunicação com:

```python
can_post_communication = True
communication_post_url = reverse("intake:post_case_communication", args=[case.case_id])
communication_next_url = request.get_full_path() + "#case-communication"
communication_max_length = CASE_COMMUNICATION_MAX_LENGTH
```

O endpoint existente `intake:post_case_communication` deve continuar sendo usado. Não criar endpoint novo para responder menção neste slice.

Se `case.status == CaseStatus.CLEANED`, neste slice a comunicação pode ficar read-only. A mensagem histórica em `CLEANED` será tratada no Slice 003 por endpoint específico CHD → NIR.

### R5. Notificação marcada como lida

O comportamento existente de `notification_open` marca a notificação como lida antes do redirect. Este slice não precisa alterar isso. Apenas garantir que o redirect final abre a tela contextual correta.

## Fora de escopo

Não implementar neste slice:

- busca histórica scheduler;
- mensagem CHD → NIR em caso `CLEANED`;
- `allow_cleaned=True` no serviço de comunicação;
- detalhe por UUID sem notificação;
- novo modelo/tabela;
- novo estado FSM;
- ações de agendamento/intercorrência;
- qualquer mudança no fluxo `WAIT_APPT` normal.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/scheduler/views.py`
2. `apps/scheduler/urls.py`
3. `templates/scheduler/context_detail.html` ou template/partial reutilizado
4. `apps/accounts/services.py`
5. testes em `apps/scheduler/tests/...` e `apps/accounts/tests/...`
6. `openspec/changes/scheduler-historical-intercurrence-requests/tasks.md` ao concluir

Se precisar tocar mais arquivos, justificar no relatório.

## TDD obrigatório

Antes de implementar, crie testes falhando.

### Testes mínimos — redirect

1. `test_scheduler_notification_for_wait_appt_still_redirects_to_confirm`
   - garante regressão: caso `WAIT_APPT` continua indo para `scheduler:confirm`.

2. `test_scheduler_notification_for_non_wait_appt_redirects_to_context_detail`
   - caso fora de `WAIT_APPT` retorna `scheduler:context_detail`.

### Testes mínimos — acesso contextual

3. `test_scheduler_context_detail_requires_scheduler_role`
   - usuário sem papel ativo `scheduler` não acessa.

4. `test_scheduler_context_detail_requires_notification_for_user`
   - scheduler sem notificação para o caso não acessa por UUID.

5. `test_scheduler_context_detail_allows_recipient_notification`
   - scheduler com `UserNotification` para o caso acessa.

6. `test_scheduler_context_detail_does_not_allow_other_scheduler_notification`
   - notificação de outro scheduler não autoriza o usuário atual.

### Testes mínimos — read-only e comunicação

7. `test_scheduler_context_detail_renders_readonly_case_context`
   - mostra paciente/ocorrência/status/thread.

8. `test_scheduler_context_detail_hides_workflow_actions`
   - resposta não contém botões/textos/rotas de confirmar/negar agendamento, lock token ou submit estruturado.

9. `test_scheduler_context_detail_allows_communication_reply_when_not_cleaned`
   - formulário de comunicação aparece quando caso não `CLEANED`.

10. `test_scheduler_context_detail_post_reply_creates_message`
    - POST via endpoint existente como scheduler cria `CaseCommunicationMessage` e retorna para `#case-communication`.

11. `test_scheduler_context_detail_cleaned_is_readonly_for_communication`
    - se caso `CLEANED`, não renderiza form de post neste slice.

### RED esperado

Antes da implementação, os testes devem falhar por ausência da rota `context_detail`, redirect ainda indo para fila e ausência de detalhe read-only.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- Coloque a autorização contextual em helper pequeno, por exemplo `_scheduler_has_context_notification(user, case)`.
- O helper não deve fazer render/redirect; apenas responder autorização.
- A view deve montar contexto e renderizar.

### DRY

- Reusar partial `templates/cases/_communication_thread.html`.
- Reusar `CASE_COMMUNICATION_MAX_LENGTH` e endpoint existente de post.
- Reusar labels/status/timeline existentes quando possível.

### YAGNI

Não antecipar:

- busca histórica;
- request model;
- fila de solicitações;
- mensagens em `CLEANED`;
- polling/AJAX;
- autocomplete de menção.

## Critérios de sucesso

- [ ] Scheduler mencionado abre notificação e cai no detalhe contextual.
- [ ] Scheduler sem notificação não acessa o detalhe contextual por UUID.
- [ ] Detail é read-only: sem lock e sem ações de agendamento/intercorrência.
- [ ] Scheduler consegue responder na comunicação quando caso não é `CLEANED`.
- [ ] Caso `CLEANED` fica sem form de comunicação neste slice.
- [ ] Redirect para `WAIT_APPT` continua indo para confirmação normal.
- [ ] Nenhum estado FSM é alterado.
- [ ] Testes novos passam.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Qual rota nova abre o detalhe contextual scheduler?
2. Como a rota valida que o scheduler foi mencionado/notificado?
3. Qual teste prova que outro scheduler não acessa por UUID?
4. Qual teste prova que o redirect de `WAIT_APPT` não quebrou?
5. Quais ações de workflow foram explicitamente escondidas?
6. O detalhe adquire lock? Se sim, está errado.
7. A resposta de comunicação reutiliza o endpoint/serviço existentes?
8. Algum suporte a caso `CLEANED` foi implementado aqui? Se sim, justificar; preferencialmente não.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/scheduler-historical-intercurrence-requests-slice-002-report.md
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
REPORT_PATH=/tmp/scheduler-historical-intercurrence-requests-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/scheduler-historical-intercurrence-requests/proposal.md, design.md, tasks.md, slices/slice-001-nir-historical-detail-before-intercurrence.md and slices/slice-002-mentioned-scheduler-readonly-context.md.
Implement ONLY Slice 002 using TDD: first add failing tests, then implement minimal code, then refactor safely.
Goal: when a scheduler/CHD user opens a notification for a case outside WAIT_APPT, redirect to a scheduler read-only contextual detail if and only if that user has a UserNotification for the case. The detail must show case context and the communication thread, allow reply through the existing communication endpoint when the case is not CLEANED, and show no workflow actions, no lock, no scheduling form and no intercurrence response form. WAIT_APPT notifications must still redirect to scheduler:confirm.
Do not implement scheduler historical search, CHD→NIR messages in CLEANED cases, allow_cleaned communication, new models, new FSM states or workflow actions.
Apply clean code, DRY and YAGNI.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/scheduler-historical-intercurrence-requests/tasks.md for Slice 002 when complete.
Create /tmp/scheduler-historical-intercurrence-requests-slice-002-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push. Return REPORT_PATH=<path> and stop.
```
