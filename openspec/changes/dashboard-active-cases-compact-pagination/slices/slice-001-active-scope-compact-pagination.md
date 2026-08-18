<!-- markdownlint-disable MD013 -->

# Slice 001: Escopo ativo/histórico e paginação compacta no dashboard

## Handoff para implementador LLM com contexto zero

Você está no monolito Django SSR em `/projects/dev/ats-web`. Este é o único slice do change `dashboard-active-cases-compact-pagination`.

Leia integralmente, nesta ordem, antes de planejar ou editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/dashboard-active-cases-compact-pagination/proposal.md`
4. `openspec/changes/dashboard-active-cases-compact-pagination/design.md`
5. `openspec/changes/dashboard-active-cases-compact-pagination/specs/dashboard-case-list/spec.md`
6. `openspec/changes/dashboard-active-cases-compact-pagination/tasks.md`
7. este arquivo
8. `apps/cases/models.py` — `CaseStatus`, especialmente `CLEANED`
9. `apps/dashboard/views.py` — `_dashboard_case_list_context()`, `_procedure_dimension_links()` e `dashboard_index()`
10. `templates/dashboard/index.html` — links de período, header e formulário `case-filter-form`
11. `templates/dashboard/_case_list.html` — cards e paginação atual
12. `static/js/dashboard_search.js` — `getFilterParams()` e fetch parcial
13. `apps/dashboard/tests/test_dashboard.py` — helpers, testes de busca/paginação/partial e contratos do layout

### Estado atual esperado

- A listagem usa `Paginator(cases_qs, 20)`; a paginação já é server-side.
- O queryset inicial inclui todo o histórico.
- O partial percorre `page_obj.paginator.page_range`, renderizando um link para cada página.
- Não existe parâmetro `case_scope`.
- A busca dinâmica usa `/dashboard/` + header `X-ATS-Partial: case-list` e preserva filtros selecionados.
- `CLEANED` é o único escopo histórico a excluir do default; não invente uma nova lista de estados ativos.
- O acesso ao dashboard continua restrito a manager/admin.

Se qualquer premissa divergir, registre antes de editar. Se houver conflito funcional, worktree sujo ou necessidade de alterar model/migration/URL/outro app, reporte **INCOMPLETE/BLOQUEADO** e pare em vez de improvisar.

### Fluxo vertical a entregar

```text
Manager abre /dashboard/
→ backend resolve case_scope=active
→ casos CLEANED ficam fora, mas backlog antigo não CLEANED permanece
→ queryset filtrado é paginado em blocos de 20
→ template mostra intervalo/total e poucos links com reticências
→ manager escolhe “Todos (inclui encerrados)”
→ case_scope=all sobrevive a filtros, paginação, métricas e busca parcial
```

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Siga o protocolo literalmente. **Se qualquer item falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma matriz `Requisito → arquivo(s) → teste(s)/inspeção`. Não implemente requisito sem teste ou justificativa explícita.
2. **Worktree e baseline antes de editar**:
   - confirme `git status --short` limpo;
   - confirme que está na branch atribuída ao change; não faça implementação diretamente em `main` sem autorização explícita;
   - garanta que somente o PostgreSQL de testes dedicado está disponível conforme `AGENTS.md`;
   - registre `BASE_REF=$(git rev-parse HEAD)`;
   - rode `uv run pytest` no estado inicial limpo;
   - cole exit code e linha de resumo com `passed`, `failed` e `errors`.
   Se o worktree estiver sujo ou o baseline tiver falha/erro, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: edite primeiro somente `apps/dashboard/tests/test_dashboard.py` e rode o subconjunto alvo. Pelo menos um teste novo deve falhar porque o default ainda inclui `CLEANED`, `case_scope=all` ainda não existe semanticamente, a faixa ainda contém todos os números ou o resumo ainda não existe. RED por import, sintaxe, fixture ou infraestrutura não conta.
4. **GREEN mínimo**: altere apenas os quatro arquivos de produção previstos e faça os testes alvo passarem. Preserve `Paginator(..., 20)`, use `Paginator.get_elided_page_range` e não crie algoritmo próprio.
5. **REFACTOR seguro**: aplique clean code, DRY e YAGNI apenas dentro do escopo. Use nomes claros, funções coesas e contexto mínimo. Não faça refactor geral de URLs/templates, não crie template tag genérica e não antecipe cursor pagination.
6. **Verificação por inspeção**: execute todos os comandos `rg`, escopo Git e `git diff --check` deste slice. Cole resultado e interpretação no relatório.
7. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O pytest final deve ter exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
8. **Relatório com evidência, não opinião**: registre baseline, RED/GREEN, snippets antes/depois, testes, inspeções, quality gate, diff de escopo e respostas aos gates. Inclua `Handoff para verificador` com arquivos alterados, comandos de rerun, riscos/limitações e checklist R1–R8. Só escreva `Status: COMPLETE` quando tudo estiver comprovado.
9. **Conclusão controlada**: somente após todos os gates passarem, marque Slice 001 e os itens comprovados em `tasks.md`, atualize o relatório, faça commit rastreável, push da branch atual, acrescente commit/push ao relatório, responda com `REPORT_PATH` e pare.

## Objetivo do slice

Entregar em um fluxo end-to-end a lista gerencial com escopo operacional seguro por padrão e navegação compacta, mantendo acesso explícito ao histórico e compatibilidade SSR/Vanilla JS.

É vertical porque modifica a resolução server-side, os controles e a renderização SSR, a melhoria progressiva existente e os testes observáveis pelo usuário no mesmo slice.

## Contexto técnico e restrições

- Django 5.2+, templates SSR e Bootstrap 5.3.
- Vanilla JS apenas; sem endpoint novo e sem resposta JSON.
- QuerySets são lazy. Não alegue que o change “introduz paginação server-side”; ele preserva a paginação já existente e corrige escopo/nav.
- `CaseStatus.CLEANED` é histórico. “Ativo” = `status != CLEANED`, sem data implícita.
- `case_scope=active` é default canônico; `case_scope=all` é opt-in.
- Filtros incompatíveis compõem normalmente. `active` + `status=CLEANED` retorna vazio; não reescreva silenciosamente o pedido.
- A lista e as métricas têm períodos independentes; não aplique `metrics_period` à query da lista.
- O partial deve continuar evitando computar métricas.
- Não relaxe `@login_required`/`@role_required("manager", "admin")`.

## Escopo funcional

### R1. Resolver escopo com fallback seguro

Em `_dashboard_case_list_context()`:

- ler `case_scope`;
- aceitar somente `active` e `all`;
- resolver ausente, vazio ou inválido como `active`;
- para `active`, excluir `CaseStatus.CLEANED` do queryset da lista;
- para `all`, não aplicar exclusão de escopo;
- devolver o valor resolvido no contexto.

A exclusão deve ocorrer antes da paginação e compor com atenção, busca, procedimento, status e datas. Não filtrar por data atual.

### R2. Expor controle de escopo coerente

Em `templates/dashboard/index.html`:

- trocar o título enganoso `Todos os Casos` por `Casos`;
- adicionar ao `case-filter-form` um select visível, associado por `label for`/`id`, com `name="case_scope"`;
- opções exatas ou semanticamente equivalentes: `Casos ativos` (`active`) e `Todos (inclui encerrados)` (`all`);
- refletir o valor resolvido com `selected`;
- “Limpar” deve voltar à URL canônica e ao default ativo;
- não duplicar `name="case_scope"` em hidden dentro do mesmo form.

### R3. Preservar escopo em navegação SSR

Quando `case_scope == "all"`, preservar `case_scope=all` em:

- links dos presets de métricas (`Hoje`, `7 dias`, `30 dias`, `Tudo`);
- botão/filtro “Atenção necessária”;
- todos os links da paginação no partial.

Os links de dimensão derivados de `request.GET` já devem preservar o parâmetro; adicione teste/inspeção, não reimplemente o helper sem necessidade.

`active` pode ser omitido por ser default. Não preservar `page` ao submeter novos filtros.

### R4. Preservar escopo na busca parcial

Em `static/js/dashboard_search.js`:

- localizar o select `case_scope` em `getFilterParams()`;
- incluir `case_scope=all` quando selecionado;
- omitir `active` por ser default canônico;
- manter debounce, mínimo de caracteres, `AbortController`, filtros existentes e fallback SSR intactos.

Não criar novo arquivo JS, framework, endpoint ou listener desnecessário.

### R5. Preparar faixa elidida no backend

Depois de obter `page_obj`, criar contexto de paginação com `paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)` ou janela igualmente pequena previamente justificada.

Requisitos:

- usar a API Django, não algoritmo próprio;
- manter `Paginator(cases_qs, 20)`;
- não materializar o queryset completo;
- a faixa deve ser limitada independentemente do total de páginas.

### R6. Renderizar paginação compacta e acessível

Em `templates/dashboard/_case_list.html`:

- iterar sobre a faixa elidida do contexto, nunca sobre `page_obj.paginator.page_range` completo;
- renderizar reticências como item desabilitado/não clicável;
- manter primeira, última, atual, vizinhas, Anterior e Próxima conforme a faixa;
- marcar página atual com `aria-current="page"`;
- identificar o nav com id estável, por exemplo `id="case-pagination"`, para teste sem falso positivo;
- permitir wrap da lista Bootstrap em viewport estreita;
- preservar todos os filtros atuais e `case_scope=all` nos hrefs.

### R7. Mostrar intervalo e total filtrado

Quando houver pelo menos um caso, exibir texto equivalente a:

```text
Exibindo 21–40 de 1.312 casos
```

Usar `page_obj.start_index`, `page_obj.end_index` e `page_obj.paginator.count`. O texto deve refletir o queryset após todos os filtros. Não mostrar `0–0` no estado vazio.

### R8. Cobertura de regressão e preservação

Adicionar testes claros em `apps/dashboard/tests/test_dashboard.py`, preferencialmente em classes coesas como `TestDashboardActiveCaseScope` e `TestDashboardCompactPagination`, cobrindo no mínimo:

1. default inclui caso antigo não `CLEANED` e exclui `CLEANED`;
2. `case_scope=all` inclui ativo e `CLEANED`;
3. valor inválido cai para ativo;
4. `active` + `status=CLEANED` retorna vazio sem rewrite mágico;
5. select reflete active/all e `case_scope=all` aparece em links relevantes;
6. JavaScript contém preservação funcional de `case_scope` sem remover contratos existentes;
7. com muitas páginas e página intermediária, a faixa tem primeira/atual/última, reticências e quantidade limitada, sem todos os números;
8. página contém no máximo 20 cards/itens e resumo X–Y/Z correto;
9. partial com `case_scope=all` mantém o escopo nos links e continua retornando somente a lista;
10. manager/admin permanecem autorizados e papel não autorizado continua bloqueado pelos testes existentes.

Para casos antigos, altere `created_at` de forma determinística; não dependa do relógio além de `timezone.localdate()`. Isole o nav por id/contexto para que números das métricas não satisfaçam asserts de paginação. Evite centenas de inserts lentos quando `bulk_create` ou um número menor suficiente puder provar elisão.

## Arquivos esperados e limite de escopo

Arquivos funcionais permitidos, máximo de cinco:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html`
4. `static/js/dashboard_search.js`
5. `apps/dashboard/tests/test_dashboard.py`

