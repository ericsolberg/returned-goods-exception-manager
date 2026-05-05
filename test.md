# Product Requirements Document (PRD)

**Title:** Pharmaceutical Pricing Validation & Chargeback Automation  
**Date:** 2026-05-04  
**Owner:** Pricing Operations / Supply Chain Finance  
**Solution Category:** n8n Workflow, AI Agent, BTP Extension

---

## Product Purpose & Value Proposition

**Elevator Pitch:**  
Every incoming pharmaceutical order is currently validated against only a subset of four pricing sources, allowing price discrepancies to pass through undetected until a supplier rejects a chargeback. This solution validates every order against all four sources simultaneously, automatically files chargeback claims for confirmed discrepancies, and gives pricing analysts an AI assistant to resolve exceptions and disputes quickly — eliminating the manual, ad hoc process that has produced $2.3M in aging claims and a 2% rise in negative-margin transactions over the last 30 days.

**Business Need:**  
The organization has four distinct pricing sources for pharmaceutical products — customer expected price, GPO contract prices, Supplier WAC pricing, and the internal pricing hub — all residing within SAP S/4HANA. Current validation happens only between pairs of these sources, not across all four. This leaves multi-source discrepancies undetected at order time. By the time a supplier rejects the resulting chargeback claim, the margin is already lost and the dispute is costly to resolve manually. There is no defined workflow for chargeback resolution, making the $2.3M aging backlog impossible to reduce systematically.

**Expected Value:**  
- Recovery and prevention of margin leakage from the $2.3M aging chargeback backlog
- Reduction in negative-margin transactions (currently trending +2% per 30 days)
- Significant reduction in analyst hours spent on manual price cross-checking and dispute preparation
- Higher EDI match rate across all four pricing sources on first-pass order validation

**Product Objectives (Prioritized):**
1. Automate 4-way price validation on every incoming order (EDI and manual) to prevent undetected discrepancies from reaching fulfillment
2. Automatically generate and route supplier chargeback claims for validated discrepancies, eliminating the current fully manual claim-creation step
3. Provide pricing analysts with an AI assistant that can resolve exceptions and chargeback disputes using live S/4HANA pricing and contract data

---

## User Profiles & Personas

### Primary Persona: Pricing Analyst — "Maria"

Maria is a 34-year-old pricing analyst at a pharmaceutical wholesale distributor. She spends 60–70% of her day managing price discrepancies that surface after orders have been released or invoiced. She regularly opens three or four separate screens in SAP S/4HANA to compare GPO contract conditions, WAC pricing, and customer expected prices — a process she performs dozens of times each day. She is technically proficient with SAP but finds the cross-source validation effort repetitive and error-prone. Her biggest frustration is that she cannot always tell whether a discrepancy is a data entry error, a GPO contract update that didn't sync, or a genuine supplier billing error. She needs a single interface that surfaces discrepancies with context and a recommended resolution path.

### Secondary Persona: Chargeback Specialist — "James"

James is a 41-year-old chargeback specialist responsible for submitting and tracking supplier chargeback claims. He manages a queue of 200+ open claims at any given time, most of which are resolved via email exchanges or phone calls with supplier accounts-payable contacts. He has no systematic way to prioritize his queue by recovery probability or aging risk. He spends significant time reconstructing the pricing evidence needed to support each dispute — going back to the original order, the GPO contract, and the WAC price in effect at the time of shipment. He needs automated claim creation with pre-populated evidence and a priority-ranked queue.

### Secondary Persona: Finance Controller — "Sandra"

Sandra monitors margin exposure and cash flow impact from unresolved chargebacks. She needs aggregate visibility into chargeback recovery rates, aging buckets, and negative-margin order trends. She does not work individual claims but needs dashboard-level metrics to escalate with leadership and track whether the automation initiative is delivering ROI.

### Other User Types

- Order Management Specialist: monitors orders blocked pending price resolution and releases them once validated
- SAP S/4HANA System Administrator: manages API credentials, authorization objects, and integration configuration

---

## User Goals & Tasks

