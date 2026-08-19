# dashboard-case-list Specification

## Purpose
TBD - created by archiving change dashboard-active-cases-compact-pagination. Update Purpose after archive.
## Requirements
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

The resolved `case_scope` SHALL be preserved for both `active` and `all` across list pagination, metric-period navigation and the existing partial SSR search request. Non-empty list dates SHALL also remain preserved. Navigation SHALL NOT rely on omission of `case_scope` to infer user intent.

#### Scenario: User searches the default daily all-state list

- **GIVEN** the initial list resolved to `case_scope=all` and today's date bounds
- **WHEN** the user searches through the progressive Vanilla JavaScript behavior
- **THEN** the partial SSR request includes `case_scope=all`
- **AND** it includes both effective date bounds
- **AND** returned pagination links retain the same scope and dates.

#### Scenario: User searches or paginates active backlog

- **GIVEN** `case_scope=active` is selected without date bounds
- **WHEN** the user searches or follows list pagination
- **THEN** the request retains `case_scope=active`
- **AND** it does not gain an implicit current-day predicate
- **AND** the traditional GET submit remains a functional no-JavaScript fallback.

### Requirement: Dashboard shall default the case list to cases received today in every state

The dashboard case list SHALL resolve an initial request with omitted, empty, or invalid list scope as `case_scope=all` bounded by the current local date in both `date_from` and `date_to`. The initial list SHALL therefore include active and `CLEANED` cases received today and SHALL exclude cases received before today.

#### Scenario: Initial dashboard load explains today's received cohort

- **GIVEN** active and `CLEANED` cases were created today
- **AND** active and `CLEANED` cases were created before the current local day
- **WHEN** a manager or admin opens the dashboard without list filters
- **THEN** the effective scope is `all`
- **AND** both date bounds equal the current local date
- **AND** both cases received today are listed
- **AND** neither older case is listed.

#### Scenario: Invalid or empty scope falls back to the initial cohort

- **GIVEN** cases exist inside and outside the current local day
- **WHEN** the dashboard is opened with an empty or unsupported `case_scope` and no explicit dates
- **THEN** the scope resolves as `all`
- **AND** the list remains bounded to cases received today
- **AND** the request does not expose the complete history accidentally.

#### Scenario: Explicit all scope without dates retains historical access

- **GIVEN** active and `CLEANED` historical cases exist
- **WHEN** the manager explicitly requests `case_scope=all` without date values
- **THEN** no implicit current-day predicate is applied
- **AND** active and `CLEANED` historical cases remain eligible for the list.

### Requirement: Dashboard shall provide direct access to active backlog

The dashboard list SHALL expose a visible `Casos ativos` action that requests `case_scope=active` without date bounds. Active backlog SHALL mean every case whose current status is not `CLEANED`, regardless of creation date.

#### Scenario: Manager opens active backlog

- **GIVEN** an old active case and an old `CLEANED` case exist
- **WHEN** the manager activates `Casos ativos`
- **THEN** the old active case is listed
- **AND** the old `CLEANED` case is not listed
- **AND** the effective date controls are empty.

### Requirement: Attention access shall remain transversal to the daily default

The `Atenção necessária` action and a direct request with `attention=1` SHALL NOT inherit the implicit current-day bounds. When no explicit scope is supplied, attention mode SHALL resolve as active. Explicit date bounds supplied by the user SHALL continue to compose with attention criteria.

#### Scenario: Old problematic case remains reachable from the initial dashboard

- **GIVEN** a case received before today satisfies the existing attention criteria
- **WHEN** the manager follows `Atenção necessária` from the initial dashboard
- **THEN** the request uses active scope without implicit date bounds
- **AND** the old problematic case is listed
- **AND** existing attention thresholds and `CLEANED` exclusion remain unchanged.

#### Scenario: User explicitly limits attention by date

- **GIVEN** attention-worthy cases exist on multiple dates
- **WHEN** the manager submits `attention=1` with explicit `date_from` and `date_to`
- **THEN** the explicit dates compose with the existing attention predicate
- **AND** the server does not silently clear the user's dates.

