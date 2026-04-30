## Context

New CAP Node.js side-by-side extension on SAP BTP. The service is the system of record for return order exceptions produced by an external matching agent. Human reviewers (finance clerks, returns clerks) act on exceptions via a Fiori Elements UI. After a decision, the CAP service signals an external posting agent that posts journal entries to S/4HANA On Premise. No direct S/4HANA integration exists in this service.

## Goals / Non-Goals

**Goals:**
- Model return order exceptions with a status lifecycle (MATCHED → RESOLVED, PARTIAL → RESOLVED, UNMATCHED → RESOLVED)
- Expose bound CAP actions for each resolution path: `confirm`, `resolve`, `reject`, `escalate`, `linkOrder`
- Record every decision in an append-only `AuditHistory` composition
- Signal the posting agent via outbound HTTP after each resolution action
- Provide Fiori Elements List Report + Object Page UI
- Expose an inbound OData V4 write endpoint for the matching agent

**Non-Goals:**
- Direct S/4HANA posting (handled by posting agent)
- Modifying the matching agent or posting agent
- BTP deployment, HANA Cloud, XSUAA (local development only at this stage)

## Decisions

**D1: Status as `sap.common.CodeList`**
Use a `ReturnOrderStatus` CodeList entity (`MATCHED`, `AMBIGUOUS`, `UNMATCHED`, `RESOLVED_CONFIRMED`, `RESOLVED_REJECTED`, `RESOLVED_LINKED`, `PENDING_SIGNAL`) rather than a plain String enum. Reason: CAP convention for classifying fields; enables localized labels; Fiori Elements renders CodeList associations as value help dropdowns automatically.

**D2: Bound actions on `ReturnOrders` entity**
Five bound actions on `ReturnOrders`: `confirm`, `resolve`, `reject`, `escalate`, `linkOrder(linkedOrderId)`. All take a mandatory `reason: String not null` (except `confirm`). Reason: bound actions carry the entity key automatically, avoiding redundant parameters, and map cleanly to OData POST `.../ReturnOrders(<id>)/ExceptionService.confirm`.

**D3: `AuditHistory` as composition**
`AuditHistory` is a `Composition of many` child of `ReturnOrders`. Reason: lifecycle is tied to the parent order; CAP cascades deep reads and deletes automatically; audit entries are insert-only (no update/delete needed — use `@insertonly` on the service projection).

**D4: `ReceivedItems` as composition**
Received goods line items stored as `Composition of many ReceivedItems` on `ReturnOrders`. Expected items from the original order stored as `Composition of many ExpectedItems`. This enables the side-by-side discrepancy view in the Object Page.

**D5: Outbound posting agent signal via `node-fetch` / `axios` in after-handler**
After a successful action, call the posting agent URL (from `cds.env.requires.postingAgent.url`) using a plain `fetch` call. Store signal failure in a `signalStatus` field (`PENDING`, `SENT`, `FAILED`) on `ReturnOrders`. Reason: keeps the posting agent decoupled; no CAP remote service definition needed since the posting agent does not expose an OData/CDS interface. A `retrySignal` bound action allows manual retry when `signalStatus === 'FAILED'`.

**D6: Two services — `ExceptionService` (UI + actions) and `IntakeService` (matching agent writes)**
Split into two CDS services:
- `ExceptionService`: exposes `ReturnOrders` (read + actions), `AuditHistory` (read), `ExpectedItems` (read), `ReceivedItems` (read) to the UI. Restricts destructive CRUD to internal/admin.
- `IntakeService`: exposes `ReturnOrders` (CREATE + UPDATE only) and `ReceivedItems` / `ExpectedItems` (CREATE) for the matching agent. No actions exposed here.
Reason: avoids two projections of the same entity in one service (CAP CDS restriction); cleanly separates concerns and authorization.

**D7: Fiori Elements annotations in `app/` annotation files**
All `@UI`, `@Common`, `@Communication` annotations kept in `app/annotations.cds`. CDS service definitions stay clean. Reason: CAP convention per `cap-development` skill.

**D8: Mock posting agent with CAP test fixture**
Local development uses an Express mock server (or `cds.test` stub) at a configurable URL. `cds.env` `[development]` profile sets `requires.postingAgent.url` to `http://localhost:5005/signal`. Reason: no `.env` files per project constraints; environment supplied at runtime.

## Risks / Trade-offs

- **Outbound HTTP in action handler** — if the posting agent is slow, the OData action response is delayed. Mitigation: set a short timeout (5 s); persist the decision immediately before the HTTP call; update `signalStatus` after.
- **Two services sharing the same DB entity** — CDS association auto-redirect limitations. Mitigation: D6 strictly prevents two projections of the same entity within the same service; each service has its own isolated projections.
- **`linkOrder` requires a valid `linkedOrderId`** — no cross-system validation of the provided order ID at this stage (posting agent validates). Mitigation: document assumption in task; add `@assert.notNull` on the parameter.
