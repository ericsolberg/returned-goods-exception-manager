## ADDED Requirements

### Requirement: confirm action resolves a MATCHED order
The system SHALL expose a bound action `confirm` on `ReturnOrders` in `ExceptionService`. When called on an order with status MATCHED, it SHALL transition the status to RESOLVED_CONFIRMED, create an AuditHistory entry, and trigger the posting agent signal. An optional `reason` String parameter SHALL be accepted.

#### Scenario: Successful confirm
- **WHEN** `POST ExceptionService/ReturnOrders(<id>)/ExceptionService.confirm` is called on a MATCHED order
- **THEN** status becomes RESOLVED_CONFIRMED, one AuditHistory entry is created with action=CONFIRMED, and the posting agent signal is dispatched

#### Scenario: confirm on non-MATCHED order fails
- **WHEN** `confirm` is called on an order with status UNMATCHED
- **THEN** the service returns HTTP 409 with message "Action not allowed in current status"

### Requirement: resolve action closes an AMBIGUOUS order
The system SHALL expose a bound action `resolve(reason: String not null, decision: String not null)` on `ReturnOrders`. When called on an AMBIGUOUS order with `decision` of ACCEPT or REJECT, it SHALL transition to RESOLVED_CONFIRMED or RESOLVED_REJECTED respectively, create an AuditHistory entry, and signal the posting agent.

#### Scenario: Successful resolve with ACCEPT
- **WHEN** `resolve` is called with `decision=ACCEPT` and a non-empty `reason` on an AMBIGUOUS order
- **THEN** status becomes RESOLVED_CONFIRMED, AuditHistory entry created with action=RESOLVED_ACCEPTED, posting agent signalled

#### Scenario: resolve with missing reason fails
- **WHEN** `resolve` is called without a `reason` value
- **THEN** the service returns HTTP 400

### Requirement: escalate action moves an order to AMBIGUOUS
The system SHALL expose a bound action `escalate(reason: String not null)` on `ReturnOrders` that transitions a MATCHED order to AMBIGUOUS status and records an AuditHistory entry. No posting agent signal is sent for escalations.

#### Scenario: Successful escalate
- **WHEN** `escalate` is called with a reason on a MATCHED order
- **THEN** status becomes AMBIGUOUS and an AuditHistory entry is created with action=ESCALATED

### Requirement: linkOrder action resolves an UNMATCHED order
The system SHALL expose a bound action `linkOrder(linkedOrderId: String not null, reason: String)` on `ReturnOrders`. When called on an UNMATCHED order, it SHALL set `linkedOrderId`, transition status to RESOLVED_LINKED, create an AuditHistory entry, and signal the posting agent.

#### Scenario: Successful linkOrder
- **WHEN** `linkOrder` is called with a non-empty `linkedOrderId` on an UNMATCHED order
- **THEN** `linkedOrderId` is stored, status becomes RESOLVED_LINKED, AuditHistory entry created, posting agent signalled

### Requirement: reject action closes an UNMATCHED or AMBIGUOUS order without posting
The system SHALL expose a bound action `reject(reason: String not null)` on `ReturnOrders`. It SHALL transition the order to RESOLVED_REJECTED, record an AuditHistory entry, and signal the posting agent with decision=REJECTED.

#### Scenario: Successful reject
- **WHEN** `reject` is called with a reason on an UNMATCHED order
- **THEN** status becomes RESOLVED_REJECTED, AuditHistory entry created, posting agent signalled with decision REJECTED

### Requirement: retrySignal action resends the posting agent signal
The system SHALL expose a bound action `retrySignal` on `ReturnOrders`. When called on an order with `signalStatus=FAILED`, it SHALL attempt the outbound HTTP call again and update `signalStatus` to SENT on success or leave it FAILED on failure.

#### Scenario: Successful retry
- **WHEN** `retrySignal` is called on an order with signalStatus=FAILED
- **THEN** the posting agent HTTP call is made and signalStatus becomes SENT on success
