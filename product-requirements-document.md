# Product Requirements Document (PRD)

**Title:** Returned Goods Exception Management Service  
**Date:** 2026-04-20  
**Solution Category:** BTP Extension (CAP Node.js + SAP UI5 Fiori Elements)

---

## Product Purpose & Value Proposition

**Elevator Pitch:**  
When automated returns matching produces ambiguous or unmatched results, there is currently no tooling for human resolution. Finance and warehouse staff have no way to act on these exceptions, leaving the financial close incomplete and refunds unreconciled against actual returned goods.

**Business Need:**  
The existing matching agent classifies every returned goods case as matched, ambiguous, or unmatched — but has no UI surface to expose exceptions for human action. Confirmed-match cases with no discrepancy have no confirmation workflow. Ambiguous and unmatched cases block journal entry posting indefinitely. A dedicated exception management service is required to give the right person the right view and the right action at each stage.

**Product Objectives:**
1. Eliminate the backlog of unresolved exception cases by providing a single, status-segmented worklist for all return order exceptions.
2. Enable finance staff to confirm matched orders and trigger journal posting with a full audit trail.
3. Enable returns clerks to resolve ambiguous and unmatched cases through a structured review and manual matching UI.

---

## User Profiles & Personas

### Primary Persona: Finance Reviewer

**Role:** Accounts Receivable / Finance Clerk  
**Environment:** Desktop, BTP Fiori Launchpad  
**Daily tasks:** Reviews and approves financial transactions, ensures revenue and refund records are balanced, monitors open items in the financial close cycle.  
**Pain points:** Return exceptions sit in an unstructured state with no clear owner; no audit trail exists for who confirmed or adjusted a return; journal entry posting is blocked until cases are manually chased across teams.  
**Technical comfort:** Proficient with SAP Fiori apps; not a developer.  
**Success measure:** All matched exceptions confirmed and posted within SLA; zero unresolved items at period close.

### Secondary Persona: Returns Clerk

**Role:** Warehouse / Returns Processing Staff  
**Environment:** Desktop or shared terminal in the warehouse office.  
**Daily tasks:** Receives returned goods physically, inspects items, records discrepancies, and reconciles actual received goods against expected return documentation.  
**Pain points:** No system to see which return orders are waiting for their input; must chase order references manually; cannot record a resolution decision in any system — today this is done via email or spreadsheet.  
**Technical comfort:** Comfortable with list-based transactional UIs; minimal configuration or admin tasks.  
**Success measure:** Every unmatched and ambiguous case has a clear resolution path; no case requires off-system workarounds.

---

## Business Context

**Current State:**  
The automated matching agent classifies return orders into three states — matched, ambiguous, and unmatched — and writes them into the CAP service. Cases that cannot be automatically closed block the downstream posting agent. No UI exists to surface these cases. Finance and warehouse teams track them ad-hoc. The S/4HANA journal entries for those orders are never posted until someone resolves the exception manually outside any system.

**Strategic Alignment:**  
Closes the last human-in-the-loop gap in the Customer Returns Management process within Lead to Cash. Supports financial close quality and reduces period-end exceptions.

**Success Criteria:**
- All matched return orders are confirmed or escalated within one business day of receipt.
- Ambiguous and unmatched orders are resolved within an agreed SLA (e.g., 3 business days).
- Zero return-related journal entries remain unposted at period close due to tooling gaps.
- Full audit trail exists for every decision made in the exception management service.

---

## Goals and Non-Goals

### Goals (In Scope)

- Expose a three-status worklist (Matched / Ambiguous / Unmatched) for all return order exceptions.
- Enable confirmed matched orders to trigger a signal to the downstream posting agent.
- Enable reviewers to investigate ambiguous orders and submit a resolution that signals the posting agent.
- Enable returns clerks to manually link unmatched received goods to an order, or reject them, and signal the posting agent.
- Persist every human decision with user ID, timestamp, and decision rationale as an audit record.
- Provide the matching agent with an OData V4 write endpoint to register new exceptions.

### Non-Goals (Out of Scope)

- Building or modifying the matching agent itself.
- Building or modifying the downstream journal-entry posting agent.
- Triggering S/4HANA postings directly from the CAP service (this remains with the posting agent).
- Customer-facing return initiation or refund calculation.
- Warehouse goods receipt or inspection workflows beyond recording a resolution decision.
- SLA alerting via Situation Handling (post-MVP consideration).

