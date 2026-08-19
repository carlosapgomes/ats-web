<!-- markdownlint-disable MD013 -->

# Slice 001: Default diário completo, backlog ativo e atenção transversal

## Handoff para implementador LLM com contexto zero

Você está no monolito Django SSR em `/projects/dev/ats-web`. Este é o **único slice** do change `dashboard-today-all-states-default`. Não existe slice futuro a antecipar.

Leia integralmente, nesta ordem, antes de planejar ou editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/dashboard-today-all-states-default/proposal.md`
4. `openspec/changes/dashboard-today-all-states-default/design.md`
5. `openspec/changes/dashboard-today-all-states-default/specs/dashboard-case-list/spec.md`
6. `openspec/changes/dashboard-today-all-states-default/tasks.md`
7. este arquivo
8. `openspec/specs/dashboard-case-list/spec.md` — contrato canônico atual da `v0.4.0` que este delta modifica
9. `apps/cases/models.py` — somente para confirmar `CaseStatus.CLEANED` e campos de data; não editar
10. `apps/dashboard/views.py` — `_dashboard_case_list_context()`, `_attention_q()`, `_procedure_dimension_links()` e `dashboard_index()`
11. `templates/dashboard/index.html` — períodos, “Atenção necessária” e `case-filter-form`
12. `templates/dashboard/_case_list.html` — paginação e preservação de parâmetros
13. `static/js/dashboard_search.js` — `getFilterParams()`, debounce e partial SSR
14. `apps/dashboard/tests/test_dashboard.py` — helpers e classes de métricas, busca, atenção, escopo e paginação

### Estado atual esperado

- Ausência, vazio ou valor inválido de `case_scope` resolve para `active`.
- `active` exclui `CLEANED` e não aplica data implícita; por isso backlog ativo antigo aparece e encerrados de hoje somem.
- `case_scope=all` remove somente a exclusão por estado e, sem datas, consulta todo o histórico.
- `date_from` e `date_to` já filtram `Case.created_at` e são independentes de `metrics_period`.
- Métricas usam `today` por padrão; `_compute_stage_waiting()` continua snapshot global.
- O select de escopo existe. Links/JS propagam principalmente `all`, porque `active` era o default.
- “Atenção necessária” exclui `CLEANED`; o contador padrão considera backlog global.
- O backend já usa `Paginator(cases_qs, 20)` e `get_elided_page_range`; não reimplemente paginação.
- O dashboard é restrito por `@login_required` e `@role_required("manager", "admin")`.

Se qualquer premissa divergir, registre no relatório antes de editar. Se houver conflito funcional, worktree sujo, baseline vermelho ou necessidade de model/migration/URL/outro app, reporte **INCOMPLETE/BLOQUEADO** e pare em vez de improvisar.

### Fluxo vertical a entregar

```text
Manager abre /dashboard/
→ backend resolve all + data local de hoje
→ lista mostra recebidos hoje ativos e CLEANED
→ manager clica “Casos ativos”
→ backend remove data implícita, aplica active e mostra backlog antigo não CLEANED
→ manager volta e clica “Atenção necessária”
→ backend usa active sem data implícita e mostra backlog problemático antigo
→ escopo/datas sobrevivem a submit SSR, paginação e busca parcial
```

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Siga este protocolo literalmente. **Se qualquer item falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma matriz `Requisito → arquivo(s) → teste(s)/inspeção`. Não implemente requisito sem teste ou justificativa explícita.
2. **Worktree e baseline antes de editar**:
   - confirme `git status --short` limpo;
   - confirme branch atribuída ao change; não implemente diretamente em `main` sem autorização explícita;
   - use somente o PostgreSQL de testes dedicado conforme `AGENTS.md`;
   - registre `BASE_REF=$(git rev-parse HEAD)`;
   - rode `uv run pytest` no estado inicial limpo;
   - cole exit code e resumo explícito com `passed`, `failed=0` e `errors=0`.
   Se worktree não estiver limpo ou baseline tiver falha/erro, pare e reporte INCOMPLETE/BLOQUEADO.
3. **RED real**: edite primeiro somente `apps/dashboard/tests/test_dashboard.py`. Atualize os testes cujo contrato `active` default foi explicitamente superado e adicione os novos cenários. Rode o subconjunto alvo. Pelo menos um teste deve falhar porque o código ainda usa o default antigo ou porque o atalho/preservação não existe. RED por import, sintaxe, fixture, banco ou selector frágil não conta.
4. **GREEN mínimo**: altere somente os quatro arquivos de produção permitidos e implemente R1–R7. Não altere métricas, atenção, paginação, permissões ou outros apps.
5. **REFACTOR seguro**: aplique clean code, DRY e YAGNI apenas no trecho tocado. Um helper privado pequeno para resolver defaults é aceitável; dataclass, form, service, template tag ou refactor genérico de query strings não são.
6. **Verificação por inspeção**: execute todos os comandos `rg`, testes alvo, escopo Git e `git diff --check` descritos neste slice. Cole output/resumo e interpretação no relatório.
7. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O pytest final deve ter exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
8. **Relatório com evidência, não opinião**: registre baseline, RED/GREEN, snippets antes/depois, inspeções, quality gate, diff de escopo e respostas aos gates. Inclua `Handoff para verificador` com arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R8. Só escreva `Status: COMPLETE` quando tudo estiver comprovado.
9. **Conclusão controlada**: somente após todos os gates passarem, marque Slice 001 e os itens comprovados em `tasks.md`, faça commit rastreável, push da branch atual, atualize o relatório com commit/push, responda com `REPORT_PATH` e pare.

## Objetivo do slice

Entregar de ponta a ponta a jornada inicial “Recebidos hoje + Todos os estados”, mantendo dois acessos operacionais explícitos e sem recorte diário: backlog em “Casos ativos” e backlog problemático em “Atenção necessária”.

É um único slice porque backend, SSR, partial, JavaScript e testes compartilham a mesma resolução de parâmetros. Separá-los criaria slices horizontais e estados intermediários em que paginação ou busca mudariam silenciosamente o escopo.

## Contexto técnico e restrições

- Django 5.2+, PostgreSQL, templates SSR, Bootstrap 5.3 e Vanilla JS.
- “Recebido hoje” = `Case.created_at` na data local de `timezone.localdate()`.
- “Todos os estados” = `case_scope=all`, isto é, não excluir `CLEANED`; não criar enum de status.
- “Ativo” = `status != CaseStatus.CLEANED`, independentemente de data.
- `?case_scope=all` explicitamente informado e sem datas deve continuar consultando histórico completo.
- `?case_scope=active` explicitamente informado e sem datas deve continuar consultando backlog ativo completo.
- `attention=1` sem datas deve ser transversal; datas explicitamente fornecidas pelo usuário continuam compondo por AND.
- `metrics_period` não deve ser aplicado à lista. O default diário da lista usa apenas `date_from`/`date_to` existentes.
- O partial deve continuar sem computar métricas.
- Não relaxe decorators, não mude `_attention_q()`, thresholds, contagens, ordenação, page size ou faixa elidida.

## Escopo funcional

### R1. Resolver default inicial como hoje + todos os estados

Em `_dashboard_case_list_context()`:

- aceitar somente `case_scope=active|all` como valores válidos;
- para request inicial sem escopo válido, sem atenção e sem datas explícitas, resolver:
  - `case_scope = "all"`;
  - `date_from = timezone.localdate().isoformat()`;
  - `date_to = timezone.localdate().isoformat()`;
- vazio ou inválido sem datas também cai nesse default, sem erro e sem abrir o histórico completo;
- devolver os valores efetivos no contexto para que select e inputs exibam o estado real;
- aplicar escopo e datas antes da paginação;
- incluir `CLEANED` de hoje e excluir casos antigos pelo recorte de criação.

Não reutilizar `metrics_period`, não criar `date=today` e não alterar campos/timestamps.

### R2. Preservar seleções explícitas e histórico

A resolução deve distinguir defaults de intenção explícita:

- `?case_scope=all` sem datas: todos os estados, todas as datas;
- `?case_scope=active` sem datas: apenas não `CLEANED`, todas as datas;
- `?case_scope=all&date_from=&date_to=`: datas permanecem vazias;
- qualquer data não vazia fornecida pelo usuário continua sendo aplicada normalmente;
- `active&status=CLEANED` continua vazio, sem rewrite mágico;
- o botão “Limpar” continua apontando à URL canônica e agora retorna ao default hoje/all.

Use solução coesa e mínima. Se criar helper, mantenha-o privado em `apps/dashboard/views.py` e cubra seu comportamento pela view, não por API nova.

### R3. Manter backlog ativo facilmente acessível

Em `templates/dashboard/index.html`:

- manter o select de escopo e suas duas opções;
- fazer o default refletir `all` e a visão de backlog refletir `active`;
- adicionar ação visível com texto **Casos ativos** (ou “Ver casos ativos” contendo esse texto);
- o href deve enviar `case_scope=active` e não enviar `date_from`/`date_to`;
- a ação deve abrir o backlog sem depender de JavaScript;
- não criar página, rota, CSS ou listener de mudança para limpar datas.

O select continua servindo para composições avançadas; o atalho é o caminho rápido para todas as datas.

### R4. Preservar atenção como acesso transversal

Backend e template devem garantir:

- `?attention=1` sem escopo/datas resolve como `active` e datas vazias;
- o link “Atenção necessária” envia `attention=1` e `case_scope=active`;
- esse link não herda `date_from`/`date_to` do default diário;
- caso antigo que já satisfaz `_attention_q(now)` aparece;
- `CLEANED` continua excluído pela regra existente;
- datas fornecidas explicitamente com `attention=1` continuam sendo respeitadas;
- `_attention_q()`, `ATTENTION_*`, contador e thresholds não são modificados.

Preserve os demais parâmetros do link apenas conforme comportamento atual e sem impedir a transversalidade temporal. Não expanda o escopo para redefinir busca/procedimento em atenção.

### R5. Preservar modalidade na navegação SSR

Como `all` passa a ser default inicial, omitir o escopo pode mudar intenção. Ajuste localmente:

- links dos presets/formulários de métricas preservam o `case_scope` resolvido (`active` ou `all`);
- paginação em `_case_list.html` preserva ambos os escopos;
- datas não vazias continuam preservadas;
- links de dimensão derivados de `request.GET` continuam funcionais;
- o `case-filter-form` contém exatamente um controle `name="case_scope"` e não preserva `page`;
- histórico explícito sem datas não recebe hoje ao paginar;
- backlog ativo sem datas não recebe hoje ao paginar;
- fallback GET sem JavaScript permanece funcional.

Não criar template tag/utilitário global de query string e não reescrever a paginação.

### R6. Preservar modalidade na busca parcial

Em `static/js/dashboard_search.js::getFilterParams()`:

- localizar o select de escopo já existente;
- enviar seu valor atual tanto para `active` quanto para `all`;
- continuar enviando `date_from`/`date_to` somente quando não vazios;
- manter `DASHBOARD_SEARCH_DEBOUNCE_MS`, `DASHBOARD_SEARCH_MIN_CHARS`, `AbortController`, `X-ATS-Partial`, history update e fallback SSR;
- não adicionar framework, endpoint, listener ou arquivo JS.

O anti-pattern proibido é continuar omitindo `active` com `scopeSelect.value !== 'active'`, pois a busca voltaria ao default all/today.

### R7. Preservar contratos não relacionados

Não alterar:

- `_compute_summary`, `_compute_stage_waiting`, `_compute_admission_flow`, `_compute_average_times` ou procedure analytics;
- `_attention_q`, thresholds e contador de atenção;
- `Paginator(cases_qs, 20)`, `get_elided_page_range`, ordenação e resumo X–Y/Z;
- partial leve sem métricas;
- permissões manager/admin;
- models, migrations, FSM, eventos, URLs, settings, CSS, dependências ou outros apps.

Se um teste de outro arquivo revelar impacto real, pare e consulte o planner antes de adicionar sexto arquivo funcional.

### R8. Cobertura TDD comportamental

Atualize a cobertura contraditória da `v0.4.0` e adicione testes em `apps/dashboard/tests/test_dashboard.py`, preferencialmente em classe coesa `TestDashboardTodayAllStatesDefault` ou nomes equivalentes. Cobrir no mínimo:

1. default mostra hoje ativo e hoje `CLEANED`, mas não antigos;
2. contexto default contém `case_scope == "all"` e datas iguais a `timezone.localdate().isoformat()`;
3. vazio/inválido sem datas usa hoje/all;
4. `?case_scope=all` sem datas restaura histórico ativo + `CLEANED`;
5. datas explicitamente vazias não reaplicam hoje;
6. `?case_scope=active` inclui ativo antigo, exclui `CLEANED` e deixa datas vazias;
7. ação visível “Casos ativos” aponta para active sem datas;
8. `?attention=1` inclui caso problemático antigo, resolve active e deixa datas vazias;
9. link de atenção contém active e não contém datas do default;
10. atenção com datas explícitas respeita o intervalo;
11. links/paginação/partial preservam `active` e `all` corretamente;
12. JS envia ambos os escopos e mantém debounce/cancelamento/header;
13. paginação continua 20/elidida e permissões permanecem cobertas pelas regressões existentes.

Não mantenha testes afirmando que `/dashboard/` default inclui ativo antigo e exclui `CLEANED`; esse requisito foi explicitamente superado. Não remova cobertura de `active`, histórico, paginação ou permissões: adapte-a aos parâmetros explícitos.

## Arquivos esperados e limite de escopo

Arquivos funcionais permitidos, máximo de cinco:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html`
4. `static/js/dashboard_search.js`
5. `apps/dashboard/tests/test_dashboard.py`

