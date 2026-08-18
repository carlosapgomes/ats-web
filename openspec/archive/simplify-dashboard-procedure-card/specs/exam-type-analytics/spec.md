<!-- markdownlint-disable MD013 -->

# exam-type-analytics Spec Delta

## MODIFIED Requirements

### Requirement: Dashboard apresenta breakdown por tipo

Gestor MUST escolher `solicitado`, `detectado` ou `autorizado` e ver, em um resumo compacto, as categorias exclusivas EDA, Colonoscopia, EDA + Colonoscopia e Nenhum quando aplicável. As chaves técnicas MUST permanecer `declared|detected|approved`, e a interface MUST rotulá-las como `Solicitado (NIR)`, `Detectado (análise)` e `Autorizado (médico)`.

#### Scenario: Resumo autorizado

- **GIVEN** o período possui aprovações únicas, combinadas e negativas integrais
- **WHEN** a dimensão `Autorizado (médico)` é selecionada
- **THEN** cada caso pertence a exatamente uma das quatro categorias visíveis
- **AND** a soma fecha com o universo aplicável
- **AND** o card não mistura contagens de casos com volume de componentes.

### Requirement: Volume de procedimentos é distinto de volume de casos

O motor analítico MUST continuar distinguindo volume EDA e Colonoscopia por componente de volume case-level. O card principal do dashboard MUST apresentar somente categorias exclusivas de casos e MUST NOT renderizar painel separado de volume de componentes ou explicações de dupla contagem.

#### Scenario: Um único combinado no resumo

- **GIVEN** exatamente um caso combinado no período
- **WHEN** o resumo de procedimentos é renderizado
- **THEN** EDA + Colonoscopia exibe um caso
- **AND** não são exibidos dois casos nem um painel adicional de componentes
- **AND** o motor analítico preserva internamente um componente EDA e um componente Colonoscopia.

### Requirement: Conversões são auditáveis e agregáveis

As dimensões solicitado, detectado e autorizado MUST permanecer autoritativas e a agregação de seus caminhos MUST continuar verificável no motor analítico. O dashboard principal MUST NOT renderizar matriz, tabela de caminhos ou apresentação equivalente de comparação cruzada até que uma demanda futura seja especificada em change próprio.

#### Scenario: EDA ampliada para combinado e reduzida pelo médico

- **GIVEN** caso solicitado EDA, detectado combinado e autorizado Colonoscopia
- **WHEN** o dashboard principal é renderizado
- **THEN** nenhuma matriz de conversão é apresentada
- **AND** cada dimensão pode ser consultada separadamente no resumo
- **AND** o caminho exato continua coberto pelo contrato analítico interno sem reclassificação incompatível.

### Requirement: Agendamento casado é mensurável

Casos com EDA e Colonoscopia autorizadas e agendamento confirmado MUST compor o contador de agendamentos combinados uma vez. O resumo MUST exibir esse indicador secundário somente quando o contador for maior que zero.

#### Scenario: Combinado confirmado

- **GIVEN** ambos os procedimentos estão autorizados e um agendamento está confirmado
- **WHEN** a métrica é calculada e o resumo é renderizado
- **THEN** agendamentos combinados confirmados aumenta em um
- **AND** o indicador aparece uma única vez.

#### Scenario: Nenhum combinado confirmado

- **GIVEN** o contador de agendamentos combinados confirmados é zero
- **WHEN** o resumo é renderizado
- **THEN** nenhum placeholder ou bloco desse indicador ocupa espaço no card.
