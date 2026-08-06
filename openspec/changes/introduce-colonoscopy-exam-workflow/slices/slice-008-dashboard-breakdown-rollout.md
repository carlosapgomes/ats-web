# Slice 008: Breakdown gerencial, documentação e rollout

## Handoff contexto zero

Leia AGENTS/PROJECT_CONTEXT, todos artefatos do change/ADR, `specs/exam-type-analytics/spec.md`, este slice, `apps/dashboard/views.py` (summary/stage/average/list context), templates dashboard/partials, JS de busca dinâmica, testes dashboard, `docs/manual/manual-usuarios.md`, `.env.example`, compose/settings e runbooks existentes.

Objetivo final vertical:

```text
Gestor mantém métricas consolidadas
→ vê breakdown EDA/Colonoscopia no período
→ filtra tabela por tipo junto aos filtros atuais
→ operador tem manual e runbook para ativar flag, monitorar e reverter
```

Este slice fecha documentação, mas não é “quality-only”: entrega valor gerencial e operação verificável.

## Protocolo DeepSeek4-Flash

**Qualquer falha = INCOMPLETO; não marque task/commit/push.**

1. Confirme branch `feature/colonoscopy-exam-workflow`, árvore limpa e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Registre matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest` baseline antes de editar; pare com failure/error.
3. Escreva testes primeiro e prove RED real.
4. Faça GREEN mínimo sem antecipar escopo.
5. Faça REFACTOR estreito com clean code, DRY, YAGNI e sem código morto.
6. Execute/interprete todos os checks `rg`/diff.
7. Rode exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório deve conter comandos/exit codes, snippets, comparação e seção **Handoff para verificador**; atualize PROJECT_CONTEXT/manual apenas conforme implementação real.
9. Só então marque Slice 008, commit/push, responda REPORT_PATH e PARE.

Máximo **8 arquivos produto/teste/docs** + tasks; extras exigem revisão.

## Requisitos

### R1. Consolidado preservado

Cards atuais continuam agregando ambos os tipos e preservam semântica de accepted/denied/admin-closed/in-progress e período customizado. Testes com um caso de cada tipo provam contagem única.

### R2. Breakdown type-aware

Criar helper que reutiliza fórmulas existentes parametrizando QuerySet, não copiando lógica. Para EDA/colonoscopia mostrar no período:

- total;
- aceitos;
- negados;
- encerrados administrativamente;
- em andamento;
- WAIT_DOCTOR;
- WAIT_APPT;
- WAIT_R1_CLEANUP_THUMBS.

Soma fecha com consolidado no universo de dois tipos, respeitando definição temporal documentada. Se waiting atual é snapshot e summary é período, rotular claramente para não misturar semânticas.

### R3. Apresentação acessível

Tabela/card de breakdown com headers explícitos, labels EDA/Colonoscopia, responsiva Bootstrap e sem gráfico/dependência JS. Período ativo visível. Não duplicar cards principais.

### R4. Filtro da tabela

Adicionar `exam_type=all|eda|colonoscopy` à listagem/paginação e partial dinâmico. Compor por AND com busca/status/datas/attention; preservar em paginação/forms/requests de busca. Badge por linha/card.

### R5. Documentação do usuário

Atualizar manual somente com comportamento entregue:

- seleção homogênea no upload;
- filtros médico/CHD/NIR/dashboard;
- mixed PDFs separados;
- alerta medicamentoso informativo;
- correção antes da fila médica;
- flag não é assunto de usuário comum.

### R6. Runbook operacional

Criar `docs/deploy/introduce-colonoscopy-exam-workflow.md` com:

1. prechecks/backup;
2. migration/backfill EDA;
3. seed/ativação dos prompts colonoscopy;
4. flag inicialmente false e como ativar globalmente;
5. smoke tests EDA/colonoscopia/mixed/medication;
6. queries/checks de casos em voo por tipo/status;
7. monitoramento de falhas/mismatch/filas;
8. rollback: desligar intake, drenar/encerrar; preferir manter a imagem nova; reverter imagem antiga exige bridge de schema (`SET DEFAULT 'eda'`, verificável);
9. reativação de prompt EDA anterior se rollback de contrato medicamentoso exigir;
10. confirmação de que worker não usa flag para bloquear existentes.

Atualizar `.env.example`/compose se Slice 002 ainda não documentou propagação completa, sem duplicar configuração.

### R7. Contexto e artifacts

Atualizar `PROJECT_CONTEXT.md` com estado final somente após testes. Verificar consistência entre proposal/design/spec/ADR/código; não marcar change como arquivado. `tasks.md` recebe Slice 008, mas DoD global só deve ser marcado se todo item estiver comprovado.

## Arquivos esperados/proibidos

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html` e/ou partial (máximo dois templates)
3. `apps/dashboard/tests/test_dashboard.py` ou teste focado
4. JS dashboard existente apenas se necessário para preservar type param
5. `docs/manual/manual-usuarios.md`
6. `docs/deploy/introduce-colonoscopy-exam-workflow.md`
7. `PROJECT_CONTEXT.md`
8. config/env somente se gap comprovado, substituindo outro extra

