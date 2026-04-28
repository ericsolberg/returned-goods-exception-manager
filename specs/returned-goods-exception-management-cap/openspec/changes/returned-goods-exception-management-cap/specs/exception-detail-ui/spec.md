## ADDED Requirements

### Requirement: Object Page shows order header and discrepancy detail
The Object Page SHALL display: order header section (external order ref, customer, received date, status, signal status, linked order ID if present) and two tables side-by-side or in separate sections — Expected Items and Received Items — showing material, quantity, and unit.

#### Scenario: Object Page loads for a MATCHED order
- **WHEN** the user navigates to a MATCHED ReturnOrder
- **THEN** the header, expected items, and received items sections are all populated

#### Scenario: Object Page loads for an UNMATCHED order with no expected items
- **WHEN** the user navigates to an UNMATCHED ReturnOrder
- **THEN** the expected items table is empty and received items are shown

### Requirement: Resolution action buttons are contextually shown
The Object Page SHALL show action buttons appropriate to the current status:
- MATCHED: `Confirm` and `Escalate`
- AMBIGUOUS: `Resolve` (with decision: Accept / Reject) and `Reject`
- UNMATCHED: `Link Order` and `Reject`
- Any order with signalStatus=FAILED: `Retry Signal`
Actions not applicable to the current status SHALL be hidden.

#### Scenario: Confirm and Escalate shown for MATCHED
- **WHEN** the user opens a MATCHED order
- **THEN** only Confirm and Escalate buttons are visible in the action area

#### Scenario: Link Order shown for UNMATCHED
- **WHEN** the user opens an UNMATCHED order
- **THEN** the Link Order and Reject buttons are visible

### Requirement: Audit History tab shows decision log
The Object Page SHALL include a tab labelled "History" showing the AuditHistory entries for the order in reverse-chronological order with columns: timestamp, user, action, reason.

#### Scenario: History tab populates after a confirm
- **WHEN** the user confirms an order and then opens the History tab
- **THEN** the CONFIRMED entry appears at the top with the correct user and timestamp
