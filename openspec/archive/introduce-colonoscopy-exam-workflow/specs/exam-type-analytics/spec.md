# Capability: Busca NIR e métricas por tipo de exame

## ADDED Requirements

### Requirement: NIR filtra casos operacionais e encerrados

O sistema MUST permitir que o NIR componha o tipo de exame com os filtros existentes nas listas operacional e histórica.

#### Scenario: Operacionais por colonoscopia

- **GIVEN** NIR possui acesso à fila compartilhada com EDA e colonoscopia
- **WHEN** seleciona Colonoscopia
- **THEN** lista somente casos operacionais desse tipo
- **AND** compõe com ocorrência/status existentes
- **AND** polling preserva o filtro.

#### Scenario: Encerrados por EDA

- **GIVEN** busca de encerrados contém ambos os tipos
- **WHEN** seleciona EDA
- **THEN** somente casos EDA são retornados
- **AND** Todos restaura ambos.

### Requirement: Dashboard mantém métricas consolidadas

O dashboard MUST preservar os indicadores consolidados, contando EDA e colonoscopia com a semântica atual de desfechos.

#### Scenario: Período com dois tipos

- **GIVEN** período contém EDA e colonoscopia
- **WHEN** dashboard calcula cards principais
- **THEN** total/aceitos/negados/admin-closed/em andamento incluem ambos uma vez
- **AND** semântica atual de decisões permanece.

### Requirement: Dashboard apresenta breakdown por tipo

O dashboard MUST apresentar uma decomposição verificável das métricas por tipo no período selecionado.

#### Scenario: Breakdown do período

- **GIVEN** período ativo
- **WHEN** dashboard é renderizado
- **THEN** apresenta linha EDA e linha Colonoscopia
- **AND** cada linha informa total, desfechos e esperas por etapa
- **AND** soma dos tipos fecha com consolidado quando não há outro tipo suportado.

### Requirement: Tabela gerencial compõe filtro de tipo

A tabela gerencial MUST aplicar o tipo por conjunção com busca, status, datas, atenção e paginação.

#### Scenario: Busca dinâmica com tipo

- **GIVEN** gestor selecionou Colonoscopia e digitou nome/ocorrência
- **WHEN** partial da lista é atualizado
- **THEN** resultados satisfazem tipo e termo
- **AND** status, datas, atenção e paginação continuam compondo.

### Requirement: Rollout é reversível sem apagar dados

A operação MUST poder bloquear novos uploads de colonoscopia sem apagar dados ou interromper casos já criados.

#### Scenario: Desligamento emergencial

- **GIVEN** colonoscopia ativa em produção
- **WHEN** operação desliga `COLONOSCOPY_INTAKE_ENABLED`
- **THEN** novos uploads são bloqueados
- **AND** casos existentes continuam visíveis/processáveis
- **AND** nenhuma migration destrutiva é necessária.