Após todos os gates, o único arquivo adicional permitido é:

- `openspec/changes/dashboard-today-all-states-default/tasks.md`

É proibido alterar/criar:

- `apps/cases/models.py`, services de casos ou qualquer model;
- migrations, URLs, decorators, middleware, settings ou permissões;
- outros apps ou arquivos de teste de outros apps;
- CSS, dependências, `pyproject.toml` ou `uv.lock`;
- template tags, forms Django, endpoint/API, DRF, HTMX ou framework JS;
- artefatos OpenSpec de outros changes/specs durante a implementação.

Qualquer arquivo funcional extra exige parar e consultar o planner. Não basta justificar depois; sem autorização explícita, arquivo extra torna o slice INCOMPLETE/BLOQUEADO.

## TDD obrigatório: RED → GREEN → REFACTOR

### 1. Preparação e baseline

Antes de editar:

```bash
git status --short
BASE_REF=$(git rev-parse HEAD)
printf 'BASE_REF=%s\n' "$BASE_REF"
uv run pytest
```

Se necessário, suba somente o banco de teste conforme `AGENTS.md`. Não mude settings para contornar infraestrutura.

Registre hash, exit code, resumo completo, `failed=0`, `errors=0` e `passed_baseline`.

### 2. RED real

Edite primeiro apenas `apps/dashboard/tests/test_dashboard.py`. Atualize os testes superseded e escreva os novos comportamentos antes do código de produção. Rode:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v -k 'today_all_states or active_backlog or attention_transversal'
```

Se escolher nomes diferentes, adapte somente a expressão `-k`, registre o comando exato e garanta que ele selecione os novos testes.

Resultado obrigatório: exit code não zero e pelo menos uma falha semântica esperada, por exemplo:

- `CLEANED` de hoje ainda é omitido no default;
- ativo antigo ainda aparece no default;
- contexto ainda resolve `active` e datas vazias;
- link “Casos ativos” não existe;
- escopo active se perde em paginação/busca.

RED por erro de sintaxe/import/fixture/infraestrutura não vale. Teste que passa antes da implementação precisa ser reforçado ou justificado como regressão, não contado como RED.

### 3. GREEN mínimo

Implemente R1–R7 somente nos quatro arquivos de produção permitidos. Rode:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v -k 'today_all_states or active_backlog or attention_transversal'
uv run pytest apps/dashboard/tests/test_dashboard.py -q
```

