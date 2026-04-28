---
name: prd-to-spec
description: Intent-Based Development (IBD). Transform PRD to OpenSpec specification. Requires product-requirements-document.md to exist — run product-requirements-document skill first if missing (and intent-analysis before that for any new request). Skip if a valid OpenSpec change already exists in specs/<asset-name>/openspec/changes/ — use spec-to-code instead. Requires the openspec-propose skill (installed by workspace setup). Keywords - "spec from PRD", "specification", "generate spec".
compatibility: Requires Node.js/npm for OpenSpec auto-installation
allowed-tools: Bash(npm:*) Bash(openspec:*) Bash(chmod:*) Bash(ls:*) Bash(cd:*) Read Write Edit Glob
---

# PRD to Spec Agent Skill

This skill automates the workflow of processing Product Requirements Documents (PRDs) using OpenSpec and generating specifications. It initializes projects based on task type (agent, cap or n8n). **For implementation, use the spec-to-code skill after generating the spec.**

## Fast Track Mode
- **CRITICAL**: OpenSpec change artifacts (proposal.md, design.md, specs/, tasks.md) MUST always be created, even in fast-track mode. Fast-track means minimal spec content, NOT skipping the artifacts.
- If and only if the user's request explicitly contains "fast track", this skill generates the most minimal/essential spec artifacts possible and directly triggers implementation (auto-codegen).
- **All questions and detailed options are bypassed.**
- You **MUST** use the `sap-agent-extensibility` skill. Bypass any questions that are required in the skill, make assumptions. Give clear indication that the skill has been invoked.
  - **CRITICAL**: "MUST use" means invoke the skill AND complete its entire workflow, not just load it and move on
  - The extensibility skill must result in actual code (extension_capabilities.py or equivalent) in the agent codebase
  - Verify extensibility completion before proceeding: check that extension points, interfaces, and registration mechanisms exist in code
- **CRITICAL**: For AI Agent solutions, business step instrumentation MUST be implemented based on the milestones defined in the PRD, even in fast-track mode. The OpenSpec config will automatically include instrumentation tasks.
- The produced spec files should not exceed 50 lines. The only exception is the `tasks.md` file, which should be as detailed as necessary to contain all relevant details on implementation.
- No confirmation for proceeding to the next skill is asked - just proceed immediately to the implementation with the `spec-to-code` skill.
- In normal mode (no "fast track"), the full workflow and validations are performed with prompts as per the PRD, spec, and user clarification below.

### What "Fast Track" Means:

**SKIP (reduce interaction time):**
- ✅ Interactive questions and clarifications
- ✅ Detailed explanations and options
- ✅ Confirmations before proceeding to next steps
- ✅ Verbose documentation and comments

**NEVER SKIP (implementation requirements):**
- ❌ Actual implementation of all features
- ❌ For task type "agent": Business step instrumentation (milestones + OpenTelemetry spans), Extensibility implementation and Tests
- ❌ Validation steps

**Fast track = faster workflow, NOT incomplete implementation.**

**Supported AI Coding Agents:** OpenCode, Cline, Cursor, and GitHub Copilot

## Overview

This skill initializes projects based on task type, discovers relevant SAP APIs, and generates specifications from PRDs using OpenSpec.

1. Determines task type(s) from the PRD `Solution Category` field
2. Initializes each asset with task-specific configuration and stubs under `assets/<asset-name>/`
3. Discovers relevant SAP APIs (if solution requires API integration)
4. Generates one spec per asset using OpenSpec, each isolated in `specs/<asset-name>/openspec/`
5. When multiple specs are generated: validates cross-spec compatibility and fixes any mismatches
6. **For implementation:** Use the `spec-to-code` skill

## Prerequisites

### Required

- **OpenSpec Skills** - The openspec-propose and openspec-apply-change skills must be installed. These are set up automatically by the workspace setup script.
- **Node.js and npm** - For OpenSpec auto-installation (if not already installed)

**Note:** The setup script will auto-install OpenSpec CLI if not found and verify all requirements.

### Agent Skills

This skill requires two OpenSpec agent skills installed by the workspace setup script:

- `openspec-propose` - Creates a new OpenSpec change and generates all spec artifacts (proposal, design, specs, tasks) in one step. 
- `openspec-apply-change` - Applies specifications to implement code (used by spec-to-code skill). 

