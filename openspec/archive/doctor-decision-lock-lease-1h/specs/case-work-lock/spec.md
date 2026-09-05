<!-- markdownlint-disable MD013 -->

# case-work-lock Spec Delta

## ADDED Requirements

### Requirement: Lock lease duration shall be resolved per work context

The case work lock lease duration SHALL be resolved with the following precedence: an explicit `lease_seconds` argument, when provided, SHALL take precedence; otherwise a context-specific setting SHALL apply when one is registered for the lock context; otherwise the global `CASE_LOCK_LEASE_SECONDS` SHALL apply. The `doctor_decision` context SHALL resolve to `CASE_LOCK_LEASE_SECONDS_DOCTOR` (default 3600 seconds). The `nir_receipt` and `scheduler_confirm` contexts SHALL continue to resolve to the global `CASE_LOCK_LEASE_SECONDS` (default 300 seconds).

#### Scenario: Doctor decision claim uses the one-hour lease

- **GIVEN** `CASE_LOCK_LEASE_SECONDS_DOCTOR = 3600`
- **WHEN** a doctor claims the lock with `context="doctor_decision"` and no explicit `lease_seconds`
- **THEN** the resulting `locked_until` is approximately `now + 3600s`.

#### Scenario: Other contexts keep the global lease

- **GIVEN** the global `CASE_LOCK_LEASE_SECONDS = 300`
- **WHEN** a lock is claimed with `context="nir_receipt"` or `context="scheduler_confirm"` without an explicit lease
- **THEN** the resulting `locked_until` is approximately `now + 300s`.

#### Scenario: Explicit lease argument wins over context settings

- **GIVEN** `CASE_LOCK_LEASE_SECONDS_DOCTOR = 3600`
- **WHEN** a lock is claimed with `context="doctor_decision"` and `lease_seconds=120`
- **THEN** the resulting `locked_until` is approximately `now + 120s`.

### Requirement: Lock renewal shall use the same per-context lease resolution

`renew_case_lock` SHALL resolve the lease duration with the same precedence rules as the claim, extending `locked_until` to approximately `now + resolved_lease` on each successful heartbeat. Renewal of an expired lock SHALL continue to fail, and heartbeat and activity-grace settings SHALL remain unchanged.

#### Scenario: Doctor heartbeat renews by the one-hour lease

- **GIVEN** an active `doctor_decision` lock
- **WHEN** the holder renews it successfully
- **THEN** `locked_until` is approximately `now + 3600s`.

#### Scenario: Renewal of an expired lock still fails

- **GIVEN** a `doctor_decision` lock whose `locked_until` is in the past
- **WHEN** the holder attempts to renew it
- **THEN** renewal is refused with `acquired=False`.
