<!-- markdownlint-disable MD013 -->

# Slice 001: Entregar resumo compacto de procedimentos e retirar comparação avançada

## Handoff para implementador LLM com contexto zero

Projeto Django SSR em `/projects/dev/ats-web`. Leia completamente, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `docs/adr/ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md`
4. `openspec/specs/exam-type-analytics/spec.md`
5. `openspec/changes/simplify-dashboard-procedure-card/proposal.md`
6. `openspec/changes/simplify-dashboard-procedure-card/design.md`
7. `openspec/changes/simplify-dashboard-procedure-card/tasks.md`
8. este slice

Depois inspecione antes de editar:

- `templates/dashboard/index.html`, principalmente o card `PROCEDIMENTOS POR DIMENSÃO` e o form `id="case-filter-form"`;
- `apps/dashboard/views.py`, principalmente `_procedure_dimension_links()`, `_matrix_display_rows()` e `dashboard_index()`;
- `apps/dashboard/procedure_analytics.py`;
- `apps/dashboard/tests/test_dashboard.py`;
- `apps/dashboard/tests/test_procedure_analytics.py`.

### Estado atual resumido

O dashboard já calcula corretamente quatro categorias exclusivas por dimensão, volume de componentes, matriz de conversão e agendamentos casados. O problema deste slice é somente a experiência da visão principal: tabela, volume, explicações e matriz geram alta carga cognitiva e ocupam espaço sem ação operacional clara.

A lista de casos usa os mesmos parâmetros `procedure_dimension=declared|detected|approved` e `procedure_selection=all|eda|colonoscopy|eda_colonoscopy|none`. Esses contratos, os cálculos subjacentes e as permissões devem permanecer.

### Fluxo vertical entregue

```text
Manager/admin abre o dashboard
→ escolhe Solicitado, Detectado ou Autorizado
→ vê quatro contagens exclusivas de casos em resumo compacto
→ não vê volume de componentes nem matriz de conversão
→ se houver agendamento combinado confirmado, vê um indicador secundário
→ filtros e lista continuam usando a dimensão escolhida
```

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **Baseline de pytest antes de editar**: confirme árvore limpa, registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no estado inicial. Cole no relatório o exit code e a linha de resumo. Se houver `failed/error` no baseline, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
4. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe visualização analítica futura.
5. **Verificação por inspeção**: além dos testes, rode as buscas `rg` e inspeções descritas neste slice para comprovar os contratos críticos.
6. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O `uv run pytest` final deve ter exit code 0, zero failures/errors e contagem `passed` maior ou igual ao baseline. Se `failed > 0`, `errors > 0`, exit code != 0, ou `passed_final < passed_baseline`, o slice está INCOMPLETO.
7. **Relatório com evidência, não opinião**: cole comandos executados, exit codes, linhas de resumo do pytest baseline/final, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..R6. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

## Objetivo do slice

Substituir o card analítico atual por um resumo compacto e acionável, remover somente a adaptação de apresentação que ficar morta e preservar integralmente domínio, motor analítico, filtros e navegação SSR.

## Requisitos funcionais

### R1. Resumo compacto case-level

O card deve:

- usar `.procedure-summary-card` como marcador estrutural;
- ter título `PROCEDIMENTOS — {{ metrics_period_label }}` sem `POR DIMENSÃO`;
- manter os links SSR para alternar a dimensão;
- renderizar exatamente quatro elementos `.procedure-summary-item`, um para cada row de `procedure_breakdown_rows`;
- mostrar em cada elemento o label e a contagem;
- informar de forma curta que cada caso é contado uma vez.

Usar grid/classes Bootstrap 5.3 já disponíveis. Não criar CSS.

### R2. Rótulos compreensíveis e consistentes

Manter as chaves técnicas e URLs, alterando somente o texto visível:

- `declared` → `Solicitado (NIR)`;
- `detected` → `Detectado (análise)`;
- `approved` → `Autorizado (médico)`.

Atualizar `DIMENSION_LABELS` como fonte única. O select `name="procedure_dimension"` da lista deve iterar a mesma coleção de dimensões usada pelos links, evitando três options hardcoded com labels divergentes. Badges/títulos dimensionais da lista devem refletir os novos labels sem alterar a projeção de dados.

### R3. Comparação avançada ausente da visão principal

O HTML do dashboard não deve conter nem esconder em outro componente:

- `BREAKDOWN POR CATEGORIA`;
- `VOLUME DE PROCEDIMENTOS`;
- `MATRIZ DE CONVERSÃO`;
- `Casos contam uma vez por categoria · Procedimentos ≠ casos`;
- `Componentes ≠ casos`;
- tabela/células declarado→detectado→autorizado.

Não substituir por accordion, `<details>`, modal, gráfico, link novo ou CSS `display:none`.

### R4. Analytics e filtros preservados

Não alterar o contrato nem a lógica de `compute_procedure_analytics()` além dos labels constantes permitidos em R2. Seus resultados `breakdown`, `volume`, `matrix` e `paired_confirmed` devem continuar existindo e os testes atuais devem continuar passando.

Preservar:

- `procedure_dimension=declared|detected|approved` e fallback seguro;
- `procedure_selection` e sua composição com busca/status/datas/atenção/escopo/paginação;
- `_procedure_dimension_links()` e preservação da query string;
- partial `_case_list.html`, `X-ATS-Partial` e `dashboard_search.js` sem alterações;
- guards `manager`/`admin`.

### R5. Remoção local de código de apresentação morto

Remover de `apps/dashboard/views.py` somente o que ficar sem consumidor após R3:

- `_matrix_display_rows()`;
- contexto `procedure_volume`;
- contexto `procedure_matrix_rows`;
- contexto `procedure_matrix_detected_keys`;
- contexto `procedure_category_labels`;
- contexto genérico `procedure_analytics`, substituindo-o por um valor escalar com nome explícito para R6;
- `procedure_total_cases`, caso não seja exibido pelo resumo final.

Não mover, dividir, generalizar nem parametrizar `compute_procedure_analytics()`. Não apagar testes internos de volume/matriz para “fazer o novo teste passar”.

### R6. Agendamento combinado por exceção

Passar ao template uma chave escalar explícita, preferencialmente `procedure_paired_confirmed`, e renderizar `Agendamentos combinados confirmados: N` somente quando `N > 0`.

- com zero: nenhum título, placeholder ou card vazio;
- positivo: uma única ocorrência compacta;
- o contador continua independente da dimensão ativa e conta cada par uma vez.

## Arquivos esperados e limite de escopo

Arquivos de produto/teste permitidos — **cap de 5**:

1. `templates/dashboard/index.html`
2. `apps/dashboard/views.py`
3. `apps/dashboard/procedure_analytics.py` — somente labels de R2
4. `apps/dashboard/tests/test_dashboard.py`
5. `apps/dashboard/tests/test_procedure_analytics.py`

Artefato de controle permitido ao concluir:

6. `openspec/changes/simplify-dashboard-procedure-card/tasks.md`

### Arquivos proibidos / fora de escopo

- `apps/cases/`, models, migrations, FSM e eventos;
- `apps/intake/`, `apps/doctor/`, `apps/scheduler/`, `apps/pipeline/`;
- `static/css/` e `static/js/`;
- settings, URLs, middleware, permissões, templates base e infraestrutura;
- specs canônicas fora do delta deste change.

Se acreditar que um sexto arquivo de produto/teste é indispensável, **pare antes de editá-lo**, reporte bloqueio e peça aprovação. Não use o relatório como autorização retroativa.

## TDD obrigatório

### RED

Antes de alterar produto:

1. Adicione teste estrutural que exija `.procedure-summary-card`, quatro `.procedure-summary-item`, título compacto e as quatro categorias.
2. Adicione teste que proíba no HTML todos os títulos/explicações de R3.
3. Adicione teste para labels consistentes no seletor do card, no `select name="procedure_dimension"` e no badge dimensional.
4. Adicione ou ajuste teste que prove os dois ramos de R6: zero ausente e positivo presente uma vez.
5. Ajuste caracterizações antigas que legitimamente esperavam `PROCEDIMENTOS POR DIMENSÃO`/`Declarado`, sem enfraquecer asserções.
6. Rode o subconjunto e registre ao menos uma falha causada pela UI antiga, não por erro de fixture/import.