---

## Requirements

### Must-Have Requirements

**R1: Status-Segmented Exception Worklist**

- **Problem to Solve:** Users have no single place to see all open return exceptions and their current status.
- **User Story:** As a finance reviewer or returns clerk, I need a worklist that groups return orders by status (Matched, Ambiguous, Unmatched) so that I can immediately see what requires my attention.
- **Acceptance Criteria:**
  - Given I open the application, when the list loads, then I see return orders grouped or filterable by status: Matched, Ambiguous, Unmatched, and Resolved.
  - Given I select a status tab, when the list filters, then only orders in that status are shown.
  - Given a new exception is written by the matching agent, when I refresh the list, then the new order appears in the correct status group.
- **Maps to Objective:** 1
- **Priority Rank:** 1

**R2: Matched Order Confirmation**

- **Problem to Solve:** Finance staff cannot confirm matched return orders or trigger journal posting through any system today.
- **User Story:** As a finance reviewer, I need to review a matched return order and confirm it so that the posting agent is signalled to post the journal entries.
- **Acceptance Criteria:**
  - Given a return order in Matched status, when I open it, then I see the order header, line items, and the matched goods details side-by-side.
  - Given I choose Confirm, when I submit, then the order status moves to Resolved, the posting agent is signalled, and my decision is recorded with user ID and timestamp.
  - Given I choose to escalate rather than confirm, when I submit, then the order status changes to Ambiguous and a reason note is required.
- **Maps to Objective:** 2
- **Priority Rank:** 2

**R3: Ambiguous Order Review and Resolution**

- **Problem to Solve:** Ambiguous orders — where received goods partially match or contain discrepancies — have no structured review workflow.
- **User Story:** As a finance reviewer, I need to see the discrepancy detail for an ambiguous order and record a resolution decision so that the case can be closed and posting triggered.
- **Acceptance Criteria:**
  - Given a return order in Ambiguous status, when I open it, then I see the expected vs. received goods comparison with discrepancies highlighted.
  - Given I choose Accept with adjustment, Reject, or Escalate, when I submit with a mandatory reason note, then the status is updated accordingly and the posting agent is signalled (for Accept/Reject).
  - Given the posting agent is signalled, when signalling fails, then the system records the failure, retains the decision, and displays an error requiring retry.
- **Maps to Objective:** 3
- **Priority Rank:** 3

**R4: Manual Matching for Unmatched Orders**

- **Problem to Solve:** Unmatched orders — where no automatic candidate was found — require a returns clerk to manually search for and link the correct sales order.
- **User Story:** As a returns clerk, I need to search for a sales order and link it to an unmatched return so that the exception is resolved and the posting agent can proceed.
- **Acceptance Criteria:**
  - Given a return order in Unmatched status, when I open it, then I see the received goods details and a search panel to find candidate sales orders.
  - Given I search by order number, customer, or material, when results are returned, then I can select one and confirm the link.
  - Given I confirm the link, when I submit, then the order status moves to Resolved, the posting agent is signalled, and the decision is audited.
  - Given no matching order can be found, when I choose Reject, then the order status moves to Resolved (rejected) and a reason note is required.
- **Maps to Objective:** 3
- **Priority Rank:** 4

**R5: Inbound OData Write Endpoint for Matching Agent**

- **Problem to Solve:** The matching agent needs a structured, authenticated endpoint to register new return order exceptions into the CAP service.
- **User Story:** As the matching agent, I need to create and update return order records in the exception service so that they appear in the user's worklist.
- **Acceptance Criteria:**
  - Given the matching agent sends a POST to the OData endpoint, when the payload is valid, then the record is persisted with the correct status and is immediately visible in the UI.
  - Given the matching agent sends an invalid payload, when rejected, then a structured error response is returned.
- **Maps to Objective:** 1
- **Priority Rank:** 1

**R6: Decision Audit Trail**

- **Problem to Solve:** There is no record of who made which decision on a return order exception or when.
- **User Story:** As a finance reviewer or auditor, I need a full history of decisions made on each return order so that I can trace every action for compliance and dispute resolution.
- **Acceptance Criteria:**
  - Given any decision is submitted (confirm, resolve, reject, escalate), when saved, then a history entry is created with: user ID, role, timestamp, action taken, and reason note.
  - Given I view a resolved or escalated order, when I open the history tab, then I see all recorded decision events in chronological order.
