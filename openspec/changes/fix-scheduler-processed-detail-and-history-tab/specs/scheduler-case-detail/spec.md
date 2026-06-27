# scheduler-case-detail Spec Delta

## MODIFIED Requirements

### Requirement: Scheduler processed case detail shall use scheduler read-only detail

The scheduler processed-today detail SHALL use the scheduler read-only case detail experience, not the NIR operational detail template.

#### Scenario: Scheduler opens a processed-today case detail
- **GIVEN** a scheduler has processed a case today
- **WHEN** the scheduler opens the detail from `Processados Hoje`
- **THEN** the page renders the scheduler read-only detail template
- **AND** it does not render NIR workflow actions
- **AND** it shows the case context, scheduling outcome, communication thread and timeline

#### Scenario: Scheduler detail excludes corrected resubmission action
- **GIVEN** a scheduler opens a case detail from `Processados Hoje`
- **WHEN** the page is rendered
- **THEN** it does not contain `Reenviar caso corrigido`
- **AND** it does not contain `Confirmar Recebimento`

### Requirement: Scheduler shall communicate NIR from processed/historical scheduled cases

The scheduler SHALL be able to send an operational message to NIR from the scheduler case detail for scheduled cases that have already been processed.

#### Scenario: Scheduler sends NIR message from processed-today detail
- **GIVEN** a scheduler opens the detail of a case they processed today
- **AND** the case is in scheduler historical scope
- **WHEN** the scheduler submits a message via `Comunicar NIR`
- **THEN** a `CaseCommunicationMessage` is created
- **AND** the saved message includes or generates a `@nir` mention
- **AND** active NIR users receive in-app notification according to the existing mention service
- **AND** `Case.status` is not changed

#### Scenario: Additional mentions are preserved
- **GIVEN** a scheduler message to NIR includes another valid mention
- **WHEN** the message is submitted
- **THEN** the additional mention remains in the saved body
- **AND** notification handling follows the existing parser/service behavior

### Requirement: Scheduler historical search shall be a primary tab

The scheduler main navigation SHALL expose historical search as a primary tab/entry alongside pending and processed-today work.

#### Scenario: Scheduler queue navigation shows three tabs
- **GIVEN** a scheduler opens `/scheduler/`
- **WHEN** the navigation is rendered
- **THEN** it shows `Pendentes`
- **AND** it shows `Processados Hoje`
- **AND** it shows `Buscar caso antigo`
- **AND** historical search is not only exposed as a small standalone icon button

#### Scenario: Historical search page shows active historical tab
- **GIVEN** a scheduler opens `/scheduler/historical/`
- **WHEN** the page is rendered
- **THEN** the same scheduler navigation is visible
- **AND** `Buscar caso antigo` is the active tab
