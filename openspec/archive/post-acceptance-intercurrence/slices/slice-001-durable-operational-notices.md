<!-- markdownlint-disable MD013 -->

# Slice 001: Notices operacionais duráveis até ACK

## Handoff para implementador LLM com contexto zero

Leia integralmente, antes de editar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/post-acceptance-intercurrence/proposal.md`
- `openspec/changes/post-acceptance-intercurrence/design.md`
- `openspec/changes/post-acceptance-intercurrence/tasks.md`
- `openspec/changes/post-acceptance-intercurrence/specs/post-acceptance-intercurrence/spec.md`
- este slice
- `apps/cases/services.py::local_day_bounds`
- `apps/cases/services.py::unacknowledged_operational_notice_qs`
- `apps/scheduler/views.py::_scheduler_queue_context`
- `apps/scheduler/views.py::immediate_ack`
- `apps/accounts/context_processors.py::queue_counts`
- testes existentes de notices/queue count.

Estado atual: notices de `immediate/pre_icu/ward_icu_backup/pediatric_em` são filtrados pelo dia de criação do evento. Um notice sem ACK criado ontem some hoje. Fila e badge já compartilham `unacknowledged_operational_notice_qs()`, portanto a correção deve permanecer centralizada nesse helper.

Implemente **somente** a durabilidade do notice inicial. Não implemente ainda nomenclatura pós-aceitação, migration, `cycle_id`, novos motivos ou fluxo de intercorrência sem agenda.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Siga literalmente. **Se qualquer item falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. Escreva no relatório a matriz `Requisito → arquivo(s) → teste(s)` antes de editar.
2. Registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no baseline limpo. Registre exit code e resumo. Se houver failure/error, pare.
3. Escreva testes primeiro e demonstre RED real pelo motivo esperado.
4. Implemente GREEN mínimo, sem refactor amplo ou antecipação dos próximos slices.
5. Execute e interprete todos os checks de inspeção deste arquivo.
6. Execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`.
7. O pytest final deve ter exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Gere relatório com evidência e `Handoff para verificador`. Somente então marque o slice em `tasks.md`, faça commit/push e pare.

### Condições automáticas de INCOMPLETO

- baseline completo ausente ou com falha;
- nenhum teste novo/ajustado falhou em RED;
- teste de notice do dia anterior ausente;
- fila e badge não foram ambos comprovados;
- histórico do ACK no dia atual não foi preservado por teste;
- compatibilidade de eventos novos e legados não foi testada;
- consulta ainda restringe timestamp do notice ao dia local;
- qualquer gate falha ou não é executado;
- pytest final tem exit code não zero, failures/errors ou menos `passed` que o baseline;
- `tasks.md` marcado com pendência;
- relatório exigido ausente.

## Objetivo do slice

```text
Notice operacional criado em D-1 sem ACK
→ permanece na fila e badge CHD em D
→ CHD confirma ciência em D
→ card/badge somem
→ ACK aparece no histórico de confirmados em D
```

## Requisitos funcionais

### R1. Pendência sem expiração diária

`unacknowledged_operational_notice_qs()` deve retornar notice elegível sem ACK independentemente da data de criação.

### R2. Fila e badge consistentes

A fila scheduler e `queue_counts()` devem incluir o mesmo notice antigo exatamente uma vez.

### R3. ACK e histórico preservados

`immediate_ack` continua idempotente. Depois do ACK, o notice some da fila/badge e aparece em “Ciências operacionais confirmadas hoje”, usando a data do ACK, não do notice.

### R4. Compatibilidade

Reconhecer:

- notices `ADMISSION_FLOW_OPERATIONAL_NOTICE` e legado `IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE`;
- ACKs `SCHEDULER_OPERATIONAL_NOTICE_ACK` e legado `SCHEDULER_IMMEDIATE_ACK`;
- todos os quatro `OPERATIONAL_NOTICE_FLOWS`.

### R5. Sem mudança colateral

Não alterar FSM, campos do `Case`, migrations, templates, rotas, permissões ou semântica do histórico de hoje.

## Arquivos esperados

Idealmente:

- `apps/cases/services.py`
- `apps/scheduler/tests/test_views.py` e/ou teste coeso novo no app scheduler
- `apps/accounts/tests/test_context_processors.py`
- `openspec/changes/post-acceptance-intercurrence/tasks.md` somente ao concluir

Qualquer arquivo produtivo além de `apps/cases/services.py` exige justificativa explícita no relatório.

