## ADDED Requirements

### Requirement: Every resolution decision is recorded in AuditHistory
The system SHALL create an AuditHistory entry on every status transition caused by a resolution action. Each entry SHALL contain: `orderId` (FK), `action` (CONFIRMED / RESOLVED_ACCEPTED / RESOLVED_REJECTED / RESOLVED_LINKED / ESCALATED / REJECTED / SIGNAL_FAILED / SIGNAL_SENT), `reason` (String), `userId` (from `req.user.id`), `timestamp` (managed, auto-set). AuditHistory entries SHALL be insert-only — no UPDATE or DELETE is permitted.

#### Scenario: AuditHistory entry created on confirm
- **WHEN** the `confirm` action succeeds
- **THEN** one new AuditHistory row exists with action=CONFIRMED, userId set to the calling user, and timestamp within 1 second of the call

#### Scenario: AuditHistory entries are readable via ExceptionService
- **WHEN** GET `ExceptionService/ReturnOrders(<id>)/auditHistory` is called
- **THEN** all history entries for that order are returned in ascending timestamp order

#### Scenario: Direct DELETE on AuditHistory is rejected
- **WHEN** DELETE is sent to `ExceptionService/AuditHistory(<id>)`
- **THEN** the service returns HTTP 405 or 403
