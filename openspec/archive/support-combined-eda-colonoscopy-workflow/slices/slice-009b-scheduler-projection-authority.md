# Slice 009-B: CHD lista e agenda somente autorização projetada

## Handoff com contexto zero

Pré-condição bloqueante: Slice 009-A deve estar commitado, enviado e aprovado, com relatório `/tmp/support-combined-eda-colonoscopy-workflow-slice-009a-doctor-projection-authority-report.md`. Se não estiver, responda `BLOCKED` sem editar.

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, proposal/design/tasks, ADR-0004, relatórios aprovados 001–008 e 009-A, além dos dois relatórios `INCOMPLETE` do 009 original. Inspecione todos os universos e ações em `apps/scheduler/views.py`, serviços de notices/issues usados pela fila e fixtures que criam casos já em `WAIT_APPT`/estágios posteriores.

O commit `9caf210` tornou snapshot e filtro histórico específico estritos, mas ainda deixa caso sem aprovação aparecer em “Todos” e alcançar confirmação/submissão. A tentativa corretiva não foi versionada; refaça RED/GREEN.

### Fluxo entregue

```text
decisão médica possui ≥1 CaseProcedure approved
→ universos CHD incluem somente casos com aprovação projetada
→ card/bucket/snapshot usam exatamente o conjunto aprovado
→ acesso direto revalida aprovação antes e depois do lock relevante
→ zero aprovado não agenda, não transita e não gera evento
→ dois aprovados continuam em um caso, um appointment_at e um evento casado
```

## Protocolo obrigatório para DeepSeek4-Flash

Qualquer falha = `INCOMPLETE`: não marque task, não faça commit/push de conclusão e pare.

1. Confirme 009-A aprovado, branch/árvore/remoto e registre `BASE_REF`.
2. Matriz requisito→arquivo→teste e inventário de todos os querysets/ações CHD.
3. Baseline completo `uv run pytest` antes de editar; failure/error bloqueia.
4. RED real para fila, acesso direto e agenda casada.
5. GREEN mínimo em scheduler + fixtures que atravessam CHD.
6. REFACTOR local; predicate/query helper único, sem inferência da ponte.
7. Inspeções + quality gate completo; zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório, marcar somente 009-B, commit normal, push e PARE.

**Cap: 11 arquivos produto/teste.** Artefatos/relatório não contam. Acima disso, pare com inventário; não crie slice horizontal de fixtures nem aumente o cap silenciosamente.

## Requisitos

### R1. Todos os universos CHD exigem aprovação

Centralizar um predicate/query helper baseado em `Exists(CaseProcedure)` ou equivalente, exigindo `doctor_disposition=approved`, e aplicá-lo aos universos operacionais relevantes:

- `WAIT_APPT` pendentes;
- notices operacionais iniciais;
- issues operacionais abertas;
- processados hoje;
- ciências reconhecidas quando compõem cards CHD;
- histórico/pesquisa, inclusive `exam_type=all` ou busca apenas por termo.

Caso sem row aprovada não aparece em “Todos”, não incrementa contadores e não entra em bucket. Não usar `doctor_decision=accept` nem `Case.exam_type` como fallback.

Preservar sem duplicação a composição existente de notices/issues e o ownership dos processados.

### R2. Confirm/submit revalidam fail-closed

`scheduler_confirm` deve recusar caso normal de agendamento sem aprovação antes de adquirir lock. `scheduler_submit` deve revalidar a projeção na instância protegida pelo contrato de lock/transação, cobrindo remoção/race entre GET e POST.

Em falha:

- nenhuma transição FSM;
- nenhum `appointment_at`, status/reason/scheduler timestamp novo;
- nenhum `APPT_*`/`SCHEDULER_PAIRED_APPOINTMENT_CONFIRMED` com conjunto vazio;
- lock não fica abandonado se já foi adquirido;
- resposta segue padrão seguro existente (404 ou redirect+mensagem testado), sem vazar detalhes.

Não bloquear a resolução legítima de intercorrência pós-agendamento de um caso que possui projeção aprovada preservada.

### R3. Snapshot e buckets são estritos

Preservar `_approved_snapshot(...fallback_to_bridge=False)` e `_filter_by_approved_dimension` sem fallback. `approved_procedures` do evento é não vazio e igual às rows aprovadas no instante protegido. Simples pertence a um bucket; combinado exige duas aprovações e conta uma vez.

### R4. Agenda casada permanece única

Duas aprovações produzem exatamente:

- um card/caso;
- um `appointment_at`;
- uma transição de confirmação;
- um evento de confirmação com `approved_procedures=["eda", "colonoscopy"]` ordenado e `paired=true`;
- `SCHEDULER_PAIRED_APPOINTMENT_CONFIRMED` somente conforme contrato já definido, sem duplicação.

CHD nunca altera o conjunto autorizado.

### R5. Fixtures que atravessam CHD são explícitas

Migrar somente fixtures que falham por criar caso downstream sem rows. Calls devem fornecer conjuntos `declared`, `detected`, `approved` e razões quando aprovação não detectada for intencional.

Helper compartilhado é permitido apenas se explícito no call site e sem ler `case.exam_type`, sem inferir por status e sem signal/autouse. `advance_to` pode avançar FSM, mas não deve inventar projeção; o teste prepara a projeção explicitamente antes do estágio que a exige.

Fixtures fail-closed sem aprovação devem ser nomeadas/comentadas como inválidas intencionais.

### R6. Segurança e fluxos existentes preservados

