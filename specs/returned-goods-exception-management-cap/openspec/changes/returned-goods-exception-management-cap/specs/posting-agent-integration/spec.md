## ADDED Requirements

### Requirement: Resolution actions signal the posting agent via outbound HTTP
After a successful resolution action (confirm, resolve, linkOrder, reject), the system SHALL make an HTTP POST to the posting agent URL configured in `cds.env.requires.postingAgent.url`. The payload SHALL include: `orderId`, `decision` (CONFIRMED / ACCEPTED / REJECTED / LINKED), `linkedOrderId` (if applicable), `userId`, and `timestamp`. The request SHALL timeout after 5 seconds.

#### Scenario: Successful signal on confirm
- **WHEN** the `confirm` action completes and the posting agent returns HTTP 200
- **THEN** `signalStatus` on the ReturnOrder is set to SENT

#### Scenario: Signal failure is recorded, decision is not lost
- **WHEN** the posting agent returns a non-2xx response or times out
- **THEN** the resolution decision is already persisted, `signalStatus` is set to FAILED, and the action response includes a warning message to the user

### Requirement: Posting agent URL is configurable without code changes
The posting agent endpoint URL SHALL be read from `cds.env.requires.postingAgent.url`. In local development this SHALL default to `http://localhost:5005/signal`. No `.env` files SHALL be used; the value is supplied via the `[development]` profile in `.cdsrc.json`.

#### Scenario: Local development uses mock URL
- **WHEN** `cds watch` starts with the development profile
- **THEN** outbound signals are sent to `http://localhost:5005/signal`
