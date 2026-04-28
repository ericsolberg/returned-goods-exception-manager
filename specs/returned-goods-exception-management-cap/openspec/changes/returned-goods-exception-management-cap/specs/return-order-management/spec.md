## ADDED Requirements

### Requirement: Return order exceptions are persisted with a status lifecycle
The system SHALL store return order exceptions written by the matching agent with a status of MATCHED, AMBIGUOUS, or UNMATCHED. Each return order SHALL carry an order reference, customer reference, received date, and composition of `ExpectedItems` and `ReceivedItems`. Status SHALL only be transitioned by resolution actions, not by direct PATCH.

#### Scenario: Matching agent creates a MATCHED exception
- **WHEN** the matching agent POSTs a valid return order with status MATCHED to `IntakeService/ReturnOrders`
- **THEN** the record is persisted with status MATCHED and is immediately queryable via `ExceptionService/ReturnOrders`

#### Scenario: Matching agent creates an UNMATCHED exception with received items
- **WHEN** the matching agent POSTs a return order with status UNMATCHED and a deep insert of `receivedItems`
- **THEN** the order and its received items are persisted; no expected items exist

#### Scenario: Invalid payload is rejected
- **WHEN** the matching agent POSTs a return order missing the required `externalOrderRef` field
- **THEN** the service returns HTTP 400 with a structured OData error response

### Requirement: Status field uses a CodeList association
The `status` element of `ReturnOrders` SHALL be an association to a `ReturnOrderStatus` CodeList entity with codes: MATCHED, AMBIGUOUS, UNMATCHED, RESOLVED_CONFIRMED, RESOLVED_REJECTED, RESOLVED_LINKED, PENDING_SIGNAL. Direct update of the `status_code` field via PATCH on `ExceptionService` SHALL be rejected.

#### Scenario: Status is readable as a code and label
- **WHEN** the UI reads a ReturnOrder via ExceptionService
- **THEN** the response includes `status_code` and `status.name` (localized label)

### Requirement: ReturnOrders are read-only in ExceptionService except via actions
The `ReturnOrders` projection in `ExceptionService` SHALL be annotated `@readonly` for standard CRUD. Only bound actions SHALL mutate state.

#### Scenario: Direct PATCH is rejected on ExceptionService
- **WHEN** a client sends PATCH to `ExceptionService/ReturnOrders(<id>)` with a body
- **THEN** the service returns HTTP 405 or 403
