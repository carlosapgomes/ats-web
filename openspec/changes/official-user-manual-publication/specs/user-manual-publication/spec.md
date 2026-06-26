# user-manual-publication Spec Delta

## ADDED Requirements

### Requirement: Official user manual shall be versioned as Markdown

The system repository SHALL contain an official user manual in Markdown, derived from the reviewed draft, and this Markdown file SHALL be the canonical source for publication.

#### Scenario: Official manual exists
- **GIVEN** the repository is checked out
- **WHEN** a contributor looks for the official user manual
- **THEN** `docs/manual/manual-usuarios.md` exists
- **AND** it contains practical instructions separated by NIR, Médico and CHD/Agendador

#### Scenario: Manual covers current operational flows
- **GIVEN** the official manual exists
- **WHEN** its content is inspected
- **THEN** it covers upload/acompanhamento NIR
- **AND** medical decision flows
- **AND** scheduling confirmation/denial flows
- **AND** immediate admission awareness for CHD
- **AND** post-schedule intercurrence opened by NIR
- **AND** CHD historical communication to NIR for internal scheduling changes

#### Scenario: Manual documents file constraints
- **GIVEN** the official manual exists
- **WHEN** its upload/anexo sections are inspected
- **THEN** it documents supported file types
- **AND** it documents relevant size/count limits shown by the system

### Requirement: Manual PDF shall be generated reproducibly

The repository SHALL provide a script that generates a valid PDF for divulgation from the official Markdown manual.

#### Scenario: Default PDF generation
- **GIVEN** `docs/manual/manual-usuarios.md` exists
- **WHEN** the PDF generation script is executed with default options
- **THEN** a PDF file is created in the default output location
- **AND** the PDF is valid
- **AND** the PDF is generated from the official Markdown source

#### Scenario: Custom PDF output path
- **GIVEN** `docs/manual/manual-usuarios.md` exists
- **WHEN** the PDF generation script is executed with a custom output path
- **THEN** the PDF is created at the requested path
- **AND** parent directories are created when necessary

#### Scenario: Missing manual source fails clearly
- **GIVEN** the requested Markdown input path does not exist
- **WHEN** the PDF generation script is executed
- **THEN** the command fails
- **AND** the error message explains that the input file was not found

### Requirement: Authenticated users shall access the manual in-app

The system SHALL expose an authenticated manual page that renders the official Markdown manual inside the application.

#### Scenario: Authenticated user opens manual page
- **GIVEN** an authenticated user with any active role
- **WHEN** the user opens `/manual/`
- **THEN** the manual page is rendered
- **AND** it contains the official manual content
- **AND** the content is read from `docs/manual/manual-usuarios.md`

#### Scenario: Anonymous user cannot open manual page
- **GIVEN** an anonymous user
- **WHEN** the user opens `/manual/`
- **THEN** the request is redirected to login or denied according to existing authentication behavior

#### Scenario: Manual rendering escapes unsafe HTML
- **GIVEN** Markdown content containing raw unsafe HTML
- **WHEN** the manual renderer creates HTML
- **THEN** unsafe tags are escaped rather than executed/rendered as trusted HTML

### Requirement: Header shall link to manual in a new tab

The authenticated global header SHALL include a Manual link that opens the in-app manual page in a new browser tab.

#### Scenario: Authenticated header shows Manual link
- **GIVEN** an authenticated user
- **WHEN** any page using `templates/base.html` is rendered
- **THEN** the header includes a `Manual` link
- **AND** the link points to the manual page route
- **AND** the link has `target="_blank"`
- **AND** the link has `rel="noopener"`

#### Scenario: Anonymous header does not expose manual link
- **GIVEN** an anonymous user on the login page
- **WHEN** the header is rendered
- **THEN** the authenticated Manual link is not shown