**How to use these skills:**
- **DO NOT execute these as bash commands** (e.g., `./openspec-propose` or `bash -c "openspec-propose"`)
- **DO load the skill and perform the actions** it defines using the Skill tool
- These are agent skills that contain instructions and workflows, not executable scripts

### Available Tools

- **ekx_search**: If the solution requires integration with SAP APIs, call `ekx_search` with `mode: "api_discovery"` and the use case as the `query` to discover available APIs, Data Products, and Events from the Business Accelerator Hub, including ORD IDs and spec file download links. Use the `output_file` parameter to save the raw response to a file (e.g., `api-discovery-results.md` in the workspace root). The tool returns the response in context AND saves it to the file. You must include all links to specifications if provided.

## Workflow

### Step 1: Determine Task Type(s)

**CRITICAL:** Before running setup, you **must** determine all task types.

**Supported task types:**

- `agent` - Pro-Code AI Agent for SAP App Foundation using Agent2Agent (A2A) protocol
- `cap` - Side-by-side extension with CAP and frontend
- `n8n-workflow` - n8n workflow automation flow

**How to determine the task type(s):**

1. Read `product-requirements-document.md` and look for the **Solution Category** field:
   ```
   [AI Agent | BTP Extension | n8n Workflow]
   ```
2. Split the field value on commas to get a list of solution categories. Map each to a task type:
   - AI Agent → `agent`
   - BTP Extension → `cap`
   - n8n Workflow → `n8n-workflow`
3. If the field is missing or its value does not match any supported task type, ask the user: *"What should be implemented? Please choose: agent, cap or n8n-workflow."*. This skill does not support any other task types besides the three listed above.

**Examples:**
- `Solution Category: AI Agent` → task types: `["agent"]`
- `Solution Category: n8n Workflow, AI Agent` → task types: `["n8n-workflow", "agent"]`

Also select a **shared feature name** to be used as the prefix for all change IDs and directory names (e.g. `purchase-order-approval`). This prefix is the same for all task types.

**Change ID and asset name:** `<feature>-<task-type>` (e.g. `purchase-order-approval-agent`, `purchase-order-approval-n8n-workflow`)

The asset name **is** the change ID. Both the asset directory and the spec directory use this name:
- `assets/<feature>-<task-type>/` — where code is generated (e.g. `assets/purchase-order-approval-agent/`)
- `specs/<feature>-<task-type>/` — where OpenSpec artifacts live (e.g. `specs/purchase-order-approval-agent/`)

This naming allows multiple assets of the same task type (e.g. two agents) to coexist without conflict.


### Step 2: Run Setup

**Run setup for all task types in parallel** — each asset has its own isolated `specs/<asset-name>/` directory so there are no conflicts. For every task type:

1. Create both the asset directory and the spec directory if they do not exist:
   ```bash
   mkdir -p assets/<asset-name>
   mkdir -p specs/<asset-name>
   ```

2. Run the setup script **from inside the spec directory** (this ensures all OpenSpec files are created under `specs/<asset-name>/openspec/`):
   ```bash
   node /path/to/skills/prd-to-spec/scripts/setup.mjs <task_type>
   # working directory must be: specs/<asset-name>/
   ```

**Examples** (feature name: `purchase-order-approval`):
```bash
# For an AI agent
mkdir -p assets/purchase-order-approval-agent
mkdir -p specs/purchase-order-approval-agent
# run from specs/purchase-order-approval-agent/:
node /path/to/skills/prd-to-spec/scripts/setup.mjs agent

# For an n8n workflow
mkdir -p assets/purchase-order-approval-n8n-workflow
mkdir -p specs/purchase-order-approval-n8n-workflow
# run from specs/purchase-order-approval-n8n-workflow/:
node /path/to/skills/prd-to-spec/scripts/setup.mjs n8n-workflow
```

**What this does (per asset):**

1. **Validates task type parameter**
   - Ensures a valid task type is provided (agent, cap or n8n-workflow)
   - Exits with error if missing or invalid

2. **Installs OpenSpec**
   - Auto-installs if not found (requires npm)
   - Configures environment and disables telemetry

3. **Initializes project based on task type**
   - Copies task-specific config file to `specs/<asset-name>/openspec/config.yaml`
   - Copies project stub files for the selected task type into `assets/<asset-name>/`
   - **Note:** `agent` has no project stub — the `sap-agent-bootstrap` skill (automatically invoked by `spec-to-code`) provides the project scaffolding instead. The bootstrap skill operates on the current working directory, so it must be invoked from inside `assets/<asset-name>/` (e.g. `assets/<feature>-agent/`).
   - Creates necessary directory structure

