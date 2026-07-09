<!-- markdownlint-disable MD013 -->

# Design: Polimento visual dos filtros de "Todos os Casos"

## Estado atual

O card "Todos os Casos" em `templates/dashboard/index.html` usa uma estrutura
horizontal com `d-flex` para título, botão `Atenção necessária` e formulário de
filtros. Com busca, status, datas e labels visíveis, o resultado fica apertado e
visualmente desalinhado.

O formulário também pode conter um hidden `name="search"` no mesmo form em que
já existe o input visível `type="search" name="search"`. Isso é ruim para o
fallback sem JavaScript porque, em query string com chaves repetidas, Django
retorna o último valor em `request.GET.get("search")`.

## Decisão

Usar layout em duas linhas lógicas dentro do card:

1. `card header` visual:
   - `Todos os Casos` à esquerda;
   - botão/link `Atenção necessária` à direita em telas médias/grandes;
   - em telas pequenas, permitir wrap/empilhamento limpo.
2. formulário de filtros abaixo:
   - grid Bootstrap com `row`, espaçamento (`g-2`/`g-md-3`) e `align-items-end`;
   - busca em coluna mais larga;
   - status e datas em colunas menores;
   - ações alinhadas pela base dos inputs.

## Grid sugerido

```text
Busca:        col-12 col-lg-4
Status:       col-12 col-sm-6 col-lg-2
Data inicial: col-6  col-lg-2
Data final:   col-6  col-lg-2
Ações:        col-12 col-lg-2
```

A implementação pode ajustar levemente as classes, desde que preserve:

- busca com destaque no desktop;
- empilhamento legível no mobile;
- botões alinhados com inputs.

## Preservação de comportamento

O slice não altera backend. Deve preservar:

- `id="dashboard-case-list"`;
- `data-dashboard-search-target`;
- input visível `id="search" name="search"`;
- hidden `metrics_date` no formulário da lista quando aplicável;
- link `attention=1` preservando parâmetros relevantes;
- inclusão de `static/js/dashboard_search.js`;
- submit tradicional sem JavaScript.

## Correção de `search` duplicado

Remover hidden `name="search"` do formulário da lista se ele existir no mesmo
form que o input visível de busca.

Manter hidden `search` em outros formulários que não tenham input visível de
busca, por exemplo o formulário de `metrics_date`, se necessário para preservar
estado.

## Testes

Usar testes de contrato HTML em `apps/dashboard/tests/test_dashboard.py`.
Não adicionar Selenium, Playwright ou screenshot tests.

## Rollback

Reverter o template e os testes deste slice. Não há migration nem alteração de
dados.