- **Maps to Objective:** 2, 3
- **Priority Rank:** 2

### High-Want Requirements

**R7: Posting Agent Signal Retry**

- **Problem to Solve:** If the signal to the posting agent fails, decisions may be silently lost.
- **User Story:** As a system administrator, I need failed posting agent signals to be retried automatically so that no confirmed decision is lost due to transient connectivity issues.
- **Priority Rank:** 1

**R8: Exception Count Indicators on Worklist Tabs**

- **Problem to Solve:** Users cannot see at a glance how many open items require attention in each status group.
- **User Story:** As a finance reviewer, I need to see the count of open exceptions per status tab so that I can prioritise my work.
- **Priority Rank:** 2

### Nice-to-Have Requirements

**R9: SLA Age Indicator**

- **Problem to Solve:** Long-aging exceptions are not visually distinguished from recently received ones.
- **User Story:** As a team lead, I need overdue exceptions to be flagged visually so that I can escalate them before period close.
- **Priority Rank:** 1

---

## Non-Functional Requirements

### Performance
- **Latency:** List report and object page must load within 3 seconds under normal load.
- **Throughput:** The service must handle concurrent access by up to 50 users without degradation.

### Reliability
- **Availability:** 99.5% during business hours; the service must not be a blocking dependency for the posting agent.
- **Fallback:** If the outbound signal to the posting agent fails, the decision is persisted and the user is informed; retry is available without resubmitting the decision.

### Explainability
- **Traceability:** Every resolution decision is traceable to a specific user action, with the payload sent to the posting agent logged alongside it.
- **Decision Logging:** All status transitions and outbound signals are written to the audit history entity.

---

## Solution Architecture

**Architecture Overview:**  
A CAP Node.js application deployed on SAP BTP Cloud Foundry. The CAP service is the system of record for return order exceptions. It exposes OData V4 endpoints consumed by a Fiori Elements UI and by the matching agent. After human decisions, the CAP service emits an outbound HTTP call to the existing posting agent.

**Key Components:**

- **CAP Service (Node.js):** Owns the `ReturnOrders` and `AuditHistory` entities; implements custom actions for confirm, resolve, reject, and escalate; handles outbound signalling to the posting agent.
- **Fiori Elements UI (SAP UI5):** List Report page with status-based filtering; Object Page per return order showing order/goods detail and resolution actions.
- **SAP HANA Cloud:** Persistence layer for the CAP service.
- **Matching Agent (external):** Writes new exception records into the CAP service via OData; not modified by this project.
- **Posting Agent (external):** Receives outbound HTTP signal from CAP after a human decision; posts journal entries to S/4HANA; not modified by this project.

**Integration Points:**

- **Inbound — Matching Agent → CAP:** OData V4 POST/PATCH to create and update return order records.
- **Outbound — CAP → Posting Agent:** HTTP action triggered after confirm/resolve/reject; payload includes order ID, decision, and resolution details.
- **Downstream — Posting Agent → S/4HANA On Premise:** Handled entirely by the posting agent outside this scope; CAP has no direct S/4HANA integration.

**Deployment Environments:**

- **Dev:** BTP subaccount for development; uses HANA Cloud dev instance.
- **Prod:** Dedicated BTP subaccount; HANA Cloud production instance; posting agent endpoint configured via BTP destination.

### Automation & Agent Behaviour

**Automation Level:** Rule-based (status classification is done upstream by the matching agent; this service is human-in-the-loop workflow only).

**Actions the system performs without human approval:**
- Persisting new exception records written by the matching agent.
- Recording audit history entries on every status transition.

**Actions that require human review or approval:**
- Confirming a matched order.
- Resolving or rejecting an ambiguous order.
- Manually linking or rejecting an unmatched order.
- Signalling the posting agent (triggered by human action, not autonomously).

**Guardrails & fail-safes:**
- The posting agent is only signalled after an explicit human submission — never automatically on record creation.
- If outbound signalling fails, the decision is persisted and the order remains in a "pending signal" state; no data is lost.
- Status transitions are one-directional in normal flow (Unmatched/Ambiguous → Resolved); only supervisors can re-open a resolved case (post-MVP).

### Configuration & Data

**Configuration Scope:**  
BTP destination for the posting agent endpoint (URL, authentication). No S/4HANA configuration required for this service.

**Master Data:**  
Return order records and received goods details are written by the matching agent. No master data setup is required in this application.

---

## Governance, Risk & Compliance

