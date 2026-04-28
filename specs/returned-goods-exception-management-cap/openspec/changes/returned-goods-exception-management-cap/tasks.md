## 1. Prerequisites

- [x] 1.1 Re-read `product-requirements-document.md` in the project root to confirm all requirements before starting implementation
- [x] 1.2 Re-read the `cap-development` skill (`SKILL.md`) and its references (`references/react-frontend.md`, `references/write-tests.md`) to confirm all conventions before writing any code

## 2. Project Initialisation

- [x] 2.1 From the `assets/` directory, run: `cds init returned-goods-exception-management-cap --nodejs` to scaffold the CAP project
- [x] 2.2 From `assets/returned-goods-exception-management-cap/`, run: `npm add -D @sap/cds-dk && npm pkg set scripts.build="cds build && cp -R app gen/srv/app && find gen/srv/app -name '*.cds' -delete && mkdir -p gen/srv/db && cp -R db/data gen/srv/db/data"`
- [x] 2.3 Create `assets/returned-goods-exception-management-cap/asset.yaml` with the following content (replace `{{placeholder-id}}` with a generated UUID and `{{application-name}}` with `returned-goods-exception-management`):
  ```yaml
  apiVersion: asset.sap/v1
  kind: Asset
  type: base-ui
  metadata:
    id: {{placeholder-id}}
    name: returned-goods-exception-management
  probes:
    startup:
      path: /health
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 18
    liveness:
      path: /health
      initialDelaySeconds: 15
      periodSeconds: 10
      timeoutSeconds: 5
      failureThreshold: 3
    readiness:
      path: /health
      initialDelaySeconds: 5
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 3
  container:
    buildPath: gen/srv
    port: 4004
    env:
      PORT: "4004"
  ```

## 3. CDS Data Model

- [x] 3.1 Create `db/schema.cds` with namespace `returns.exceptions`. Define the following entities:
  - `ReturnOrderStatus` — extends `sap.common.CodeList`, key `code: String(30)`. Add initial data records in `db/data/returns.exceptions-ReturnOrderStatus.csv`: MATCHED, AMBIGUOUS, UNMATCHED, RESOLVED_CONFIRMED, RESOLVED_REJECTED, RESOLVED_LINKED, PENDING_SIGNAL (with English name labels).
  - `ReturnOrders` — aspects `cuid, managed`. Elements: `externalOrderRef: String(50) not null`, `customerRef: String(100)`, `receivedDate: Date`, `status: Association to ReturnOrderStatus`, `signalStatus: String(20) default 'PENDING'` (values: PENDING, SENT, FAILED), `linkedOrderId: String(50)`, `notes: String(500)`. Compositions: `expectedItems: Composition of many ExpectedItems on expectedItems.order = $self`, `receivedItems: Composition of many ReceivedItems on receivedItems.order = $self`, `auditHistory: Composition of many AuditHistory on auditHistory.order = $self`.
  - `ExpectedItems` — aspects `cuid`. Elements: `order: Association to ReturnOrders`, `materialId: String(50)`, `materialDescription: String(200)`, `expectedQty: Decimal(10,3)`, `unit: String(10)`.
  - `ReceivedItems` — aspects `cuid`. Elements: `order: Association to ReturnOrders`, `materialId: String(50)`, `materialDescription: String(200)`, `receivedQty: Decimal(10,3)`, `unit: String(10)`, `condition: String(50)`.
  - `AuditHistory` — aspects `cuid, managed`. Elements: `order: Association to ReturnOrders`, `action: String(50) not null`, `reason: String(500)`, `userId: String(200)`.
- [x] 3.2 Run `cds compile db/` from the project root and fix any errors before proceeding

## 4. Service Definitions

- [x] 4.1 Create `srv/exception-service.cds`. Define `ExceptionService @(path: '/exception')`. Expose:
  - `ReturnOrders` as `@readonly` projection with `@odata.draft.enabled: false`. Expose all scalar fields plus `status`, `auditHistory`, `expectedItems`, `receivedItems`. Annotate status with `@Common.ValueList` pointing to `ReturnOrderStatus`. Bind actions on `ReturnOrders`:
    - `action confirm(reason: String)`
    - `action escalate(reason: String not null)`
    - `action resolve(decision: String not null, reason: String not null)`
    - `action reject(reason: String not null)`
    - `action linkOrder(linkedOrderId: String not null, reason: String)`
    - `action retrySignal()`
  - `AuditHistory` as `@readonly @insertonly` projection (read allowed, no DELETE, no UPDATE via service)