Após todos os gates, o único arquivo adicional permitido é:

- `openspec/changes/dashboard-active-cases-compact-pagination/tasks.md`

É proibido alterar/criar:

- `apps/cases/models.py` ou qualquer model;
- migrations;
- URLs, decorators, middleware, settings ou permissões;
- outros apps ou testes de outros apps;
- CSS novo, dependências, `pyproject.toml` ou `uv.lock`;
- templates tags, endpoint/API, DRF, HTMX ou framework JS.

Qualquer arquivo funcional extra exige parar e consultar o planner. Não basta justificar depois: com o design atual, arquivo extra torna o slice INCOMPLETE/BLOQUEADO.

## TDD obrigatório: RED → GREEN → REFACTOR

### 1. Preparação e baseline

Antes de editar:

```bash
git status --short
BASE_REF=$(git rev-parse HEAD)
printf 'BASE_REF=%s\n' "$BASE_REF"
uv run pytest
```

Se necessário, suba somente o banco de teste conforme `AGENTS.md`. Não altere settings para contornar problema ambiental.

Registre hash, exit code, resumo completo, `failed=0`, `errors=0` e `passed_baseline`.

### 2. RED real

Edite primeiro apenas `apps/dashboard/tests/test_dashboard.py`. Crie os testes comportamentais de R8 antes da implementação e rode:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v -k 'active_scope or compact_pagination'
```

Se os nomes escolhidos forem diferentes, ajuste apenas a expressão `-k` e registre-a. Resultado obrigatório: exit code não zero e pelo menos um teste falhando por comportamento ausente. Exemplos de RED válido:

- `CLEANED` ainda aparece sem parâmetro;
- `case_scope=all` não é refletido no controle/links;
- nav ainda possui todos os números;
- resumo de intervalo não existe.

Não aceite RED por import, banco, erro de factory, selector frágil ou sintaxe.

### 3. GREEN mínimo

Implemente R1–R7 somente nos quatro arquivos de produção previstos. Rode:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v -k 'active_scope or compact_pagination'
```