### For Maria (Pricing Analyst):

**Goals:**
- Spend time on genuine exceptions, not routine cross-referencing
- Resolve exceptions with confidence, knowing all four price sources have been checked

**Key Tasks:**
- Review the exception queue for orders flagged by the validation workflow
- Invoke the AI agent to analyze a specific discrepancy and get a recommended resolution
- Approve or override the agent's recommendation and record the decision with an audit note

### For James (Chargeback Specialist):

**Goals:**
- Process more claims per day with less manual effort
- Prioritize claims by recovery probability and aging

**Key Tasks:**
- Review auto-generated chargeback claims with pre-populated pricing evidence
- Use the AI agent to draft dispute correspondence or identify missing contract documentation
- Track claim status and escalate stalled disputes

---

## Business Context

**Current State:**  
Incoming orders (mix of EDI X12 850 and manual entry) enter SAP S/4HANA SD with pricing validated only between select pairs of sources. Discrepancies pass through to fulfillment and invoicing. The existing Chargeback Root Cause Classifier Agent analyzes disputes to classify the root cause, and customer communications are managed through the existing Customer Messaging Agent. Today: $2.3M aging supplier chargeback claims, negative-margin transactions +2% over 30 days.

**Strategic Alignment:**  
Improving chargeback recovery and EDI match rates directly protects gross margin, reduces working capital tied up in disputed claims, and improves supplier relationships by reducing erroneous claims.

**Success Criteria:**
- EDI match rate across all four pricing sources reaches ≥95% (from current partial-pair baseline)
- Automated chargeback claims cover ≥90% of validated discrepancies without manual intervention
- Analyst time per exception resolution reduced by ≥50%
- Aging chargeback backlog reduced by ≥40% within 90 days of go-live

---

## Goals and Non-Goals

### Goals (In Scope)

- 4-way price validation on every incoming order line against customer expected price, GPO contract price, Supplier WAC, and internal pricing hub — all sourced from SAP S/4HANA
- Automated chargeback claim creation in S/4HANA for validated discrepancies exceeding configured tolerance thresholds
- AI agent available to pricing analysts and chargeback specialists for exception analysis and dispute resolution support
- Operational dashboard (BTP) showing match rates, exception queue, chargeback aging, and resolution status

### Non-Goals (Out of Scope)

- Replacing or reconfiguring the existing S/4HANA pricing condition and contract master data setup
- EDI infrastructure build (assumes existing AS2/VAN or SAP Integration Suite middleware is in place)
- Automated supplier communication (agent recommends; human sends)
- Coverage of non-pharmaceutical product lines
- Real-time price updates from external GPO portals (GPO data is already maintained in S/4HANA condition records)

---

## Requirements

### Must-Have Requirements

**R1**: 4-Way Order Price Validation Workflow

- **Problem to Solve**: Incoming orders are validated against only a subset of pricing sources, allowing discrepancies to reach fulfillment undetected.
- **User Story**: As an Order Management Specialist, I need every incoming order line automatically validated against all four pricing sources so that price mismatches are caught before the order is released.
- **Acceptance Criteria**:
  - Given an inbound order (EDI or manual), when the validation workflow is triggered, then each line is compared against customer expected price, GPO contract price, Supplier WAC, and internal S/4HANA pricing conditions.
  - Given all four source prices are within configured tolerance, when validation completes, then the order line is auto-approved and proceeds to fulfillment.
  - Given a discrepancy exceeds tolerance on any source pair, when validation completes, then the line is routed to the exception queue and/or chargeback creation.
- **Maps to Objective**: Objective 1
- **Priority Rank**: 1

**R2**: Automated Chargeback Claim Creation

- **Problem to Solve**: Chargeback claims are created manually today, causing delays, inconsistent evidence, and a growing backlog.
- **User Story**: As a Chargeback Specialist, I need confirmed supplier price discrepancies to automatically generate a chargeback claim in S/4HANA with pre-populated pricing evidence so that I can focus on dispute resolution rather than claim setup.
- **Acceptance Criteria**:
  - Given a validated discrepancy attributable to a supplier pricing error, when the workflow confirms it exceeds threshold, then a chargeback claim is created in S/4HANA with order reference, pricing source comparison, and variance amount.
  - Given a claim is created, when it is routed, then it appears in the chargeback specialist's queue within the dashboard.