**Expected output:**
- Task type confirmation
- OpenSpec installation status (installed or auto-installed)
- Project initialization progress
- Config file and stub files copy confirmation

After setup for all task types, confirm the shared change name prefix selected in Step 1.

### Step 3: API Discovery (Conditional)

**When to run:** If the PRD indicates the solution requires integration with SAP APIs (e.g., references OData services, S/4HANA, Business Accelerator Hub APIs, events, or data products).

**Skip this step** if the solution does not involve SAP API integration.

Run API discovery scoped to each asset that requires it (primarily `agent`; `n8n-workflow` only if it directly calls SAP APIs rather than routing through an agent).

For each relevant asset:
1. Call `ekx_search` with `mode: \"api_discovery\"`, a concise description of the API integration needs from the PRD as the `query`, and `output_file: \"api-discovery-results.md\"`. The tool saves the raw response to the file automatically while still returning it in context. This guarantees the full response (including any pre-signed S3 download URLs) is persisted as-is.
2. For each API that has a Download Link (pre-signed S3 URL) in the response, fetch the spec file and save the **raw downloaded content as-is** to `specs/<asset-name>/openspec/changes/<change-id>/api-specs/` (e.g., `specs/<asset-name>/openspec/changes/<change-id>/api-specs/supplier-invoices.json`). Create the directory if needed. Do not summarize or replace the content — always persist the original spec file.
3. For each downloaded spec, do a targeted read to extract only the relevant parts: scan the `paths` or `channels` keys for endpoints matching the use case, then read the associated request/response schemas. Do not read the entire spec end-to-end.

Ask the user to confirm a retry process if the EKX search fails (e.g. prompt for a specific query or mode; try again a few minutes later; etc.).
This step is mandatory for agent solutions that require API integration, as the discovered APIs and their schemas are essential for both the specification and implementation.

The discovered ORD IDs and API spec file paths must be included, later on, in the OpenSpec spec artifacts (`design.md` API References section) so they are available downstream to `spec-to-code`, `mcp-translation-file`, and any other skills that might need them.

### Step 4: Create OpenSpec Changes and Generate Specifications

**Run openspec-propose for all assets in parallel using sub-agents** — because each asset operates in its own isolated `specs/<asset-name>/openspec/` directory, there are no conflicts and all specs can be generated simultaneously.

Launch one sub-agent per asset. Each sub-agent:

1. Sets its working directory to `specs/<asset-name>/`.
2. Loads the `openspec-propose` skill and follows its instructions to create a new OpenSpec change named `<asset-name>` and generates all artifacts (proposal, design, specs, tasks) in one step, using the PRD as input.
3. All artifacts land in `specs/<asset-name>/openspec/changes/<asset-name>/`.

Wait for all sub-agents to complete before proceeding to Step 5.

**IMPORTANT:** Each spec is **self-contained and independent** — do not add cross-references or hard dependencies between specs. If an n8n workflow calls an agent, document the agent's interface as a configurable HTTP endpoint in the n8n spec (e.g. `{{AGENT_BASE_URL}}`), not as a hard-coded reference to the agent spec artifacts.

You MUST keep each OpenSpec specification as brief as possible to save time and tokens. The only exception is the `tasks.md` file, which should be as detailed as necessary to contain all relevant details on implementation.

**If API discovery produced results:** The generated spec artifacts (design.md, spec.md, tasks.md) must reference the concrete API names, ORD IDs, endpoints/paths, and entity schemas — not just generic descriptions like "query S/4HANA". The design.md must include an **API References** section listing the paths to `api-discovery-results.md` and the raw spec files in `openspec/changes/<change-id>/api-specs/`, so the implementation agent can read them when it needs full schema details. You MUST include all links to the specifications if provided, in particular the amazonaws links if returned.

### Step 5: Validate Specifications

Run validation for all assets in parallel — each from its own spec directory:

```bash
openspec validate <asset-name> --strict --no-interactive
# working directory: specs/<asset-name>/
```

**Validation checks:**
- Spec structure and format
- Required fields and metadata
- Cross-references and consistency
- Task completeness


### Step 6: Cross-Spec Compatibility Check (Multi-Type Only)

**Only perform this step when two or more specs have been generated.**

When multiple assets are being built together, their interfaces must be compatible even though the specs are independently authored. This step detects and resolves mismatches **before** implementation begins.

**How to perform the check:**