Todos devem passar. Não enfraqueça asserts nem altere factories globais para mascarar o comportamento.

### 4. REFACTOR seguro

Revise os cinco arquivos:

- defaults resolvidos em um único trecho/helper coeso;
- sem condicionais duplicadas evitáveis para data implícita;
- nomes deixam clara a diferença entre escopo explícito e efetivo;
- templates preservam parâmetros sem abstração genérica;
- JS sempre envia o escopo atual;
- nenhum código morto, refactor amplo ou comportamento futuro;
- comentários antigos que afirmam `active` default foram atualizados.

Rode novamente os testes alvo depois de qualquer refactor.

## Checks de inspeção obrigatórios antes de concluir

Execute todos e cole resultado + interpretação no relatório.

### I1. Resolução backend e contratos preservados

```bash
rg -n 'case_scope|timezone\.localdate|date_from|date_to|attention_filter|CaseStatus\.CLEANED|Paginator\(cases_qs, 20\)|get_elided_page_range' apps/dashboard/views.py
```

Confirme hoje/all inicial, active sem data para atenção/backlog, exclusão de `CLEANED` apenas quando aplicável e paginação inalterada.

### I2. Controles e links SSR

```bash
rg -n 'Casos ativos|Atenção necessária|name="case_scope"|case_scope=|date_from|date_to|metrics_period' templates/dashboard/index.html templates/dashboard/_case_list.html
```

