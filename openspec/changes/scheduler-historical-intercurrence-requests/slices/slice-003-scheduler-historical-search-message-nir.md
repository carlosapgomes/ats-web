# Slice 003: CHD histórico — busca e mensagem operacional ao NIR

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR. Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/scheduler-historical-intercurrence-requests/proposal.md`
4. `openspec/changes/scheduler-historical-intercurrence-requests/design.md`
5. `openspec/changes/scheduler-historical-intercurrence-requests/tasks.md`
6. `openspec/changes/scheduler-historical-intercurrence-requests/slices/slice-001-nir-historical-detail-before-intercurrence.md`
7. `openspec/changes/scheduler-historical-intercurrence-requests/slices/slice-002-mentioned-scheduler-readonly-context.md`
8. Este arquivo
9. Código atual em:
   - `apps/scheduler/views.py`
   - `apps/scheduler/urls.py`
   - `apps/cases/services.py`
   - `apps/accounts/services.py`
   - `apps/accounts/models.py`
   - `templates/scheduler/queue.html`
   - `templates/scheduler/_queue_content.html`
   - `templates/cases/_communication_thread.html`

Assuma que Slices 001 e 002 estão completos. Implemente **somente este slice** usando TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Permitir que o CHD/agendador localize caso histórico agendado/processado e avise o NIR dentro do sistema:

```text
CHD acessa busca histórica
→ pesquisa por ocorrência ou nome
→ vê cards históricos com Detalhes
→ abre detalhe read-only do caso
→ envia mensagem operacional ao NIR, podendo mencionar também médico/usuário/grupo adicional
→ sistema garante @nir e preserva menções adicionais
→ UserNotification é criada para NIR e para demais destinatários mencionados pelo parser existente
→ NIR abre notificação no detalhe histórico (Slice 001)
→ NIR decide se abre intercorrência no detalhe
```

A mensagem do CHD não reabre o caso, não muda FSM e não substitui a intercorrência.

## Escopo funcional

### R1. Busca histórica scheduler

Criar rota, por exemplo:

```python
path("historical/", views.scheduler_historical_search, name="historical_search")
```

A view deve:

- exigir login e `@role_required("scheduler")`;
- aceitar query `q`;
- pesquisar por:
  - `agency_record_number__icontains=q`;
  - `structured_data__patient__name__icontains=q`;
- limitar a casos em escopo histórico do agendador;
- renderizar cards com botão `Detalhes`.

Escopo histórico inicial:

```text
doctor_decision == "accept"
doctor_admission_flow == "scheduled"
appointment_status in {"confirmed", "denied", "cancelled"}
```

Incluir `CLEANED` e casos finais/pós-agendamento que ainda tenham `appointment_status` preenchido. Não limitar a processados hoje.

Não filtrar por `scheduler=request.user`, salvo se descobrir restrição de segurança já documentada no projeto. A intenção do produto é busca institucional para o papel `scheduler`.

### R2. Link de navegação

Adicionar entrada discreta na UI do agendador, por exemplo:

```text
Histórico / Buscar histórico
```

Pode ser link em `templates/scheduler/queue.html` ou em bloco de ações. Não reintroduzir a antiga aba “Histórico” removida por `scheduler-processed-today-tab`; prefira link separado para busca histórica.

### R3. Detalhe histórico scheduler

Reusar a rota contextual criada no Slice 002 (`scheduler:context_detail`) ou criar rota histórica explícita se ficar mais simples.

Neste slice, ampliar a autorização do detalhe para permitir acesso quando o caso está no escopo histórico scheduler, mesmo sem notificação prévia.

O detalhe deve continuar read-only:

- sem lock;
- sem `SchedulerDecisionForm`;
- sem resposta estruturada de intercorrência;
- sem botões de confirmar/negar agendamento;
- sem ações NIR.

### R4. Mensagem operacional CHD → NIR

Criar endpoint scheduler específico, por exemplo:

```python
path("historical/<uuid:case_id>/message-nir/", views.scheduler_historical_message_nir, name="historical_message_nir")
```

Regras:

- exige `@role_required("scheduler")`;
- aceita apenas POST;
- valida que o caso está no escopo histórico scheduler;
- body obrigatório, `strip()` e limite `CASE_COMMUNICATION_MAX_LENGTH`;
- garante menção a `@nir` para gerar notificação;
- permite e preserva menções adicionais (`@medico`/`@doctor`, `@username`, `@supervisor` etc.) para que o parser existente notifique também esses destinatários;
- cria `CaseCommunicationMessage` via serviço central;
- redireciona de volta para o detalhe `#case-communication`;
- não altera `Case.status`.

