<!-- markdownlint-disable MD013 -->

# Proposal: Polimento visual dos filtros de "Todos os Casos"

**Change ID**: `dashboard-case-list-filter-layout-polish`  
**Risco**: ESSENCIAL  
**Dependências**: `dashboard-metrics-search-ux`

## Problema

Após a implementação de métricas por data, busca server-side e busca dinâmica,
o card "Todos os Casos" passou a concentrar muitos controles na mesma faixa:

- título do card;
- botão `Atenção necessária`;
- busca por nome/registro;
- filtro de status;
- datas inicial/final;
- botão `Filtrar`.

No desktop, os controles ficam muito próximos e desalinhados. No mobile, o
agrupamento tende a ficar pouco legível.

## Objetivo

Melhorar a UI do card "Todos os Casos" usando um layout em duas linhas:

1. header limpo com título à esquerda e `Atenção necessária` à direita;
2. área de filtros abaixo em grid Bootstrap responsivo.

A busca deve ter destaque/largura maior que status e datas no desktop. Labels
visíveis devem ser preservadas.

## Escopo

- Ajustar `templates/dashboard/index.html`.
- Adicionar testes de contrato HTML em `apps/dashboard/tests/test_dashboard.py`.
- Corrigir eventual `search` duplicado no formulário da lista, preservando o
  fallback sem JavaScript.

## Fora de escopo

- Alterar queries, busca, índices, migrations ou models.
- Criar endpoint novo.
- Alterar partial `_case_list.html`, salvo se estritamente necessário.
- Adicionar framework JS, CSS complexo ou screenshots automatizados.
- Mudar regras de permissão, FSM ou métricas.

## Critérios de sucesso

- Header do card fica separado visualmente dos filtros.
- `Atenção necessária` não fica espremido entre inputs.
- Filtros usam grid responsivo e ficam alinhados pela base.
- Busca ocupa mais espaço no desktop e largura total no mobile.
- Labels continuam visíveis e associadas aos campos.
- Formulário da lista não envia `search` duplicado.
- Busca dinâmica e fallback SSR continuam funcionando.
- Quality gate do `AGENTS.md` passa.