Confirme ação ativa visível sem datas, atenção ativa sem datas, controle único e preservação de ambos os escopos/datas em navegação comum.

### I3. Partial não pode preservar somente all

```bash
if rg -n "case_scope == 'all'" templates/dashboard/_case_list.html; then
  echo 'ERRO: paginação ainda condiciona preservação somente ao escopo all'
  exit 1
else
  echo 'OK: paginação não trata all como único escopo preservável'
fi
```

### I4. Busca parcial envia ambos os escopos

```bash
rg -n 'scopeSelect|case_scope|AbortController|DASHBOARD_SEARCH_DEBOUNCE_MS|DASHBOARD_SEARCH_MIN_CHARS|X-ATS-Partial' static/js/dashboard_search.js
if rg -n "scopeSelect\.value !== 'active'|scopeSelect\.value != 'active'" static/js/dashboard_search.js; then
  echo 'ERRO: JS ainda omite active e pode voltar ao novo default'
  exit 1
else
  echo 'OK: JS não usa o antigo active-default para omitir escopo'
fi
```

Interprete também se `params.set('case_scope', scopeSelect.value)` ou comportamento equivalente cobre os dois valores sem remover debounce/cancelamento/header.

### I5. Atenção não foi redefinida

```bash
rg -n 'ATTENTION_PROCESSING_STUCK_AFTER|ATTENTION_WAITING_STUCK_AFTER|def _attention_q|def _get_attention_reason' apps/dashboard/views.py
git diff "$BASE_REF" -- apps/dashboard/views.py | rg -n 'ATTENTION_|_attention_q|_get_attention_reason' || true
```

