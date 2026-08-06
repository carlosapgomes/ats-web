# Slice 004: CHD recebe conjunto autorizado e faz um agendamento casado

## Handoff com contexto zero

Leia artefatos/ADR/relatórios 001–003 e:

- `apps/scheduler/{forms.py,views.py}` e templates queue/confirm/history/context;
- `apps/cases/{models.py,services.py,admission.py}`;
- `static/js/scheduler_queue_filter.js`;
- testes scheduler, locks, notices, issues, histórico e filtros.

### Fluxo entregue

```text
Médico autoriza 1–2 procedimentos
→ CHD vê conjunto autorizado e transformação detectado→autorizado
→ ambos = badge Agendamento casado
→ confirma uma data/hora/local
→ uma transição + um appointment_at
→ Processados/Histórico filtram pelo autorizado
```

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Qualquer falha = INCOMPLETO; não marque task, não faça commit/push e reporte bloqueio com evidência.**

1. Confirme branch, árvore limpa, ADR-0004 aceita e registre BASE_REF.
2. Registre matriz requisito→arquivo→teste e rode `uv run pytest` completo antes de editar; baseline falho bloqueia.
3. Escreva testes primeiro e prove RED funcional real.
4. Faça GREEN mínimo sem antecipar NIR/dashboard/cutover.
5. Faça REFACTOR local com clean code, DRY, YAGNI, coesão e sem código morto.
6. Execute/interprete todas as inspeções deste slice.
7. Rode exatamente ruff check, format check, mypy e pytest completos; exit 0, zero failures/errors e passed final >= baseline.
8. Gere relatório factual com snippets antes/depois e Handoff para verificador.
9. Só então marque Slice 004, commit normal, push, responda REPORT_PATH e PARE.

**Cap: 9 arquivos produto/teste.**

### Quality gate obrigatório

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Requisitos

### R1. Cards/detalhe por autorizado

Usar somente procedimentos `approved` para badge/filtro principal. Mostrar `EDA + Colonoscopia · Agendamento casado` para ambos. Se detectado divergir, mostrar comparação e razões médicas textuais.

### R2. Uma agenda invariável

Reutilizar `SchedulerDecisionForm` com uma data/hora/local. Submit combinado persiste exatamente um `appointment_at`, uma decisão e uma transição. Não criar modelo/row por procedimento nem campos de segunda agenda.

### R3. CHD não altera conjunto

Nenhum controle permite incluir/remover procedimento. POST manipulado não muda `CaseProcedure`. Impedimentos usam comunicação/intercorrência existente.

### R4. Snapshot auditável

Evento de confirmação/negativa inclui conjunto aprovado ordenado; combinado confirmado registra fato casado sem duplicar evento/transição. Payload sem texto clínico integral.

### R5. Filtros e contadores

Pendentes (WAIT_APPT + notices/issues do universo existente), Processados Hoje e Histórico usam autorizado. Opções Todos/EDA/Colonoscopia/Combinado; histórico aceita seleção sem termo e mantém top 50/order. Polling e counts preservados.

### R6. Regressões operacionais

Locks, ownership, acknowledgements, admission flows, post-schedule/post-acceptance issues e filtros de período permanecem. Nenhum notice é duplicado por haver dois componentes.

## Arquivos esperados

- scheduler views/forms (preferir não mudar form);
- queue/confirm/history templates, máximo 3;
- JS filtro;
- cases service somente para helper/snapshot;
- até três testes.

Proibido model/migration/FSM/doctor/intake/dashboard/pipeline/prompts.

## TDD RED mínimo

1. combinado aparece com badge casado;
2. alteração detectado→autorizado e razões visíveis;
3. confirmar combinado cria um appointment/event/transition;
4. POST não altera rows aprovadas;
5. negar preserva motivos/fluxo atual;
6. filtros pending abrangem três grupos e contam combinado uma vez;
7. Processados/Histórico por combinado;
8. histórico combinado sem termo limita 50/order;
9. locks/ownership inválidos bloqueiam;
10. notices/issues/ACKs/admission regressam sem duplicação.

## Inspeções obrigatórias

```bash
rg -n "Agendamento casado|Autorizado|Detectado|approved|eda_colonoscopy" apps/scheduler templates/scheduler static/js/scheduler_queue_filter.js
rg -n "appointment_at|scheduler_decide|final_reply_posted|assert_case_lock" apps/scheduler/views.py
rg -n "CaseProcedure.*(create|update|delete)|doctor_disposition.*=" apps/scheduler || true
rg -n "appointment_.*(eda|colon)|second.*appointment|paired.*DateTime" apps/scheduler apps/cases || true

git diff --name-only "$BASE_REF"
git diff -- apps/cases/models.py apps/cases/migrations apps/doctor apps/intake apps/dashboard apps/pipeline
```

## Critérios/gates

- [ ] R1–R6 provados.
- [ ] Um único horário/transição/evento operacional.
- [ ] CHD não muda conjunto.
- [ ] Todos grupos/filtros usam autorizado.
- [ ] Regressões locks/notices/issues verdes.
- [ ] ≤9 arquivos, gates e relatório completos.

## Gates de autoavaliação

Responder no relatório:

1. Qual teste prova exatamente um appointment/evento/transição?
2. Qual prova que POST manipulado não altera procedimentos?
3. Como queries/filtros escolhem a dimensão autorizada?
4. Como combinado conta uma vez em cada grupo pendente?
5. Qual teste prova histórico combinado sem termo e limite 50?
6. Quais regressões de locks/notices/issues/admission passaram?
7. Quais arquivos mudaram e por quê?
8. Qual a comparação baseline-final com zero failures/errors?

### Condições automáticas de INCOMPLETO

Protocolo ausente; dois appointments/eventos/transições; CHD altera procedimento; filtro usa declared/detected/legacy; grupo pendente omitido; badge sem texto; lock/ownership relaxado; notice duplicado; model/FSM/app futuro tocado; >9 sem revisão; final falha/passed menor; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-004-report.md` com Status, matriz requisito→arquivo→teste, branch/BASE_REF/baseline, evidência RED/GREEN/REFACTOR, snippets antes/depois de card/submit/event/filter, inspeções interpretadas, diff/cap, quality gate completo, comparação pytest e respostas aos gates.

Incluir **Handoff para verificador** com arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R6.

## Prompt pronto

```text
Read all required artifacts, accepted ADR-0004, approved reports 001-003 and Slice 004 files. Implement ONLY Slice 004. Follow the DeepSeek4-Flash protocol literally; any missing/failing check, final failure/error, passed regression or >9 files without approval means INCOMPLETE and no tasks/commit/push.

Make CHD consume the approved procedure set, visibly identify paired EDA+Colonoscopy and transformations, confirm exactly one date/time with existing lock/FSM, forbid CHD procedure mutation, audit the approved snapshot, and filter Pending/Processed/Historical by approved selection while preserving all notices/issues/ACKs/admission flows. Do not alter models, migrations, FSM, doctor, NIR, dashboard or LLM.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-004-report.md; if complete mark only Slice 004, commit, push, reply REPORT_PATH and STOP.
```
