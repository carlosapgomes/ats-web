<!-- markdownlint-disable MD013 -->

# user-notifications Spec Delta

## ADDED Requirements

### Requirement: Notification list shall display only unread and recently read notifications

The user notification list SHALL display only notifications that are unread (`read_at IS NULL`) or read within the retention window (`read_at >= now - NOTIFICATION_READ_RETENTION_HOURS`, default 48 hours). Notifications read before the window boundary SHALL be hidden from the list without being deleted. The window SHALL be measured from `read_at`, never from `created_at`.

#### Scenario: Notification read more than 48 hours ago is hidden

- **GIVEN** the recipient has a notification with `read_at` 49 hours in the past
- **WHEN** the recipient opens the notification list
- **THEN** the notification is not listed
- **AND** the row still exists in the database.

#### Scenario: Notification read within the window remains visible

- **GIVEN** the recipient has a notification with `read_at` 1 hour in the past
- **WHEN** the recipient opens the notification list
- **THEN** the notification is listed.

#### Scenario: Old unread notification is never hidden

- **GIVEN** the recipient has an unread notification (`read_at IS NULL`) created 30 days ago
- **WHEN** the recipient opens the notification list
- **THEN** the notification is listed.

#### Scenario: Window is measured from the reading moment

- **GIVEN** a notification created 100 hours ago whose `read_at` is 1 hour in the past
- **AND** a notification created 1 hour ago whose `read_at` is 100 hours in the past
- **WHEN** the recipient opens the notification list
- **THEN** the first notification is listed
- **AND** the second is hidden.

### Requirement: Hiding notifications shall not mutate or delete notification data

The visibility filter SHALL be a read-time query concern only. Hidden notifications SHALL NOT be deleted or updated, and the unread badge count, notification opening, and mark-as-read flows SHALL remain unchanged for every notification, visible or hidden.

#### Scenario: Hidden notification remains accessible by direct URL

- **GIVEN** a notification hidden by the retention window
- **WHEN** the recipient opens its direct URL
- **THEN** the notification is resolved and the existing redirect/read behavior applies
- **AND** the database row is preserved.

#### Scenario: Unread badge is unaffected by hidden notifications

- **GIVEN** the recipient has read notifications hidden by the window
- **WHEN** the unread badge count is computed
- **THEN** the count equals the number of unread notifications only, as before the change.
