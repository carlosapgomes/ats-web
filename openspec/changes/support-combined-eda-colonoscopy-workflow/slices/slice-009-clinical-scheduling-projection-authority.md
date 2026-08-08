# Slice 009: Médico e CHD operam por detecção/autorização normalizadas — INCOMPLETE/SUPERSEDED

## Handoff com contexto zero

Leia artefatos, ADR-0004 e relatórios 001–008. Inspecione doctor views/reporting/presenter, `apps/pipeline/prior_case.py`, scheduler views e testes desses fluxos. O pipeline novo já é v2; JSON 1.1 histórico ainda precisa renderizar.

### Fluxo entregue

```text
médico vê declarado/detectado por rows
→ relatório 1.1 deriva seu tipo do JSON histórico ou row declarada
→ lookup anterior exige procedure_type explícito
→ decisão projeta autorização por componente
→ CHD filtra somente doctor_disposition=approved
→ uma agenda casada continua
```

A coluna ainda existe fisicamente até o Slice 011, mas médico/CHD não podem lê-la. Dashboard/helper global serão finalizados no Slice 010.

## Protocolo obrigatório para DeepSeek4-Flash

1. Branch/árvore/ADR/`BASE_REF`; matriz requisito→arquivo→teste.
2. Baseline `uv run pytest` antes de editar; falha bloqueia.
3. Inventário de readers da coluna, context keys legítimas e payload JSON 1.1.
4. RED real primeiro.
5. GREEN mínimo apenas doctor/prior-case/scheduler.
6. REFACTOR local, DRY/YAGNI, sem redesenho de UI.
7. Inspeções + quality gate completo; final zero failures/errors e passed >= baseline.
8. Relatório, checkbox 009, commit/push e PARE.

**Cap: 13 arquivos produto/teste.** Acima disso, pare antes de editar.

## Requisitos

### R1. Cards médicos usam projeções

Remover `case.get_exam_type_display()`/`case.exam_type` de cards e contexto. Campos de template/JS chamados `exam_type` podem permanecer se receberem `selection_key`/label projetado; documentar essa semântica. Pendentes usam detectado; decididos usam autorizado/none.

### R2. Relatório histórico 1.1 continua legível sem coluna

Para schema 1.1, derive o tipo do payload histórico validado (`preop_screening.exam_type`) e, se ausente, de uma única row declarada inequívoca. Ambiguidade/ausência é fail-closed/label neutro, nunca default EDA. O presenter pode manter parâmetro interno de compatibilidade, mas reporting não passa a coluna.

### R3. Lookup anterior exige dimensão explícita

`lookup_prior_case_context` recebe `procedure_type` obrigatório e consulta `CaseProcedure`; remover `_lookup_legacy_exam_type_context` e query `filter(exam_type=...)`. Casos históricos já foram backfillados no Slice 001. Janela, deduplicação e decisões por componente permanecem.

### R4. CHD sem fallback da coluna

Remover fallbacks `exam_type` de `_filter_by_approved_dimension` e demais readers scheduler. Buckets exigem rows aprovadas; caso sem autorização projetada não aparece. Combinado exige duas aprovações e continua produzindo um único `appointment_at`/evento.

### R5. Fixtures clínicas/CHD explícitas

Testes afetados criam rows detectadas/aprovadas/declaradas coerentes com o estágio. Remover leitura de `case.exam_type` em helpers. Fixtures inválidas usadas para fail-closed devem ser explícitas.

### R6. Regressões de segurança

Preservar role decorators, locks, FSM, razão por componente, ausência de rerun por inclusão, snapshot agendado e JSON/eventos 1.1.

## Arquivos esperados

Produto: `apps/doctor/views.py`, `apps/doctor/reporting.py`, `apps/doctor/presenters.py`, `apps/pipeline/prior_case.py`, `apps/scheduler/views.py`. Testes: prior-case, doctor queue/report/decision e scheduler filters/paired appointment estritamente necessários.

Proibido: models/migrations, intake, dashboard/analytics, prompt seed/orchestrator, templates/JS salvo acesso direto comprovado, docs rollout.

## TDD obrigatório

RED: cards ainda leem coluna; report 1.1 depende dela; lookup aceita path singular; scheduler inclui caso sem rows; fixtures não têm projeção. GREEN mínimo e REFACTOR coeso sem mudar contrato visual além da fonte.

## Inspeções obrigatórias

```bash
rg -n "Case\.exam_type|case\.exam_type|get_exam_type_display|filter\([^\n]*exam_type|Q\([^\n]*exam_type|exam_type=" apps/doctor apps/scheduler apps/pipeline/prior_case.py apps/doctor/tests apps/scheduler/tests apps/pipeline/tests/test_prior_case.py
rg -n "preop_screening|schema_version.*1\.1|legacy|procedure_type" apps/doctor/reporting.py apps/doctor/presenters.py apps/pipeline/prior_case.py
rg -n "doctor_disposition|detection_status|get_(declared|detected|approved)_procedure_types" apps/doctor apps/scheduler apps/pipeline/prior_case.py
rg -n "@role_required|select_for_update|appointment_at|SCHEDULER_PAIRED_APPOINTMENT_CONFIRMED" apps/doctor apps/scheduler
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
git diff --name-only "$BASE_REF"
```