Proibido: models/migrations/pipeline/policy/doctor/scheduler/intake workflows/FSM/prompts; alterar fórmula clínica para “fechar” teste; arquivar change; criar gráficos/dependências.

## TDD

RED mínimo:

1. consolidado ambos tipos;
2. breakdown por tipo para desfechos e etapas;
3. admin-closed mutuamente correto;
4. período presets/custom;
5. filtro all/eda/colon;
6. filtro compõe busca/status/date/attention;
7. partial/paginação preservam tipo;
8. template headers/labels/badges;
9. docs/runbook por inspeção.

## Inspeções

```bash
rg -n "exam_type|exam_type_breakdown|EDA|Colonoscopia|waiting_doctor|administratively_closed" apps/dashboard templates/dashboard
rg -n "search|status|date_from|date_to|attention|page|exam_type" apps/dashboard/views.py templates/dashboard static/js
rg -n "COLONOSCOPY_INTAKE_ENABLED|rollback|prompt|migration|mixed|worker|WAIT_DOCTOR|WAIT_APPT" docs/deploy/introduce-colonoscopy-exam-workflow.md .env.example docker-compose*.yml
rg -n "Colonoscopia|medicamento|anticoagul|antiagreg|tipo de exame" docs/manual/manual-usuarios.md PROJECT_CONTEXT.md

git diff --name-only "$BASE_REF"
git diff -- apps/cases apps/pipeline apps/doctor apps/scheduler apps/intake apps/llm apps/admin_ui
```

## Critérios/gates

- [ ] R1–R7; consolidado não regressa; breakdown sem lógica duplicada; snapshot/período rotulados; filtro compõe/persiste; docs fiéis; runbook rollback; ≤8; baseline/gate/report.

## Gates de autoavaliação

Responder no relatório: como evita duplicar fórmula; soma fecha; waiting snapshot vs período; prova filtros AND; partial preserva; rollback de casos em voo/prompts; docs não prometem fora escopo; extras/pytest.

### Condições automáticas de INCOMPLETO

Baseline/RED/gate/report ausentes; consolidado muda incorretamente; accepted/denied dupla contagem; breakdown copia/diverge da fórmula; waiting mal rotulado; filtro perde paginação/partial ou usa OR; docs prometem CPRE/preparo/hard medication; runbook omite flag/casos em voo/prompts/coluna; código de outro app alterado; >8; requisito sem prova; PROJECT_CONTEXT atualizado com falso status; change arquivado; final falha/passed menor; commit prematuro.

## Relatório obrigatório

`/tmp/introduce-colonoscopy-exam-workflow-slice-008-report.md` contendo matriz, baseline, RED/GREEN/REFACTOR, snippets helpers/template/filter, evidência docs/runbook, inspeções, full gate, baseline-final, gates, diff, consistência dos artefatos, comandos rerun e Handoff R1–R7.

## Prompt pronto

```text
Read the complete handoff in slice-008-dashboard-breakdown-rollout.md. Implement ONLY Slice 008 on feature/colonoscopy-exam-workflow under the mandatory DeepSeek protocol: clean BASE_REF, full pytest baseline first, real RED, minimal GREEN, narrow clean/DRY/YAGNI refactor, all inspections, exact full gate and passed comparison. Any failure means INCOMPLETE; no tasks/commit/push.

Preserve consolidated metrics, add a DRY EDA/Colonoscopy breakdown and type filter that composes with all dashboard filters/partial/pagination, then document actual user behavior and a production activation/monitoring/rollback runbook including flag, prompts, migrations and in-flight cases. Do not touch clinical/workflow apps, archive the change or promise CPRE/bowel prep/medication decisions.

Create /tmp/introduce-colonoscopy-exam-workflow-slice-008-report.md with full evidence and verifier handoff. If complete mark only Slice 008, update only truthful global DoD items, commit, push, reply REPORT_PATH=... and STOP.
```