- **Maps to Objective**: Objective 2
- **Priority Rank**: 2

**R3**: AI-Assisted Exception and Dispute Resolution

- **Problem to Solve**: Pricing analysts and chargeback specialists spend significant time reconstructing context for each exception without an intelligent assistant.
- **User Story**: As a Pricing Analyst, I need an AI agent that can analyze a pricing discrepancy using live contract and pricing data from S/4HANA and provide a recommended resolution so that I can resolve exceptions faster and with greater confidence.
- **Acceptance Criteria**:
  - Given an exception in the queue, when a pricing analyst invokes the agent, then the agent retrieves the relevant GPO contract terms, WAC price history, customer expected price, and internal conditions and presents a structured analysis with a recommended resolution action.
  - Given an agent recommendation, when the analyst reviews it, then they can accept, override, or escalate with a recorded decision and audit trail.
- **Maps to Objective**: Objective 3
- **Priority Rank**: 3

**R4**: Pricing Operations Dashboard

- **Problem to Solve**: No unified visibility into match rates, exception backlog, or chargeback aging exists today.
- **User Story**: As a Finance Controller, I need a dashboard that shows real-time match rates, aging chargeback values, and exception queue status so that I can monitor the health of the pricing validation process.
- **Acceptance Criteria**:
  - Dashboard displays: 4-way match rate by source pair, open exception count by aging bucket, chargeback claim value by status (open / disputed / recovered).
  - Exception queue is filterable by product, customer, GPO, and age.
- **Maps to Objective**: Objectives 1, 2, 3
- **Priority Rank**: 4

---

## Solution Architecture

**Architecture Overview:**  
Three integrated components deployed on SAP BTP, all reading from and writing to SAP S/4HANA via standard OData APIs. The n8n workflow handles order-event-driven automation. The AI agent handles open-ended reasoning on exceptions. The BTP Extension (CAP + React) provides the operational UI.

**Key Components:**

- **n8n Workflow – Order Price Validation Pipeline**: Triggered on each inbound order event. Fetches all four pricing sources from S/4HANA (Condition Record for Pricing in Sales, Price Simulation API, Sales Contract API). Computes per-line variance. Routes auto-approved lines to fulfillment; routes exception lines to the exception queue and/or chargeback creation.
- **AI Agent – Chargeback Resolution Assistant**: Pro-code Python A2A agent. Tools: query S/4HANA sales contracts, pricing condition records, purchase order history, chargeback claim status. Invoke the Chargeback Root Cause Agent to determine root cause to plan remediation options. Invoked on-demand by pricing analysts or automatically by the workflow for exception lines. Returns structured analysis and recommended resolution.
- **BTP Extension – Pricing Operations Dashboard**: CAP service (Node.js) + React UI with SAP UI5 Web Components. Displays match rates, exception queue, chargeback aging, and resolution status. Provides the interface for analysts to invoke the agent and record decisions.

**Integration Points:**

- SAP S/4HANA ↔ n8n Workflow: OData APIs — `Condition Record for Pricing in Sales` (`API_SLSPRICINGCONDITIONRECORD_SRV`), `Price Simulation – Read` (`CE_PURGDOCPRICINGSIMULATION_0001`), `Sales Contract` (`API_SALES_CONTRACT_SRV`), `Purchase Order` (`OP_API_PURCHASEORDER_PROCESS_SRV_0001`); read and write
- SAP S/4HANA ↔ AI Agent: same OData APIs, read-only for analysis; chargeback claim creation via SD API on resolution
- EDI/Manual Order Entry ↔ n8n Workflow: inbound order event trigger (via SAP Integration Suite or webhook from S/4HANA order creation event)
- Chargeback Root Classifier Agent: Used for automated determination of root cause for chargeback dispute, provides input for remediation plan.
- Customer Messenger Agent: Used for all customer communications regarding their order disposition.