## Critérios/gates

- [ ] R1–R6 provados.
- [ ] Zero reader/query da coluna em doctor/scheduler/prior-case.
- [ ] JSON 1.1 renderiza sem default silencioso.
- [ ] Lookup exige procedure_type e usa rows.
- [ ] CHD filtra aprovado e agenda uma vez.
- [ ] Fixtures relevantes são explícitas.
- [ ] Segurança/FSM/roles preservados.
- [ ] Cap/gates verdes.

Responder: como schema 1.1 deriva tipo; como ambiguidade falha; qual teste elimina query legada; como fila CHD exclui ausência; quais context keys são nomes legítimos; fixtures migradas; arquivos; baseline-final.

### Condições automáticas de INCOMPLETO

Qualquer reader/query da coluna; default EDA em legado ambíguo; lookup singular residual; scheduler fallback; JSON 1.1 quebrado; fixture mascarada; permissão/FSM/lock/agenda relaxados; app externo alterado; cap/gate falha; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-009-report.md` com matriz, baseline, RED/GREEN/REFACTOR, snippets, inventário/classificação, inspections, cap/gates, baseline-final e Handoff R1–R6.

## Addendum de correção — Status: INCOMPLETE (revisão pós-commit `9caf210`)

Tentativa de correção (C1–C5) iniciada a partir de `9caf210`. Produto corretamente
implementado (C1 doctor strict via `fallback_to_bridge=False`; C2 `_require_approved_procedure`
em todos os universos + fail-closed em `scheduler_confirm`/`scheduler_submit`;
`decision.html` projetado; C4 spies/divergência; C3 helpers explícitos). RED real
provado para C1 (doctor strict) e C2 (exclusão/bloqueio CHD).

**Bloqueador (INCOMPLETE):** C1 (doctor strict) + C2 (filtrar universos CHD)
enforçam invariantes de produção (`WAIT_DOCTOR` ⇒ rows detectadas;
`WAIT_APPT` ⇒ rows aprovadas). A infraestrutura de teste existente cria casos
nesses estados **sem `CaseProcedure`** (bypass do pipeline via `advance_to` e
`Case.objects.create(status=WAIT_APPT/WAIT_DOCTOR, ...)`), violando esses
invariantes. Aplicar C1+C2 quebra **~105 testes** em **~10 arquivos de teste**
(scheduler: `test_views` 58, `test_post_schedule_issue` 24 via `advance_to`,
`test_operational_post_acceptance_chd` 11, `test_communication` 2; doctor:
`test_pediatric_em_scheduling` 4, `test_views` 1, `test_operational_admission_flows` 1,
`test_colonoscopy_doctor` 1, `test_queue_exam_type_filters` 2; intake:
`test_exam_type_intake` 1). Migrar todas as fixtures é o trabalho correto, mas o
diff acumulado (`78b390b..HEAD`) subiria para **~24 arquivos produto/teste/template**
(~13 arquivos de teste além dos 13 do commit reprovado) — **não enxuto**.

C3 proíbe usar `advance_to`/signals/autouse (mecanismo global) para esconder
fixtures incompletas — e ~66 fixtures scheduler usam justamente `advance_to`
(`test_post_schedule_issue`), tornando a migração por-teste o único caminho
permitido, porém volumoso.

Per C5 ("Se não puder justificar um cap enxuto, reporte INCOMPLETE"): reportado
**INCOMPLETE**. Produto/teste foram revertidos ao estado limpo `9caf210`
(3045 passed) para não deixar a árvore quebrada. Recomendação: (a) dedicar um
slice próprio à migração da infraestrutura de teste scheduler/doctor para criar
rows coerentes (declaradas/detectadas/aprovadas) antes de reexecutar C1+C2, ou
(b) elevar substancialmente o cap e migrar as ~100 fixtures num único esforço.
C4 (derivação 1.1 fail-closed + spy) já está correto no commit `9caf210` e não
requer mudança de produto.

## Redimensionamento vinculante após revisão

Este arquivo é evidência histórica da tentativa reprovada e **não deve ser executado novamente**. O trabalho restante foi substituído, nesta ordem, por:

1. `slice-009a-doctor-projection-authority.md`;
2. `slice-009b-scheduler-projection-authority.md`.

Somente após ambos terem relatório aprovado o Slice 010 pode começar. Não marcar um checkbox para este arquivo histórico e não usar o prompt abaixo.

## Prompt obsoleto — NÃO EXECUTAR

```text
Read all artifacts, ADR-0004 and approved reports 001-008. Implement ONLY resized Slice 009 with TDD and the mandatory protocol.

Remove all Case.exam_type readers/queries from doctor, prior-case lookup and scheduler. Project doctor cards from detected/approved rows; make procedure_type mandatory in prior lookup; render schema 1.1 by its historical payload or one unequivocal declared row without default EDA; filter CHD only by approved rows while preserving one paired appointment. Migrate affected fixtures explicitly. Preserve permissions, locks, FSM, reasons, no-rerun behavior and historical JSON/events. Do not touch models/migrations, intake, dashboard, prompts or rollout docs. Above 13 files or any gate failure = INCOMPLETE.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-009-report.md; if complete mark only Slice 009, commit, push, reply REPORT_PATH and STOP.
```
