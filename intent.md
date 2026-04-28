# Returned Goods Exception Management

Returned Goods Exception Management Service — CAP + UI5 BTP Extension

## Business challenge

When a customer initiates a product return they are given an immediate refund along with return instructions. An existing agent matches returned goods against orders and line items. When goods match, journal entries are posted to complete the process. When discrepancies exist, no tooling currently exists to manage these exceptions. A dedicated service is needed to surface these exceptions and give returns clerks and finance staff the ability to confirm matched orders, review ambiguous cases, and manually resolve unmatched orders — after which the existing posting agent is signalled to complete the financial close.

## Key Milestones

1. **Exception Received** — matching agent writes a return order with status (matched/ambiguous/unmatched) into the CAP service.
2. **Matched Order Confirmed** — finance staff reviews and confirms a matched order; CAP signals the posting agent.
3. **Ambiguous Order Resolved** — reviewer investigates discrepancies, makes a determination, and submits the resolution; CAP signals the posting agent.
4. **Unmatched Order Resolved** — returns clerk manually links received goods to an order or rejects; CAP signals the posting agent.
5. **Journal Entries Posted** — downstream posting agent completes the S/4HANA journal entry; exception is closed.

## Business Architecture (RBA)

### End-to-End Process

Lead to Cash / Customer Returns Management (scope item 25I)

### Process Hierarchy

```
Lead to Cash (E2E)
└── Order Fulfillment
    └── Customer Returns Management
        └── Receive and Inspect Returned Goods
            └── Match Returned Goods to Order
            └── Identify and Classify Discrepancies
        └── Discrepancy Resolution
            └── Confirm Matched Orders
            └── Review Ambiguous Cases
            └── Manual Resolution of Unmatched Orders
        └── Financial Close
            └── Signal Posting Agent
            └── Post Journal Entries to S/4HANA
```

### Summary

The challenge maps to Customer Returns Management within Lead to Cash, specifically the sub-process gap where the standard returns flow has no tooling for human-in-the-loop exception handling after automated matching produces ambiguous or unmatched results.

## Fit Gap Analysis

| Requirement (business) | Standard asset(s) found | Gap? | Notes / assumptions |
| --- | --- | --- | --- |
| Worklist of return exceptions segmented by status (matched / ambiguous / unmatched) | My Inbox (Workflow Items); Situation Handling | Maybe | Standard inbox exists but no pre-built returns-matching task type; custom CAP service + UI5 list report required |
| Confirm auto-matched orders with audit trail | SAP Build Process Automation; My Inbox | Maybe | SBPA supports approval tasks but bespoke workflow definition and business context needed |
| Manual matching UI for unmatched orders | — | Yes | No standard SAP asset; fully bespoke CAP/UI5 screen required |
| Ambiguity review with side-by-side discrepancy comparison | — | Yes | No standard UI; custom object page with discrepancy detail needed |
| Signal downstream agent after human decision | — | Yes | Custom action in CAP service (event / webhook / API call to agent) |
| Post journal entries to S/4HANA after confirmation | Journal Entry – Post (Synchronous) SOAP API | No | Standard API exists; handled by the existing posting agent outside this scope |
| Exception aging and SLA notifications | Situation Handling (custom situations) | Maybe | Situation Handling can be configured; requires event emission from CAP |

### Key findings

- The CAP application is the system of record for all exception states; the existing matching agent writes return-order records into it.
- Manual matching and ambiguity resolution UIs are fully custom — no standard SAP asset covers these workflows.
- Journal posting remains with the existing agent; the CAP app only signals it after a human decision is recorded.
- UI5 List Report + Object Page (Fiori Elements) is the appropriate pattern: the list provides the three-status worklist, the object page provides the resolution workspace.
- Situation Handling is available for SLA-based alerting on aging exceptions but requires custom situation types emitted from the CAP layer.
- S/4HANA On Premise (active, functional fit: perfect for ERP) is the downstream system; the Journal Entry Post API is the integration point already handled by the existing agent.

## Recommendations

### Returned Goods Exception Management Service

#### Executive Summary

Build a CAP Node.js service with a UI5 (Fiori Elements) frontend on SAP BTP. The service acts as the system of record for returned goods exceptions, exposes three status-segmented views, and emits a signal to the existing posting agent upon human confirmation or resolution.

#### Recommended Solution

A BTP Extension consisting of:
- **CAP Node.js service** — owns the `ReturnOrder` entity with status (`MATCHED`, `AMBIGUOUS`, `UNMATCHED`, `RESOLVED`), exposes OData V4 endpoints for the UI and for the matching agent to write into, and provides a custom action (`/confirm`, `/resolve`, `/reject`) that signals the downstream posting agent via REST/event.
- **SAP UI5 Fiori Elements frontend** — List Report page with status filter tabs (Matched / Ambiguous / Unmatched), and an Object Page per order exposing order header, line items, received goods details, discrepancy highlights, and resolution actions.
- **Integration** — matching agent writes to CAP via OData; CAP signals posting agent via a configurable outbound HTTP action after human decision.

#### Affected User Roles

- Returns clerks / warehouse staff — resolve unmatched and review ambiguous cases
- Finance / accounting team — confirm matched orders and oversee financial close

#### Recommended solution category

BTP Extension

#### Intent fit
92%