Todos os testes alvo devem passar. Depois rode o arquivo completo:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -q
```

Não enfraqueça asserts para acomodar o código.

### 4. REFACTOR seguro

Revise os cinco arquivos:

- resolução do escopo centralizada uma vez;
- nomes de contexto e testes claros;
- uso direto de `get_elided_page_range`;
- nenhuma duplicação nova evitável dentro do trecho alterado;
- template acessível e sem código morto;
- JS apenas preserva o novo parâmetro;
- nenhum comportamento futuro ou abstração genérica.

Rode os testes alvo novamente após qualquer refactor.

## Checks de inspeção obrigatórios antes de concluir

Execute todos os comandos e cole resultado + interpretação no relatório.

### I1. Backend e contrato de paginação

```bash
rg -n 'case_scope|CaseStatus\.CLEANED|get_elided_page_range|Paginator\(cases_qs, 20\)' apps/dashboard/views.py
```

Confirme que há fallback ativo, exclusão apenas no escopo ativo, paginação de 20 e API Django de elisão.

### I2. Template e preservação

```bash
rg -n 'name="case_scope"|Casos ativos|inclui encerrados|case_scope=all|case-pagination|aria-current|Exibindo|ELLIPSIS' templates/dashboard/index.html templates/dashboard/_case_list.html
```

Confirme controle único, links preservados, nav identificável, página atual acessível, resumo e reticências não clicáveis.

### I3. Ausência do anti-pattern original

```bash
if rg -n 'page_obj\.paginator\.page_range' templates/dashboard/_case_list.html; then
  echo 'ERRO: partial ainda percorre todas as páginas'
  exit 1
