# Slice 004: Filtros médicos por tipo com busca preservada

## Handoff contexto zero

Leia AGENTS/PROJECT_CONTEXT, todos os artefatos deste change, `specs/exam-type-work-queues/spec.md`, este slice, `apps/doctor/views.py::_doctor_queue_context`, `templates/doctor/{queue.html,_queue_content.html,_nav.html}`, `static/js/doctor_queue_filter.js` e testes da fila. Slice 003 já deve produzir cards EDA/colonoscopia com tipo persistido.

Objetivo:

```text
Médico em Pendentes filtra Todos/EDA/Colonoscopia
+ busca nome/ocorrência permanece ao trocar tipo
+ Limpar apaga termo imediatamente sem trocar tipo
+ polling reaplica ambos
+ Decididos Hoje tem badge/filtro simples
```

Não alterar queries clínicas, ordering, lock, decision, model, pipeline ou CHD.

## Protocolo DeepSeek4-Flash

**Qualquer falha = INCOMPLETO; não marque task/commit/push.**

1. Confirme branch `feature/colonoscopy-exam-workflow`, árvore limpa e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Registre matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest` baseline antes de editar; pare se houver failure/error.
3. Escreva testes primeiro e prove RED real.
4. Faça GREEN mínimo, sem antecipar slices.
5. Faça REFACTOR estreito com clean code, DRY, YAGNI e sem código morto.
6. Execute/interprete todos os `rg`/diff.
7. Rode exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exit 0, zero failures/errors, `passed_final >= passed_baseline`.
8. Relatório deve ter comandos/exit codes, snippets, comparação e seção **Handoff para verificador**.
9. Só então marque Slice 004, commit/push, responda REPORT_PATH e PARE.

## Requisitos

### R1. Controle acessível e contadores

Dentro de Pendentes, renderizar controle secundário `Todos | EDA | Colonoscopia`, Todos default, contagens reais e labels acessíveis. Não substituir tabs primárias. Contagem Pendentes principal continua total.

### R2. Contrato dos cards

Cards pending/decided expõem `data-exam-type` a partir do campo persistido e mostram badge real de tipo. Não inferir pelo texto/JSON.

### R3. Um único filtro composto

Evoluir `doctor_queue_filter.js` para aplicar simultaneamente tipo + termo sobre cards. Preservar normalização, limiar de 3 letras e busca numérica atual. Trocar tipo não apaga input.

### R4. Limpeza e polling

Botão `Limpar`, Esc e input vazio limpam termo e atualizam imediatamente, preservando tipo. `htmx:afterSwap` reaplica tipo/termo. Status usa “casos” e informa visível/total/escopo. Sem resultado é claro.

### R5. Decididos Hoje

Badge por card e filtro client-side simples com Todos padrão. Não adicionar busca. Pode reutilizar mesmo JS/helper sem acoplar seletores frágeis.

## Arquivos esperados/proibidos

Máximo 4 produto/teste + tasks:

1. `templates/doctor/queue.html`
2. `templates/doctor/_queue_content.html`
3. `static/js/doctor_queue_filter.js`
4. `apps/doctor/tests/test_views.py` ou teste focado único

Proibido: views/queries, model/migration, pipeline, scheduler/intake/dashboard, CSS novo salvo bloqueio comprovado (Bootstrap basta), storage/cookie/sessão/endpoint.

## TDD

RED server-side/inspeção estática:

1. controles/contadores apenas nas tabs corretas;
2. cards têm badge e `data-exam-type`;
3. script contém estado/função composta por tipo+termo;
4. Limpar preserva seleção;
5. polling reaplica;
6. decidiu filter sem busca;
7. ordering/locks/links permanecem.

Sem runner JS, documentar matriz de casos manual/estática: `Todos+joao`, `Colonoscopia+joao`, troca mantendo termo, Limpar mantendo tipo, Esc, no-results, afterSwap.

## Inspeções

```bash
rg -n "Todos|EDA|Colonoscopia|data-exam-type|data-doctor-exam" templates/doctor static/js/doctor_queue_filter.js
rg -n "Limpar|Escape|htmx:afterSwap|normalize|data-doctor-queue-card" static/js/doctor_queue_filter.js
rg -n "WAIT_DOCTOR|order_by|regulation_days_on_screen|claim_case_lock" apps/doctor/views.py

git diff --name-only "$BASE_REF"
git diff -- apps/doctor/views.py apps/cases apps/pipeline apps/intake apps/scheduler apps/dashboard
```

Diff proibido vazio.

## Critérios/gates

- [ ] R1–R5 comprovados; Todos default; termo preservado; limpeza imediata preserva tipo; afterSwap; badges; decided simples; sem mudança query/lock/FSM; ≤4 arquivos; baseline/gate/relatório.

## Gates de autoavaliação

Responder no relatório: onde estado do tipo vive; como compõe com termo; qual teste prova data persistida; como limpeza preserva tipo; o que ocorre após swap; aba primária intacta; extras; comparação pytest.

### Condições automáticas de INCOMPLETO

Baseline/RED/gate/relatório ausentes; filtro substitui tabs; termo apagado ao trocar tipo; Limpar não atualiza ou troca tipo; afterSwap perde filtro; tipo inferido de texto; busca existente regressa; view/model/pipeline tocado; endpoint/storage criado; requisito sem prova; >4 arquivos; final falha/passed menor; commit prematuro.

## Relatório obrigatório

Criar `/tmp/introduce-colonoscopy-exam-workflow-slice-004-report.md` com matriz, baseline, RED/GREEN/REFACTOR, snippets HTML/JS antes-depois, matriz de comportamento JS, inspeções, full gate, baseline vs final, gates, diff, rerun e Handoff para verificador R1–R5.

## Prompt pronto

```text
Read the full handoff in slice-004-doctor-exam-type-filters.md and implement ONLY Slice 004 on feature/colonoscopy-exam-workflow. Follow the mandatory DeepSeek protocol: clean BASE_REF, full pytest baseline first, real RED, minimal GREEN, narrow clean/DRY/YAGNI refactor, all inspections, exact full gate and passed comparison. Failure means INCOMPLETE: no tasks/commit/push.

Keep lifecycle tabs. Add accessible Todos/EDA/Colonoscopia counters, persisted-type badges/data attributes, composed client-side type+name/occurrence filtering, term preservation across type changes and HTMX polling, immediate Limpar/Esc behavior preserving type, and a simple Decididos Hoje type filter. Touch only the four expected files; no views/queries/models/pipeline/endpoints/storage.

Create /tmp/introduce-colonoscopy-exam-workflow-slice-004-report.md with RED/GREEN, snippets, JS matrix, quality gate, rerun commands and verifier handoff. If complete mark only Slice 004, commit, push, reply REPORT_PATH=... and STOP.
```
