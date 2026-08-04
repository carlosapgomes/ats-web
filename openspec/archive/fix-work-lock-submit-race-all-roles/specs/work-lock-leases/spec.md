# work-lock-leases Spec Delta

## ADDED Requirements

### Requirement: Lock-managed workflow submits shall not release the lock before the protected POST is processed

Pages that manage a case work lock SHALL avoid client-side lock release while submitting a protected workflow form carrying the current `lock_token`.

#### Scenario: Scheduler submits appointment confirmation
- **GIVEN** a scheduler has opened a `WAIT_APPT` case and holds a valid `scheduler_confirm` lock
- **WHEN** the scheduler confirms or denies the appointment using the lock-managed form
- **THEN** the client-side unload/release handlers do not release the lock before the submit POST is processed
- **AND** the backend remains responsible for releasing the lock after successful business logic

#### Scenario: Doctor submits medical decision
- **GIVEN** a doctor has opened a `WAIT_DOCTOR` case and holds a valid `doctor_decision` lock
- **WHEN** the doctor submits the decision form with the current `lock_token`
- **THEN** the client-side unload/release handlers do not release the lock before the submit POST is processed
- **AND** the backend remains responsible for releasing the lock after successful business logic

#### Scenario: NIR confirms final receipt
- **GIVEN** a NIR user has opened a final-result case and holds a valid `nir_receipt` lock
- **WHEN** the NIR user submits the receipt confirmation form with the current `lock_token`
- **THEN** the client-side unload/release handlers do not release the lock before the submit POST is processed
- **AND** the backend remains responsible for clearing the lock after successful completion

#### Scenario: Submit is intercepted for validation or confirmation modal
- **GIVEN** a locked case page uses a submit handler to validate fields or open a confirmation modal
- **WHEN** that handler cancels the initial submit event with `preventDefault()`
- **THEN** the work-lock submit guard does not treat the canceled event as protected workflow completion
- **AND** lock release behavior is not suppressed solely because a modal was opened

#### Scenario: Non-workflow form on a locked page is submitted
- **GIVEN** a locked case page contains another form that does not carry the current `lock_token`
- **WHEN** the user submits that non-workflow form
- **THEN** the work-lock submit guard does not treat it as protected workflow completion
- **AND** lock release behavior is not suppressed solely because of that form

### Requirement: Hiding a locked browser tab shall not explicitly release the work lock

A browser tab visibility change SHALL NOT be treated as abandonment of a lock-managed case screen.

#### Scenario: User switches tabs while reviewing a locked case
- **GIVEN** a user has a lock-managed case screen open
- **WHEN** the browser fires `visibilitychange` with state `hidden`
- **THEN** the client does not call the lock release endpoint because of that event
- **AND** normal lease expiry/heartbeat behavior remains responsible for abandoned sessions

### Requirement: Lost-lock errors shall be actionable for users

When a protected submit reaches the backend after the lock has been lost or expired, the user-facing error SHALL explain that the screen reservation expired or was released before submission and instruct the user to reopen the case from the queue.

#### Scenario: Submit after lock was already released
- **GIVEN** a user submits a lock-protected workflow form with an old token
- **AND** the case no longer has an active lock
- **WHEN** the backend validates the lock
- **THEN** the user sees: `A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.`
- **AND** the workflow action is not applied

#### Scenario: Submit after lock expired
- **GIVEN** a user submits a lock-protected workflow form with an expired lock
- **WHEN** the backend validates the lock
- **THEN** the user sees: `A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.`
- **AND** the workflow action is not applied
