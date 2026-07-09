<!-- markdownlint-disable MD013 -->

# Proposal: Melhorias de UX e busca do dashboard

**Change ID**: `dashboard-metrics-search-ux`  
**Risco**: PROFISSIONAL  
**Dependências**: app `apps/dashboard`, app `apps/cases`, PostgreSQL 17+

## Problema

O dashboard gerencial atende manager/admin, mas alguns pontos reduzem a
usabilidade operacional:

1. A seção de métricas mostra o dia atual, sem seleção explícita de data.
2. O card "Tempo médio" mostra valores altos apenas em minutos, por exemplo
   `1100 min`.
3. Os filtros de data de "Todos os Casos" dependem de placeholders em inputs
   `type="date"`, que podem não aparecer no Android/mobile.
4. A lista "Todos os Casos" não possui busca por nome ou registro, o que
   dificulta localizar casos em bases grandes.

## Objetivo

Evoluir o dashboard mantendo SSR puro, Vanilla JS e escopo enxuto:

- permitir selecionar uma data para métricas diárias;
- tornar tempos médios legíveis em horas quando aplicável;
- melhorar labels dos filtros de data em mobile;
- adicionar busca server-side por nome do paciente ou número de ocorrência;
- adicionar melhoria progressiva com busca dinâmica após 3 caracteres;
- criar índices PostgreSQL adequados para o volume de dados.

## Decisões de escopo

### Não criar aba histórica agora

A primeira entrega usará um seletor de data na própria seção de métricas. Uma
aba histórica separada fica fora de escopo até existir necessidade de comparar
períodos, exportar relatórios ou mostrar séries temporais.

### Métrica histórica sem reconstrução de snapshot de fila

Contagens de casos do dia, fluxo de admissão e tempos médios serão calculados
para a data selecionada. O card de "Aguardando por etapa" continuará sendo um
snapshot atual da fila, pois reconstruir fila histórica exige consulta temporal
a eventos e aumentaria muito o escopo.

### Busca dinâmica como melhoria progressiva

A busca server-side tradicional via query string será entregue antes. Depois,
o mesmo backend será reaproveitado por Vanilla JS para atualizar a lista sem
recarregar a página. Sem Django REST Framework, sem SPA e sem endpoint JSON.

## Escopo

- Dashboard `/dashboard/`.
- Helpers e queries de `apps/dashboard/views.py`.
- Template `templates/dashboard/index.html`.
- Testes de dashboard.
- Migration em `apps/cases/migrations/` para índices de busca.
- Um arquivo JS estático para a melhoria dinâmica.

## Fora de escopo

- Aba ou página histórica dedicada.
- Comparação entre intervalos de datas.
- Gráficos, exportação CSV/PDF ou BI.
- Reconstrução histórica de filas a partir de `CaseEvent`.
- Autocomplete completo, typeahead com sugestões ou highlight de termos.
- Busca fuzzy avançada, ranking ou busca fonética.
- Django REST Framework, SPA, WebSocket, SSE ou framework JS.

## Dimensionamento em slices

O change será dividido em quatro slices verticais e enxutos:

1. **Polimento de UX imediato**: labels mobile e duração humana.
2. **Métricas por data selecionada**: seletor de data e queries diárias.
3. **Busca server-side indexada**: query string, form, paginação e migration.
4. **Busca dinâmica progressiva**: partial SSR e Vanilla JS com debounce.

Essa divisão evita um slice grande com migration, JavaScript e mudanças de
métricas ao mesmo tempo, mas mantém cada entrega com valor end-to-end.

## Critérios de sucesso globais

- Dashboard continua acessível apenas para manager/admin.
- Sem JavaScript, todos os filtros e a busca continuam funcionando via submit.
- Com JavaScript, busca dinâmica só dispara após 3 caracteres ou campo vazio.
- Datas de filtros de casos têm labels visíveis em mobile.
- Tempo médio maior ou igual a 60 minutos aparece em horas/minutos.
- Métricas diárias usam a data selecionada e hoje é o padrão.
- Busca por nome e registro é server-side, composta com filtros existentes.
- Índices PostgreSQL de trigram existem para os campos pesquisados.
- Quality gate do `AGENTS.md` passa ao fim de cada slice.

## Política de commits e markdown

Durante a implementação dos slices, o implementador deve commitar apenas código,
testes, migrations e arquivos criados para a aplicação. Não deve commitar as
especificações do OpenSpec antes do arquivamento final do change.

Se criar arquivos Markdown, como relatório temporário do slice, deve aplicar
`markdownlint-cli2` somente nesses arquivos criados. Não deve rodar
markdownlint em massa nem corrigir Markdown legado fora do escopo.