**Deployment Environments:**

- Dev: SAP Joule Studio runtime sandbox S/4HANA tenant; synthetic order data only
- QA: SAP Joule Studio runtime S/4HANA QA system; representative pricing master data
- Prod: SAP Joule Studio runtime connected to production S/4HANA; full authorization and audit logging enabled

### Automation & Agent Behaviour

**Automation Level:** Hybrid — rule-based workflow for validation and chargeback creation; autonomous AI agent for exception reasoning

**Actions the system performs without human approval:**
- Retrieve pricing conditions from all four sources and compute variance
- Auto-approve order lines within configured tolerance
- Create chargeback claims in S/4HANA for validated supplier discrepancies above threshold
- Route exceptions to the analyst queue

**Actions that require human review or approval:**
- Resolution of exception lines (accept, dispute, escalate) — agent recommends, analyst approves
- Sending dispute correspondence to suppliers
- Adjusting pricing tolerance thresholds

**Model or engine used:** GPT-4o via SAP Generative AI Hub (AI agent reasoning); deterministic rule engine (workflow validation and tolerance checks)

**Knowledge & data sources accessed:**
- SAP S/4HANA Condition Records for Pricing in Sales — authoritative GPO and WAC pricing conditions
- SAP S/4HANA Sales Contracts — GPO contract terms and eligible customer/product combinations
- SAP S/4HANA Purchase Orders and Order History — context for dispute evidence
- SAP S/4HANA Chargeback Claims (SD) — claim status for tracking and resolution

**Tools or connectors invoked:**
- `get_pricing_conditions`: reads condition records for a given customer/material/date combination — read-only
- `get_sales_contract`: retrieves GPO contract terms and pricing — read-only
- `get_order_history`: fetches order and billing document history — read-only
- `get_chargeback_status`: reads open chargeback claims — read-only
- `create_chargeback_claim`: creates a new chargeback claim in S/4HANA SD — write, triggered only on validated discrepancy

**Guardrails & fail-safes:**
- Agent never modifies pricing master data or condition records
- Agent never sends external communications autonomously
- If S/4HANA API is unreachable, the validation workflow halts the order line and routes to manual review rather than auto-approving
- All agent recommendations are logged with the source data used for the reasoning
- Low-confidence agent responses surface a confidence indicator and escalate to human review

---

## Milestones

### M1: Order Ingested

- **Description**: An incoming order (EDI or manual) has been received, parsed, and enriched with NDC/product and customer identifiers.
- **Achieved when**: Order line data is available in the validation workflow with all required identifiers to query the four pricing sources.
- **Log on achievement**: `M1.achieved: order ingested and enriched — order_id={order_id}, line_count={line_count}, channel={edi|manual}`
- **Log on miss**: `M1.missed: order ingestion failed or incomplete — order_id={order_id}, reason={reason}`

### M2: 4-Way Price Match Executed

- **Description**: All four pricing sources have been queried from S/4HANA and the variance for each order line has been computed.
- **Achieved when**: Condition records, GPO contract price, Supplier WAC, and internal pricing hub price have all been retrieved and compared for every line.
- **Log on achievement**: `M2.achieved: 4-way price match completed — order_id={order_id}, lines_matched={count}, lines_discrepant={count}`
- **Log on miss**: `M2.missed: price match incomplete — order_id={order_id}, missing_sources={list}, reason={reason}`

### M3: Discrepancy Classified

- **Description**: Each discrepant order line has been classified as auto-resolvable (within tolerance) or an exception requiring human or agent review.
- **Achieved when**: Tolerance rules have been applied and each line is assigned a status: approved, exception, or chargeback.
- **Log on achievement**: `M3.achieved: discrepancy classified — order_id={order_id}, auto_approved={count}, exceptions={count}, chargebacks={count}`
- **Log on miss**: `M3.missed: classification failed — order_id={order_id}, reason={reason}`

### M4: Chargeback Claim Created

