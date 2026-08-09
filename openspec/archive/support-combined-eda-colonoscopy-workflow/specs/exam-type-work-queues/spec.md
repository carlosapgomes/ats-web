# Capability: Filas por dimensão de procedimento

## MODIFIED Requirements

### Requirement: Médico filtra pendências sem perder a busca

A aba médica `Pendentes` MUST manter lifecycle primário e filtrar por `Todos | EDA | Colonoscopia | EDA + Colonoscopia`, usando procedimentos detectados.

#### Scenario: Combinado e nome compostos

- **GIVEN** médico digitou termo e selecionou EDA + Colonoscopia
- **WHEN** filtro é aplicado ou polling atualiza cards
- **THEN** somente casos com ambos detectados e termo correspondente aparecem
- **AND** termo e seleção permanecem.

### Requirement: Decididos Hoje tem badge e filtro simples

A aba médica `Decididos Hoje` MUST identificar e filtrar pelo conjunto autorizado, preservando casos integralmente negados com indicação `Nenhum autorizado` quando exibidos.

#### Scenario: Combinado parcialmente aprovado

- **GIVEN** caso detectado combinado terminou autorizado somente para EDA
- **WHEN** médico abre Decididos Hoje
- **THEN** badge principal de resultado é EDA
- **AND** transformação combinado → EDA permanece visível.

### Requirement: CHD filtra todas as pendências pelo mesmo universo do contador

O filtro CHD MUST usar procedimentos aprovados em todos os grupos que compõem Pendentes.

#### Scenario: Agendamento casado em grupos operacionais

- **GIVEN** casos combinados autorizados em grupos elegíveis
- **WHEN** CHD seleciona EDA + Colonoscopia
- **THEN** todos os grupos usam o mesmo predicado de ambos aprovados
- **AND** contadores fecham com o universo primário.

### Requirement: Processados Hoje tem badge e filtro

Processados Hoje MUST exibir o snapshot autorizado/agendado e permitir filtro por EDA, Colonoscopia ou combinado.

#### Scenario: Combinado confirmado

- **GIVEN** CHD confirmou caso com ambos aprovados
- **WHEN** consulta Processados Hoje
- **THEN** vê `EDA + Colonoscopia · Agendamento casado`
- **AND** uma única data/hora.

### Requirement: Histórico CHD combina tipo e busca

A busca histórica MUST aceitar `all|eda|colonoscopy|eda_colonoscopy`, usar dimensão autorizada e manter limite/ordering atuais.

#### Scenario: Combinado sem termo

- **GIVEN** CHD seleciona EDA + Colonoscopia sem termo
- **WHEN** submete
- **THEN** vê até os 50 casos históricos mais recentes com ambos autorizados.

### Requirement: Tipo não muda operação

Casos únicos e combinados MUST reutilizar forms, locks, permissões e transições existentes.

#### Scenario: Mesmo submit de agendamento

- **GIVEN** caso combinado em `WAIT_APPT`
- **WHEN** CHD confirma
- **THEN** uma transição atual é usada
- **AND** nenhuma FSM paralela ou segundo agendamento é criado.

## ADDED Requirements

### Requirement: Alterações ficam explícitas nas filas downstream

Quando declaração, detecção e autorização diferirem, médico e CHD MUST receber comparação textual, sem depender apenas de cor.

#### Scenario: Médico substituiu EDA por Colonoscopia

- **GIVEN** caso detectado EDA foi autorizado como Colonoscopia
- **WHEN** CHD abre card/detalhe
- **THEN** vê `Detectado: EDA` e `Autorizado: Colonoscopia`
- **AND** justificativas médicas correspondentes.