Preservar `@role_required("scheduler")`, intranet guard, ownership, locks, FSM, comunicação, notices/issues, pediatric appointment, razões, snapshots históricos e JSON/eventos 1.1. Nenhuma alteração de model/migration/endpoint público.

## Arquivos esperados

Produto:

- `apps/scheduler/views.py`.

Testes, somente conforme falha comprovada:

- `apps/scheduler/tests/test_slice_004_paired_scheduler_appointment.py`;
- `apps/scheduler/tests/test_views.py`;
- `apps/scheduler/tests/test_post_schedule_issue.py`;
- `apps/scheduler/tests/test_operational_post_acceptance_chd.py`;
- `apps/scheduler/tests/test_communication.py`;
- `apps/doctor/tests/test_pediatric_em_scheduling.py`;
- `apps/doctor/tests/test_operational_admission_flows.py`;
- `apps/intake/tests/test_exam_type_intake.py` (somente cenário end-to-end que chega ao CHD);
- `tests/shared_case_fixtures.py` (helper explícito opcional, se não entregue por 009-A).

Doctor product/template, dashboard, models/migrations e pipeline são proibidos. Arquivo extra exige justificativa e respeito ao cap.

## TDD obrigatório

### RED

1. `WAIT_APPT` sem approved não aparece, não conta em “Todos” e não possui CTA.
2. Notice/issue/processado/histórico sem approved também não aparece no universo CHD correspondente.
3. GET confirm direto sem approved é recusado sem adquirir/deixar lock.
4. POST com lock válido e aprovação removida antes da persistência não transita nem gera evento/campos.
5. Caso combinado aprovado aparece/agendado exatamente uma vez.

### GREEN

Predicate único para querysets, guard fail-closed em ações e fixtures explícitas mínimas.

### REFACTOR

Evitar filtros divergentes e N+1. Não transformar `apps/scheduler/views.py` em God helper; manter predicate de elegibilidade separado do snapshot de apresentação.

## Inspeções obrigatórias

```bash
rg -n "Case\.exam_type|case\.exam_type|get_exam_type_display|filter\([^\n]*exam_type|Q\([^\n]*exam_type" apps/scheduler templates/scheduler
rg -n "doctor_decision.*accept|fallback_to_bridge|doctor_disposition|Exists|OuterRef" apps/scheduler/views.py
rg -n "WAIT_APPT|unacknowledged_operational|processed_qs|acknowledged_notice|historical" apps/scheduler/views.py
rg -n "@role_required|assert_case_lock|claim_case_lock|release_lock|appointment_at|SCHEDULER_PAIRED_APPOINTMENT_CONFIRMED" apps/scheduler
rg -n "case\.exam_type" apps/scheduler/tests apps/doctor/tests/test_pediatric_em_scheduling.py apps/doctor/tests/test_operational_admission_flows.py apps/intake/tests/test_exam_type_intake.py tests/shared_case_fixtures.py
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
git diff --name-only "$BASE_REF"
```

No relatório, liste cada universo CHD e a linha/helper que prova sua elegibilidade. Nome HTTP/context key `exam_type` pode permanecer como seleção derivada; reader/query da coluna é `INCOMPLETE`.

## Critérios/gates

- [ ] R1–R6 provados.
- [ ] Todos os universos CHD excluem zero aprovado, inclusive “Todos”.
- [ ] Confirm/submit falham sem efeitos quando aprovação falta/desaparece.
- [ ] Evento de agenda nunca contém `approved_procedures=[]`.
- [ ] Combinado agenda uma vez e snapshot ordenado permanece.
- [ ] Fixtures downstream explícitas, sem inferência global.
- [ ] Roles, locks, FSM, notices/issues e ownership preservados.
- [ ] Cap/gates verdes.

Responder: quais universos foram filtrados; qual SQL/predicate comum; ordem das revalidações e lock; prova de zero efeitos; fixtures migradas; prova da agenda casada; resíduos; baseline-final.

### Condições automáticas de INCOMPLETO

Caso sem approved em qualquer universo/contador; direct action operável sem approved; evento vazio; fallback por `doctor_decision`/coluna; race sem revalidação; lock abandonado; combinado duplicado; fixture inferida por status/coluna; doctor product alterado; cap/gate falha; relatório ausente; 010 iniciado.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-009b-scheduler-projection-authority-report.md` com status, matriz, baseline, RED/GREEN/REFACTOR, inventário por universo, SQL/predicate, lock/race, snippets, fixtures, agenda casada, cap, quality gate, baseline-final e handoff R1–R6.

## Prompt pronto

```text
Read AGENTS.md, PROJECT_CONTEXT.md, this change's proposal/design/tasks, ADR-0004, approved reports 001-008 and 009-A, and both original 009 INCOMPLETE reports. If 009-A is not approved, STOP BLOCKED. Implement ONLY Slice 009-B with TDD.

Require at least one approved CaseProcedure in every CHD operational universe, including all/search-only history; make scheduler_confirm and scheduler_submit fail closed against missing/raced-away approval with no FSM/appointment/event side effects or abandoned lock; preserve strict snapshots and one paired appointment for two approvals. Migrate only fixtures that cross CHD, using explicit declared/detected/approved sets and no Case.exam_type/status inference, signal or autouse magic. Preserve roles, intranet, ownership, locks, FSM, notices/issues, pediatric scheduling, reasons and historical contracts. Do not touch doctor product, models/migrations, dashboard, pipeline or Slice 010. Above 11 product/test files or any gate failure = INCOMPLETE.

Create the required temporary report, mark only 009-B if complete, commit, push, reply REPORT_PATH and STOP.
```
