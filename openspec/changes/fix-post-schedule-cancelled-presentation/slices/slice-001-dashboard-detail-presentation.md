# Slice 001: Corrigir apresentação de agendamento cancelado após intercorrência

## Handoff — contexto zero para implementador LLM

Você está no projeto `/projects/dev/ats-web`, um monolito Django SSR para triagem de EDA. Leia antes de implementar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/fix-post-schedule-cancelled-presentation/proposal.md`
4. `openspec/changes/fix-post-schedule-cancelled-presentation/design.md`
5. `openspec/changes/fix-post-schedule-cancelled-presentation/tasks.md`
6. este slice

O sistema usa `Case.status` com `django-fsm`. `CLEANED` é terminal operacional. O fluxo de intercorrência pós-agendamento pode cancelar um agendamento já confirmado. Nessa situação, o caso termina `CLEANED` com `appointment_status="cancelled"`.

Bug atual: o dashboard gerencial não trata `cancelled` explicitamente. O card pode mostrar “Aguardando Agendamento” e o detalhe pode mostrar “Agendamento Confirmado”. Isso é incorreto. Se o scheduler respondeu intercorrência com `cancel`, deve aparecer como cancelado após intercorrência. Se respondeu com `reschedule`/`maintain` e o status atual continua `confirmed`, deve continuar aparecendo como confirmado.

## Objetivo vertical

Entregar de ponta a ponta:

```text
Caso CLEANED + doctor_decision=accept + doctor_admission_flow=scheduled + appointment_status=cancelled
→ card do dashboard mostra cancelamento após intercorrência
→ detalhe do dashboard mostra resultado final de cancelamento
→ caso confirmed continua confirmado
```

## Escopo enxuto

Arquivos esperados:

1. `apps/dashboard/tests/test_dashboard.py`
2. `apps/dashboard/views.py`
3. `templates/intake/case_detail.html`
4. `openspec/changes/fix-post-schedule-cancelled-presentation/tasks.md` após implementação
5. relatório temporário em `/tmp/...md`

Não tocar serviços de intercorrência, FSM, migrations, banco de produção, filas ou templates não relacionados.

## Requisitos funcionais

### R1. Card do dashboard

Em `apps/dashboard/views.py::_compute_result`, tratar `case.appointment_status == "cancelled"` antes do fallback de `doctor_decision == "accept"`.

Label esperado, ou equivalente muito próximo:

```text
Agendamento cancelado após intercorrência
```

A classe visual pode ser `bg-warning text-dark` ou equivalente coerente com Bootstrap.

### R2. Detalhe gerencial

Em `dashboard_case_detail`, antes do fallback `accepted_scheduled`, retornar um `result_info` específico para `appointment_status == "cancelled"`.

No template `templates/intake/case_detail.html`, renderizar esse tipo como cancelamento após intercorrência. Não usar badge verde nem texto “Agendamento Confirmado”. Se exibir data/hora/instruções existentes, rotular como agendamento anterior ou dados do agendamento cancelado.

### R3. Confirmados continuam confirmados

Não quebrar casos com `appointment_status == "confirmed"`. Reagendamento e manutenção devem continuar aparecendo como “Agendamento Confirmado”, usando os dados atuais do agendamento.

## Metodologia obrigatória

Use TDD:

1. **RED** — adicione testes que falham com o comportamento atual.
2. **GREEN** — implemente a menor correção para passar.
3. **REFACTOR** — limpe mantendo simplicidade.

Princípios:

- Clean code: nomes claros e regras legíveis.
- DRY: não duplicar lógica complexa sem necessidade.
- YAGNI: não criar novos serviços, enums, migrations, telas ou abstrações genéricas.
- Slice vertical: entregar card + detalhe + teste + docs em uma única fatia pequena.

## Testes mínimos

Adicionar/ajustar testes em `apps/dashboard/tests/test_dashboard.py`:

1. `test_dashboard_list_shows_cancelled_after_post_schedule_issue`
   - cria caso `CLEANED`, aceito/agendado, `appointment_status="cancelled"`;
   - GET `/dashboard/` como manager/admin;
   - assert contém “Agendamento cancelado após intercorrência”;
   - assert não contém “Aguardando Agendamento”.

2. `test_dashboard_detail_shows_cancelled_after_post_schedule_issue`
   - GET detalhe do caso;
   - assert contém “Agendamento cancelado após intercorrência”;
   - assert não contém “Agendamento Confirmado”.

3. `test_dashboard_detail_keeps_confirmed_after_reschedule_or_maintain`
   - caso equivalente com `appointment_status="confirmed"`;
   - GET detalhe;
   - assert contém “Agendamento Confirmado”.

## Gates de autoavaliação

Antes de concluir, responda no relatório:

- Onde a precedência de `cancelled` foi implementada no card?
- Onde a precedência de `cancelled` foi implementada no detalhe?
- Qual teste garante que `cancelled` não aparece como aguardando?
- Qual teste garante que `cancelled` não aparece como confirmado?
- Qual teste garante que `confirmed` continua confirmado?
- Houve alguma alteração em FSM, banco ou serviços? Se sim, justificar; esperado: não.

## Comandos de validação

Executar, no mínimo:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -k "cancelled_after_post_schedule_issue or keeps_confirmed_after_reschedule_or_maintain"
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Relatório obrigatório

Criar relatório temporário em markdown, por exemplo:

```text
/tmp/ats-web-fix-post-schedule-cancelled-presentation-slice-001-report.md
```

O relatório deve conter:

- resumo;
- arquivos alterados;
- snippets antes/depois relevantes;
- evidência RED/GREEN/REFACTOR;
- resultados dos comandos de validação;
- respostas aos gates de autoavaliação;
- riscos/rollback.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, and openspec/changes/fix-post-schedule-cancelled-presentation/*.
Implement ONLY Slice 001. Use TDD RED→GREEN→REFACTOR.
Fix dashboard presentation for cases with appointment_status="cancelled" after post-schedule intercurrence: dashboard list and detail must show “Agendamento cancelado após intercorrência”, not “Aguardando Agendamento” or “Agendamento Confirmado”. Cases with appointment_status="confirmed" must remain “Agendamento Confirmado”.
Keep the slice lean: do not alter FSM, services, migrations, queues or database data. Touch only tests, dashboard presentation code, shared detail template if needed, tasks.md, and a temporary report.
Run validations from AGENTS.md. Update tasks.md. Create /tmp/ats-web-fix-post-schedule-cancelled-presentation-slice-001-report.md with before/after snippets and validation evidence. Commit and push. Reply with REPORT_PATH and stop.
```
