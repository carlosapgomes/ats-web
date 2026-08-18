<!-- markdownlint-disable MD013 -->

# dashboard-case-list Spec Delta

## ADDED Requirements

### Requirement: Dashboard shall default the case list to active cases

The dashboard case list SHALL resolve an omitted, empty, or invalid `case_scope` as `active` and SHALL define active cases as every case whose current status is not `CLEANED`, regardless of creation date.

#### Scenario: Initial dashboard load contains old active backlog

- **GIVEN** a manager or admin has an active case created before the current day and a `CLEANED` case
- **WHEN** the dashboard is opened without `case_scope`
- **THEN** the old active case is listed
- **AND** the `CLEANED` case is not listed
- **AND** no implicit current-day date predicate is applied

#### Scenario: Invalid scope falls back safely

- **GIVEN** active and `CLEANED` cases exist
- **WHEN** the dashboard is opened with an unsupported `case_scope`
- **THEN** the scope is resolved as `active`
- **AND** the unsupported value does not cause an error or expose `CLEANED` cases

### Requirement: Dashboard shall provide explicit access to the complete case history

The dashboard case list SHALL offer `case_scope=all`, which removes only the default active-scope predicate and continues to compose with all existing list filters.

#### Scenario: Manager selects all cases

- **GIVEN** active and `CLEANED` cases exist
- **WHEN** the manager selects the all-cases scope
- **THEN** both active and `CLEANED` cases are eligible for the list
- **AND** search, procedure dimension/selection, status, date and attention filters remain server-side predicates

#### Scenario: Active scope is combined with cleaned status

- **GIVEN** a `CLEANED` case exists
- **WHEN** `case_scope=active` and `status=CLEANED` are submitted together
- **THEN** the list is empty because the explicit predicates are incompatible
- **AND** the server does not silently rewrite either user selection

### Requirement: Dashboard shall keep case pagination server-side and bounded

The dashboard case list SHALL paginate the filtered queryset with 20 cases per page and SHALL render a bounded elided navigation range instead of one link for every available page.

#### Scenario: Many result pages exist

- **GIVEN** the filtered list has enough cases for many pages
- **WHEN** an intermediate page is rendered
- **THEN** only a bounded set containing the first, current, neighboring and last pages is shown
- **AND** omitted ranges are represented by non-clickable ellipses
- **AND** previous and next navigation remains available when applicable
- **AND** the server returns at most 20 case cards for the current page

#### Scenario: Filtered page interval is reported

- **GIVEN** a filtered result spans more than one page
- **WHEN** a non-empty page is rendered
- **THEN** the dashboard states the one-based start and end positions of that page
- **AND** it states the total number of cases after all filters

### Requirement: Case scope shall survive dashboard navigation and progressive search

A non-default `case_scope=all` SHALL be preserved across list pagination, metric-period navigation, attention navigation and the existing partial SSR search request.

#### Scenario: User searches while viewing all cases

- **GIVEN** `case_scope=all` is selected
- **WHEN** the user searches through the progressive Vanilla JavaScript behavior
- **THEN** the partial SSR request includes `case_scope=all`
- **AND** returned pagination links retain `case_scope=all`
- **AND** the traditional GET submit remains a functional no-JavaScript fallback