A primeira busca deve encontrar os contratos existentes. O diff não deve mostrar alteração de thresholds/critério; apenas contexto de chamada/resolução de defaults pode aparecer.

### I6. Testes, escopo e higiene

```bash
rg -n 'today_all_states|active_backlog|attention_transversal|case_scope|CLEANED|localdate|date_from|date_to' apps/dashboard/tests/test_dashboard.py
git diff --check
git diff --name-only "$BASE_REF" -- | sort
git status --short
```

Antes de marcar tasks, a lista deve conter somente os cinco arquivos funcionais. Depois, pode conter também `openspec/changes/dashboard-today-all-states-default/tasks.md`. Qualquer outro arquivo é bloqueio.

### I7. Testes alvo finais

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v -k 'today_all_states or active_backlog or attention_transversal'
uv run pytest apps/dashboard/tests/test_dashboard.py -q
```

Se a expressão foi adaptada, registre o comando exato e prove que todos os novos testes foram selecionados.

## Critérios de sucesso binários

- [ ] S1. Worktree inicial limpo, branch autorizada, `BASE_REF` registrado e baseline completo verde.
- [ ] S2. Matriz requisito→arquivo→teste foi escrita antes da implementação.
- [ ] S3. RED real capturado antes de código de produção por comportamento antigo ainda presente.
- [ ] S4. `/dashboard/` resolve all + hoje/hoje no contexto.
- [ ] S5. Default lista hoje ativo e hoje `CLEANED`, e exclui casos antigos.
- [ ] S6. Vazio/inválido sem datas cai para hoje/all sem erro nem histórico completo.
- [ ] S7. `?case_scope=all` explícito e datas vazias mantêm histórico sem limite temporal.
- [ ] S8. `?case_scope=active` mantém backlog antigo ativo, exclui `CLEANED` e não recebe datas.
- [ ] S9. Ação “Casos ativos” é visível, SSR e não contém datas.
- [ ] S10. `?attention=1` sem filtros usa active sem datas e alcança caso problemático antigo.
- [ ] S11. Link de atenção não herda datas do default; datas explícitas ainda compõem.
- [ ] S12. Nenhum threshold, critério ou contador de atenção foi redefinido.
- [ ] S13. Scope active/all e datas sobrevivem a links SSR, paginação, dimensão e partial.
- [ ] S14. JS envia ambos os escopos e mantém debounce, mínimo, AbortController e header partial.
- [ ] S15. Form contém um único `name="case_scope"`, não preserva page e fallback sem JS funciona.
- [ ] S16. Métricas/períodos, snapshot de espera e analytics permanecem independentes da lista.
- [ ] S17. Paginação continua server-side em 20, elidida, acessível e com resumo X–Y/Z.
- [ ] S18. Partial continua leve e permissões manager/admin não foram relaxadas.
- [ ] S19. Testes alvo e arquivo completo do dashboard passam.
- [ ] S20. Todos os checks I1–I7 foram executados e interpretados.
- [ ] S21. Somente cinco arquivos funcionais permitidos foram alterados; nenhum arquivo proibido mudou.
- [ ] S22. Quality gate completo passou com pytest final exit 0, `failed=0`, `errors=0` e `passed_final >= passed_baseline`.
- [ ] S23. Relatório temporário contém matriz, baseline, RED/GREEN, snippets, inspeções, rerun, gates e handoff.
- [ ] S24. `tasks.md` foi atualizado somente após S1–S23; commit e push foram concluídos.

## Gates de autoavaliação

Responda objetivamente no relatório, citando teste, linha ou comando:

1. Qual população exata `/dashboard/` mostra agora? Prove com quatro casos: hoje ativo, hoje `CLEANED`, antigo ativo e antigo `CLEANED`.
2. Qual timezone/data define “hoje”? Foi usado `timezone.localdate()` em vez de `date.today()`?
3. “Hoje” significa recebimento ou atividade? A resposta correta é `created_at`/recebimento; cite o limite.
4. Como o código distingue ausência de escopo de `case_scope=all` explícito?
5. O que ocorre com `case_scope=` vazio ou inválido sem datas? Ele pode abrir todo o histórico? A resposta correta é não.
6. `?case_scope=all` sem datas ainda abre ativos e `CLEANED` antigos? Qual teste prova compatibilidade?
7. Datas explicitamente vazias continuam vazias após render, busca e paginação?
8. `?case_scope=active` inclui um caso antigo não `CLEANED` e exclui um antigo `CLEANED`? Qual teste prova?
9. Onde está a ação visível “Casos ativos”? Seu href contém alguma data? A resposta correta é não.
10. `?attention=1` direto, sem parâmetros, aplica hoje? A resposta correta é não. Qual teste prova com caso antigo?
11. O link de atenção da carga inicial inclui `case_scope=active` e omite `date_from/date_to`?
12. Datas explícitas em atenção são respeitadas? Qual teste prova composição?
13. Algum threshold, `_attention_q()` ou contador mudou? A resposta correta é não; mostre diff/inspeção.
14. Paginação preserva active e all explicitamente? Mostre hrefs/testes de ambos.
15. Busca parcial sempre envia o valor atual do select? O antigo `!== 'active'` desapareceu?
16. Debounce, mínimo de três caracteres, `AbortController` e `X-ATS-Partial` permanecem?
17. Métricas continuam usando `metrics_period`, e a lista continua usando `date_from/date_to`? Houve acoplamento indevido?
18. `Paginator(..., 20)`, faixa elidida e partial sem métricas permanecem intactos?
19. Permissões, models, migrations, FSM, URLs, CSS e dependências permaneceram intactos?
20. Quais arquivos mudaram desde `BASE_REF`? Coincidem exatamente com o limite?
21. Qual teste falhou no RED e por que a falha era semanticamente correta?
22. Qual foi a contagem pytest baseline/final? Final teve exit 0, zero failures/errors e `passed_final >= passed_baseline`?
23. Houve necessidade real de abstração além de helper privado pequeno? Se sim, por que não viola YAGNI?
24. Qual risco residual permanece? Cite que casos antigos ativos não aparecem no default, mas ficam acessíveis por “Casos ativos” e atenção.

## Condições automáticas de INCOMPLETO

Marque **INCOMPLETE/BLOQUEADO**, não atualize `tasks.md` e não faça commit/push se ocorrer qualquer situação:

- worktree inicial sujo ou implementação fora de branch autorizada;
- baseline completo ausente, não registrado ou com exit code diferente de 0/falha/erro;
- matriz requisito→arquivo→teste ausente;
- teste planejado não escrito/executado;
- ausência de RED real antes da implementação;
- RED causado por sintaxe/import/fixture/infraestrutura em vez do contrato;
- teste antigo contraditório apenas removido sem cobertura equivalente do novo default e do active explícito;
- teste enfraquecido para permitir GREEN incorreto;
- default não resolver all + hoje/hoje;
- `CLEANED` de hoje continuar omitido ou caso antigo continuar no default;
- vazio/inválido sem datas expor histórico completo;
- `case_scope=all` explícito perder acesso histórico;
- datas explicitamente vazias receberem hoje silenciosamente;
- `case_scope=active` receber filtro diário ou incluir `CLEANED`;
- ação “Casos ativos” ausente, dependente de JS ou com datas;
- `attention=1` receber default diário ou deixar caso problemático antigo inacessível;
- link de atenção herdar datas do default;
- data explícita de atenção ser ignorada;
- `_attention_q`, thresholds ou contador de atenção serem alterados;
- active/all se perder em links, paginação ou busca parcial;
- JS ainda omitir active pelo antigo default;
- debounce, mínimo, `AbortController`, header partial ou fallback SSR ser removido;
- métricas serem acopladas ao filtro da lista;
- paginação 20/elidida, resumo ou partial leve regredir;
- permissão existente ser relaxada;
- qualquer model, migration, FSM, URL, settings, CSS, dependência, outro app ou arquivo funcional extra ser alterado;
- qualquer check I1–I7 não ser executado ou revelar anti-pattern proibido;
- `git diff --check` falhar;
- testes alvo ou arquivo de dashboard falharem;
- quality gate completo não ser executado;
- qualquer ruff, format, mypy ou pytest falhar;
- pytest final ter exit code != 0, `failed > 0` ou `errors > 0`;
- `passed_final < passed_baseline`;
- relatório registrar só quantidade de passed sem exit code e zero failures/errors explícitos;
- relatório temporário não existir no caminho exigido;
- relatório não conter RED/GREEN, snippets antes/depois, comandos de rerun ou `Handoff para verificador`;
- `tasks.md` ser marcado antes de todos os gates;
- commit/push ser feito apesar de gate faltante ou falho.

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
/tmp/dashboard-today-all-states-default-slice-001-report.md
```

