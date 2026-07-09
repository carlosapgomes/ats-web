<!-- markdownlint-disable MD013 -->

# Slice 004: Busca dinâmica progressiva

## Contexto zero para implementador

Este slice depende dos Slices 001, 002 e 003 completos. A busca server-side por
`search` já deve funcionar por submit tradicional e já deve ter índices
PostgreSQL.

Agora precisamos melhorar a experiência: após o usuário digitar pelo menos 3
caracteres no campo de busca, o dashboard deve atualizar a lista de casos sem
recarregar a página inteira. O sistema continua sendo SSR puro: a resposta do
servidor deve ser HTML parcial, não JSON, e sem framework JS.

Arquivos principais:

- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- novo partial `templates/dashboard/_case_list.html`
- novo JS `static/js/dashboard_search.js`
- `apps/dashboard/tests/test_dashboard.py`

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/dashboard-metrics-search-ux/proposal.md`
- `openspec/changes/dashboard-metrics-search-ux/design.md`
- `openspec/changes/dashboard-metrics-search-ux/tasks.md`
- slices anteriores deste change
- este slice

## Objetivo do slice

Entregar fluxo vertical completo:

```text
Manager/admin abre dashboard
→ digita 3 caracteres em "Buscar por nome ou registro"
→ Vanilla JS aguarda debounce
→ faz fetch SSR parcial para /dashboard/
→ servidor retorna HTML dos cards e paginação
→ lista é atualizada sem reload completo
→ sem JS, o submit tradicional continua funcionando
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html`
4. `static/js/dashboard_search.js`
5. `apps/dashboard/tests/test_dashboard.py`

Se precisar tocar outro arquivo, justificar no relatório.

## Requisitos funcionais

### R1. Partial SSR para lista de casos

Extrair a renderização dos cards, estado vazio e paginação para:

```text
templates/dashboard/_case_list.html
```

`index.html` deve incluir esse partial. Isso evita duplicação entre renderização
normal e renderização parcial.

A view `dashboard_index` deve retornar apenas o partial quando receber um header
explícito, por exemplo:

```text
X-ATS-Partial: case-list
```

Não usar JSON. Não criar API REST.

### R2. Container atualizável

Adicionar um container com id estável no template, por exemplo:

```html
<div id="dashboard-case-list" data-dashboard-search-target>
  {% include "dashboard/_case_list.html" %}
</div>
```

O JS deve substituir apenas o conteúdo desse container.

### R3. JavaScript Vanilla com debounce

Criar `static/js/dashboard_search.js` com:

- escopo restrito ao dashboard;
- debounce entre 300 ms e 500 ms;
- fetch somente quando termo normalizado tiver 3 ou mais caracteres;
- fetch também quando o campo for esvaziado, para limpar a busca;
- nenhum fetch para termos com 1 ou 2 caracteres;
- preservação dos outros filtros do formulário;
- atualização de `history.replaceState` para refletir `search` na URL;
- tratamento simples de erro sem quebrar o formulário tradicional.

### R4. Evitar respostas antigas

Usar uma das abordagens:

- `AbortController` para cancelar request anterior; ou
- contador sequencial para ignorar resposta antiga.

Isso evita resultado fora de ordem quando o usuário digita rápido.

### R5. Fallback sem JavaScript

O formulário existente deve continuar com submit normal. Não remover o botão
`Filtrar`.

A busca dinâmica deve ser melhoria progressiva. Se o JS falhar, o dashboard
continua usável.

### R6. Paginação

Links de paginação do partial devem preservar `search` e os filtros existentes,
como no Slice 003.

Não é obrigatório interceptar cliques de paginação via JS neste slice. É
aceitável que a paginação faça navegação normal, desde que preserve filtros.

## TDD obrigatório

Antes de implementar, adicionar testes falhando onde possível.

Testes mínimos de Django/template:

1. GET `/dashboard/` renderiza `id="dashboard-case-list"`.
2. GET `/dashboard/` inclui `static/js/dashboard_search.js`.
3. GET `/dashboard/` inclui o markup extraído sem duplicar lista.
4. GET `/dashboard/` com header `X-ATS-Partial: case-list` retorna apenas o
   partial, sem `base.html` completo.
5. Partial com `?search=ana` contém caso esperado e exclui caso não esperado.
6. Paginação do partial preserva `search`.
7. Arquivo JS contém debounce e regra de mínimo de 3 caracteres.

Se o projeto não tiver infraestrutura de browser test, não adicionar Selenium ou
Playwright neste slice. Testar o contrato SSR e a presença do JS é suficiente.

## Critérios de sucesso

- [ ] Testes foram escritos antes da implementação e falharam inicialmente.
- [ ] Lista e paginação estão em partial DRY.
- [ ] View retorna partial HTML com header explícito.
- [ ] JS dispara fetch apenas com 3 ou mais caracteres, ou campo vazio.
- [ ] JS usa debounce.
- [ ] JS cancela ou ignora resposta antiga.
- [ ] Sem JavaScript, submit tradicional continua funcional.
- [ ] Sem JSON, DRF, SPA, WebSocket ou SSE.
- [ ] Quality gate do `AGENTS.md` passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Qual teste prova que o partial não renderiza a página completa?
2. Onde está o container atualizado pelo JS?
3. Qual mecanismo evita respostas antigas?
4. Qual regra impede fetch com 1 ou 2 caracteres?
5. O formulário continua funcionando sem JS? Como foi preservado?
6. A paginação preserva `search`?
7. Foi criado JSON ou API REST? Se sim, está errado.
8. O relatório contém snippets antes/depois dos pontos principais?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-metrics-search-ux/proposal.md, design.md, tasks.md and slices/slice-001 through slice-004.
Assume Slices 001, 002 and 003 are complete. Implement ONLY Slice 004.
Use TDD: first add failing tests for the partial rendering contract, template hooks and JS inclusion, then implement minimal code.
Follow clean code, DRY and YAGNI. Do not introduce a JS framework, JSON endpoint, DRF, SPA, WebSocket or SSE.
Extract the dashboard case list markup into templates/dashboard/_case_list.html and include it from index.html.
Make dashboard_index return that partial when header X-ATS-Partial: case-list is present.
Create static/js/dashboard_search.js with Vanilla JS debounce, min 3 characters, empty-term reset, filter preservation and stale-response cancellation or ignoring.
Keep the normal form submit as fallback. Do not intercept pagination unless needed; preserving query params is enough.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Create a detailed temporary markdown report with before/after snippets and self-evaluation answers.
Run markdownlint-cli2 only on markdown files you create, such as the temporary report. Do not lint or rewrite existing markdown broadly.
Commit and push only implementation files created/changed for this slice. Do not commit OpenSpec files before final archival of the change.
Return REPORT_PATH=<path> and stop. Do not start any next slice without explicit confirmation.
```
