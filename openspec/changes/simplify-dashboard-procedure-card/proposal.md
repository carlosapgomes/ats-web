<!-- markdownlint-disable MD013 -->

# Proposal: Simplificar o card de procedimentos do dashboard

**Change ID**: `simplify-dashboard-procedure-card`

**Risco**: ESSENCIAL

**Dependências**: `support-combined-eda-colonoscopy-workflow`

## Why

O card `PROCEDIMENTOS POR DIMENSÃO` mistura breakdown de casos, volume de componentes, agendamentos casados e uma matriz declarado→detectado→autorizado. A apresentação exige interpretação especializada, repete EDA/Colonoscopia com unidades diferentes e ocupa espaço desproporcional sem conduzir a uma ação operacional clara.

Neste momento do produto, a visão principal precisa priorizar leitura rápida. A comparação cruzada entre dimensões deve sair do dashboard até que uma demanda gerencial concreta justifique uma experiência analítica própria.

## What Changes

- Substituir o card atual por resumo compacto com quatro categorias exclusivas de casos: EDA, Colonoscopia, EDA + Colonoscopia e Nenhum.
- Manter o seletor SSR de dimensão com labels mais compreensíveis:
  - `declared` → `Solicitado (NIR)`;
  - `detected` → `Detectado (análise)`;
  - `approved` → `Autorizado (médico)`.
- Retirar da visão principal:
  - tabela técnica `BREAKDOWN POR CATEGORIA`;
  - painel `VOLUME DE PROCEDIMENTOS`;
  - badge e explicações sobre casos versus componentes;
  - `MATRIZ DE CONVERSÃO`.
- Exibir agendamentos combinados confirmados como indicador secundário somente quando o contador for maior que zero.
- Remover helpers e chaves de contexto exclusivos da apresentação retirada quando ficarem sem uso.
- Preservar os dados autoritativos, `compute_procedure_analytics()`, resultados internos de volume/matriz, filtros dimensionais, navegação SSR, busca e paginação.
- Não substituir a matriz por accordion, `<details>`, modal, gráfico ou link alternativo neste change.

## Capabilities

### New Capabilities

- Nenhuma.

### Modified Capabilities

- `exam-type-analytics`: o dashboard passa a apresentar somente o resumo case-level por dimensão; volume de componentes e conversões continuam verificáveis no motor analítico, mas deixam de ser renderizados na visão principal; o contador de agendamento combinado passa a ser exibido por exceção.

## Impact

- **Template:** `templates/dashboard/index.html`.
- **Contexto SSR:** `apps/dashboard/views.py`.
- **Labels de apresentação:** `apps/dashboard/procedure_analytics.py`, sem alterar chaves ou cálculos.
- **Testes:** `apps/dashboard/tests/test_dashboard.py` e `apps/dashboard/tests/test_procedure_analytics.py`.
- **Spec modificada:** `exam-type-analytics`.
- **Dados/API:** nenhuma migration, alteração de model, FSM, rota, permissão ou contrato de query string.
- **Frontend:** Bootstrap existente; nenhum CSS ou JavaScript novo.
- **Rollback:** reversão de um único commit, sem transformação de dados ou passo operacional.

## Out of Scope

- Excluir ou redesenhar `CaseProcedure` ou as três dimensões autoritativas.
- Alterar ou remover de `compute_procedure_analytics()` os resultados `volume` e `matrix`.
- Criar relatório, funil, matriz simplificada ou página analítica alternativa.
- Alterar fórmulas, período, queries de casos, partial, paginação, busca dinâmica ou permissões.
- Alterar models, migrations, FSM, eventos, filas, pipeline ou workflows clínicos.
- Adicionar CSS, JavaScript, API, DRF, SPA, HTMX, WebSocket ou SSE.

## Success Criteria

- O card exibe somente quatro contagens exclusivas de casos para a dimensão ativa.
- Os labels visíveis mudam sem alterar `procedure_dimension=declared|detected|approved`.
- Matriz, volume de componentes e explicações técnicas não aparecem no HTML do dashboard.
- Agendamentos combinados confirmados aparecem apenas quando o contador é positivo.
- Filtro dimensional, busca, paginação e preservação de parâmetros continuam funcionando.
- Testes existentes de breakdown, volume, matriz e agendamento casado permanecem verdes, comprovando que apenas a apresentação foi simplificada.
- Nenhum model, migration, FSM, permissão, CSS ou JS é alterado.
- Quality gate completo passa.