1. Read the `design.md` and `tasks.md` for every generated change (from `specs/<asset-name>/openspec/changes/<asset-name>/`).
2. Reason across all specs and identify any interface incompatibilities. The check is intentionally open-ended — focus on anything that would cause the components to fail when communicating at runtime. Examples of what to look for (not exhaustive):
   - If one component calls another over HTTP: does the caller's assumed endpoint path, HTTP method, request body shape, and response body shape match what the callee exposes?
   - Are shared data entities (field names, types, formats) consistent across specs?
   - Are authentication/credential assumptions aligned (e.g. one spec assumes bearer token, the other assumes no auth)?
   - Are error codes or failure shapes that one component can emit handled in the other component's error branches?
   - Are any environment variable names or configuration keys referenced by both specs consistent?
3. Produce a **Compatibility Report** as a short written summary listing:
   - **Compatible:** items that are correctly aligned
   - **Incompatible:** each mismatch with: which specs are affected, what the conflict is, and the proposed fix

**If incompatibilities are found:**
- **Do not proceed to spec-to-code.**
- Fix the relevant spec artifact(s) — typically `design.md` and/or `tasks.md` in the affected change(s).
- Re-run `openspec validate` for any changed spec.
- Re-run the compatibility check until all items are marked Compatible.

**If all items are Compatible:**
- State the result clearly and proceed to Next Steps.


## Next Steps

After generating, validating, and (if applicable) confirming cross-spec compatibility, there are two possibilities for continuing:

1. **Implementation**: If the user explicitly requested implementation or code generation (e.g., with a prompt like 'Please generate spec and code from the PRD' or 'Create a workflow'), or wants to execute the tasks defined in tasks.md, then you can proceed with implementation using the `spec-to-code` skill.
2. **Review and Feedback**: If the user did not explicitly request implementation (e.g., with a prompt like 'Please generate a spec from the PRD'), suggest that they review the generated specification and ask if they want to proceed with implementation.

Note: These two options are the only valid paths forward. Do not perform or suggest any other next steps besides these two. Implementation **MUST** always start with loading the `spec-to-code` skill. Do NOT invoke `mcp-translation-file` or `setup-solution` directly — those are chained automatically by `spec-to-code` or executed separately.
When handing off to `spec-to-code`, provide the full list of `(spec directory, asset directory, change ID)` tuples:

```
specs/<feature>-agent/          →  assets/<feature>-agent/          →  <feature>-agent
specs/<feature>-n8n-workflow/   →  assets/<feature>-n8n-workflow/   →  <feature>-n8n-workflow
```


## What the Agent Does NOT Do

The agent does **NOT** perform the following actions (these are left to the user or other skills):

- **Implement code** - Use the `spec-to-code` skill for implementation

**Rationale:** 
- Specification and implementation are separate concerns
- The user should review all generated artifacts before proceeding

## Command Reference

### Setup Commands

| Command | Purpose |
|---------|---------|
| `node /path/to/skills/prd-to-spec/scripts/setup.mjs <task_type>` | Complete setup — run from `specs/<asset-name>/` as working directory |

### Agent Skills (Slash Commands)

**CRITICAL:** These are agent skills that contain instructions and workflows, **NOT bash commands or executable scripts**.

**How to use these skills:**
1. Use the Skill tool to load the skill by name
2. Follow the instructions provided by the loaded skill
3. **DO NOT** execute these as bash commands (e.g., `./openspec-new-change` or `bash -c "openspec-new-change"`)

| Skill Name | Purpose |
|------------|---------| 
| `openspec-propose` | Create a new OpenSpec change and generate the spec artifacts in one step - Load this skill with the change name and PRD as input |

**Note:** For implementation, use the `spec-to-code` skill which utilizes the `openspec-apply-change` skill.

### OpenSpec CLI Commands

| Command | Purpose |
|---------|---------|
| `openspec validate <id> --strict` | Validate a change (run from the spec directory) |
| `openspec list` | List active changes |
| `openspec show <item>` | View change or spec details |

## Troubleshooting

For common issues and detailed solutions, see [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md).

### Quick Fixes

**"Invalid task_type"** - Ensure you provide a valid task type: agent, cap or n8n-workflow

**"Missing required OpenSpec skills"** - Run the workspace setup script to install the OpenSpec agent skills

**"Config file not found"** - Ensure the prd-to-spec skill includes the `assets/config_files` directory with task-type-specific config files

## Reference

- For detailed setup instructions: [references/SETUP.md](references/SETUP.md)