- [x] 4.2 Create `srv/intake-service.cds`. Define `IntakeService @(path: '/intake')`. Expose:
  - `ReturnOrders` — CREATE and UPDATE only (annotate `@restrict: [{grant: 'CREATE'}, {grant: 'UPDATE'}]`). Deep insert of `expectedItems` and `receivedItems` SHALL be supported.
  - `ExpectedItems` — CREATE only
  - `ReceivedItems` — CREATE only
  - Do NOT expose `AuditHistory` or actions in this service
- [x] 4.3 Run `cds compile srv/` and fix any errors before proceeding

## 5. Custom Action Handlers

- [x] 5.1 Create `srv/exception-service.js`. Register bound action handlers using `srv.on('confirm', 'ReturnOrders', ...)` pattern. For each action, follow the single-UPDATE guard pattern from the cap-development skill (one DB call — UPDATE with WHERE clause on current status, then check rows affected):

  **`confirm` handler:**
  - Update ReturnOrders: set `status_code = 'RESOLVED_CONFIRMED'` WHERE `ID = req.params[0].ID AND status_code = 'MATCHED'`. If 0 rows updated, call `req.reject(409, 'Action not allowed in current status')`.
  - Insert AuditHistory entry: `{ order_ID, action: 'CONFIRMED', reason: req.data.reason || '', userId: req.user.id }`.
  - Call `signalPostingAgent(order_ID, 'CONFIRMED', null, req.user.id)` (see task 5.6). On signal failure, update `signalStatus = 'FAILED'` and append a warning to the response via `req.warn(...)`.
  - Log: `console.log(\`M2.achieved: matched order confirmed and posting agent signalled [orderId=${order_ID}, userId=${req.user.id}]\`)` on success, or `console.log(\`M2.missed: confirmation submitted but posting agent signal failed [orderId=${order_ID}, error=${err.message}]\`)` on signal failure.

  **`escalate` handler:**
  - Update: set `status_code = 'AMBIGUOUS'` WHERE `ID AND status_code = 'MATCHED'`. Reject 409 if 0 rows.
  - Insert AuditHistory: `action: 'ESCALATED'`, reason from `req.data.reason`, userId from `req.user.id`.
  - Log: `M3.missed: ambiguous order resolution failed` is not applicable here — log `console.log(\`M3.achieved: order escalated to ambiguous [orderId=${order_ID}]\`)`.

  **`resolve` handler:**
  - Validate `req.data.decision` is one of `['ACCEPT', 'REJECT']`; if not, `req.reject(400, 'decision must be ACCEPT or REJECT')`.
  - Determine target status: `ACCEPT → RESOLVED_CONFIRMED`, `REJECT → RESOLVED_REJECTED`.
  - Update: set `status_code = targetStatus` WHERE `ID AND status_code = 'AMBIGUOUS'`. Reject 409 if 0 rows.
  - Insert AuditHistory: `action: decision === 'ACCEPT' ? 'RESOLVED_ACCEPTED' : 'RESOLVED_REJECTED'`, reason, userId.
  - Call `signalPostingAgent`. Handle failure same as `confirm`.
  - Log achievement: `M3.achieved: ambiguous order resolved [orderId=${order_ID}, decision=${req.data.decision}, userId=${req.user.id}]`. Log miss on signal failure.

  **`reject` handler:**
  - Update: set `status_code = 'RESOLVED_REJECTED'` WHERE `ID AND status_code IN ('UNMATCHED', 'AMBIGUOUS')`. Reject 409 if 0 rows.
  - Insert AuditHistory: `action: 'REJECTED'`, reason, userId.
  - Call `signalPostingAgent` with `decision: 'REJECTED'`. Handle failure.
  - Log: `M4.achieved: unmatched order manually resolved [orderId=..., linkedOrderId=null, userId=...]` or `M3.achieved` depending on original status — use `M4` for UNMATCHED origin, `M3` for AMBIGUOUS origin (read original status before update to determine which to use).

  **`linkOrder` handler:**
  - Update: set `status_code = 'RESOLVED_LINKED', linkedOrderId = req.data.linkedOrderId` WHERE `ID AND status_code = 'UNMATCHED'`. Reject 409 if 0 rows.
  - Insert AuditHistory: `action: 'RESOLVED_LINKED'`, reason, userId.
  - Call `signalPostingAgent` with `decision: 'LINKED', linkedOrderId: req.data.linkedOrderId`. Handle failure.
  - Log: `M4.achieved: unmatched order manually resolved [orderId=${order_ID}, linkedOrderId=${req.data.linkedOrderId}, userId=${req.user.id}]`.

  **`retrySignal` handler:**
  - Read current `signalStatus` for the order. If not `'FAILED'`, `req.reject(409, 'Signal retry only allowed when signalStatus is FAILED')`.
  - Call `signalPostingAgent`. On success update `signalStatus = 'SENT'`. On failure leave `FAILED` and warn.
  - Log: `M5.achieved: journal entries posted [orderId=..., postingReference=...]` on success.

