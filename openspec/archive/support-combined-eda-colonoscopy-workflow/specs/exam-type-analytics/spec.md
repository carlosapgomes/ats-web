# Capability: Analytics por dimensão e volume de procedimentos

## MODIFIED Requirements

### Requirement: NIR filtra casos operacionais e encerrados

Listas operacionais e encerradas do NIR MUST filtrar por `all|eda|colonoscopy|eda_colonoscopy` usando procedimentos declarados.

#### Scenario: Combinado declarado

- **GIVEN** casos declarados únicos e combinados
- **WHEN** NIR seleciona EDA + Colonoscopia
- **THEN** somente casos com ambos declarados aparecem
- **AND** filtros/polling existentes continuam compondo.

### Requirement: Dashboard mantém métricas consolidadas

Cards principais MUST contar cada `Case` uma única vez independentemente de possuir um ou dois procedimentos.

#### Scenario: Um caso combinado

- **GIVEN** período contém um caso combinado
- **WHEN** total consolidado é calculado
- **THEN** total aumenta em um, não dois
- **AND** semântica de desfecho atual permanece.

### Requirement: Dashboard apresenta breakdown por tipo

Gestor MUST escolher `declarado`, `detectado` ou `autorizado` e ver categorias exclusivas EDA, Colonoscopia, EDA + Colonoscopia e Nenhum quando aplicável.

#### Scenario: Breakdown autorizado

- **GIVEN** período possui aprovações únicas, combinadas e negativas integrais
- **WHEN** dimensão autorizado é selecionada
- **THEN** cada caso pertence a exatamente uma categoria
- **AND** soma fecha com o universo aplicável.

### Requirement: Tabela gerencial compõe filtro de tipo

Tabela MUST combinar dimensão + seleção com busca/status/datas/atenção/paginação.

#### Scenario: Detectado combinado com termo

- **GIVEN** gestor selecionou dimensão detectado, combinação e termo
- **WHEN** partial atualiza
- **THEN** resultados satisfazem todos os predicados
- **AND** paginação preserva parâmetros.

### Requirement: Rollout é reversível sem apagar dados

Operação MUST desabilitar novos casos com Colonoscopia sem apagar `CaseProcedure` ou interromper casos existentes.

#### Scenario: Kill switch

- **GIVEN** casos únicos/combinados em voo
- **WHEN** flag é desligada
- **THEN** apenas novos uploads de Colonoscopia/combinado são bloqueados
- **AND** casos existentes continuam.

## ADDED Requirements

### Requirement: Volume de procedimentos é distinto de volume de casos

Dashboard MUST informar volume EDA e Colonoscopia por componente e MUST rotular que combinado soma dois procedimentos.

#### Scenario: Um único combinado

- **GIVEN** exatamente um caso combinado no período
- **WHEN** volume de procedimentos é calculado
- **THEN** EDA aumenta em um
- **AND** Colonoscopia aumenta em um
- **AND** casos continuam iguais a um.

### Requirement: Conversões são auditáveis e agregáveis

Dashboard MUST apresentar ou disponibilizar uma matriz verificável entre declarado, detectado e autorizado.

#### Scenario: EDA ampliada para combinado e reduzida pelo médico

- **GIVEN** caso declarado EDA, detectado combinado e autorizado Colonoscopia
- **WHEN** conversões são agregadas
- **THEN** caso aparece na célula/caminho correspondente
- **AND** não é contado em caminho incompatível.

### Requirement: Agendamento casado é mensurável

Casos com EDA e Colonoscopia autorizadas e agendamento confirmado MUST compor contador de agendamentos casados uma vez.

#### Scenario: Combinado confirmado

- **GIVEN** ambos autorizados e um `appointment_at` confirmado
- **WHEN** métrica é calculada
- **THEN** agendamentos casados aumenta em um
- **AND** não aumenta em dois.