else
  echo 'OK: partial não percorre page_range completo'
fi
```

### I4. Busca parcial e preservação dos contratos existentes

```bash
rg -n 'case_scope|AbortController|DASHBOARD_SEARCH_DEBOUNCE_MS|DASHBOARD_SEARCH_MIN_CHARS|X-ATS-Partial' static/js/dashboard_search.js
```

Interprete: `case_scope=all` deve ser incluído pela montagem de parâmetros e os contratos de debounce/cancelamento/header devem continuar presentes.

### I5. Testes e escopo do diff

```bash
rg -n 'active_scope|compact_pagination|case_scope|CLEANED|get_elided|Exibindo' apps/dashboard/tests/test_dashboard.py
git diff --check
git diff --name-only "$BASE_REF" -- | sort
git status --short
```

Antes de marcar tasks, a lista deve conter somente os cinco arquivos funcionais. Depois, pode conter também `openspec/changes/dashboard-active-cases-compact-pagination/tasks.md`. Qualquer outro arquivo é bloqueio.

### I6. Testes alvo finais

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v -k 'active_scope or compact_pagination'
uv run pytest apps/dashboard/tests/test_dashboard.py -q
```

Se a expressão `-k` foi adaptada aos nomes reais, registrar o comando exato.

## Critérios de sucesso binários

