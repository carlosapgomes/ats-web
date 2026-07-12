# Spec: Mobile/PWA PDF viewer

## Requirement: Desktop PDF viewing remains embedded

### Scenario: Desktop PDF remains embedded on case pages

- **GIVEN** a user opens a case page on a desktop viewport
- **WHEN** the case has an authorized PDF
- **THEN** the page still provides an inline `<embed type="application/pdf">` viewer
- **AND** the embed source uses the protected app route for the PDF
- **AND** the desktop control does not require navigating away from the case page

## Requirement: Mobile PDF viewing uses an internal app page

### Scenario: Mobile PDF link navigates inside the PWA

- **GIVEN** a user opens a case page on a mobile/PWA viewport
- **WHEN** the case has an authorized PDF
- **THEN** the visible mobile PDF action links to an internal viewer route in the same app
- **AND** the mobile action does not use `target="_blank"`
- **AND** the mobile action does not link directly to `MEDIA_URL`

## Requirement: Internal viewer provides safe navigation back

### Scenario: Viewer page has top and bottom return actions

- **GIVEN** an authorized user opens the internal PDF viewer page
- **WHEN** the page renders
- **THEN** it shows a “Voltar” action near the top
- **AND** it shows a “Voltar” action after the PDF content area
- **AND** both actions point to a validated `next` URL or a canonical app URL
- **AND** the page does not rely only on browser chrome or `history.back()`

## Requirement: PDF.js renders PDF content with fallback

### Scenario: Viewer loads PDF through the protected route

- **GIVEN** an authorized user opens the viewer page
- **WHEN** PDF.js initializes
- **THEN** it requests the PDF from the existing protected PDF route
- **AND** it renders pages into canvas elements
- **AND** it renders progressively/lazily to avoid loading all pages at once on mobile

### Scenario: Viewer shows fallback when PDF.js fails

- **GIVEN** PDF.js cannot load or render the document
- **WHEN** an error is detected
- **THEN** the viewer shows a clear error message
- **AND** it offers a fallback link to open the original protected PDF route

## Requirement: Authorization and sensitive file handling are preserved

### Scenario: Unauthorized user cannot open viewer route

- **GIVEN** a user without the required active role or object-level permission
- **WHEN** the user requests a PDF viewer route
- **THEN** access is denied consistently with the corresponding case/PDF surface

### Scenario: PDF response remains protected and non-cacheable

- **GIVEN** an authorized user requests a PDF binary route touched by this change
- **WHEN** the response is returned
- **THEN** `Content-Type` is `application/pdf`
- **AND** `Cache-Control` includes `no-store`
- **AND** the response does not expose a filesystem path or direct media URL
