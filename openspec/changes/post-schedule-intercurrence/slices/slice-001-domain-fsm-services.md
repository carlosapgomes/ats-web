# Slice 001: Modelo, FSM e serviços de domínio

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. Este slice inicia o change `post-schedule-intercurrence`. Ele deve preparar a base de domínio para que slices futuros criem telas NIR/agendador.

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/post-schedule-intercurrence/proposal.md`
4. `openspec/changes/post-schedule-intercurrence/design.md`
5. `openspec/changes/post-schedule-intercurrence/tasks.md`
6. Este arquivo
7. `apps/cases/models.py`
8. `apps/cases/services.py`, se existir
9. `apps/cases/tests/test_fsm.py`

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Adicionar suporte de domínio, sem UI, para abrir/responder/confirmar uma intercorrência pós-agendamento em caso elegível.

Fluxo mínimo testável neste slice:

```text
Case CLEANED com agendamento confirmado
→ serviço abre intercorrência
→ status volta para WAIT_APPT e issue fica opened
→ serviço responde intercorrência
→ status vai para WAIT_R1_CLEANUP_THUMBS e issue fica responded
→ serviço confirma ciência
→ status volta para CLEANED e issue é limpo/encerrado
```

## Escopo funcional

- Adicionar campos mínimos em `Case` para intercorrência ativa/latest conforme `design.md`.
- Criar migration.
- Adicionar transição FSM explícita de abertura: `CLEANED → WAIT_APPT`.
- Adicionar transição ou serviço para resposta do agendador que reutilize estados existentes e leve a `WAIT_R1_CLEANUP_THUMBS`.
- Adicionar serviço/helper transacional em `apps/cases/services.py` ou módulo coeso existente para:
  - checar elegibilidade;
  - retornar motivo de inelegibilidade;
  - abrir intercorrência;
  - responder intercorrência;
  - confirmar ciência/encerrar metadados.
- Registrar eventos:
  - `POST_SCHEDULE_ISSUE_OPENED`;
  - `POST_SCHEDULE_ISSUE_RESPONDED`;
  - `POST_SCHEDULE_ISSUE_ACKNOWLEDGED`.
- Impedir duas intercorrências ativas simultâneas, preferencialmente com `transaction.atomic()` + `select_for_update()`.

## Regras de negócio obrigatórias

Elegível para abertura somente se:

```text
status == CLEANED
doctor_decision == "accept"
doctor_admission_flow == "scheduled"
appointment_status == "confirmed"
post_schedule_issue_status vazio/none
```

Motivos NIR oficiais:

```text
death
clinical_condition
transport_unavailable
external_regulation
reschedule_request
other
```

Mensagem NIR:

- opcional para `death` e `external_regulation`;
- obrigatória para `clinical_condition`, `transport_unavailable`, `reschedule_request`, `other`.

Ações do agendador:

```text
cancel
reschedule
maintain
deny
```

Atualização de agendamento:

- `cancel`: `appointment_status="cancelled"`; registrar snapshot anterior no evento.
- `reschedule`: `appointment_status="confirmed"`; atualizar data/local/instruções.
- `maintain`: preservar `appointment_status="confirmed"` e data/local.
- `deny`: preservar `appointment_status="confirmed"` e data/local; a negativa é da solicitação, não do agendamento original.

## Fora de escopo

- Criar páginas/templates/rotas NIR ou agendador.
- Alterar dashboards.
- Criar tabela separada de histórico.
- Criar novos estados FSM.
- Implementar busca por nome/ocorrência.
- Alterar locks existentes, salvo se um teste mostrar quebra direta.

## Arquivos prováveis

1. `apps/cases/models.py`
2. `apps/cases/services.py`
3. `apps/cases/migrations/00xx_*.py`
4. `apps/cases/tests/test_fsm.py` ou novo `apps/cases/tests/test_post_schedule_issue_services.py`
5. `openspec/changes/post-schedule-intercurrence/tasks.md` ao final

## Plano TDD obrigatório

### RED

Criar testes de domínio antes da implementação:

1. Caso elegível `CLEANED` abre intercorrência e vai para `WAIT_APPT`.
2. Abertura registra `POST_SCHEDULE_ISSUE_OPENED` com motivo, mensagem e snapshot do agendamento.
3. Caso negado pelo médico não é elegível.
4. Caso sem agendamento confirmado não é elegível.
5. Motivo `death` permite mensagem vazia.
6. Motivo `clinical_condition` exige mensagem.
7. Segunda abertura com issue `opened` ou `responded` falha.
8. Resposta `reschedule` atualiza data/local/instruções e vai para `WAIT_R1_CLEANUP_THUMBS`.
9. Resposta `cancel` marca `appointment_status="cancelled"` e vai para `WAIT_R1_CLEANUP_THUMBS`.
10. Resposta `deny` preserva agendamento confirmado e vai para `WAIT_R1_CLEANUP_THUMBS`.
11. Ciência NIR limpa issue ativa e retorna para `CLEANED`.
12. Múltiplos ciclos sequenciais são possíveis após ciência.

### GREEN

Implementar o mínimo para passar. Prefira helpers pequenos e explícitos. Evite classes complexas.

### REFACTOR

- Remover duplicação de snapshots de agendamento com helper pequeno.
- Nomes claros para constantes/motivos/ações.
- Não generalizar para workflow genérico.

## Critérios de aceitação

- [ ] Todos os testes de domínio passam.
- [ ] Migration criada e aplicada nos testes.
- [ ] Nenhum novo estado FSM foi criado.
- [ ] Eventos são registrados via `CaseEvent`.
- [ ] Abertura é transacional e impede duplicidade ativa.
- [ ] Regras de mensagem condicional foram implementadas.
- [ ] Campos principais de agendamento seguem as regras do design.

## Gates de autoavaliação

Responder no relatório:

1. Quais campos foram adicionados ao `Case` e por quê?
2. Como o código impede duas intercorrências ativas?
3. `deny` preserva o agendamento confirmado? Mostre teste/snippet.
4. `cancel` não cria novo fluxo? Mostre teste/snippet.
5. Como múltiplos ciclos ficam preservados se os campos do `Case` são limpos/reusados?

## Comandos de validação mínimos

```bash
uv run pytest apps/cases/tests -q
uv run ruff check apps/cases
uv run ruff format --check apps/cases
uv run mypy apps/cases
```

Quality gate completo, se possível:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-001-post-schedule-domain-report.md
```

Incluir resumo, arquivos tocados, snippets antes/depois, testes RED/GREEN, validações, riscos, atualização de `tasks.md`, commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-001-post-schedule-domain-report.md
```

Pare e peça confirmação antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/post-schedule-intercurrence through Slice 001. Implement ONLY Slice 001 using TDD. Add domain support for post-schedule intercurrence: Case fields, migration, FSM transition CLEANED→WAIT_APPT, transactional services to open/respond/acknowledge, eligibility rules, conditional NIR message validation, scheduler actions cancel/reschedule/maintain/deny, and CaseEvent audit events. Do not create UI or new FSM states. Keep code simple, DRY and YAGNI. Run validations, update tasks.md, create /tmp/ats-web-slice-001-post-schedule-domain-report.md, commit and push, reply REPORT_PATH and stop.
```
