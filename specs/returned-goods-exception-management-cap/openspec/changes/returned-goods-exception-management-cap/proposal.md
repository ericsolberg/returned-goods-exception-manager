## Why

The automated returns matching agent classifies incoming return orders as Matched, Ambiguous, or Unmatched, but there is no application for human reviewers to act on these exceptions. Unresolved exceptions block the downstream journal-entry posting agent, leaving financial close incomplete.

## What Changes

- New CAP Node.js service exposing OData V4 endpoints for return order exception management
- New Fiori Elements UI with List Report (status-segmented worklist) and Object Page (resolution workspace)
- Custom CAP actions: `confirm`, `resolve`, `reject`, `escalate`, `linkOrder` with outbound HTTP signalling to the posting agent
- Audit history entity recording every user decision with user ID, timestamp, action, and reason note
- Inbound write endpoint for the external matching agent to register new exceptions

## Capabilities

### New Capabilities

- `return-order-management`: Core CRUD and status lifecycle for return order exceptions (Matched / Ambiguous / Unmatched / Resolved). Inbound OData endpoint for matching agent writes.
- `exception-resolution`: Custom actions (confirm, resolve, reject, escalate, linkOrder) that transition order status, record audit history, and signal the downstream posting agent via outbound HTTP.
- `audit-history`: Append-only audit trail entity tracking every decision event per return order.
- `posting-agent-integration`: Outbound HTTP call to the posting agent after a resolution decision; handles failure recording and retry state.
- `exception-worklist-ui`: Fiori Elements List Report with status filter tabs, count badges, and navigation to the Object Page.
- `exception-detail-ui`: Fiori Elements Object Page showing order header, line items, received goods, discrepancy highlights, resolution action buttons, and audit history tab.

### Modified Capabilities

*(none — new application)*

## Impact

- New CAP project under `assets/returned-goods-exception-management-cap/`
- New Fiori Elements app under `assets/returned-goods-exception-management-cap/app/`
- External dependency: posting agent HTTP endpoint (mocked locally)
- External dependency: matching agent writes via OData (no code change to the agent in this project)
