<!-- markdownlint-disable MD013 -->

# Slice 001: Reorganizar seletor de período como toolbar/card responsivo

## Contexto zero para implementador

Projeto Django SSR em `/projects/dev/ats-web`. Leia primeiro:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/dashboard-period-selector-ui-polish/proposal.md`
4. `openspec/changes/dashboard-period-selector-ui-polish/design.md`
5. `openspec/changes/dashboard-period-selector-ui-polish/tasks.md`
6. este arquivo

O dashboard fica em:

- `templates/dashboard/index.html`
- `static/css/app.css`
- `apps/dashboard/tests/test_dashboard.py`

O seletor `Período das métricas` já é funcional e aceita:

- `metrics_period=today|7d|30d|all`
- `metrics_period=custom_date&metrics_date=YYYY-MM-DD`
- `metrics_period=custom_range&metrics_start=YYYY-MM-DD&metrics_end=YYYY-MM-DD`

Não altere regra de negócio.

## Objetivo

Melhorar a UI/UX do seletor para desktop e mobile:

- card/toolbar compacto;
- botões alinhados e com padrão hospitalar;
- `Personalizado` integrado ao grupo visual;
- mobile em grid responsivo, sem botão avulso desalinhado.

## Arquivos esperados

Tocar apenas:

1. `templates/dashboard/index.html`
2. `static/css/app.css`
3. `apps/dashboard/tests/test_dashboard.py`
4. `openspec/changes/dashboard-period-selector-ui-polish/tasks.md` ao concluir

## Requisitos

### R1. Card/toolbar

O seletor deve renderizar com classes semânticas:

- `.metrics-period-card`
- `.metrics-period-options`
- `.metrics-period-option`
- `.metrics-period-custom-panel`

### R2. Sem Bootstrap primary no seletor

Dentro do bloco `id="metrics-period-selector"`, não usar:

- `btn-group`
- `btn-primary`
- `btn-outline-primary`

Use classes próprias + CSS hospitalar.

### R3. Responsivo

CSS deve garantir:

- desktop: opções alinhadas em uma linha quando houver espaço;
- mobile: grid de 2 colunas para presets e `Personalizado` em largura total;
- inputs do personalizado não geram overflow.

### R4. Funcionalidade preservada

Manter:

- links dos presets com preservação de filtros;
- `<details>` para personalizado;
- dois mini-forms SSR independentes;
- hidden inputs existentes;
- `id="case-filter-form"` e busca dinâmica sem regressão.

## TDD obrigatório

Antes de implementar, adicione testes falhando em `apps/dashboard/tests/test_dashboard.py`:

1. `test_metrics_period_selector_uses_hospital_toolbar_classes`
   - GET `/dashboard/` contém `.metrics-period-card`, `.metrics-period-options`, `.metrics-period-option`, `.metrics-period-custom-panel`.

2. `test_metrics_period_selector_does_not_use_bootstrap_primary_group`
   - extrair trecho entre `id="metrics-period-selector"` e o fechamento do card/bloco;
   - assert que não contém `btn-group`, `btn-primary`, `btn-outline-primary`.

3. `test_metrics_period_selector_css_has_responsive_rules`
   - ler `static/css/app.css`;
   - assert contém `.metrics-period-options`, `.metrics-period-option.is-active`, `@media (max-width: 575.98px)` e `.metrics-period-custom`.

Depois implemente o mínimo para passar e refatore mantendo clean code, DRY e YAGNI.

## Critérios de aceitação

- [ ] UI visualmente alinhada em desktop e mobile.
- [ ] Sem regressão funcional do personalizado.
- [ ] Sem JS novo.
- [ ] Sem alteração de view/calculadoras de métricas.
- [ ] Sem models/migrations/FSM/permissões.
- [ ] Testes adicionados passam.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Quais classes novas controlam a toolbar?
2. Como o mobile evita botão `Personalizado` desalinhado?
3. O slice alterou algum cálculo de métrica ou query param? Não deveria.
4. Os mini-forms SSR de `Personalizado` continuaram independentes?
5. Algum JS novo foi criado? Não deveria.

## Validação

Executar pelo menos:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -q -k "metrics_period_selector or personalizado or custom_metrics"
uv run ruff check apps/dashboard/tests/test_dashboard.py
uv run ruff format --check apps/dashboard/tests/test_dashboard.py
```

Antes de finalizar:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório esperado

Criar:

```text
/tmp/ats-web-slice-001-dashboard-period-selector-ui-polish-report.md
```

Conteúdo:

- resumo;
- arquivos alterados;
- snippets antes/depois;
- evidência RED/GREEN;
- validações;
- respostas aos gates de autoavaliação.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-period-selector-ui-polish/proposal.md, design.md, tasks.md and slices/slice-001-period-selector-toolbar.md.
Implement ONLY Slice 001. Use TDD: add failing structural tests first, then change templates/dashboard/index.html and static/css/app.css minimally. Keep clean code, DRY and YAGNI. Do not alter views, metrics calculations, query params, models, migrations, FSM, permissions or add JS. Preserve the existing SSR mini-forms for Personalizado. Run validations, create /tmp/ats-web-slice-001-dashboard-period-selector-ui-polish-report.md, commit and push, reply REPORT_PATH and stop.
```
