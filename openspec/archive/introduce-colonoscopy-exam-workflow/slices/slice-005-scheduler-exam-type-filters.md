# Slice 005: Filtros CHD em Pendentes, Processados e Histórico

## Handoff contexto zero

Leia AGENTS/PROJECT_CONTEXT, todos artefatos do change, `specs/exam-type-work-queues/spec.md`, este slice, `apps/scheduler/views.py` (queue context, processed, historical queryset/search), `templates/scheduler/{queue.html,_queue_content.html,_nav.html,historical_search.html}` e testes scheduler. Entenda que Pendentes soma WAIT_APPT + notices iniciais + issues operacionais; o filtro deve cobrir todos.

Objetivo:

```text
CHD filtra todas as Pendências por tipo com contagens fechando
→ Processados Hoje filtra por tipo
→ Histórico combina tipo e termo ou lista últimos 50 só pelo tipo
```

Não alterar workflow, form, lock, FSM, notices, issues ou autorização.

## Protocolo DeepSeek4-Flash

**Qualquer falha = INCOMPLETO; não marque task/commit/push.**

1. Confirme branch `feature/colonoscopy-exam-workflow`, árvore limpa e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Registre matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest` baseline antes de editar; pare com failure/error.
3. Escreva testes primeiro e prove RED real.
4. Faça GREEN mínimo sem antecipar slices.
5. Faça REFACTOR estreito com clean code, DRY, YAGNI e sem código morto.
6. Execute/interprete todos os checks `rg`/diff.
7. Rode exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório deve conter comandos/exit codes, snippets, comparação e seção **Handoff para verificador**.
9. Só então marque Slice 005, commit/push, responda REPORT_PATH e PARE.

## Requisitos

### R1. Contagens pendentes por tipo

Calcular EDA/colonoscopia em cada um dos três QuerySets e somar no mesmo universo de `total_notice_count`. Todos é default. Contadores não podem incluir Processados/Histórico.

### R2. Filtro Pendentes

Controle secundário acessível. Ao selecionar tipo, filtrar cards de WAIT_APPT, notices e issues. Pode ser client-side se todos já estão no DOM; cada card usa `data-exam-type` persistido e badge. Não remover grupos/copy/ações.

### R3. Processados Hoje

Badge e filtro simples por tipo; sem alterar ownership por scheduler, período local ou listas de ciências reconhecidas.

### R4. Histórico server-side

Adicionar `exam_type=all|eda|colonoscopy`, validar fallback para all e compor com q. Tipo específico sem q lista últimos 50 desse tipo; all sem q pode listar últimos 50 gerais para consistência. Botão Limpar zera q/tipo. Resultados mostram badge.

### R5. Operação preservada

Testes regressão garantem confirmação/negativa, ACK notices/issues, locks e autorização intactos. Nenhuma ação depende do filtro.

## Arquivos esperados/proibidos

Máximo 6 produto/teste + tasks:

1. `apps/scheduler/views.py`
2. `templates/scheduler/queue.html` e/ou `_queue_content.html` (grupo templates conta individualmente; preferir partial)
3. `templates/scheduler/historical_search.html`
4. JS Vanilla novo/reutilizado, se necessário
5. `apps/scheduler/tests/test_views.py` ou teste focado
6. segundo teste focado somente se necessário para notices/issues

Proibido: models/migrations/FSM, forms/submit business logic, cases services, doctor/intake/dashboard/pipeline, permissões/rotas novas, alterar semântica dos contadores.

## TDD

RED mínimo:

1. contagens type-aware fecham com total;
2. filtro colon mantém cards dos três grupos e remove EDA;
3. cards/badges data type;
4. Processados filtro/badge;
5. histórico tipo sem q retorna últimos do tipo;
6. q+tipo intersectam;
7. inválido cai all;
8. confirmação/negação/ACK continuam possíveis;
9. acesso scheduler preservado.

## Inspeções

```bash
rg -n "exam_type|eda.*count|colonoscopy.*count|total_notice_count" apps/scheduler/views.py templates/scheduler
rg -n "data-exam-type|Todos|EDA|Colonoscopia" templates/scheduler static/js
rg -n "historical_search|exam_type|\[:50\]" apps/scheduler/views.py templates/scheduler/historical_search.html
rg -n "claim_case_lock|assert_case_lock|scheduler_decide|immediate_ack|operational_issue_ack" apps/scheduler/views.py

git diff --name-only "$BASE_REF"
git diff -- apps/cases apps/doctor apps/intake apps/dashboard apps/pipeline apps/scheduler/forms.py
```

Interpretar contagens por três grupos e diff proibido vazio.

## Critérios/gates

- [ ] R1–R5; total fecha; três grupos filtrados; processed/historical; tipo sem q; badges; operação/locks intactos; ≤6 arquivos; baseline/gate/relatório.

## Gates de autoavaliação

Responder no relatório: fórmula de cada contador; quais três grupos; teste de tipo sem q; filtro interfere POST? esperado não; all inválido; locks/ACK preservados; extras; comparação pytest.

### Condições automáticas de INCOMPLETO

Baseline/RED/gate/relatório ausentes; contador exclui notices/issues ou não fecha; filtro só WAIT_APPT; ação/lock/form alterado; histórico ainda exige q para tipo; q e tipo usam OR; badge inferido; permissão relaxada; arquivo proibido/rota/model; >6 sem revisão; requisito sem prova; final falha/passed menor; commit prematuro.

## Relatório obrigatório

`/tmp/introduce-colonoscopy-exam-workflow-slice-005-report.md` com matriz, baseline, RED/GREEN/REFACTOR, snippets contadores/3 grupos/histórico, inspeções, full gate, baseline-final, gates, diff, rerun e Handoff R1–R5.

## Prompt pronto

```text
Read the full handoff in slice-005-scheduler-exam-type-filters.md. Implement ONLY Slice 005 on feature/colonoscopy-exam-workflow under the mandatory DeepSeek protocol: clean BASE_REF, full pytest baseline first, real RED, minimal GREEN, narrow clean/DRY/YAGNI refactor, all inspections, exact full gate and passed comparison. Failure means INCOMPLETE; no tasks/commit/push.

Add type counts/filter across all three CHD pending groups, badges/simple filtering in Processados Hoje, and server-side historical type+q filtering where type alone lists recent cases. Preserve forms, locks, ACKs, FSM, permissions and total semantics. Stay within expected files.

Create /tmp/introduce-colonoscopy-exam-workflow-slice-005-report.md with evidence, snippets, rerun and verifier handoff. If complete mark only Slice 005, commit, push, reply REPORT_PATH=... and STOP.
```
