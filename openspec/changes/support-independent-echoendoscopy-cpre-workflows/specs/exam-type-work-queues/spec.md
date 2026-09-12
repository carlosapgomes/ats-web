## MODIFIED Requirements

### Requirement: Médico filtra pendências sem perder a busca

A aba médica `Pendentes` MUST manter lifecycle primário e filtrar por `Todos | EDA | Colonoscopia | EDA + Colonoscopia | Ecoendoscopia | CPRE`, usando procedimentos detectados.

#### Scenario: Ecoendoscopia e nome compostos

- **GIVEN** médico digitou termo e selecionou Ecoendoscopia
- **WHEN** filtro é aplicado ou polling atualiza cards
- **THEN** somente casos com Ecoendoscopia detectada e termo correspondente aparecem
- **AND** termo e seleção permanecem.

#### Scenario: Combinado e nome compostos

- **GIVEN** médico digitou termo e selecionou EDA + Colonoscopia
- **WHEN** filtro é aplicado ou polling atualiza cards
- **THEN** somente casos com ambos detectados e termo correspondente aparecem
- **AND** termo e seleção permanecem.

### Requirement: Decididos Hoje tem badge e filtro simples

A aba médica `Decididos Hoje` MUST identificar e filtrar pelo conjunto autorizado entre EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia, CPRE ou Nenhum autorizado.

#### Scenario: EDA substituída por CPRE

- **GIVEN** caso detectado como EDA terminou autorizado somente como CPRE
- **WHEN** médico abre Decididos Hoje
- **THEN** badge principal de resultado é CPRE
- **AND** transformação EDA → CPRE permanece visível.

#### Scenario: Combinado parcialmente aprovado

- **GIVEN** caso detectado EDA + Colonoscopia terminou autorizado somente para EDA
- **WHEN** médico abre Decididos Hoje
- **THEN** badge principal de resultado é EDA
- **AND** transformação combinado → EDA permanece visível.

### Requirement: CHD filtra todas as pendências pelo mesmo universo do contador

O filtro CHD MUST usar procedimentos aprovados em todos os grupos de Pendentes e MUST aceitar EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia ou CPRE.

#### Scenario: CPRE em grupo operacional

- **GIVEN** caso de CPRE autorizado pertence a grupo elegível
- **WHEN** CHD seleciona CPRE
- **THEN** o mesmo predicado do contador é aplicado
- **AND** somente CPRE autorizada aparece.

#### Scenario: Agendamento casado em grupos operacionais

- **GIVEN** casos EDA + Colonoscopia autorizados em grupos elegíveis
- **WHEN** CHD seleciona EDA + Colonoscopia
- **THEN** todos os grupos usam o mesmo predicado de ambos aprovados
- **AND** contadores fecham com o universo primário.

### Requirement: Processados Hoje tem badge e filtro

Processados Hoje MUST exibir o snapshot autorizado/agendado e permitir filtro por EDA, Colonoscopia, combinado, Ecoendoscopia ou CPRE. Somente EDA + Colonoscopia MUST usar o sufixo `Agendamento casado`.

#### Scenario: Ecoendoscopia confirmada

- **GIVEN** CHD confirmou caso autorizado como Ecoendoscopia
- **WHEN** consulta Processados Hoje
- **THEN** vê `Ecoendoscopia` e uma única data/hora
- **AND** não vê `EDA` nem `Agendamento casado`.

#### Scenario: Combinado confirmado

- **GIVEN** CHD confirmou caso com EDA e Colonoscopia aprovadas
- **WHEN** consulta Processados Hoje
- **THEN** vê `EDA + Colonoscopia · Agendamento casado`
- **AND** uma única data/hora.

### Requirement: Histórico CHD combina tipo e busca

A busca histórica MUST aceitar `all|eda|colonoscopy|eda_colonoscopy|echoendoscopy|cpre`, usar dimensão autorizada e manter limite/ordering atuais.

#### Scenario: CPRE sem termo

- **GIVEN** CHD seleciona CPRE sem termo
- **WHEN** submete
- **THEN** vê até os 50 casos históricos mais recentes autorizados como CPRE.

#### Scenario: Combinado sem termo

- **GIVEN** CHD seleciona EDA + Colonoscopia sem termo
- **WHEN** submete
- **THEN** vê até os 50 casos históricos mais recentes com ambos autorizados.

### Requirement: Alterações ficam explícitas nas filas downstream

Quando declaração, detecção e autorização diferirem, médico, CHD e NIR MUST receber comparação textual, sem depender apenas de cor. Mudança do conjunto autorizado MUST gerar evento append-only e mensagem sistêmica idempotente na thread, sem criar notificação global.

#### Scenario: Médico substituiu EDA por Ecoendoscopia

- **GIVEN** caso detectado EDA foi autorizado como Ecoendoscopia
- **WHEN** CHD ou NIR abre card/detalhe
- **THEN** vê `Detectado: EDA` e `Autorizado: Ecoendoscopia`
- **AND** justificativa médica correspondente
- **AND** a thread contém uma mensagem sistêmica da transformação.

#### Scenario: Mensagem sistêmica não gera inbox

- **GIVEN** evento de mudança do conjunto médico foi criado
- **WHEN** sua mensagem sistêmica é projetada
- **THEN** nenhuma `UserNotification` é criada
- **AND** nenhum badge global de notificação aumenta.

#### Scenario: Médico substituiu EDA por Colonoscopia

- **GIVEN** caso detectado EDA foi autorizado como Colonoscopia
- **WHEN** CHD abre card/detalhe
- **THEN** vê `Detectado: EDA` e `Autorizado: Colonoscopia`
- **AND** justificativas médicas correspondentes.
