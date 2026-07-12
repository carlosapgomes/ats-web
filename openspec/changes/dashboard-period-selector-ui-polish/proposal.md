<!-- markdownlint-disable MD013 -->

# Proposal: Polimento visual do seletor de período das métricas

**Change ID**: `dashboard-period-selector-ui-polish`  
**Risco**: ESSENCIAL  
**Dependências**: `dashboard-metrics-custom-date-range`

## Problema

Após a inclusão de `Personalizado` no seletor `Período das métricas`, a UI ficou funcional, mas visualmente desalinhada:

- no desktop, `Personalizado` parece um botão avulso separado dos presets;
- no mobile, o botão quebra para outra linha sem composição consistente;
- o seletor usa `btn-primary`/`btn-outline-primary` Bootstrap puro, destoando da paleta hospitalar do app;
- o bloco não tem o mesmo tratamento visual de card/toolbar usado no restante do dashboard.

## Objetivo

Reorganizar o seletor de período das métricas como uma toolbar/card compacta, responsiva e alinhada ao design system hospitalar, mantendo SSR puro e sem alterar regras de negócio.

## Escopo

- `templates/dashboard/index.html`
  - reorganizar o bloco `Período das métricas`;
  - manter todos os links, mini-forms SSR e preservação de query string;
  - aplicar classes semânticas para layout responsivo.
- `static/css/app.css`
  - adicionar estilos locais para a toolbar/card de período;
  - garantir grid responsivo no mobile e alinhamento no desktop;
  - usar paleta `--hospital-*`, não o azul padrão Bootstrap.
- `apps/dashboard/tests/test_dashboard.py`
  - adicionar regressões estruturais de template/CSS para evitar retorno ao `btn-group`/`btn-primary` desalinhado.

## Fora de escopo

- Alterar cálculo de métricas, parsing de datas, query params ou permissões.
- Alterar models, migrations, FSM, filas ou workers.
- Criar JS novo, API JSON, DRF, SPA, HTMX, WebSocket ou SSE.
- Redesenhar cards de métricas, filtros da lista ou layout geral do dashboard.

## Critérios de sucesso globais

- `Período das métricas` fica dentro de um card/toolbar compacto.
- Presets e `Personalizado` compartilham o mesmo padrão visual.
- Mobile usa layout responsivo em grid, sem botão avulso desalinhado.
- Desktop mantém a toolbar alinhada em uma linha quando houver espaço.
- UI usa paleta hospitalar por classes próprias, evitando `btn-primary`/`btn-outline-primary` nesse seletor.
- Fluxo `Personalizado` continua SSR puro com dois mini-forms independentes.
- Todos os query params existentes continuam preservados.
- Testes relevantes e quality gate passam.