**Data Handling:**
- Return order data may include customer identifiers and financial amounts; standard BTP data protection controls apply.
- Audit history records must be retained for the duration of the financial records retention policy.

**Approval Flows:**
- All financial resolution decisions (confirm, resolve) must be made by an authenticated user with the finance reviewer role; no anonymous or shared-account actions are permitted.

---

## Milestones

### M1: Exception Received

- **Description:** A return order exception is written by the matching agent into the CAP service.
- **Achieved when:** A valid return order record is persisted with status Matched, Ambiguous, or Unmatched.
- **Log on achievement:** `M1.achieved: return order exception received [orderId={id}, status={status}]`
- **Log on miss:** `M1.missed: return order exception payload invalid or rejected [reason={reason}]`

### M2: Matched Order Confirmed

- **Description:** A finance reviewer confirms a matched return order, recording the decision and signalling the posting agent.
- **Achieved when:** The order status transitions to Resolved and the posting agent signal is dispatched successfully.
- **Log on achievement:** `M2.achieved: matched order confirmed and posting agent signalled [orderId={id}, userId={userId}]`
- **Log on miss:** `M2.missed: confirmation submitted but posting agent signal failed [orderId={id}, error={error}]`

### M3: Ambiguous Order Resolved

- **Description:** A reviewer investigates the discrepancy and submits a resolution decision for an ambiguous order.
- **Achieved when:** The order status transitions to Resolved and the posting agent signal is dispatched (or the order is rejected).
- **Log on achievement:** `M3.achieved: ambiguous order resolved [orderId={id}, decision={decision}, userId={userId}]`
- **Log on miss:** `M3.missed: ambiguous order resolution failed [orderId={id}, reason={reason}]`

### M4: Unmatched Order Resolved

- **Description:** A returns clerk manually links received goods to a sales order or rejects the return.
- **Achieved when:** The order status transitions to Resolved and the posting agent signal is dispatched.
- **Log on achievement:** `M4.achieved: unmatched order manually resolved [orderId={id}, linkedOrderId={linkedOrderId}, userId={userId}]`
- **Log on miss:** `M4.missed: unmatched order resolution failed [orderId={id}, reason={reason}]`

### M5: Journal Entries Posted

- **Description:** The downstream posting agent confirms successful posting of journal entries to S/4HANA.
- **Achieved when:** The CAP service receives a callback or confirmation from the posting agent that posting succeeded.
- **Log on achievement:** `M5.achieved: journal entries posted [orderId={id}, postingReference={ref}]`
- **Log on miss:** `M5.missed: posting agent reported failure or no confirmation received [orderId={id}]`

---

## Risks, Assumptions, and Dependencies

### Risks

- **Posting agent API contract:** If the posting agent's expected payload changes, outbound signals will fail silently unless versioning or schema validation is in place.
- **Matching agent write volume:** If the matching agent sends bursts of new records, the CAP service must handle concurrent writes without data integrity issues.

### Assumptions

- The matching agent is already capable of writing to an OData V4 endpoint and will be updated to target this service's endpoint.
- The posting agent exposes a documented, stable HTTP endpoint that can receive a structured signal payload.
- BTP XSUAA is used for authentication; user roles (finance reviewer, returns clerk) are manageable via BTP role collections.

### Dependencies

- Matching agent: must be configured to write to this service's OData endpoint.
- Posting agent: must expose a callable HTTP endpoint; its availability affects the signal reliability of this service.
- SAP HANA Cloud instance on BTP.

---

## Appendix

### Glossary

- **Matched:** A return order where the matching agent found a confident 1:1 correspondence between received goods and the original order/line items.
- **Ambiguous:** A return order where the matching agent found partial or conflicting matches requiring human judgement.
- **Unmatched:** A return order where the matching agent found no candidate order; requires manual lookup and linking.
- **Resolved:** A return order on which a human decision has been recorded and the posting agent has been signalled.
- **Posting Agent:** The existing AI agent responsible for posting journal entries to S/4HANA after receiving a signal from the exception management service.
- **Matching Agent:** The existing agent that processes received goods and writes classified exception records into the CAP service.

### References

- SAP Customer Returns Management scope item: 25I
- SAP Fiori Elements — List Report and Object Page: https://ui5.sap.com/
- SAP CAP documentation: https://cap.cloud.sap/
- Journal Entry – Post (Synchronous) SOAP API: SAP Business Accelerator Hub