- [x] 5.2 Also register a `before('CREATE', 'ReturnOrders')` handler in `srv/intake-service.js` to log milestone M1:
  - On successful create: `console.log(\`M1.achieved: return order exception received [orderId=${req.data.ID}, status=${req.data.status_code}]\`)`
  - Register a `before('CREATE')` with validation: if `externalOrderRef` is missing, `req.reject(400, 'externalOrderRef is required')` and log `M1.missed`.

- [x] 5.3 Run `cds compile srv/` and fix any errors

## 6. Posting Agent Integration

- [x] 6.1 Add a `.cdsrc.json` at the project root with the development profile posting agent config:
  ```json
  {
    "requires": {
      "postingAgent": {
        "url": "http://localhost:5005/signal"
      }
    },
    "[development]": {
      "requires": {
        "postingAgent": {
          "url": "http://localhost:5005/signal"
        }
      }
    }
  }
  ```
- [x] 6.2 In `srv/exception-service.js`, implement the `signalPostingAgent(orderId, decision, linkedOrderId, userId)` async helper function:
  - Read `cds.env.requires.postingAgent.url` for the endpoint URL
  - Use Node.js built-in `fetch` (Node 18+) or `require('node-fetch')` to POST the payload `{ orderId, decision, linkedOrderId, userId, timestamp: new Date().toISOString() }` with `Content-Type: application/json` and a 5-second `AbortController` timeout
  - On non-2xx response: throw an Error with status and body text
  - On success: update `signalStatus = 'SENT'` on the ReturnOrder record
  - Log `M5.achieved` on success; log `M5.missed` on failure

## 7. Sample Data

- [x] 7.1 From `assets/returned-goods-exception-management-cap/`, run: `cds add data --records 5 --filter "ReturnOrders"` then `cds add data --records 3 --filter "ExpectedItems"` then `cds add data --records 4 --filter "ReceivedItems"` then `cds add data --records 2 --filter "AuditHistory"`
- [x] 7.2 Edit the generated CSV files to replace placeholder values with realistic domain content:
  - `ReturnOrders`: assign statuses MATCHED (2), AMBIGUOUS (1), UNMATCHED (2); use realistic `externalOrderRef` like `SO-2024-00123`; set `signalStatus` to PENDING for all; keep generated UUIDs as IDs
  - `ExpectedItems` / `ReceivedItems`: use material IDs like `MAT-001`, quantities like 2.000, units like `EA`
  - `AuditHistory`: leave empty or with 1–2 realistic entries for the RESOLVED sample if needed
  - Keep `ReturnOrderStatus.csv` aligned with the codes from task 3.1

## 8. Tests

