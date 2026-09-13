# exam-type-analytics Specification

## Purpose
TBD - created by archiving change introduce-colonoscopy-exam-workflow. Update Purpose after archive.

## Requirements

### Requirement: NIR filtra casos operacionais e encerrados

Listas operacionais e encerradas do NIR MUST filtrar por `all|eda|colonoscopy|eda_colonoscopy|echoendoscopy|cpre` usando procedimentos declarados.

#### Scenario: Procedimento especializado declarado

- **GIVEN** existem casos declarados de Ecoendoscopia e CPRE
- **WHEN** NIR seleciona um dos filtros especializados
- **THEN** somente casos com aquele procedimento declarado aparecem
- **AND** filtros/polling existentes continuam compondo.

#### Scenario: Combinado declarado

- **GIVEN** casos declarados únicos e EDA + Colonoscopia
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

Gestor MUST escolher `solicitado`, `detectado` ou `autorizado` e ver, em resumo compacto, categorias exclusivas EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia, CPRE e Nenhum quando aplicável. As chaves técnicas MUST permanecer `declared|detected|approved`.

#### Scenario: Resumo autorizado com especializados

- **GIVEN** período possui casos autorizados como EDA, combinado, Ecoendoscopia, CPRE e negativa integral
- **WHEN** dimensão `Autorizado (médico)` é selecionada
- **THEN** cada caso pertence a exatamente uma categoria visível
- **AND** a soma fecha com o universo aplicável
- **AND** nenhuma combinação especializada inválida é criada por contagem.

#### Scenario: Resumo autorizado

- **GIVEN** período possui aprovações únicas, combinadas e negativas integrais
- **WHEN** dimensão `Autorizado (médico)` é selecionada
- **THEN** cada caso pertence a exatamente uma categoria visível
- **AND** a soma fecha com o universo aplicável
- **AND** o card não mistura contagens de casos com volume de componentes.

### Requirement: Tabela gerencial compõe filtro de tipo

Tabela MUST combinar dimensão + seleção `all|eda|colonoscopy|eda_colonoscopy|echoendoscopy|cpre|none`, quando `none` for aplicável, com busca/status/datas/atenção/paginação.

#### Scenario: CPRE detectada com termo

- **GIVEN** gestor selecionou dimensão detectado, CPRE e termo de busca
- **WHEN** partial atualiza
- **THEN** resultados satisfazem todos os predicados
- **AND** paginação preserva parâmetros.

#### Scenario: Detectado combinado com termo

- **GIVEN** gestor selecionou dimensão detectado, EDA + Colonoscopia e termo
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

### Requirement: Volume de procedimentos é distinto de volume de casos

O motor analítico MUST distinguir volumes EDA, Colonoscopia, Ecoendoscopia e CPRE por componente de volume case-level. O card principal MUST apresentar categorias exclusivas de casos e MUST NOT transformar Ecoendoscopia/CPRE em componentes de EDA.

#### Scenario: Um caso especializado

- **GIVEN** exatamente um caso de Ecoendoscopia no período
- **WHEN** resumo e volume interno são calculados
- **THEN** Ecoendoscopia exibe um caso e um componente
- **AND** EDA não aumenta por causa desse caso.

#### Scenario: Um único combinado no resumo

- **GIVEN** exatamente um caso EDA + Colonoscopia no período
- **WHEN** resumo é renderizado
- **THEN** EDA + Colonoscopia exibe um caso
- **AND** não são exibidos dois casos nem painel adicional de componentes
- **AND** motor analítico preserva internamente um componente de cada tipo.

### Requirement: Conversões são auditáveis e agregáveis

As dimensões solicitado, detectado e autorizado MUST permanecer autoritativas e a agregação de seus caminhos MUST continuar verificável no motor analítico. O dashboard principal MUST NOT renderizar matriz, tabela de caminhos ou apresentação equivalente de comparação cruzada até que uma demanda futura seja especificada em change próprio.

#### Scenario: EDA ampliada para combinado e reduzida pelo médico

- **GIVEN** caso solicitado EDA, detectado combinado e autorizado Colonoscopia
- **WHEN** o dashboard principal é renderizado
- **THEN** nenhuma matriz de conversão é apresentada
- **AND** cada dimensão pode ser consultada separadamente no resumo
- **AND** o caminho exato continua coberto pelo contrato analítico interno sem reclassificação incompatível.

### Requirement: Agendamento casado é mensurável

Somente casos com exatamente EDA e Colonoscopia autorizadas e agendamento confirmado MUST compor o contador de agendamentos combinados uma vez. Ecoendoscopia e CPRE MUST NOT entrar nesse contador.

#### Scenario: Especializado confirmado

- **GIVEN** Ecoendoscopia ou CPRE possui agendamento confirmado
- **WHEN** métrica é calculada
- **THEN** volume do procedimento especializado aumenta
- **AND** agendamentos combinados confirmados não aumenta.

#### Scenario: Combinado confirmado

- **GIVEN** EDA e Colonoscopia estão autorizadas e um agendamento está confirmado
- **WHEN** métrica e resumo são calculados
- **THEN** agendamentos combinados confirmados aumenta em um
- **AND** indicador aparece uma única vez.

#### Scenario: Nenhum combinado confirmado

- **GIVEN** contador de agendamentos combinados confirmados é zero
- **WHEN** resumo é renderizado
- **THEN** nenhum placeholder desse indicador ocupa espaço no card.
