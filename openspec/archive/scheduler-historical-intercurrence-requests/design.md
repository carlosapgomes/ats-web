# Design: Acesso contextual CHD, busca histórica e detalhe antes da intercorrência

## Estado atual

O sistema já possui:

- `Case` com FSM preservada e campos de intercorrência pós-agendamento (`post_schedule_issue_*`);
- serviço `open_post_schedule_issue(case, user, reason, message)` que move caso elegível de `CLEANED` para `WAIT_APPT`;
- busca NIR de casos encerrados em `apps/intake/views.py::closed_cases_search`;
- formulário NIR de abertura de intercorrência em `post_schedule_issue_open`;
- `CaseCommunicationMessage` append-only por caso;
- endpoint POST único de comunicação `/cases/<case_id>/communication/`;
- menções `@nir`/`@doctor`/`@scheduler`/`@chd` etc. gerando `UserNotification`;
- inbox “Minhas notificações” e `resolve_notification_redirect_url`;
- detalhe read-only de processados hoje do scheduler (`scheduler_processed_detail`) que já reutiliza `templates/intake/case_detail.html`.

Limitações atuais relevantes:

- `intake:case_detail` bloqueia `CLEANED`.
- `intake:serve_pdf` bloqueia `CLEANED`.
- `resolve_notification_redirect_url(active_role="nir")` envia NIR com caso `CLEANED` para home.
- `resolve_notification_redirect_url(active_role="scheduler")` envia scheduler fora de `WAIT_APPT` para fila.
- `post_case_communication_message` bloqueia mensagens em caso `CLEANED`.

## Decisões

### D1. Criar detalhe histórico NIR separado da rota operacional

Não relaxar `intake:case_detail`. Ela continua sendo rota operacional para casos não `CLEANED`.

Criar rota histórica explícita, por exemplo:

```python
path("closed-cases/<uuid:case_id>/", views.closed_case_detail, name="closed_case_detail")
path("closed-cases/<uuid:case_id>/pdf/", views.closed_case_pdf, name="closed_case_pdf")
```

Essa rota:

- exige `@role_required("nir")`;
- aceita somente casos `CLEANED` ou casos com intercorrência ativa/respondida, conforme busca atual já considera;
- é read-only para dados do caso;
- não adquire lock;
- monta timeline, resultado, attachments visíveis quando seguro e thread de comunicação;
- exibe ação de intercorrência dentro do detalhe quando `is_post_schedule_issue_eligible(case)` for verdadeiro.

### D2. Busca NIR lista cards com botão `Detalhes`

`closed_cases_search` deve continuar pesquisando por:

- `agency_record_number__icontains=query`;
- `structured_data__patient__name__icontains=query`.

Mas a ação principal do card será `Detalhes` apontando para `closed_case_detail`.

O botão direto “Registrar intercorrência” deve ser removido da listagem ou tornado secundário apenas se não prejudicar a decisão D1. Preferência: abrir intercorrência somente a partir do detalhe.

### D3. Intercorrência dentro do detalhe NIR

O detalhe histórico NIR pode renderizar o `PostScheduleIssueForm` dentro da página quando elegível.

Opções aceitáveis para implementação enxuta:

1. manter `post_schedule_issue_open` como endpoint POST e renderizar o formulário no detalhe apontando para ele; ou
2. aceitar POST diretamente em `closed_case_detail` e delegar para `open_post_schedule_issue`.

Critério: a regra de negócio deve continuar no serviço `open_post_schedule_issue`; views não duplicam elegibilidade crítica.

Após sucesso, redirecionar para:

- `intake:closed_case_detail` do mesmo caso, se ainda fizer sentido para feedback; ou
- `intake:closed_cases_search`, se esse for o padrão existente.

A implementação deve documentar a escolha no relatório.

### D4. Redirect de notificação NIR para detalhe histórico

Atualizar `resolve_notification_redirect_url`:

```python
if active_role == "nir":
    if status != CaseStatus.CLEANED:
        return reverse("intake:case_detail", kwargs={"case_id": case.pk})
    return reverse("intake:closed_case_detail", kwargs={"case_id": case.pk})
```

Assim NIR marcado em mensagem de caso encerrado consegue abrir o detalhe, ler a mensagem e criar intercorrência se couber.

### D5. Detalhe contextual scheduler por menção

Criar rota scheduler read-only contextual, por exemplo:

```python
path("context/<uuid:case_id>/", views.scheduler_context_detail, name="context_detail")
```

Acesso permitido quando pelo menos uma das condições for verdadeira:

1. o scheduler logado recebeu `UserNotification` vinculada ao caso; ou
2. o caso é elegível para detalhe histórico do scheduler (D7); ou
3. o caso foi processado pelo próprio scheduler (pode continuar pela rota já existente `processed_detail`).

No Slice 002, implementar apenas a condição 1. No Slice 003, ampliar para condição 2.

A tela deve:

- usar read-only; sem lock;
- não mostrar botões de agendamento/intercorrência;
- mostrar contexto suficiente do caso;
- mostrar thread de comunicação;
- permitir post na comunicação quando `case.status != CLEANED`;
- para `CLEANED`, só permitir mensagem ao NIR pelo endpoint histórico do Slice 003.

### D6. Redirect de notificação scheduler para detalhe contextual

Atualizar `resolve_notification_redirect_url`:

```python
if active_role == "scheduler":
    if status == CaseStatus.WAIT_APPT:
        return reverse("scheduler:confirm", kwargs={"case_id": case.pk})
    return reverse("scheduler:context_detail", kwargs={"case_id": case.pk})
```

A rota `context_detail` deve validar que existe notificação para o usuário/caso. Não confiar apenas no redirect.

### D7. Busca histórica scheduler

Criar rota, por exemplo:

```python
path("historical/", views.scheduler_historical_search, name="historical_search")
```

Escopo inicial de casos pesquisáveis:

- casos com `doctor_decision="accept"`;
- `doctor_admission_flow="scheduled"`;
- `appointment_status` em `confirmed`, `denied` ou `cancelled` conforme campos atuais;
- incluir `CLEANED` e casos em etapa final pós-agendamento (`WAIT_R1_CLEANUP_THUMBS`) se já processados;
- busca por ocorrência ou nome do paciente.

Não filtrar por `scheduler=request.user`; o objetivo é CHD/agenda institucional conseguir localizar histórico operacional do serviço. Se isso for sensível demais na implementação, o relatório deve justificar uma restrição temporária, mas a intenção do produto é busca institucional para o papel `scheduler`.

### D8. Mensagem operacional CHD → NIR em caso histórico

Criar endpoint scheduler específico, por exemplo:

```python
path("historical/<uuid:case_id>/message-nir/", views.scheduler_historical_message_nir, name="historical_message_nir")
```

Regras:

- exige `@role_required("scheduler")`;
- valida que o caso é pesquisável no histórico scheduler;
- body obrigatório, strip e limite de `CASE_COMMUNICATION_MAX_LENGTH`;
- garante menção a `@nir` para criar `UserNotification`;
- preserva menções adicionais digitadas pelo agendador e deixa o parser existente notificar os demais destinatários (`@medico`/`@doctor`, `@username`, `@supervisor` etc.);
- chama serviço central de comunicação com permissão explícita para `CLEANED`.

Para evitar duplicar lógica de comunicação, alterar o serviço para aceitar parâmetro explícito e seguro:

```python
def post_case_communication_message(..., allow_cleaned: bool = False) -> CaseCommunicationMessage:
    if case.status == CaseStatus.CLEANED and not allow_cleaned:
        raise CaseCommunicationError(...)
```

O valor padrão permanece `False`, preservando comportamento existente. Apenas o endpoint histórico scheduler chama com `allow_cleaned=True` depois de validar acesso contextual.

### D9. Não criar request/ticket model neste MVP

Não adicionar campos no `Case` nem nova tabela para solicitação CHD.

A cadeia rastreável fica:

```text
CHD posta CaseCommunicationMessage com @nir e, opcionalmente, outras menções
→ UserNotification para NIR e para demais destinatários mencionados
→ NIR abre detalhe histórico pela notificação
→ NIR registra intercorrência pelo serviço existente
→ POST_SCHEDULE_ISSUE_OPENED + mensagem sistêmica
→ caso entra em WAIT_APPT para scheduler responder
```

Se depois houver necessidade de fila estruturada de solicitações CHD pendentes, ela será outro change.

### D10. Autorização explícita para detalhes read-only

Não usar “conheço o UUID” como autorização suficiente.

Cada rota nova precisa validar uma condição clara:

- NIR closed detail: papel `nir` e caso em escopo histórico NIR (`CLEANED` ou intercorrência ativa/respondida vinda da busca).
- Scheduler context detail: papel `scheduler` e notificação existente para usuário/caso, ou elegibilidade histórica do scheduler.
- Scheduler historical detail: papel `scheduler` e caso em escopo histórico scheduler.
- Scheduler historical message: mesmas condições do detalhe histórico.

### D11. Templates e reutilização

Preferir reutilizar `templates/intake/case_detail.html` quando viável, passando flags/contexto para esconder ações indevidas.

Se a parametrização do template ficar confusa, criar partials pequenos ou template específico read-only. Evitar duplicar blocos grandes de HTML.

Campos de contexto a padronizar quando possível:

```python
communication_messages = case.communication_messages.select_related("author").all()
can_post_communication = ...
communication_post_url = ...
communication_next_url = request.get_full_path() + "#case-communication"
communication_max_length = CASE_COMMUNICATION_MAX_LENGTH
```

## Slices planejados

### Slice 001 — NIR histórico: cards → detalhe → intercorrência

Entrega o fluxo NIR primeiro porque ele é o destino das notificações CHD e corrige a decisão do item 3.

Arquivos prováveis:

| Arquivo | Mudança |
| --- | --- |
| `apps/intake/views.py` | `closed_case_detail`, `closed_case_pdf`, busca com cards/detalhes, form de intercorrência no detalhe |
| `apps/intake/urls.py` | novas rotas históricas |
| `templates/intake/closed_cases_search.html` | cards com botão Detalhes |
| `templates/intake/closed_case_detail.html` ou `case_detail.html` parametrizado | detalhe histórico + form de intercorrência |
| `apps/accounts/services.py` | redirect NIR `CLEANED` para detalhe histórico |
| testes intake/accounts | cobertura do fluxo |

### Slice 002 — CHD mencionado: detalhe read-only e resposta sem workflow

Arquivos prováveis:

| Arquivo | Mudança |
| --- | --- |
| `apps/scheduler/views.py` | `scheduler_context_detail` com acesso por `UserNotification` |
| `apps/scheduler/urls.py` | rota contextual |
| `templates/scheduler/context_detail.html` ou reutilização de detail read-only | UI sem ações de workflow |
| `apps/accounts/services.py` | redirect scheduler fora de `WAIT_APPT` para contexto |
| testes scheduler/accounts | cobertura de acesso, redirect e ausência de ações |

### Slice 003 — CHD histórico: busca e mensagem operacional ao NIR

Arquivos prováveis:

| Arquivo | Mudança |
| --- | --- |
| `apps/scheduler/views.py` | busca histórica, detalhe por elegibilidade histórica, endpoint message-nir |
| `apps/scheduler/urls.py` | rotas históricas |
| `templates/scheduler/historical_search.html` | cards históricos |
| `templates/scheduler/context_detail.html` | formulário/CTA de mensagem ao NIR em histórico |
| `apps/cases/services.py` | `allow_cleaned` explícito em `post_case_communication_message` |
| testes scheduler/cases/accounts | busca, mensagem, notificação, sem mudança FSM |

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Acesso por UUID a caso histórico | Condições explícitas por rota; testes de 404/403 |
| CHD alterar workflow fora da fila | Detalhes read-only; sem lock; sem botões de submit estruturado |
| Mensagem em `CLEANED` virar chat ilimitado | `allow_cleaned=False` por padrão; somente endpoint histórico scheduler com validação |
| NIR abrir intercorrência sem ler contexto | Botão vai para detalhe; form fica dentro do detalhe |
| Notificação de CHD não chegar ao NIR | Endpoint histórico garante menção `@nir`; testes validam `UserNotification` |
| Menções adicionais serem perdidas | Endpoint preserva o corpo do agendador e apenas prefixa/adiciona `@nir` quando ausente; parser existente continua responsável pelas demais menções |
| Duplicação de template grande | Preferir partials/flags; justificar se criar template próprio |
| Novo modelo desnecessário | Não criar request/ticket model neste MVP |
| Quebrar rotas operacionais existentes | Não relaxar `case_detail`; adicionar rotas históricas separadas |

## Futuro fora deste change

- Fila estruturada de solicitações CHD pendentes com status próprio.
- Atribuição/claim de solicitações CHD por NIR.
- Filtros avançados na busca histórica.
- Auditoria/report específico de mensagens CHD → NIR.
- Preferências de notificação por grupo.
