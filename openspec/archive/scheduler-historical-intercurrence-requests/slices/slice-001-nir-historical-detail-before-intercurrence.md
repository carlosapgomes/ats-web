# Slice 001: NIR histórico — cards → detalhe → intercorrência

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR. Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/scheduler-historical-intercurrence-requests/proposal.md`
4. `openspec/changes/scheduler-historical-intercurrence-requests/design.md`
5. `openspec/changes/scheduler-historical-intercurrence-requests/tasks.md`
6. Este arquivo
7. Código atual em:
   - `apps/intake/views.py`
   - `apps/intake/urls.py`
   - `apps/intake/forms.py`
   - `apps/cases/services.py`
   - `apps/accounts/services.py`
   - `templates/intake/closed_cases_search.html`
   - `templates/intake/post_schedule_issue_form.html`
   - `templates/intake/case_detail.html`

Implemente **somente este slice** usando TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Entregar verticalmente o novo fluxo NIR para casos encerrados:

```text
NIR acessa busca de casos encerrados
→ pesquisa por ocorrência ou nome
→ vê cards com botão Detalhes
→ abre detalhe histórico read-only do caso
→ lê contexto/timeline/comunicação
→ se elegível, registra intercorrência dentro do detalhe
→ serviço existente move caso para WAIT_APPT
```

Também ajustar o redirect de notificação NIR para caso `CLEANED`:

```text
NIR abre notificação vinculada a caso CLEANED
→ vai para detalhe histórico do caso
```

## Escopo funcional

### R1. Busca NIR com cards e botão Detalhes

A view `closed_cases_search` já existe em `apps/intake/views.py`.

Ajustar a experiência para que cada resultado seja um card com ação principal:

```text
Detalhes
```

O botão deve apontar para uma nova rota histórica NIR, por exemplo:

```python
reverse("intake:closed_case_detail", args=[case.case_id])
```

Preferência do produto: não abrir intercorrência diretamente a partir do card. A intercorrência deve ocorrer dentro do detalhe.

### R2. Detalhe histórico NIR

Criar rota explícita, por exemplo:

```python
path("closed-cases/<uuid:case_id>/", views.closed_case_detail, name="closed_case_detail")
```

A view deve:

- exigir login e `@role_required("nir")`;
- buscar o caso por `case_id`;
- permitir caso `CLEANED` e, se necessário para feedback de intercorrência ativa, casos com `post_schedule_issue_status` em `opened`/`responded`;
- bloquear casos fora do escopo histórico NIR com 404;
- não adquirir lock;
- não alterar FSM em GET;
- renderizar contexto do caso, timeline e comunicação operacional.

Pode reutilizar `templates/intake/case_detail.html` com flags, ou criar `templates/intake/closed_case_detail.html` se isso for mais limpo. Evite duplicar blocos grandes de HTML.

### R3. PDF histórico NIR, se o detalhe embutir PDF

`intake:serve_pdf` bloqueia `CLEANED`. Se o detalhe histórico renderizar PDF, criar rota separada:

```python
path("closed-cases/<uuid:case_id>/pdf/", views.closed_case_pdf, name="closed_case_pdf")
```

Essa rota deve:

- exigir papel `nir`;
- permitir apenas escopo histórico NIR;
- servir o `pdf_file` se existir;
- retornar 404 quando não houver PDF.

Se a implementação decidir não embutir PDF no detalhe histórico, justificar no relatório. O detalhe ainda precisa mostrar dados/timeline/comunicação suficientes.

### R4. Intercorrência dentro do detalhe

No detalhe histórico, se `is_post_schedule_issue_eligible(case)` for verdadeiro:

- renderizar `PostScheduleIssueForm` ou formulário equivalente;
- POST deve chamar `open_post_schedule_issue` existente;
- não duplicar regra de elegibilidade na view;
- em sucesso, mostrar mensagem de sucesso e redirecionar de modo claro.

Opções aceitas:

1. formulário no detalhe postando para `intake:post_schedule_issue_open` existente; ou
2. `closed_case_detail` aceitar POST e chamar `open_post_schedule_issue`.

Documente a escolha no relatório.

Se inelegível, detalhe deve exibir `get_post_schedule_issue_ineligibility_reason(case)`.

### R5. Comunicação no detalhe histórico

Mostrar a thread de comunicação existente:

```python
communication_messages = case.communication_messages.select_related("author").all()
```

Neste slice, não é obrigatório permitir NIR postar mensagem em caso `CLEANED`. Se permitir, precisa haver autorização explícita e mudança segura no serviço. Preferência para manter read-only em `CLEANED` neste slice e focar na abertura de intercorrência.

### R6. Redirect de notificação NIR

Atualizar `apps/accounts/services.py::resolve_notification_redirect_url`:

- NIR + caso não `CLEANED` → `intake:case_detail` como hoje;
- NIR + caso `CLEANED` → nova rota `intake:closed_case_detail`.

Adicionar teste de regressão.

## Fora de escopo

Não implementar neste slice:

- detalhe contextual scheduler;
- busca histórica scheduler;
- mensagem CHD → NIR;
- alteração de `post_case_communication_message` para `allow_cleaned`;
- novo modelo/tabela;
- novo estado FSM;
- WebSocket/SSE/HTMX novo;
- busca avançada, paginação sofisticada ou exportação.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/intake/views.py`
2. `apps/intake/urls.py`
3. `templates/intake/closed_cases_search.html`
4. `templates/intake/closed_case_detail.html` ou `templates/intake/case_detail.html`
5. `apps/accounts/services.py`
6. testes em `apps/intake/tests/...` e `apps/accounts/tests/...`
7. `openspec/changes/scheduler-historical-intercurrence-requests/tasks.md` ao concluir

