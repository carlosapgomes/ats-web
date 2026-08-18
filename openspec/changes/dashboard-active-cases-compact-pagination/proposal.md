<!-- markdownlint-disable MD013 -->

# Proposal: Casos ativos por padrão e paginação compacta no dashboard

**Change ID**: `dashboard-active-cases-compact-pagination`
**Risco**: PROFISSIONAL (UX/query SSR localizada, sem dados ou FSM)
**Dependências**: `apps/dashboard`, `apps/cases.CaseStatus.CLEANED`, Bootstrap 5.3 e busca parcial SSR existente

## Problema

A listagem gerencial do dashboard consulta todo o histórico quando nenhum filtro é informado. Embora o backend já use `Paginator(cases_qs, 20)` e busque apenas a página corrente, o template percorre `page_obj.paginator.page_range` completo. Em bases com muitos casos isso produz dezenas de links numerados em uma única faixa, como 66 páginas na captura fornecida, criando ruído visual e overflow.

Além disso, iniciar em todo o histórico mistura casos encerrados com o trabalho operacional corrente. Limitar a lista ao dia atual não é seguro: um caso ainda pendente de dias anteriores desapareceria da visão gerencial.

## Objetivo

Tornar a lista do dashboard operacional e escalável sem alterar sua arquitetura SSR:

- usar **casos ativos** como escopo padrão, definidos como todo `Case` cujo status não é `CLEANED`, sem restrição de data;
- permitir ao gestor selecionar explicitamente todo o histórico, incluindo `CLEANED`;
- manter paginação server-side de 20 casos;
- substituir todos os números de página por uma faixa elidida e limitada, com reticências;
- informar o intervalo e o total, por exemplo `Exibindo 21–40 de 1.312 casos`;
- preservar o escopo escolhido em filtros, paginação, troca de período das métricas e busca parcial progressiva.

## Escopo incluído

- Resolução server-side do parâmetro `case_scope=active|all`, com `active` como padrão e fallback de valor inválido.
- Exclusão de `CaseStatus.CLEANED` apenas no escopo `active`.
- Controle visível de escopo no formulário da lista.
- Paginação compacta baseada na API de elisão do `django.core.paginator.Paginator`.
- Resumo de intervalo/total e navegação acessível.
- Propagação de `case_scope=all` nos fluxos SSR e na busca dinâmica existente.
- Testes de comportamento, composição e contrato HTML/JS.

## Fora de escopo

- Filtrar por dia atual ou vincular o período das métricas à lista de casos.
- Cursor/keyset pagination ou remoção do `COUNT` do `Paginator`.
- Infinite scroll, “carregar mais”, API JSON, DRF, SPA, HTMX, framework JS, WebSocket ou SSE.
- Alterar tamanho de página, ordenação, busca trigram, índices ou queries das métricas.
- Alterar estados FSM, significado de `CLEANED`, modelos, migrations, permissões ou auditoria.
- Criar uma nova página de histórico ou exportação.

## Dimensionamento em slices

Este change terá **um único slice vertical**.

A entrega completa exige a mesma query/contexto, os dois templates da lista, a preservação no JavaScript já existente e testes do dashboard. Separar “escopo ativo” e “paginação compacta” repetiria os mesmos arquivos e dois ciclos de integração sem reduzir risco. Um slice único mantém o fluxo end-to-end em cinco arquivos funcionais, dentro do limite ideal do projeto.

## Critérios de sucesso globais

- Dashboard sem `case_scope` mostra casos não `CLEANED`, inclusive antigos, e não mostra `CLEANED`.
- `case_scope=all` mostra ativos e encerrados.
- Valor inválido de `case_scope` cai para `active` sem erro.
- Filtros existentes continuam compondo com o escopo.
- Busca parcial preserva `case_scope=all`; sem JavaScript, o formulário GET continua funcional.
- O backend continua paginando 20 casos por vez.
- A navegação não renderiza todos os números de página e inclui primeira, última, atual, vizinhas e reticências quando necessário.
- O resumo `Exibindo X–Y de Z casos` corresponde à página filtrada.
- Permissões manager/admin e métricas permanecem inalteradas.
- Quality gate completo do `AGENTS.md` passa.

## Rollout e rollback

Não há migration nem transformação de dados. O rollout ocorre no próximo deploy da aplicação. O rollback é o revert dos arquivos do dashboard; casos `CLEANED` nunca são apagados ou alterados, apenas deixam de aparecer no escopo inicial.