### Fora de escopo/proibido

- `apps/cases/models.py` e migrations;
- nomes/eventos `POST_ACCEPTANCE_ISSUE_*`;
- templates e CSS/JS;
- fluxo de abertura/resposta da intercorrência;
- mudança no histórico “confirmados hoje” para multi-dia.

## TDD obrigatório

### RED

Adicionar testes que provem pelo menos:

1. evento de notice de ontem, sem ACK, aparece no HTML da fila hoje;
2. o mesmo caso incrementa `queue_count` hoje;
3. após POST de ACK hoje, deixa fila/count;
4. ACK aparece no histórico de hoje;
5. evento legado de ontem também permanece;
6. notice de ontem já confirmado não reaparece.

Congele o tempo ou crie timestamps de forma determinística. Não use teste que dependa do relógio real perto da meia-noite.

### GREEN

Remover apenas o filtro diário aplicado ao evento de notice ativo. Preserve filtros de fluxo, ausência de ACK, exclusão de `WAIT_APPT` e `distinct()`.

### REFACTOR

- manter helper como fonte única;
- nomes claros;
- evitar query duplicada em context processor/view;
- não criar abstração de ticket/ciclo antes do Slice 002.

## Checks de inspeção obrigatórios

```bash
rg -n "def unacknowledged_operational_notice_qs|events__timestamp__gte|events__timestamp__lt|exclude\(events__event_type__in|distinct\(\)" apps/cases/services.py
rg -n "unacknowledged_operational_notice_qs" apps/scheduler/views.py apps/accounts/context_processors.py
rg -n "ADMISSION_FLOW_OPERATIONAL_NOTICE|IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE|SCHEDULER_OPERATIONAL_NOTICE_ACK|SCHEDULER_IMMEDIATE_ACK" apps/cases/admission.py apps/cases/services.py apps/scheduler/views.py
```

Interprete no relatório: filtros de timestamp continuam válidos para histórico/local-day, mas não podem limitar a consulta ativa de notices pendentes.

## Critérios binários de sucesso

- [ ] Notice de ontem sem ACK aparece hoje.
- [ ] Badge/count inclui exatamente uma unidade.
- [ ] ACK é idempotente e remove a pendência.
- [ ] Histórico de hoje usa timestamp do ACK.
- [ ] Eventos novos e legados passam.
- [ ] Todos os quatro fluxos continuam reconhecidos.
- [ ] Nenhum schema/FSM/template foi alterado.
- [ ] Quality gate completo verde e contagem final não regrediu.

## Gates de autoavaliação

1. Há algum filtro de data ainda capaz de ocultar notice ativo antigo?
2. Um notice confirmado ontem pode reaparecer hoje?
3. O mesmo caso é contado duas vezes por joins de eventos?
4. Fila e badge chamam a mesma fonte de verdade?
5. O histórico confirmado hoje continua limitado pelo ACK de hoje?
6. Eventos legados foram exercitados por teste real?

## Relatório obrigatório

Crie `/tmp/post-acceptance-intercurrence-slice-001-report.md` contendo:

- `Status: COMPLETE|INCOMPLETE`;
- matriz requisito/arquivos/testes;
- `BASE_REF` e baseline completo;
- evidência RED e GREEN;
- snippets antes/depois;
- checks `rg` e interpretação;
- baseline vs final (`passed`, `failed`, `errors`, exit code);
- quality gate completo;
- respostas aos gates;
- `git diff --stat` e justificativa de arquivos extras;
- Handoff para verificador com arquivos, reruns, riscos e checklist R1–R5.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and every artifact under openspec/changes/post-acceptance-intercurrence, especially slices/slice-001-durable-operational-notices.md. Implement ONLY Slice 001.
Follow the DeepSeek4-Flash protocol literally: plan matrix, clean baseline with full pytest before editing, real RED, minimal GREEN, REFACTOR with clean code/DRY/YAGNI, inspection checks, full quality gate and baseline-vs-final comparison.
Make initial operational notices persist until ACK regardless of creation day, while preserving same-day ACK history, idempotency, legacy events, all four flows, permissions, FSM and schema. Do not implement post-acceptance issue fields/events/UI yet.
If any required evidence/gate is missing or failing, report INCOMPLETE and do not update tasks.md or commit. If complete, update only this slice checkbox, create /tmp/post-acceptance-intercurrence-slice-001-report.md, commit with a traceable message, push branch change/post-acceptance-intercurrence, reply REPORT_PATH=..., then STOP for planner review.
```