Implementação sugerida para garantir menção sem remover destinatários adicionais:

```python
body = form_body.strip()
parsed = parse_mentions(body)
if "nir" not in parsed.role_tokens:
    body = f"@nir {body}"
```

Use preferencialmente `parse_mentions` existente em `apps.accounts.services` para evitar falso positivo e para preservar o comportamento canônico de aliases. Não sanitize/remova outras menções: se o agendador escreveu `@medico`, `@doctor`, `@supervisor` ou `@username`, essas menções devem continuar no corpo salvo e gerar notificações pelo mecanismo existente. Se importar `parse_mentions` gerar acoplamento indesejado, documentar escolha no relatório e manter testes de preservação de menções adicionais.

### R5. Permissão explícita para postar em `CLEANED`

`post_case_communication_message` bloqueia `CLEANED`. Alterar com parâmetro opt-in:

```python
def post_case_communication_message(..., allow_cleaned: bool = False) -> CaseCommunicationMessage:
    if case.status == CaseStatus.CLEANED and not allow_cleaned:
        raise CaseCommunicationError(...)
```

Regras:

- default deve ser `False` para preservar segurança/regressão;
- endpoint genérico `intake:post_case_communication` não deve passar `allow_cleaned=True`;
- somente `scheduler_historical_message_nir`, após validar escopo histórico, chama com `allow_cleaned=True`;
- testes devem provar que chamada sem opt-in continua bloqueada.

### R6. Notificação NIR

A mensagem deve gerar `UserNotification` para usuários ativos com papel `nir`, usando mecanismo existente de menções. Menções adicionais digitadas pelo agendador também devem ser processadas pelo mesmo mecanismo.

Testar que:

- `CaseCommunicationMessage.body` contém menção a NIR ou notificação é criada;
- menções adicionais digitadas pelo agendador são preservadas no corpo salvo;
- destinatários adicionais válidos recebem `UserNotification` conforme parser existente;
- autor scheduler não recebe notificação indevida;
- NIR ativo recebe notificação;
- se houver múltiplos NIR ativos, o comportamento segue o parser/serviço existente.

### R7. NIR abre a notificação

Não reimplementar o detalhe NIR. O Slice 001 já deve ter ajustado `resolve_notification_redirect_url` para NIR + `CLEANED` → `intake:closed_case_detail`.

Adicionar teste integrado simples se viável:

```text
scheduler envia mensagem histórica → notificação NIR criada → resolve_notification_redirect_url para NIR aponta para closed_case_detail
```

## Fora de escopo

Não implementar neste slice:

- novo modelo/tabela de solicitação CHD;
- status pendente/resolvido da solicitação;
- fila NIR específica de solicitações CHD;
- CHD reabrindo caso direto para `WAIT_APPT`;
- NIR auto-convertendo mensagem em intercorrência sem ação humana;
- busca avançada/paginação/export;
- WebSocket/SSE/push/SMS/email operacional;
- liberação global de mensagens em `CLEANED` para todos os endpoints.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/scheduler/views.py`
2. `apps/scheduler/urls.py`
3. `templates/scheduler/historical_search.html`
4. `templates/scheduler/context_detail.html` ou template usado no Slice 002
5. `templates/scheduler/queue.html` ou partial de navegação
6. `apps/cases/services.py`
7. testes em `apps/scheduler/tests/...`, `apps/cases/tests/...`, talvez `apps/accounts/tests/...`
8. `openspec/changes/scheduler-historical-intercurrence-requests/tasks.md` ao concluir

Se precisar tocar mais arquivos, justificar no relatório.

## TDD obrigatório

Antes de implementar, crie testes falhando.

### Testes mínimos — busca histórica

1. `test_scheduler_historical_search_requires_scheduler_role`
   - usuário sem papel scheduler não acessa.

2. `test_scheduler_historical_search_by_agency_record_number`
   - encontra caso histórico aceito/agendado por ocorrência.

3. `test_scheduler_historical_search_by_patient_name`
   - encontra caso histórico aceito/agendado por nome do paciente.

4. `test_scheduler_historical_search_excludes_non_scheduled_acceptance`
   - exclui vinda imediata, negado médico ou sem agendamento processado.

5. `test_scheduler_historical_search_not_limited_to_today_or_current_scheduler`
   - caso antigo e/ou processado por outro scheduler aparece se estiver no escopo.

6. `test_scheduler_historical_cards_have_details_link`
   - cards apontam para detalhe read-only.

### Testes mínimos — detalhe histórico

7. `test_scheduler_context_detail_allows_historical_case_without_notification`
   - caso histórico em escopo abre sem notificação prévia.

8. `test_scheduler_context_detail_blocks_non_historical_case_without_notification`
   - caso fora do escopo e sem notificação não abre.

9. `test_scheduler_historical_detail_hides_workflow_actions`
   - sem lock, sem formulário de agendamento/intercorrência.

### Testes mínimos — mensagem ao NIR

10. `test_scheduler_historical_message_requires_post`
    - GET não executa ação.

11. `test_scheduler_historical_message_requires_historical_scope`
    - não posta em caso fora do escopo.

12. `test_scheduler_historical_message_requires_body`
    - body vazio não cria mensagem.

13. `test_scheduler_historical_message_creates_case_communication_message`
    - mensagem é criada na thread do caso.

14. `test_scheduler_historical_message_adds_nir_mention_when_missing`
    - body salvo contém `@nir` ou notificação NIR é criada mesmo sem o usuário digitar menção.

15. `test_scheduler_historical_message_preserves_additional_mentions`
    - se o agendador envia `@medico`/`@doctor` ou `@username` junto da mensagem, a menção permanece no corpo salvo.

16. `test_scheduler_historical_message_creates_nir_notification`
    - NIR ativo recebe `UserNotification`.

17. `test_scheduler_historical_message_notifies_additional_mentioned_recipient`
    - médico/usuário/grupo adicional mencionado recebe `UserNotification` conforme parser existente.

18. `test_scheduler_historical_message_does_not_change_case_status`
    - caso `CLEANED` permanece `CLEANED` após mensagem.

19. `test_post_case_communication_cleaned_still_blocked_by_default`
    - chamada padrão do serviço em `CLEANED` continua levantando `CaseCommunicationError`.

20. `test_post_case_communication_cleaned_allowed_only_with_explicit_opt_in`
    - chamada com `allow_cleaned=True` funciona para o endpoint validado.

### Teste integrado NIR

21. `test_scheduler_message_notification_redirects_nir_to_closed_detail`
    - após mensagem histórica, redirect NIR para notificação aponta para `intake:closed_case_detail`.

### RED esperado

Antes da implementação, os testes devem falhar por ausência de busca histórica, rota de mensagem, autorização histórica e `allow_cleaned`.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- Criar helper de escopo, por exemplo `_is_scheduler_historical_case(case)` ou queryset builder `_scheduler_historical_queryset()`.
- Evitar regras espalhadas: busca, detalhe e endpoint de mensagem devem usar o mesmo escopo.
- View de mensagem deve ser pequena: validar escopo, normalizar body, chamar serviço, redirecionar.

### DRY

- Reusar `post_case_communication_message` com `allow_cleaned=True` em vez de criar mensagem manualmente.
- Reusar parser de menções se possível para detectar `@nir` sem falso positivo.
- Não remover/sanitizar menções adicionais; reutilizar o parser/serviço existente para notificá-las.
- Reusar template/partial de comunicação.

### YAGNI

Não criar:

- tabela de solicitação;
- status de solicitação;
- painel NIR novo;
- filtros avançados;
- JS novo;
- polling;
- exportação;
- permissões genéricas para outros papéis.

## Critérios de sucesso

- [ ] Scheduler acessa busca histórica.
- [ ] Busca encontra caso histórico por ocorrência.
- [ ] Busca encontra caso histórico por nome do paciente.
- [ ] Busca não é limitada a “processados hoje”.
- [ ] Busca lista cards com `Detalhes`.
- [ ] Scheduler abre detalhe histórico read-only sem notificação prévia quando caso está no escopo.
- [ ] Scheduler não abre caso fora do escopo por UUID.
- [ ] Detail histórico não mostra ações de workflow nem adquire lock.
- [ ] Scheduler envia mensagem operacional ao NIR.
- [ ] Mensagem em caso `CLEANED` só é permitida pelo endpoint histórico validado.
- [ ] Mensagem garante notificação para NIR.
- [ ] Mensagem preserva menções adicionais e notifica destinatários adicionais válidos pelo parser existente.
- [ ] Mensagem não altera status do caso.
- [ ] NIR consegue abrir notificação no detalhe histórico entregue pelo Slice 001.
- [ ] Nenhum novo estado FSM/modelo de solicitação é criado.
- [ ] Testes novos passam.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Qual é o critério exato de “caso histórico scheduler” e onde ele está centralizado?
2. A busca histórica está limitada ao scheduler logado? Se sim, justificar contra o objetivo de CHD institucional.
3. Qual teste prova que a busca não se limita a processados hoje?
4. Qual teste prova que caso fora do escopo não abre por UUID?
5. Como o endpoint garante que NIR será notificado?
6. Como a implementação preserva menções adicionais e qual teste prova que destinatários adicionais são notificados?
7. `post_case_communication_message` continua bloqueando `CLEANED` por padrão?
8. Qual teste prova que a mensagem não altera `Case.status`?
9. Foi criado algum modelo/tabela/status novo de solicitação? Se sim, está fora de escopo.
10. Foi criada alguma ação para CHD reabrir caso diretamente? Se sim, está errado.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/scheduler-historical-intercurrence-requests-slice-003-report.md
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
REPORT_PATH=/tmp/scheduler-historical-intercurrence-requests-slice-003-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/scheduler-historical-intercurrence-requests/proposal.md, design.md, tasks.md and slices/slice-001/002/003.
Implement ONLY Slice 003 using TDD: first add failing tests, then implement minimal code, then refactor safely.
Goal: add scheduler historical search for accepted scheduled cases already processed/agendados, searchable by agency_record_number or patient name, not limited to today. Cards link to a read-only detail. Extend the scheduler contextual detail from Slice 002 so historical cases in scope can be opened without a notification. Add a scheduler-only POST endpoint to send an operational message to NIR from the historical detail. The endpoint must validate historical scope, require body, guarantee @nir mention/notification, preserve additional mentions typed by the scheduler and notify those valid recipients through the existing parser, call post_case_communication_message with an explicit allow_cleaned=True opt-in, and not alter Case.status.
Preserve default behavior: post_case_communication_message must still block CLEANED unless allow_cleaned=True. The generic intake communication endpoint must not pass allow_cleaned=True.
Do not create a CHD request model/table/status, do not let CHD reopen cases directly, do not add FSM states, advanced filters, WebSocket/SSE, polling, SMS/push/email operational or generic historical access for all roles.
Apply clean code, DRY and YAGNI.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/scheduler-historical-intercurrence-requests/tasks.md for Slice 003 when complete.
Create /tmp/scheduler-historical-intercurrence-requests-slice-003-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push. Return REPORT_PATH=<path> and stop.
```