O arquivo é temporário e não deve ser commitado. Estrutura mínima obrigatória:

```markdown
# Relatório — dashboard-today-all-states-default — Slice 001

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
- Arquivo de teste alterado primeiro:
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
- Antes: resolução active sem data
- Depois: resolução hoje/all e distinção explícita
- Antes/depois: links Casos ativos/Atenção
- Antes/depois: preservação SSR da paginação
- Antes/depois: preservação de ambos os escopos no JS
- Antes/depois: testes principais

## Checks de inspeção obrigatórios
- I1 backend: comando, output e interpretação
- I2 templates: comando, output e interpretação
- I3 partial: comando e exit code
- I4 JS: comandos, output e interpretação
- I5 atenção: comandos, diff e interpretação
- I6 escopo/higiene: comandos, output e interpretação
- I7 testes alvo: comandos, exit codes e resumos

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
24. ...

## Riscos e limitações residuais
- “Hoje” usa created_at, não atividade/conclusão do dia.
- Backlog antigo sai do default, mas permanece em Casos ativos/Atenção.
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
REPORT_PATH=/tmp/dashboard-today-all-states-default-slice-001-report.md
```

O handoff ao verificador deve incluir no mínimo:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v -k 'today_all_states or active_backlog or attention_transversal'
uv run pytest apps/dashboard/tests/test_dashboard.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
rg -n 'case_scope|timezone\.localdate|date_from|date_to|attention_filter|CaseStatus\.CLEANED|Paginator\(cases_qs, 20\)' apps/dashboard/views.py
rg -n 'Casos ativos|Atenção necessária|name="case_scope"|case_scope=|date_from|date_to' templates/dashboard/index.html templates/dashboard/_case_list.html
rg -n 'scopeSelect|case_scope|AbortController|X-ATS-Partial' static/js/dashboard_search.js
git diff --check "$BASE_REF"..HEAD
git show --stat --oneline HEAD
```

## Prompt pronto para implementador DeepSeek4-Flash

```text
Read completely: AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-today-all-states-default/proposal.md, design.md, specs/dashboard-case-list/spec.md, tasks.md, slices/slice-001-today-all-active-attention.md, openspec/specs/dashboard-case-list/spec.md, apps/cases/models.py, apps/dashboard/views.py, templates/dashboard/index.html, templates/dashboard/_case_list.html, static/js/dashboard_search.js and the relevant sections of apps/dashboard/tests/test_dashboard.py.