Se precisar tocar mais arquivos, justificar no relatório antes/depois.

## TDD obrigatório

Antes de implementar, crie testes falhando.

### Testes mínimos — busca e detalhe

1. `test_closed_cases_search_renders_cards_with_details_link`
   - busca encontra caso `CLEANED`;
   - resposta contém `Detalhes`;
   - link aponta para `closed_case_detail`;
   - não contém botão primário direto “Registrar intercorrência” no card.

2. `test_closed_case_detail_requires_nir_role`
   - usuário sem papel ativo `nir` não acessa.

3. `test_closed_case_detail_renders_cleaned_case_context`
   - NIR abre detalhe de caso `CLEANED`;
   - vê paciente/ocorrência/status;
   - vê timeline ou eventos principais;
   - vê thread de comunicação, se houver mensagem.

4. `test_closed_case_detail_blocks_non_historical_operational_case`
   - caso operacional comum não deve ser aberto pela rota histórica.

5. `test_closed_case_pdf_serves_cleaned_pdf_for_nir` se houver rota de PDF.

### Testes mínimos — intercorrência dentro do detalhe

6. `test_closed_case_detail_shows_post_schedule_issue_form_when_eligible`
   - caso elegível exibe formulário de intercorrência no detalhe.

7. `test_closed_case_detail_shows_ineligibility_reason_when_not_eligible`
   - caso não elegível exibe motivo claro.

8. `test_nir_opens_post_schedule_issue_from_detail`
   - POST válido via fluxo escolhido;
   - chama serviço real ou prova efeito equivalente;
   - caso vai para `WAIT_APPT`;
   - `post_schedule_issue_status == "opened"`;
   - evento `POST_SCHEDULE_ISSUE_OPENED` existe.

9. `test_second_active_issue_is_blocked_from_detail`
   - se já houver intercorrência ativa, detalhe não permite abrir outra.

### Testes mínimos — notificação NIR

10. `test_nir_notification_for_cleaned_case_redirects_to_closed_case_detail`
    - `resolve_notification_redirect_url` com `active_role="nir"` e `status=CLEANED` retorna `intake:closed_case_detail`.

### RED esperado

Antes da implementação, os testes devem falhar por ausência da rota `closed_case_detail`, ausência do link `Detalhes` ou redirect ainda indo para home.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- View orquestra request/response; regra de elegibilidade fica nos serviços existentes.
- Se montar contexto de detalhe duplicar muito `case_detail`, extraia helper pequeno e coeso.
- Use nomes explícitos: `closed_case_detail`, `closed_case_pdf`, `historical_scope`.

### DRY

- Reusar `is_post_schedule_issue_eligible`, `get_post_schedule_issue_ineligibility_reason` e `open_post_schedule_issue`.
- Reusar `PostScheduleIssueForm` se possível.
- Não duplicar labels/timeline se puder usar constantes existentes (`EVENT_LABELS`, `EVENT_DOT_CSS`).

### YAGNI

Não criar:

- nova entidade;
- filtros avançados;
- AJAX;
- polling;
- chat em tempo real;
- permissão genérica para todos os papéis verem histórico.

## Critérios de sucesso

- [ ] Busca de encerrados mostra cards com `Detalhes`.
- [ ] NIR abre detalhe histórico de caso `CLEANED`.
- [ ] Detalhe histórico é read-only para dados do caso e não adquire lock.
- [ ] Detalhe mostra timeline/comunicação.
- [ ] Detalhe mostra formulário de intercorrência apenas para caso elegível.
- [ ] Detalhe mostra motivo de inelegibilidade para caso não elegível.
- [ ] POST de intercorrência usa serviço existente e move caso para `WAIT_APPT`.
- [ ] Segunda intercorrência ativa fica bloqueada.
- [ ] Notificação NIR de caso `CLEANED` redireciona para detalhe histórico.
- [ ] Nenhum novo estado FSM é criado.
- [ ] Testes novos passam.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Onde está a nova rota de detalhe histórico NIR?
2. A busca ainda permite abrir intercorrência diretamente no card? Se sim, por quê?
3. Qual teste prova que o NIR lê detalhes antes de criar intercorrência?
4. Qual serviço é chamado para abrir intercorrência?
5. A view duplicou regra de elegibilidade ou delegou aos serviços?
6. O detalhe histórico adquire lock? Se sim, está errado.
7. Como a notificação NIR para caso `CLEANED` redireciona agora?
8. Algum estado FSM novo foi criado? Se sim, está errado.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/scheduler-historical-intercurrence-requests-slice-001-report.md
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
REPORT_PATH=/tmp/scheduler-historical-intercurrence-requests-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/scheduler-historical-intercurrence-requests/proposal.md, design.md, tasks.md and slices/slice-001-nir-historical-detail-before-intercurrence.md.
Implement ONLY Slice 001 using TDD: first add failing tests, then implement minimal code, then refactor safely.
Goal: NIR closed-case search must show cards with a Details button; NIR opens a historical read-only detail for CLEANED cases; inside that detail NIR can open a post-schedule intercurrence when eligible using the existing open_post_schedule_issue service. The detail must show timeline/context/communication and no lock. Also update notification redirect so NIR opening a notification for a CLEANED case goes to the historical detail, not home.
Keep it lean. Do not implement scheduler contextual detail, scheduler historical search, CHD→NIR messages, new models, new FSM states, WebSocket/SSE, advanced search or generic communication in CLEANED cases.
Apply clean code, DRY and YAGNI. Business rules belong in services, not duplicated in views/templates.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/scheduler-historical-intercurrence-requests/tasks.md for Slice 001 when complete.
Create /tmp/scheduler-historical-intercurrence-requests-slice-001-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push. Return REPORT_PATH=<path> and stop.
```