- **Description**: A supplier chargeback claim has been automatically created in S/4HANA for each order line with a validated supplier-attributable discrepancy.
- **Achieved when**: Chargeback claim record exists in S/4HANA with order reference, pricing evidence, and variance amount.
- **Log on achievement**: `M4.achieved: chargeback created — claim_id={claim_id}, order_id={order_id}, variance_amount={amount}, supplier={supplier_id}`
- **Log on miss**: `M4.missed: chargeback creation failed — order_id={order_id}, reason={reason}`

### M5: Exception Resolved

- **Description**: An exception has been analyzed by the AI agent and a resolution has been recorded (accepted, disputed with evidence, or escalated).
- **Achieved when**: A resolution decision with audit record exists for the exception, with the agent's analysis attached.
- **Log on achievement**: `M5.achieved: exception resolved — exception_id={id}, resolution={accept|dispute|escalate}, resolved_by={user_id}, agent_confidence={score}`
- **Log on miss**: `M5.missed: exception unresolved or timed out — exception_id={id}, age_days={days}, reason={reason}`

---

## Risks, Assumptions, and Dependencies

### Risks

- **EDI integration complexity**: Depending on current middleware maturity, parsing inbound X12 850 EDI events into the n8n workflow may require significant integration work with SAP Integration Suite or the existing EDI gateway. Scope this early.
- **S/4HANA API authorization**: The validation workflow and AI agent require specific S/4HANA authorization objects for condition records, sales contracts, and billing simulation. Provisioning delays could block development.
- **Pricing master data quality**: If GPO contract condition records or WAC prices in S/4HANA are incomplete or stale, 4-way match rates will be lower than expected regardless of automation.

### Assumptions (Validate These)

- All four pricing sources are maintained within SAP S/4HANA and accessible via standard OData APIs without custom extractors.
- An EDI middleware layer (SAP Integration Suite or equivalent) already processes inbound X12 850 orders and can emit an event or webhook on order creation.
- SAP BTP is available and provisioned for the organization.
- Tolerance thresholds for auto-approval vs. exception routing will be provided by the business before development begins.

### Dependencies

- SAP S/4HANA OData API credentials and authorization objects for: `API_SLSPRICINGCONDITIONRECORD_SRV`, `API_SALES_CONTRACT_SRV`, `CE_PURGDOCPRICINGSIMULATION_0001`, `OP_API_PURCHASEORDER_PROCESS_SRV_0001`
- SAP Generative AI Hub access with GPT-4o model deployment for the AI agent
- Existing EDI middleware capable of triggering workflow on inbound order creation

---

## Appendix

### Glossary

- **GPO**: Group Purchasing Organization — a body that negotiates contract pricing on behalf of member healthcare providers
- **WAC**: Wholesale Acquisition Cost — the manufacturer's list price to wholesalers before any discounts
- **Chargeback**: A claim submitted by a wholesaler/distributor to a manufacturer to recover the difference between the price paid (WAC) and the lower contracted price charged to the customer
- **EDI 850**: X12 electronic data interchange transaction set for a purchase order
- **4-Way Match**: Simultaneous validation of an order price against all four pricing sources: customer expected price, GPO contract price, Supplier WAC, and internal pricing hub

### References

- SAP S/4HANA: Condition Record for Pricing in Sales API — `sap.s4:apiResource:API_SLSPRICINGCONDITIONRECORD_SRV:v1`
- SAP S/4HANA: Price Simulation – Read API — `sap.s4:apiResource:CE_PURGDOCPRICINGSIMULATION_0001:v1`
- SAP S/4HANA: Sales Contract (A2X) API — `sap.s4:apiResource:API_SALES_CONTRACT_SRV:v1`
- SAP S/4HANA: Purchase Order API — `sap.s4:apiResource:OP_API_PURCHASEORDER_PROCESS_SRV_0001:v1`
- RBA: Lead to Cash – Wholesale Distribution — `https://ekg.cloud.sap/SAP/RBA/BPM/BP/LeadToCashWholesaleDistributionBPV2421`
