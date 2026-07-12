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

## Requirement: Image attachments use protected internal viewing on mobile

### Scenario: Mobile image attachment opens inside the app

- **GIVEN** a user opens an authorized case page with a PNG or JPEG attachment
- **WHEN** the mobile attachment action is rendered
- **THEN** it links to an internal image viewer route in the same app
- **AND** it does not use `target="_blank"`
- **AND** the viewer displays the image with an HTML `<img>` sourced from a protected attachment route
- **AND** the viewer provides top and bottom return actions

### Scenario: Image viewer rejects non-image attachments

- **GIVEN** an authorized user requests an image viewer route for a PDF or unsupported file type
- **WHEN** the route is evaluated
- **THEN** the request returns 404 or equivalent denial
- **AND** no direct media URL is exposed

## Requirement: Historical NIR PDF attachments use protected internal viewing

### Scenario: Closed-case PDF attachment opens in internal viewer on mobile

- **GIVEN** a NIR user opens the historical detail of an authorized closed case
- **AND** the case has a non-suppressed PDF attachment
- **WHEN** the mobile attachment action is rendered
- **THEN** it links to an internal attachment PDF viewer route
- **AND** it does not use `target="_blank"`
- **AND** the viewer loads the PDF through a protected historical attachment route

### Scenario: Historical attachment route is restricted to NIR historical scope

- **GIVEN** a case or user outside the NIR historical scope
- **WHEN** the historical attachment binary route or viewer route is requested
- **THEN** access is denied
- **AND** suppressed attachments are not served
- **AND** the operational attachment route continues to block closed cases

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
