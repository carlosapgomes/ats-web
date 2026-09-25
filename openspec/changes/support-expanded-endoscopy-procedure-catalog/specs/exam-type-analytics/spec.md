## MODIFIED Requirements

### Requirement: NIR filtra casos operacionais e encerrados

Listas operacionais e encerradas do NIR MUST filtrar por `all`, cada código atômico e `eda_colonoscopy`, usando procedimentos declarados e labels do catálogo.

#### Scenario: Procedimento especializado declarado

- **GIVEN** existem casos declarados de Ecoendoscopia e CPRE
- **WHEN** NIR seleciona um dos filtros especializados
- **THEN** somente casos com aquele procedimento declarado aparecem
- **AND** filtros/polling existentes continuam compondo.

#### Scenario: Variação declarada

- **GIVEN** existem casos EDA, EDA + GTT e Retossigmoidoscopia + Argônio
- **WHEN** NIR seleciona uma variação
- **THEN** somente casos com aquela identidade exata declarada aparecem
- **AND** filtros/polling existentes continuam compondo.

#### Scenario: Combinado declarado

- **GIVEN** existem casos singleton e EDA + Colonoscopia
- **WHEN** NIR seleciona EDA + Colonoscopia
- **THEN** somente casos com ambas as rows declaradas aparecem
- **AND** filtros/polling existentes continuam compondo.

### Requirement: Dashboard apresenta breakdown por tipo

Gestor MUST escolher `solicitado`, `detectado` ou `autorizado` e ver categorias exclusivas para as dez identidades atômicas, EDA + Colonoscopia e Nenhum quando aplicável. As chaves técnicas MUST permanecer `declared|detected|approved`, e categorias sem casos MAY ser omitidas conforme apresentação existente.

#### Scenario: Resumo autorizado com especializados

- **GIVEN** o período possui Ecoendoscopia, CPRE e outros procedimentos
- **WHEN** dimensão `Autorizado (médico)` é selecionada
- **THEN** cada caso pertence a exatamente uma categoria visível
- **AND** nenhuma identidade especializada é contada como EDA.

#### Scenario: Resumo autorizado

- **GIVEN** o período possui aprovações singleton, combinadas e negativas integrais
- **WHEN** dimensão `Autorizado (médico)` é selecionada
- **THEN** cada caso pertence a exatamente uma categoria visível
- **AND** o card não mistura casos com volume de componentes.

#### Scenario: Resumo autorizado com variações

- **GIVEN** o período possui EDA, EDA + GTT, Retossigmoidoscopia, EDA + Colonoscopia e negativa integral
- **WHEN** dimensão `Autorizado (médico)` é selecionada
- **THEN** cada caso pertence a exatamente uma categoria visível
- **AND** a soma fecha com o universo aplicável.

#### Scenario: Conjunto inválido não vira categoria

- **GIVEN** dados inconsistentes contêm variação junto de Colonoscopia
- **WHEN** o resumo é calculado
- **THEN** o caso não é silenciosamente contado como uma categoria válida
- **AND** é projetado sob a inconsistência explícita (`invalid`), nunca omitido
- **AND** a inconsistência permanece detectável.

### Requirement: Tabela gerencial compõe filtro de tipo

A tabela MUST combinar dimensão + seleção `all`, cada código atômico, `eda_colonoscopy` e `none` quando aplicável, com busca/status/datas/atenção/paginação. Singleton SHALL exigir identidade exata no conjunto da dimensão.

#### Scenario: CPRE detectada com termo

- **GIVEN** gestor selecionou dimensão detectado, CPRE e termo de busca
- **WHEN** partial atualiza
- **THEN** resultados satisfazem todos os predicados
- **AND** paginação preserva parâmetros.

#### Scenario: EDA + Cápsula detectada com termo

- **GIVEN** gestor selecionou dimensão detectado, `eda_capsule` e termo de busca
- **WHEN** partial atualiza
- **THEN** resultados satisfazem todos os predicados
- **AND** EDA simples não aparece por compartilhar família.

#### Scenario: Detectado combinado com termo

- **GIVEN** gestor selecionou dimensão detectado, EDA + Colonoscopia e termo
- **WHEN** partial atualiza
- **THEN** resultados possuem exatamente as duas identidades e satisfazem o termo
- **AND** paginação preserva parâmetros.

### Requirement: Volume de procedimentos é distinto de volume de casos

O motor analítico MUST distinguir volume de cada identidade atômica por componente do volume case-level. O card principal MUST apresentar categorias exclusivas de casos, MUST NOT desmembrar pacote em base+variação e MUST preservar EDA + Colonoscopia como dois componentes de um único caso.

#### Scenario: Um caso especializado

- **GIVEN** exatamente um caso de Ecoendoscopia no período
- **WHEN** resumo e volume interno são calculados
- **THEN** Ecoendoscopia exibe um caso e um componente
- **AND** EDA não aumenta por causa desse caso.

#### Scenario: Um caso de EDA + GTT

- **GIVEN** exatamente um caso `eda_gastrostomy` no período
- **WHEN** resumo e volume interno são calculados
- **THEN** EDA + GTT exibe um caso e um componente
- **AND** EDA não aumenta por causa desse caso.

#### Scenario: Um único combinado no resumo

- **GIVEN** exatamente um caso EDA + Colonoscopia no período
- **WHEN** resumo é renderizado
- **THEN** EDA + Colonoscopia exibe um caso
- **AND** o motor interno preserva um componente de cada tipo.

#### Scenario: Perfis compartilhados não agregam identidades

- **GIVEN** o período contém Colonoscopia e Retossigmoidoscopia
- **WHEN** volumes são calculados
- **THEN** cada código recebe seu próprio volume
- **AND** compartilhar profile não soma Retossigmoidoscopia a Colonoscopia.

### Requirement: Agendamento casado é mensurável

Somente casos com exatamente EDA e Colonoscopia autorizadas e agendamento confirmado MUST compor o contador de agendamentos combinados uma vez. Nenhuma identidade atômica, inclusive as que possuem `+` na label, SHALL entrar nesse contador.

#### Scenario: Especializado confirmado

- **GIVEN** Ecoendoscopia ou CPRE possui agendamento confirmado
- **WHEN** a métrica é calculada
- **THEN** o volume da identidade aumenta
- **AND** agendamentos combinados confirmados não aumenta.

#### Scenario: Pacote confirmado

- **GIVEN** EDA + Dilatação ou Retossigmoidoscopia + Argônio possui agendamento confirmado
- **WHEN** a métrica é calculada
- **THEN** o volume da identidade aumenta
- **AND** agendamentos combinados confirmados não aumenta.

#### Scenario: Combinado confirmado

- **GIVEN** EDA e Colonoscopia estão autorizadas e um agendamento está confirmado
- **WHEN** métrica e resumo são calculados
- **THEN** agendamentos combinados confirmados aumenta em um
- **AND** o indicador aparece uma única vez.

#### Scenario: Nenhum combinado confirmado

- **GIVEN** o contador de agendamentos combinados confirmados é zero
- **WHEN** o resumo é renderizado
- **THEN** nenhum placeholder desse indicador ocupa espaço no card.
