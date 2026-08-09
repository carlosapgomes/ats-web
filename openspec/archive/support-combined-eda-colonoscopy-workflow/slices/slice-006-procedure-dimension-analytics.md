# Slice 006: Gestor acompanha casos, procedimentos e conversões

## Handoff com contexto zero

Leia artefatos/ADR/relatórios 001–005 e:

- `apps/dashboard/{views.py}` e testes;
- `templates/dashboard/{index.html,_case_list.html}`;
- `static/js/dashboard_search.js`;
- helpers/querysets de CaseProcedure criados;
- specs canônicas de dashboard/date range/period e testes de regressão.

### Fluxo entregue

```text
Gestor escolhe dimensão Declarado/Detectado/Autorizado
→ breakdown exclusivo EDA/Colon/Combinado/Nenhum fecha por casos
→ volume por procedimento mostra componentes
→ matriz mostra conversões
→ casados confirmados contam uma vez
→ tabela combina dimensão+seleção com filtros atuais
```

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Falha em qualquer item = INCOMPLETO; não marque task, não faça commit/push e reporte bloqueio com evidência.**

1. Confirme branch, árvore limpa, ADR-0004 e registre BASE_REF.
2. Registre matriz requisito→arquivo→teste e rode pytest completo antes de editar; baseline falho bloqueia.
3. Escreva testes primeiro e prove RED real.
4. Faça GREEN mínimo sem antecipar cutover/docs.
5. REFACTOR local com clean code, DRY, YAGNI, coesão e sem código morto.
6. Execute/interprete inspeções e diff.
7. Rode exatamente ruff check, format check, mypy e pytest completos; exit 0, zero failures/errors e passed final >= baseline.
8. Gere relatório factual com exemplos numéricos, snippets antes/depois e Handoff para verificador.
9. Só então marque Slice 006, commit normal, push, responda REPORT_PATH e PARE.

**Cap: 7 arquivos produto/teste.**

### Quality gate obrigatório

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Requisitos

### R1. Métricas consolidadas continuam case-level

Total/desfechos/em andamento/esperas preservam fórmulas existentes e contam combinado uma vez. Não alterar período: desfechos usam janela, esperas são snapshot conforme labels atuais.

### R2. Breakdown por dimensão

Parâmetro SSR validado `procedure_dimension=declared|detected|approved`, default documentado. Categorias exclusivas all/eda/colonoscopy/eda_colonoscopy/none quando aplicável. Cada caso entra uma vez e fechamento é testado.

### R3. Volume de componentes

Exibir EDA e Colonoscopia por rows da dimensão, rotulando que combinado soma dois procedimentos. Não comparar soma de componentes com total de casos como se devesse fechar.

### R4. Conversões e casados

Matriz declarado→detectado→autorizado ou apresentação equivalente verificável, usando conjuntos ordenados. Contar paired confirmed uma vez quando ambos approved e appointment confirmed.

### R5. Tabela gerencial

Combinar dimensão + `procedure_selection=all|eda|colonoscopy|eda_colonoscopy|none` com busca/status/datas/atenção/paginação. Partial/header/debounce/AbortController/fallback existentes permanecem e preservam parâmetros.

### R6. Query hygiene

Centralizar predicates/annotations, usar `Exists`/subquery/distinct conscientemente e evitar N+1. Não duplicar fórmulas accepted/denied/admin-closed. Teste de query count/plano somente se padrão atual oferecer harness confiável; ao menos inspeção de bounded queries.

## Arquivos esperados

- dashboard view/query helper (máximo 2);
- index e partial;
- dashboard_search.js;
- até dois testes.

Proibido models/migrations/FSM/apps workflow/prompts/settings/compose.

## TDD RED mínimo

1. combinado soma 1 no total case-level;
2. breakdown de cada dimensão fecha e classifica none;
3. volume combinado soma 1 EDA + 1 Colon;
4. matriz classifica caminho exato;
5. paired confirmed conta 1;
6. período/desfechos/snapshot preservados;
7. filtro dimensão+seleção compõe todos filtros/paginação;
8. parâmetro inválido cai em default seguro;
9. partial JS preserva ambos parâmetros e fallback;
10. query count sem N+1 conforme baseline.

## Inspeções obrigatórias

```bash
rg -n "procedure_dimension|procedure_selection|eda_colonoscopy|paired|casad|conversion|convers" apps/dashboard templates/dashboard static/js/dashboard_search.js
rg -n "accepted|denied|admin|in_progress|WAIT_DOCTOR|WAIT_APPT" apps/dashboard/views.py
rg -n "Exists|Subquery|distinct|prefetch|annotate" apps/dashboard/views.py
rg -n "fetch\(|AbortController|X-ATS-Partial|URLSearchParams" static/js/dashboard_search.js

git diff --name-only "$BASE_REF"
git diff -- apps/cases/models.py apps/cases/migrations apps/intake apps/doctor apps/scheduler apps/pipeline config docker-compose.yml
```

## Critérios/gates

- [ ] R1–R6 provados.
- [ ] Cases vs components claramente distintos.
- [ ] Três dimensões e conversões corretas.
- [ ] Paired count uma vez.
- [ ] Filtros/período/partial regressam.
- [ ] Sem N+1/fórmulas duplicadas.
- [ ] ≤7 arquivos e gates completos.

## Gates de autoavaliação

Responder no relatório:

1. Qual teste prova um caso versus dois componentes?
2. Como cada dimensão fecha em categorias exclusivas?
3. Quando `none` pertence ao universo?
4. Qual teste prova o caminho exato na matriz?
5. Qual prova paired confirmed igual a um?
6. Como semântica período versus snapshot foi preservada?
7. Como queries evitam N+1/duplicação?
8. Quais arquivos mudaram e por quê?
9. Qual a comparação baseline-final com zero failures/errors?

### Condições automáticas de INCOMPLETO

Protocolo ausente; combinado duplica case total; breakdown não fecha; components rotulados como casos; matriz ambígua; paired conta dois; fórmula existente alterada; filtro perde parâmetro/paginação/fallback; N+1; workflow/model/settings tocado; >7 sem revisão; final falha/passed menor; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-006-report.md` com Status, matriz requisito→arquivo→teste, branch/BASE_REF/baseline, RED/GREEN/REFACTOR, exemplos numéricos de fechamento, snippets antes/depois de queries/template/JS, inspeções interpretadas, diff/cap, quality gate completo, comparação pytest e respostas aos gates.

Incluir **Handoff para verificador** com arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R6.

## Prompt pronto

```text
Read all required artifacts, accepted ADR-0004, approved reports 001-005 and Slice 006 files. Implement ONLY Slice 006 with the full DeepSeek4-Flash protocol. Missing/failing evidence, final failure/error, passed regression or >7 files without approval means INCOMPLETE and no task/commit/push.

Deliver dashboard dimensions declared/detected/approved, exclusive case-level breakdown, separate component volume, conversion matrix, one-count paired appointments, and dynamic table filtering composed with all current filters/period/pagination. Preserve semantic formulas, snapshot labels and progressive JS fallback; avoid N+1 and duplication. Do not touch workflow apps, models, migrations, FSM, prompts or infra.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-006-report.md; if complete mark only Slice 006, commit, push, reply REPORT_PATH and STOP.
```
