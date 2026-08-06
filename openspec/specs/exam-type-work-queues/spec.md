# exam-type-work-queues Specification

## Purpose
TBD - created by archiving change introduce-colonoscopy-exam-workflow. Update Purpose after archive.
## Requirements
### Requirement: Médico filtra pendências sem perder a busca

A aba médica `Pendentes` MUST manter o lifecycle primário e oferecer filtro secundário `Todos | EDA | Colonoscopia`.

#### Scenario: Todos como padrão

- **GIVEN** existem EDAs e colonoscopias pendentes
- **WHEN** médico abre a fila sem seleção anterior
- **THEN** todos os casos aparecem
- **AND** cada opção mostra sua contagem.

#### Scenario: Tipo e nome combinados

- **GIVEN** médico digitou um nome e seleciona Colonoscopia
- **WHEN** filtro é aplicado
- **THEN** somente colonoscopias cujo nome/ocorrência corresponde aparecem
- **AND** o texto digitado permanece no campo.

#### Scenario: Limpeza rápida

- **GIVEN** busca ativa
- **WHEN** médico clica `Limpar`
- **THEN** o termo é apagado
- **AND** o resultado é atualizado imediatamente
- **AND** o tipo selecionado permanece.

#### Scenario: Polling HTMX

- **GIVEN** busca e tipo ativos
- **WHEN** conteúdo da fila é atualizado automaticamente
- **THEN** ambos os filtros são reaplicados sem erro.

### Requirement: Decididos Hoje tem badge e filtro simples

A aba médica `Decididos Hoje` MUST identificar o tipo persistido e permitir filtro client-side sem nova busca.

#### Scenario: Médico consulta decididos

- **GIVEN** existem decisões EDA e colonoscopia no dia
- **WHEN** médico abre `Decididos Hoje`
- **THEN** cada card mostra o tipo
- **AND** pode filtrar client-side com Todos como padrão.

### Requirement: CHD filtra todas as pendências pelo mesmo universo do contador

O filtro CHD MUST abranger todos os grupos que alimentam o contador primário de Pendentes.

#### Scenario: Colonoscopia em grupos diferentes

- **GIVEN** há colonoscopia em `WAIT_APPT`, notice operacional e issue operacional
- **WHEN** CHD seleciona Colonoscopia em `Pendentes`
- **THEN** cards dos três grupos permanecem visíveis
- **AND** cards EDA dos três grupos são ocultados
- **AND** a contagem por tipo soma os mesmos grupos do badge primário.

### Requirement: Processados Hoje tem badge e filtro

A aba CHD `Processados Hoje` MUST identificar e filtrar casos pelo tipo persistido sem alterar agenda.

#### Scenario: CHD seleciona EDA

- **GIVEN** processados EDA e colonoscopia no dia
- **WHEN** seleciona EDA
- **THEN** somente cards EDA aparecem
- **AND** nenhum dado de agenda é alterado.

### Requirement: Histórico CHD combina tipo e busca

A busca histórica MUST combinar tipo e termo e MUST aceitar tipo específico sem termo.

#### Scenario: Tipo sem termo

- **GIVEN** CHD seleciona Colonoscopia e deixa busca vazia
- **WHEN** submete o filtro
- **THEN** vê até os últimos 50 casos históricos de colonoscopia.

#### Scenario: Tipo com nome/ocorrência

- **GIVEN** tipo Colonoscopia e termo válido
- **WHEN** busca executa
- **THEN** resultados satisfazem ambos.

### Requirement: Tipo não muda operação

EDA e colonoscopia MUST reutilizar os mesmos forms, locks, permissões e transições para o mesmo estado operacional.

#### Scenario: Mesmo fluxo para ambos

- **GIVEN** EDA e colonoscopia no mesmo estado operacional
- **WHEN** médico/CHD executa ação válida
- **THEN** usam os mesmos forms, locks, permissões e transições
- **AND** não existe atribuição automática por tipo.