- [ ] S1. Worktree inicial limpo, `BASE_REF` registrado e baseline completo verde.
- [ ] S2. RED real capturado antes de código de produção, por requisito ausente.
- [ ] S3. Default, vazio e inválido resolvem para `active`.
- [ ] S4. Default exclui apenas `CLEANED` e mantém backlog antigo não `CLEANED`.
- [ ] S5. `case_scope=all` inclui casos ativos e `CLEANED` sem mudar dados.
- [ ] S6. Controle de escopo visível reflete valor resolvido e título do card é coerente.
- [ ] S7. Escopo compõe com filtros; combinação active+CLEANED é vazia sem rewrite.
- [ ] S8. `case_scope=all` sobrevive a métricas, atenção, paginação, dimensão e busca parcial.
- [ ] S9. Submit SSR funciona sem JavaScript e mudança de filtro não preserva `page`.
- [ ] S10. `Paginator(cases_qs, 20)` permanece e a página contém no máximo 20 casos.
- [ ] S11. `get_elided_page_range` é usado com janela limitada; nenhum algoritmo próprio existe.
- [ ] S12. Partial não percorre `page_obj.paginator.page_range` completo.
- [ ] S13. Nav contém primeira/última/atual/vizinhas/reticências quando aplicável, Anterior/Próxima e `aria-current`.
- [ ] S14. Reticências não são links e paginação pode quebrar linha sem overflow horizontal extenso.
- [ ] S15. Resumo X–Y/Z está correto para queryset filtrado e ausente no estado vazio.
- [ ] S16. Partial continua sem computar métricas; permissões não foram relaxadas.
- [ ] S17. Todos os testes alvo e o arquivo completo de dashboard passam.
- [ ] S18. Todos os checks `rg`, diff e escopo foram executados e interpretados.
- [ ] S19. Nenhum arquivo proibido, model, migration, URL, dependência ou outro app foi alterado.
- [ ] S20. Quality gate completo passou com pytest final exit 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] S21. Relatório temporário contém todas as evidências, snippets, rerun e handoff.
- [ ] S22. `tasks.md` foi atualizado apenas depois de S1–S21; commit e push concluídos.

## Gates de autoavaliação

Responda objetivamente no relatório, citando teste, linha ou comando:

1. O backend já era server-side paginado antes? O que exatamente este slice mudou?
2. Qual é a definição única de “caso ativo”? Alguma data foi aplicada implicitamente?
3. Um caso não `CLEANED` de ontem/semana anterior continua visível por default? Qual teste prova?
4. Um `CLEANED` some por default e reaparece com `case_scope=all`? Quais testes provam?
5. Valor inválido expõe histórico ou gera erro? Qual fallback foi comprovado?
6. O que ocorre com `case_scope=active&status=CLEANED`? Houve rewrite mágico?
7. Onde `case_scope=all` é preservado em cada fluxo SSR e no fetch parcial?
8. O formulário contém exatamente um controle `name="case_scope"` e não preserva `page`?
9. Quantos casos no máximo são materializados/renderizados por página? O tamanho 20 foi mantido?
10. Qual chamada Django produz a faixa elidida e qual o máximo esperado de tokens com a janela escolhida?
11. Há qualquer loop remanescente sobre `page_obj.paginator.page_range` no partial? A resposta correta é não.
12. Reticências podem ser clicadas? A resposta correta é não. Qual markup/teste prova?
13. O intervalo X–Y/Z usa total filtrado? Mostre caso de teste com segunda/última página.
14. Busca dinâmica manteve debounce, mínimo de 3 caracteres, cancelamento e header partial?
15. Partial continua sem calcular métricas? Qual teste/regressão existente passou?
16. Permissões manager/admin, modelos, FSM, URLs e migrations permaneceram intactos?
17. Alguma solução fora do escopo — filtro diário, cursor, infinite scroll, API, framework JS — foi introduzida? A resposta correta é não.
18. Quais arquivos mudaram desde `BASE_REF`? Coincidem exatamente com o limite?
19. Qual teste falhou no RED e por que a falha era semanticamente correta?
20. Pytest final teve exit code 0, `failed=0`, `errors=0` e total passed maior ou igual ao baseline? Informe números.
21. Qual risco residual permanece para volumes em que o `COUNT` do Paginator se torne caro? Reconheça que cursor pagination está fora deste change.

## Condições automáticas de INCOMPLETO

Marque **INCOMPLETE/BLOQUEADO**, não atualize `tasks.md` e não faça commit/push se ocorrer qualquer situação:

- worktree inicial sujo ou implementação não isolada em branch autorizada;
- baseline completo não executado/registrado ou com exit code diferente de 0, falha ou erro;
- teste planejado não escrito ou não executado;
- ausência de RED real antes da implementação;
- RED causado por sintaxe/import/fixture/infraestrutura em vez do contrato;
- teste enfraquecido para permitir GREEN incorreto;
- default ainda inclui `CLEANED` ou aplica filtro de dia atual;
- `case_scope=all` não restaura histórico ou não compõe com filtros;
- valor inválido não cai para `active`;
- parâmetro `all` se perde na paginação, links de métricas/atenção ou busca parcial;
- fallback SSR sem JavaScript deixa de funcionar;
- tamanho de página deixa de ser 20 ou queryset completo é materializado;
- algoritmo próprio substitui `get_elided_page_range` sem bloqueio do planner;
- partial ainda percorre `page_obj.paginator.page_range` completo;
- reticências são links, página atual perde acessibilidade ou todos os números continuam renderizados;
- resumo X–Y/Z está ausente/incorreto ou mostra `0–0` no estado vazio;
- debounce, mínimo de busca, `AbortController`, header partial ou permissão existente é removido;
- qualquer model, migration, FSM, URL, dependência, outro app ou arquivo funcional extra é alterado;
- qualquer check `rg` obrigatório não executado ou com ocorrência proibida;
- `git diff --check` falha;
- teste alvo/arquivo de dashboard falha;
- quality gate completo não executado;
- qualquer ruff, format, mypy ou pytest falha;
- pytest final tem exit code != 0, `failed > 0` ou `errors > 0`;
- `passed_final < passed_baseline`;
- relatório registra só quantidade de passed sem exit code e zero failures/errors explícitos;
- relatório temporário não existe no caminho exigido;
- relatório não contém RED/GREEN, snippets antes/depois, comandos de rerun ou `Handoff para verificador`;
- `tasks.md` é marcado antes de todos os gates;
- commit/push é feito apesar de gate faltante ou falho.

Em bloqueio ambiental, preserve evidências e reporte o motivo. Não remova gates nem amplie escopo para contornar.

## Quality gate obrigatório

Após GREEN, REFACTOR e inspeções, execute separadamente e registre cada exit code:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Compare explicitamente:

```text
passed_final >= passed_baseline
failed_final = 0
errors_final = 0
exit_code_final = 0
```

Também execute:

```bash
git status --short
git diff --check
git diff --stat "$BASE_REF"
```

## Relatório markdown temporário obrigatório

Criar exatamente:

```text
/tmp/dashboard-active-cases-compact-pagination-slice-001-report.md
```

O arquivo é temporário e não deve ser commitado. Estrutura mínima:

```markdown
# Relatório — dashboard-active-cases-compact-pagination — Slice 001

## Status
Status: COMPLETE | INCOMPLETE

## Identificação
- Branch:
- BASE_REF:
- Commit final:
- Push remoto:

## Matriz requisito → arquivo(s) → teste(s)/inspeção
| Requisito | Arquivos | Testes/inspeções | Resultado |
| --- | --- | --- | --- |

## Baseline antes de editar
- `git status --short`:
- `uv run pytest`:
- Exit code:
- Resumo: passed=?, failed=0, errors=0

## RED
- Arquivo de teste criado/alterado primeiro:
- Comando:
- Exit code:
- Teste(s) falhando:
- Motivo esperado:
- Trecho de output:

## GREEN
- Implementação mínima por requisito:
- Comandos alvo:
- Exit codes e resumos:

## REFACTOR
- Limpezas realizadas:
- Evidência clean code/DRY/YAGNI:
- Confirmação de nenhum escopo futuro:

## Snippets antes/depois
- Antes: queryset sem escopo e page_range completo (via `git show BASE_REF:...`)
- Depois: resolução active/all
- Depois: faixa elidida e resumo
- Depois: controle/preservação SSR
- Depois: preservação no JS
- Depois: testes principais

## Checks de inspeção obrigatórios
- I1 backend: comando, output e interpretação
- I2 templates: comando, output e interpretação
- I3 ausência de page_range: comando, exit code
- I4 JS: comando, output e interpretação
- I5 escopo/diff: comandos, output e interpretação
- I6 testes alvo: comandos, exit codes e resumos

## Pytest baseline vs final
- Baseline: exit code, passed, failed, errors
- Final: exit code, passed, failed, errors
- `passed_final >= passed_baseline`: Sim/Não

## Quality gate completo
- `uv run ruff check .`: exit code + resumo
- `uv run ruff format --check .`: exit code + resumo
- `uv run mypy .`: exit code + resumo
- `uv run pytest`: exit code + resumo
- `git diff --check`: exit code

## Escopo do diff
- Arquivos alterados desde BASE_REF:
- Confirmação dos arquivos proibidos inalterados:
- Justificativa: deve coincidir exatamente com o slice

## Gates de autoavaliação
1. ...
21. ...

## Riscos e limitações residuais
- `Paginator` ainda executa COUNT; cursor pagination está fora de escopo.
- Outros riscos reais encontrados:

## Handoff para verificador
- Arquivos alterados:
- Commit e branch remota:
- Comandos exatos para rerun:
- Pontos de inspeção manual:
- Riscos/limitações:
- Checklist R1–R8:

## Resultado final
Status: COMPLETE
REPORT_PATH=/tmp/dashboard-active-cases-compact-pagination-slice-001-report.md
```