Implement ONLY Slice 001. Follow the DeepSeek4-Flash protocol literally: require a clean worktree and authorized branch, record BASE_REF, run full pytest baseline before editing, write/update dashboard tests first, capture a semantic RED, implement GREEN minimally, refactor safely with clean code/DRY/YAGNI, run every mandatory inspection and diff-scope check, execute the complete quality gate, compare pytest baseline-vs-final and create the required evidence report.

Deliver one vertical flow: /dashboard/ defaults to received today in every state (effective case_scope=all and date_from=date_to=timezone.localdate); today active and CLEANED cases appear while older cases do not. Preserve explicit ?case_scope=all without dates as complete history. Preserve explicit ?case_scope=active without dates as all-date active backlog. Add a visible SSR “Casos ativos” action with no dates. Keep “Atenção necessária” transversal: its link and direct ?attention=1 use active without implicit dates, while user-supplied attention dates still compose. Preserve both active and all through metric links, pagination and progressive partial search. The JS must send the current scope for both values, not omit active under the old default.

Touch only apps/dashboard/views.py, templates/dashboard/index.html, templates/dashboard/_case_list.html, static/js/dashboard_search.js and apps/dashboard/tests/test_dashboard.py, then update only this change's tasks.md after every gate passes. Do not touch models, migrations, FSM, URLs, permissions, settings, CSS, dependencies, template tags or other apps/tests. Do not alter metrics, _compute_stage_waiting, procedure analytics, _attention_q, attention thresholds/counts, Paginator(cases_qs, 20), get_elided_page_range, ordering, partial optimization, debounce, minimum search length, AbortController, X-ATS-Partial or no-JS fallback. Do not create date=today, activity-today semantics, a new page, endpoint, framework or generic query-string abstraction.

Use TDD RED -> GREEN -> REFACTOR. At least one new/updated test must fail before production code for the expected old behavior. Adapt the superseded v0.4 default tests, but preserve equivalent explicit active/history regression coverage. Test deterministic local dates and an old attention-worthy case.

If baseline fails, RED is accidental, any required test/inspection/quality gate is missing/failing, pytest final has any failure/error or exit code != 0, passed_final < passed_baseline, explicit history/active mode is lost, attention receives today's date, active is omitted in JS/pagination, a forbidden contract changes, or any extra functional file changes, report INCOMPLETE/BLOQUEADO. Do not update tasks.md and do not commit/push in that case.

If and only if all criteria pass: update openspec/changes/dashboard-today-all-states-default/tasks.md, create /tmp/dashboard-today-all-states-default-slice-001-report.md with baseline, RED/GREEN, before/after snippets, inspections and interpretations, complete quality gate, pytest comparison, all 24 self-evaluation answers, changed-file proof and Handoff para verificador. Commit with a traceable message such as `fix(dashboard): alinhar lista inicial aos recebidos hoje`, push the current branch, update the temporary report with commit/push evidence, reply exactly with REPORT_PATH=/tmp/dashboard-today-all-states-default-slice-001-report.md, and STOP for planner review.
```