Comando sugerido para RED/GREEN alvo:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py apps/dashboard/tests/test_procedure_analytics.py -q -k "procedure_summary or procedure_dimension or paired or singular_exam_type_breakdown"
```

Se os nomes criados não casarem com esse `-k`, ajuste o comando e registre no relatório.

### GREEN

- Reescreva somente o bloco do card no template.
- Centralize labels via `DIMENSION_LABELS`/`procedure_dimension_links`.
- Remova apenas contexto/helper de apresentação sem consumidor.
- Faça o subconjunto alvo e todo `apps/dashboard/tests/` passarem.

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py apps/dashboard/tests/test_procedure_analytics.py -q
uv run pytest apps/dashboard/tests/ -q
```

### REFACTOR

- Elimine markup, comentários e contexto mortos deixados pela matriz/volume.
- Prefira nomes explícitos e loop único; não duplique options de dimensão.
- Preserve clean code, DRY e YAGNI.
- Não transforme o motor analítico em framework configurável e não implemente demanda futura.

## Checks de inspeção obrigatórios antes de concluir

Execute e cole comandos/resultados interpretados no relatório:

```bash
rg -n "procedure-summary-card|procedure-summary-item|Solicitado \(NIR\)|Detectado \(análise\)|Autorizado \(médico\)" templates/dashboard/index.html apps/dashboard/procedure_analytics.py

if rg -n "BREAKDOWN POR CATEGORIA|VOLUME DE PROCEDIMENTOS|MATRIZ DE CONVERSÃO|Componentes ≠ casos|procedure_volume|procedure_matrix_rows|procedure_matrix_detected_keys|procedure_category_labels|_matrix_display_rows" templates/dashboard/index.html apps/dashboard/views.py; then
  echo "ERRO: apresentação avançada ou adaptação morta ainda presente"
  exit 1
else
  echo "OK: apresentação avançada e adaptação morta ausentes"
fi

rg -n "def compute_procedure_analytics|\"breakdown\"|\"volume\"|\"matrix\"|\"paired_confirmed\"" apps/dashboard/procedure_analytics.py apps/dashboard/tests/test_procedure_analytics.py
rg -n "procedure_dimension|procedure_selection|X-ATS-Partial|AbortController" templates/dashboard/index.html templates/dashboard/_case_list.html static/js/dashboard_search.js

git diff --name-only "$BASE_REF"
git diff --stat "$BASE_REF"
git diff --exit-code "$BASE_REF" -- apps/cases apps/intake apps/doctor apps/scheduler apps/pipeline static/css static/js config
```

Interprete explicitamente:

- por que as ocorrências positivas são esperadas;
- que o check negativo terminou com `OK`;
- que o motor ainda contém volume/matriz mesmo sem renderização;
- que nenhum arquivo proibido mudou;
- que o cap de cinco arquivos de produto/teste foi respeitado.

## Critérios de sucesso binários

- [ ] R1: card compacto possui marcador, título e exatamente quatro itens case-level.
- [ ] R2: três labels orientados ao usuário vêm da mesma fonte sem mudar chaves técnicas.
- [ ] R3: matriz, volume, tabela técnica e explicações não aparecem nem ficam escondidos.
- [ ] R4: testes existentes de breakdown/volume/matriz/filtros continuam verdes.
- [ ] R5: helper/contexto morto foi removido sem refactor amplo do analytics.
- [ ] R6: indicador casado é ausente em zero e único quando positivo.
- [ ] Busca, partial, paginação, período, escopo e permissões não regrediram.
- [ ] Nenhum CSS/JS/model/migration/FSM/app proibido foi alterado.
- [ ] No máximo cinco arquivos de produto/teste foram tocados.
- [ ] RED real, GREEN, inspeções e quality gate completo estão documentados.
- [ ] Pytest final tem exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] `tasks.md` foi marcado somente depois de todos os itens anteriores.

## Gates de autoavaliação

Responder objetivamente no relatório:

1. Qual teste prova que o card tem exatamente quatro categorias e que cada valor é case-level?
2. Qual teste/inspeção prova que matriz, volume e explicações não estão no HTML nem escondidos?
3. Como `declared|detected|approved` permaneceram inalterados apesar dos novos labels?
4. Onde está a fonte única dos labels e como o select deixou de duplicá-los?
5. Quais testes existentes provam que `volume` e `matrix` continuam corretos internamente?
6. Qual evidência prova os ramos zero e positivo de `procedure_paired_confirmed`?
7. Quais chaves/helper mortos foram removidos da view?
8. Como dimensão, seleção, filtros, paginação, partial e JS foram preservados?
9. Quais arquivos mudaram, por que cada um era necessário e o cap foi respeitado?
10. Quais foram exit code/resumo do pytest baseline e final? `passed_final >= passed_baseline` e zero failures/errors?

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- baseline completo de pytest antes de editar não foi executado ou não foi registrado com exit code e resumo;
- RED não falhou pelo motivo funcional esperado;
- quality gate completo não foi executado;
- qualquer teste, ruff ou mypy falhou;
- pytest final teve exit code diferente de 0, `failed > 0` ou `errors > 0`;
- contagem final de `passed` ficou menor que a contagem baseline;
- relatório cita apenas quantidade de `passed` sem registrar explicitamente exit code 0 e zero failures/errors;
- `tasks.md` foi marcado apesar de falha ou pendência;
- card não possui exatamente quatro itens case-level;
- qualquer matriz, painel de volume, explicação técnica ou comparação escondida permanece no dashboard;
- `compute_procedure_analytics()` perde ou altera `volume`, `matrix`, breakdown ou semântica de paired;
- chaves técnicas de dimensão/filtro, busca, paginação, partial ou permissões mudam;
- indicador de agendamento combinado ocupa espaço quando zero ou duplica quando positivo;
- CSS, JS, model, migration, FSM ou app proibido é alterado;
- mais de cinco arquivos de produto/teste são tocados sem aprovação prévia;
- relatório temporário não é criado no caminho exigido;
- commit/push é feito antes de todos os gates passarem.

## Relatório obrigatório

Criar exatamente:

```text
/tmp/simplify-dashboard-procedure-card-slice-001-report.md
```

Estrutura mínima:

```markdown
# Relatório do slice 001

## Status
Status: COMPLETE | INCOMPLETE

## Matriz requisito → arquivo(s) → teste(s)
| Requisito | Arquivos | Testes/inspeções |
| --- | --- | --- |

## Baseline e BASE_REF

## RED
- Comando, exit code, teste falhando e motivo esperado.

## GREEN e REFACTOR

## Snippets antes/depois
- Card/template.
- Contexto/helper da view.
- Fonte de labels/select.

## Checks de inspeção
- Comandos, resultados e interpretação.

## Pytest baseline vs final
- BASE_REF.
- Baseline: exit code, passed, failed, errors.
- Final: exit code, passed, failed, errors.
- Comparação passed_final >= passed_baseline.

## Quality gate completo
- uv run ruff check .
- uv run ruff format --check .
- uv run mypy .
- uv run pytest

## Gates de autoavaliação

## Handoff para verificador
- Arquivos alterados.
- Comandos exatos para rerun.
- Riscos/limitações.
- Checklist R1..R6.
```

Incluir diff/cap, commit e push. A seção final `Status: COMPLETE` só pode existir com todas as evidências verdes.

## Prompt pronto para implementador DeepSeek4-Flash

```text
Read AGENTS.md, PROJECT_CONTEXT.md, ADR-0004, the canonical exam-type-analytics spec and every artifact in openspec/changes/simplify-dashboard-procedure-card/ first. Then inspect the current dashboard template, view, analytics module and both dashboard test files listed by Slice 001.

Implement ONLY Slice 001. Follow the DeepSeek4-Flash protocol literally: clean-tree check, BASE_REF, full pytest baseline before editing, requirement→file→test plan, real RED, minimal GREEN, local REFACTOR, mandatory rg/diff inspections, full quality gate and baseline-vs-final comparison. If any baseline/test/check/gate is missing or failing, pytest final has any failure/error, passed_final < passed_baseline, or the five-file product/test cap would be exceeded, report INCOMPLETE and do not update tasks.md or commit/push.

Deliver one compact SSR procedure summary with exactly four case-level categories, labels Solicitado (NIR)/Detectado (análise)/Autorizado (médico), no component-volume panel and no conversion matrix. Show paired confirmed only when positive. Preserve compute_procedure_analytics outputs/tests, technical query keys, dimension+selection filters, period, scope, pagination, partial search, JS and manager/admin permissions. Remove only dead presentation helper/context. Do not add CSS/JS, hidden advanced UI, models, migrations, FSM or changes outside dashboard.

Run the exact validation commands, mark only Slice 001/DoD in tasks.md after all criteria pass, create /tmp/simplify-dashboard-procedure-card-slice-001-report.md with evidence and verifier handoff, commit with a traceable message, push the current branch, reply REPORT_PATH=<path> and STOP for planner review.
```