O handoff ao verificador deve incluir no mínimo:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v -k 'active_scope or compact_pagination'
uv run pytest apps/dashboard/tests/test_dashboard.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
rg -n 'case_scope|CaseStatus\.CLEANED|get_elided_page_range|Paginator\(cases_qs, 20\)' apps/dashboard/views.py
rg -n 'name="case_scope"|case_scope=all|case-pagination|aria-current|Exibindo|ELLIPSIS' templates/dashboard/index.html templates/dashboard/_case_list.html
rg -n 'case_scope|AbortController|X-ATS-Partial' static/js/dashboard_search.js
git diff --check "$BASE_REF"..HEAD
git show --stat --oneline HEAD
```

## Prompt pronto para implementador DeepSeek4-Flash

```text
Read completely: AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-active-cases-compact-pagination/proposal.md, design.md, specs/dashboard-case-list/spec.md, tasks.md, slices/slice-001-active-scope-compact-pagination.md, apps/cases/models.py, apps/dashboard/views.py, templates/dashboard/index.html, templates/dashboard/_case_list.html, static/js/dashboard_search.js and the relevant sections of apps/dashboard/tests/test_dashboard.py.

Implement ONLY Slice 001. Follow the DeepSeek4-Flash protocol literally: require a clean worktree and authorized implementation branch, record BASE_REF, run the full pytest baseline before editing, write dashboard tests first, capture a semantic RED, implement GREEN minimally, refactor safely with clean code/DRY/YAGNI, run every mandatory rg inspection and diff-scope check, execute the complete quality gate, compare baseline-vs-final pytest, and create the evidence report.

Deliver the vertical flow: /dashboard/ defaults to case_scope=active; active means status != CLEANED with no date restriction; case_scope=all explicitly restores historical CLEANED cases; the scope composes with existing filters and survives metric links, attention, pagination, dimension links and progressive partial search; Paginator remains server-side at 20 items; navigation uses Django get_elided_page_range instead of the complete page_range; the UI shows non-clickable ellipses, accessible current page, Previous/Next and the filtered X-Y/Z summary.

Touch only apps/dashboard/views.py, templates/dashboard/index.html, templates/dashboard/_case_list.html, static/js/dashboard_search.js and apps/dashboard/tests/test_dashboard.py, then update only this change's tasks.md after every gate passes. Do not touch models, migrations, FSM, URLs, permissions, settings, dependencies, CSS, template tags or other apps. Do not add a daily default, cursor pagination, infinite scroll, API/JSON, HTMX or any frontend framework. Preserve metrics independence, debounce, minimum search length, AbortController, partial SSR optimization and no-JavaScript fallback.

Use TDD RED -> GREEN -> REFACTOR. At least one new test must fail before production code for the expected missing behavior. Do not invent an elision algorithm; use Paginator.get_elided_page_range. Do not silently rewrite active + status=CLEANED; an empty result is the defined composition.

If baseline fails, RED is accidental, any required test/inspection/quality gate is missing or failing, pytest final has any failure/error or exit code != 0, passed_final < passed_baseline, full page_range remains, all scope is lost, a forbidden contract is found, or any extra functional file changes, report INCOMPLETE/BLOQUEADO. Do not update tasks.md and do not commit/push in that case.

If and only if all criteria pass: update openspec/changes/dashboard-active-cases-compact-pagination/tasks.md, create /tmp/dashboard-active-cases-compact-pagination-slice-001-report.md with baseline, RED/GREEN, before/after snippets, inspections and interpretations, full quality gate, pytest comparison, all self-evaluation answers, changed-file proof and Handoff para verificador. Commit with a traceable message such as `feat(dashboard): priorizar casos ativos e compactar paginacao`, push the current branch, update the temporary report with commit/push evidence, reply exactly with REPORT_PATH=/tmp/dashboard-active-cases-compact-pagination-slice-001-report.md, and STOP for planner review.
```
