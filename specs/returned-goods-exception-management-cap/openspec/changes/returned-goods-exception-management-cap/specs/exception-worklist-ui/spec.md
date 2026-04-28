## ADDED Requirements

### Requirement: List Report displays return orders segmented by status
The application SHALL render a Fiori Elements List Report at the root route. The list SHALL display columns: external order reference, customer, received date, status (with label), and signal status. The list SHALL support filter by `status_code` using a selection field. The default filter SHALL show all non-RESOLVED orders.

#### Scenario: List loads with open exceptions visible
- **WHEN** the user opens the List Report
- **THEN** all orders with status MATCHED, AMBIGUOUS, or UNMATCHED are visible by default

#### Scenario: User filters to MATCHED only
- **WHEN** the user sets the status filter to MATCHED and applies
- **THEN** only MATCHED orders appear in the table

#### Scenario: Count of items per status is visible
- **WHEN** the list is loaded
- **THEN** the total count of displayed rows is shown in the table header

### Requirement: List Report allows navigation to the Object Page
Each row in the list SHALL be navigable to the Object Page for that return order.

#### Scenario: Navigation from list to detail
- **WHEN** the user clicks a row in the List Report
- **THEN** the Object Page for that ReturnOrder opens
