# case-historical-communication Spec Delta

## ADDED Requirements

### Requirement: NIR historical cases shall open details before intercurrence

The system SHALL present NIR historical search results as cards with a detail action, and SHALL allow a NIR user to open a read-only historical case detail before creating a post-schedule intercurrence.

#### Scenario: NIR opens a historical detail from search results
- **GIVEN** a NIR user searches for a `CLEANED` case by occurrence number or patient name
- **WHEN** matching cases are rendered
- **THEN** each result is shown as a card with a `Detalhes` action
- **AND** the `Detalhes` action opens a NIR historical detail for that case
- **AND** the card does not require the NIR to create an intercurrence before seeing details

#### Scenario: NIR creates intercurrence from historical detail
- **GIVEN** a NIR user is viewing the historical detail of a case eligible for post-schedule intercurrence
- **WHEN** the NIR submits a valid intercurrence reason/message from the detail
- **THEN** the system uses the existing post-schedule intercurrence service
- **AND** the case moves to `WAIT_APPT`
- **AND** the existing audit events are recorded

#### Scenario: NIR sees ineligibility reason in historical detail
- **GIVEN** a NIR user is viewing the historical detail of a case not eligible for post-schedule intercurrence
- **WHEN** the detail is rendered
- **THEN** the system shows a human-readable ineligibility reason
- **AND** the system does not show an enabled intercurrence submit action

### Requirement: Notifications for NIR closed cases shall open historical detail

The system SHALL redirect a NIR user opening a notification for a `CLEANED` case to the NIR historical detail for that case.

#### Scenario: NIR opens a notification for a cleaned case
- **GIVEN** a NIR user has a notification linked to a `CLEANED` case
- **WHEN** the user opens the notification
- **THEN** the notification is marked read according to existing behavior
- **AND** the user is redirected to the NIR historical detail for the case

### Requirement: Mentioned scheduler shall receive read-only contextual access

The system SHALL allow a scheduler user who has a notification for a case outside `WAIT_APPT` to open a read-only contextual detail for that case without workflow actions.

#### Scenario: Scheduler opens notification for non-WAIT_APPT case
- **GIVEN** a scheduler user has a notification linked to a case whose status is not `WAIT_APPT`
- **WHEN** the user opens the notification
- **THEN** the user is redirected to a scheduler contextual detail
- **AND** the detail shows case context and communication
- **AND** the detail does not show scheduling, intercurrence response, or lock actions

#### Scenario: Scheduler without notification is denied contextual access
- **GIVEN** a scheduler user does not have a notification linked to a case
- **WHEN** the user attempts to open the contextual detail by URL
- **THEN** access is denied with 404 or 403

#### Scenario: Scheduler WAIT_APPT notification keeps existing workflow
- **GIVEN** a scheduler user has a notification linked to a case in `WAIT_APPT`
- **WHEN** the user opens the notification
- **THEN** the user is redirected to the existing scheduler confirmation workflow

### Requirement: Scheduler historical search shall find processed scheduled cases

The system SHALL provide scheduler users a historical search for accepted scheduled cases that have already been processed/agendados, searchable by occurrence number or patient name and not limited to today.

#### Scenario: Scheduler searches historical case by occurrence number
- **GIVEN** an accepted scheduled case with processed appointment data exists outside today's processed list
- **WHEN** a scheduler searches by its occurrence number
- **THEN** the case appears in historical search results
- **AND** the result includes a `Detalhes` action

#### Scenario: Scheduler searches historical case by patient name
- **GIVEN** an accepted scheduled case with processed appointment data exists
- **WHEN** a scheduler searches by the patient name in structured data
- **THEN** the case appears in historical search results

#### Scenario: Scheduler historical search excludes non-scheduled cases
- **GIVEN** cases that were denied by the doctor, accepted for immediate admission, or not processed by scheduling
- **WHEN** a scheduler performs a historical search
- **THEN** those cases are not returned as scheduler historical results

### Requirement: Scheduler historical message shall notify NIR without changing workflow

The system SHALL allow a scheduler user viewing an eligible historical case to send an operational message to NIR, generating in-app notifications while leaving case workflow state unchanged. The scheduler MAY include additional valid mentions in the same message, and the system SHALL preserve and process those mentions through the existing mention parser.

#### Scenario: Scheduler sends historical operational message to NIR
- **GIVEN** a scheduler user is viewing an eligible historical case detail
- **WHEN** the scheduler submits a non-empty operational message to NIR
- **THEN** the system creates a `CaseCommunicationMessage` on the case
- **AND** the system guarantees NIR is mentioned for notification purposes
- **AND** active NIR users receive `UserNotification`
- **AND** the case status is unchanged

#### Scenario: Scheduler includes additional mentions in historical message
- **GIVEN** a scheduler user is viewing an eligible historical case detail
- **AND** the scheduler needs to notify NIR and explain an operational problem to the evaluating doctor or another valid recipient
- **WHEN** the scheduler submits a message containing an additional valid mention such as `@medico`, `@doctor`, `@supervisor`, or `@username`
- **THEN** the system preserves the additional mention in the saved `CaseCommunicationMessage`
- **AND** the system still guarantees NIR is mentioned for notification purposes
- **AND** the existing mention parser creates notifications for all valid mentioned recipients according to existing rules

#### Scenario: Historical message in cleaned case requires explicit validated path
- **GIVEN** a case is `CLEANED`
- **WHEN** generic case communication is attempted without an explicit historical opt-in
- **THEN** the system rejects the message according to existing cleaned-case protection
- **WHEN** the scheduler historical message endpoint validates historical access and opts in explicitly
- **THEN** the message may be created

#### Scenario: Scheduler historical message does not open intercurrence
- **GIVEN** a scheduler user sends an operational message to NIR from a historical case
- **WHEN** the message is saved and notification is created
- **THEN** no post-schedule intercurrence is opened automatically
- **AND** only a later NIR action through the existing intercurrence flow may move the case to `WAIT_APPT`