- [x] 8.1 Run `npm add -D @cap-js/cds-test jest` and `cds add test` to scaffold test files
- [x] 8.2 Create `test/exception-service.test.js`. Call `cds.test(__dirname + '/..')` once at the top. Write the following test cases (test custom logic only — not generic CRUD):

  **Test: confirm action transitions MATCHED to RESOLVED_CONFIRMED**
  - Seed a ReturnOrder with `status_code: 'MATCHED'` directly to DB via INSERT (bypass service)
  - Call `srv.send('confirm', { ID }, { ID })` via the service
  - Assert the returned order has `status_code: 'RESOLVED_CONFIRMED'`
  - Assert one AuditHistory entry exists with `action: 'CONFIRMED'`

  **Test: confirm on UNMATCHED order is rejected with 409**
  - Seed a ReturnOrder with `status_code: 'UNMATCHED'`
  - Call `confirm` action and expect rejection with status 409

  **Test: escalate transitions MATCHED to AMBIGUOUS**
  - Seed MATCHED order; call `escalate` with reason; assert `status_code: 'AMBIGUOUS'`

  **Test: resolve with ACCEPT transitions AMBIGUOUS to RESOLVED_CONFIRMED**
  - Seed AMBIGUOUS order; call `resolve` with `decision: 'ACCEPT'`; assert RESOLVED_CONFIRMED

  **Test: resolve with invalid decision is rejected with 400**
  - Seed AMBIGUOUS order; call `resolve` with `decision: 'MAYBE'`; expect 400

  **Test: linkOrder transitions UNMATCHED to RESOLVED_LINKED**
  - Seed UNMATCHED order; call `linkOrder` with `linkedOrderId: 'SO-2024-99999'`; assert RESOLVED_LINKED and `linkedOrderId` stored

  **Test: reject transitions UNMATCHED to RESOLVED_REJECTED**
  - Seed UNMATCHED order; call `reject` with reason; assert RESOLVED_REJECTED

  **Test: IntakeService CREATE validates required externalOrderRef**
  - Connect to `IntakeService`; attempt CREATE without `externalOrderRef`; expect 400

- [x] 8.3 Run `npx jest --testPathPattern exception-service` and fix all failures before proceeding

## 9. React Frontend

- [x] 9.1 Use the `search_model` tool from `cds-mcp` to read the effective model of `ExceptionService` — collect the OData base path, entity names, key fields, scalar fields, and bound actions
- [x] 9.2 Read the template at `.claude/skills/cap-development/assets/react-app-template.html`
- [x] 9.3 Create `app/index.html` as a single-file React app

  **Tabs / Views:**
  - **Worklist tab** — default view: table of `ReturnOrders` from `ExceptionService/ReturnOrders`. Columns: External Order Ref, Customer Ref, Received Date, Status (badge coloured by status — green for RESOLVED, amber for MATCHED, red for UNMATCHED, orange for AMBIGUOUS), Signal Status (badge). Row click navigates to Detail view.
  - **Detail view** — shown when a row is selected. Displays:
    - Header section: all scalar fields of the selected order
    - Two side-by-side tables: Expected Items (`GET ReturnOrders(<id>)/expectedItems`) and Received Items (`GET ReturnOrders(<id>)/receivedItems`). Show material ID, description, quantity, unit, and (received items only) condition.
    - Action buttons, shown conditionally by `status_code`:
      - MATCHED: **Confirm** (no params — POST `.../ExceptionService.confirm`) and **Escalate** (dialog: reason field)
      - AMBIGUOUS: **Resolve** (dialog: decision dropdown ACCEPT/REJECT + reason field) and **Reject** (dialog: reason field)
      - UNMATCHED: **Link Order** (dialog: linkedOrderId text input + optional reason) and **Reject** (dialog: reason)
      - Any order with `signalStatus === 'FAILED'`: **Retry Signal** button (no params)
    - **History tab within detail**: table of `auditHistory` items (`GET ReturnOrders(<id>)/auditHistory?$orderby=createdAt desc`) showing timestamp, user, action, reason
    - **Back** button to return to Worklist
  - On action success: show green auto-dismiss banner; refresh the detail data
  - On action error: show red banner with error message from OData response
  - Use `.btn-green` for Confirm/Resolve-Accept, `.btn-amber` for Escalate, `.btn-red` for Reject, `.btn-blue` for Link Order and Retry Signal per the template CSS conventions

- [x] 9.4 Confirm `app/index.html` exists at `assets/returned-goods-exception-management-cap/app/index.html`

## 10. Validation

- [x] 10.1 Run `cds compile srv/` — fix all errors
- [x] 10.2 Start `cds watch` from the project directory and confirm the server starts on port 4004 without errors
- [x] 10.3 Smoke-test the IntakeService: expect HTTP 201
- [x] 10.4 Smoke-test ExceptionService read: expect HTTP 200 with JSON array
- [x] 10.5 Smoke-test confirm action: expect HTTP 200 or 204
- [x] 10.6 Run `npx jest` — all tests pass
- [x] 10.7 Open `http://localhost:4004` in a browser and confirm the React UI loads
