<!-- markdownlint-disable MD013 -->

# Slice 001: Polimento visual dos filtros de "Todos os Casos"

## Contexto zero para implementador

Este slice depende do change arquivado `dashboard-metrics-search-ux` completo. O dashboard já possui:

- labels visíveis nos campos de data;
- seletor `metrics_date` para métricas;
- busca server-side por `search`;
- busca dinâmica progressiva via `static/js/dashboard_search.js`;
- partial `templates/dashboard/_case_list.html` para lista/paginação.

O problema agora é puramente de UI/UX: no card "Todos os Casos", o título,
botão "Atenção necessária", busca, status, datas e botão "Filtrar" ficam muito
juntos em uma única faixa horizontal. No desktop parecem desalinhados porque
alguns controles têm label acima e o botão/chip não. No mobile, o agrupamento
tende a ficar confuso.

Referência visual do problema:

```text
tmp/todos-os-casos-card.png
```

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/archive/dashboard-metrics-search-ux/proposal.md`
- `openspec/archive/dashboard-metrics-search-ux/design.md`
- `openspec/archive/dashboard-metrics-search-ux/tasks.md`
- `openspec/changes/dashboard-case-list-filter-layout-polish/proposal.md`
- `openspec/changes/dashboard-case-list-filter-layout-polish/design.md`
- `openspec/changes/dashboard-case-list-filter-layout-polish/tasks.md`
- este slice

## Objetivo do slice

Entregar fluxo vertical completo:

```text
Manager/admin abre dashboard
→ vê o card "Todos os Casos" com header limpo em duas linhas
→ título fica separado dos filtros
→ botão "Atenção necessária" fica no canto direito do header
→ filtros ficam alinhados em grid responsivo abaixo
→ busca continua server-side e dinâmica
→ fallback sem JavaScript continua funcionando
```

## Layout alvo

### Desktop/tablet largo

```text
Todos os Casos                                      [⚠ Atenção necessária (0)]

Buscar por nome ou registro        Status          Data inicial    Data final      Ações
[Digite ao menos 3 caracteres]      [Todos...]      [__/__/____]    [__/__/____]    [Filtrar]
```

### Mobile

```text
Todos os Casos
[⚠ Atenção necessária (0)]

Buscar por nome ou registro
[__________________________]

Status
[Todos os status]

Data inicial                 Data final
[__/__/____]                 [__/__/____]

[Filtrar] [Limpar]
```

## Arquivos esperados

Idealmente tocar apenas:

1. `templates/dashboard/index.html`
2. `apps/dashboard/tests/test_dashboard.py`

Se for necessário CSS customizado, preferir classes Bootstrap existentes. Só
tocar `static/css/app.css` se Bootstrap não resolver, e justificar no relatório.
Não tocar queries, migrations, models, permissões ou FSM.

## Requisitos funcionais

### R1. Header do card em duas linhas lógicas

Separar visualmente:

1. Header do card:
   - título `Todos os Casos` à esquerda;
   - botão/link `⚠ Atenção necessária (N)` à direita em desktop;
   - em mobile, botão abaixo ou ocupando largura adequada.
2. Linha/área de filtros abaixo do header.

Não deixar o botão `Atenção necessária` espremido entre inputs.

### R2. Formulário de filtros em grid responsivo

Usar grid Bootstrap, por exemplo:

```text
Busca:        col-12 col-lg-4
Status:       col-12 col-sm-6 col-lg-2
Data inicial: col-6  col-lg-2
Data final:   col-6  col-lg-2
Ações:        col-12 col-lg-2
```

Usar `row g-2 g-md-3 align-items-end` ou equivalente para alinhar inputs e
botões pela base.

### R3. Busca como campo principal

O campo `Buscar por nome ou registro` deve ter mais largura que os demais no
desktop e ocupar largura total no mobile.

### R4. Labels visíveis e acessíveis

Manter labels visíveis para:

- `search`;
- `status` se possível, com texto `Status`;
- `date_from`;
- `date_to`.

Os labels devem preservar associação `for`/`id` onde aplicável.

### R5. Preservar comportamento existente

A mudança é de layout. Deve preservar:

- submit tradicional sem JavaScript;
- busca dinâmica do Slice 004;
- filtros `status`, `date_from`, `date_to`, `attention`, `metrics_date` e
  `search`;
- contador `attention_count`;
- estado ativo do botão `attention=1`;
- partial `_case_list.html` sem duplicar markup.

### R6. Corrigir `search` duplicado no formulário da lista

Se ainda existir hidden input duplicado:

```html
<input type="hidden" name="search" value="...">
```

no mesmo formulário que já possui:

```html
<input type="search" name="search" ...>
```

remover o hidden duplicado. Ele pode impedir fallback sem JavaScript de trocar
uma busca ativa, porque Django usa o último valor de parâmetros repetidos.

Manter hidden `search` apenas em formulários que não tenham campo visível de
busca, como o formulário de `metrics_date`, se necessário.

### R7. Sem mudança de backend desnecessária

Não alterar a lógica de busca, filtros, métricas, migrations ou índices neste
slice, salvo se um teste revelar regressão causada pelo markup.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

Testes mínimos:

1. Dashboard renderiza o header do card com `Todos os Casos` antes da área de
   filtros.
2. Botão/link `Atenção necessária` aparece no header do card e antes do `<form`
   de filtros no HTML.
3. Formulário contém classes de grid responsivo esperadas (`row`, `g-2` ou
   `g-md-3`, `align-items-end`).
4. Campo de busca está em coluna maior que status/data no desktop, por exemplo
   contém `col-lg-4`.
5. Status tem label visível `Status` associado ao select, preferencialmente com
   `for="status"` e `id="status"`.
6. Labels `Buscar por nome ou registro`, `Data inicial` e `Data final` continuam
   presentes.
7. O formulário da lista não contém dois controles `name="search"` quando
   `?search=ana` está ativo.
8. Hidden `metrics_date` continua presente no formulário da lista quando
   `?metrics_date=YYYY-MM-DD` está ativo.
9. Link `Atenção necessária` preserva `metrics_date` e `search` quando presentes.
10. JS `dashboard_search.js` continua incluído na página.

Não adicionar testes de screenshot/browser neste slice. Testes de contrato HTML
são suficientes.

## Critérios de sucesso

- [ ] Testes foram escritos antes da implementação e falharam inicialmente.
- [ ] Header do card fica visualmente separado dos filtros.
- [ ] `Atenção necessária` não fica mais espremido entre inputs.
- [ ] Formulário usa grid responsivo e campos alinhados pela base.
- [ ] Busca tem destaque/largura maior no desktop.
- [ ] Mobile empilha de forma legível.
- [ ] Labels visíveis e acessíveis foram preservadas.
- [ ] `search` duplicado no formulário da lista foi removido, se existia.
- [ ] Fallback sem JS continua funcional.
- [ ] Busca dinâmica continua funcional.
- [ ] Sem alteração de queries, migrations, models, FSM ou permissões.
- [ ] Quality gate do `AGENTS.md` passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Onde o botão `Atenção necessária` ficou no novo layout?
2. Quais classes Bootstrap garantem o grid responsivo?
3. O campo de busca tem mais largura que status/data no desktop? Onde?
4. Qual teste prova que não há `search` duplicado no formulário da lista?
5. Qual teste prova que `metrics_date` continua preservado?
6. A busca dinâmica foi preservada? Qual hook/ID continua presente?
7. Houve alteração em backend/query/migration/model? Se sim, justificar.
8. O relatório contém snippets antes/depois dos pontos principais?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/archive/dashboard-metrics-search-ux/proposal.md, openspec/archive/dashboard-metrics-search-ux/design.md, openspec/archive/dashboard-metrics-search-ux/tasks.md, openspec/changes/dashboard-case-list-filter-layout-polish/proposal.md, design.md, tasks.md and slices/slice-001-case-list-filter-layout-polish.md.
Assume archived change dashboard-metrics-search-ux is complete. Implement ONLY Slice 001 of dashboard-case-list-filter-layout-polish.
Use TDD: first add failing HTML contract tests for the new two-line/card header layout, then implement minimal template changes.
Follow clean code, DRY and YAGNI. This is a UI layout polish slice: do not change dashboard queries, migrations, models, FSM or permissions.
Target layout: first line has "Todos os Casos" on the left and "Atenção necessária" on the right; second line has a responsive Bootstrap grid with search, status, date_from, date_to and actions. Search should be wider on desktop. Labels must remain visible.
Preserve SSR fallback and dynamic search. Keep id="dashboard-case-list", data-dashboard-search-target, the search input name/id, metrics_date preservation and the dashboard_search.js inclusion.
Remove any duplicated hidden name="search" inside the same filter form that already contains the visible search input.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Create a detailed temporary markdown report with before/after snippets and self-evaluation answers.
Run markdownlint-cli2 only on markdown files you create, such as the temporary report. Do not lint or rewrite existing markdown broadly.
Commit and push only implementation files created/changed for this slice. Do not commit OpenSpec files before final archival of the change.
Return REPORT_PATH=<path> and stop. Do not start any next slice without explicit confirmation.
```
