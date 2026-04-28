---
name: spec-to-code
description: Intent-Based Development (IBD). Implement code from OpenSpec specification. Requires valid OpenSpec change(s) in specs/<asset-name>/openspec/changes/<asset-name>/ — run prd-to-spec first if missing. Keywords - "implement spec", "code from spec", "execute tasks", "tasks.md", "Run /opsx-apply".
---

# Spec to Code Agent Skill

This skill implements code from OpenSpec specifications by systematically executing all tasks defined in the `tasks.md` file. It works with existing OpenSpec changes and ensures all implementation tasks are completed.

## Fast Track Mode
- If the user's request explicitly contains "fast track", skip any interactive steps and auto-proceed. Do not ask any questions and do not seek clarification.
- The skill 'setup-solution' must always be automatically executed immediately after this skill, even in fast track mode, to ensure the solution structure is created.

### What "Fast Track" Means:

**SKIP (reduce interaction time):**
- ✅ Interactive questions and clarifications
- ✅ Detailed explanations
- ✅ Confirmations before proceeding

**NEVER SKIP (implementation requirements):**
- ❌ Implementing ALL tasks from tasks.md (especially those marked REQUIRED)
- ❌ For task type "agent": Business step instrumentation (logging + OpenTelemetry spans for each milestone), Extensibility implementation, and Tests
- ❌ Validation steps
- ❌ Verification checklist (see below)

**Fast track = skip questions, NOT skip implementation.**

**Supported AI Coding Agents:** OpenCode, Cline, Cursor, and GitHub Copilot

## Overview

The spec-to-code skill focuses exclusively on the implementation phase of the OpenSpec workflow. It takes one or more existing, validated OpenSpec specifications and implements all the tasks defined in each `tasks.md`.

**When to use this skill:**
- User wants to implement/generate code from an existing spec
- User wants to execute tasks from tasks.md
- User asks to "implement the spec" or "generate code from spec"
- Following a completed prd-to-spec workflow

**When NOT to use this skill:**
- User wants to create a spec from a PRD → Use `prd-to-spec` instead
- User wants to generate specifications → Use `prd-to-spec` instead
- User asks to "generate code from a PRD" → Use `prd-to-spec` first, then this skill

## Prerequisites

### Required

One of the following **must** be true:

1. **Option A: After prd-to-spec workflow**
   - The `prd-to-spec` skill has been run successfully
   - Valid OpenSpec change(s) exist in `specs/<asset-name>/openspec/changes/<asset-name>/`
   - Each change has been validated with `openspec validate <asset-name>` (run from `specs/<asset-name>/`)

2. **Option B: Standalone OpenSpec change**
   - A valid OpenSpec change structure exists in `specs/<asset-name>/openspec/changes/<asset-name>/`
   - The change has been validated with `openspec validate <asset-name>`
   
If validation fails, you must fix the specification before proceeding with implementation.

### Additional Requirements

- **OpenSpec CLI** - Must be installed and accessible
- **Agent skills** - The `openspec-apply-change` skill must be available

### Validation Before Implementation

Always validate each change before implementing. Run from the spec directory:

```bash
openspec validate <asset-name> --strict --no-interactive
# working directory: specs/<asset-name>/
```

If validation fails, you must fix the specification before proceeding with implementation.

## Workflow

### Step 1: Discover and Verify All Changes

**Discover all OpenSpec changes** by scanning for spec directories that contain an OpenSpec changes folder:

```bash
ls specs/
# For each <asset-name> directory found:
ls specs/<asset-name>/openspec/changes/
```

For each `(spec-dir, asset-dir, change-id)` tuple discovered (spec-dir and asset-dir share the same `<asset-name>`):

1. **Change exists:**
   ```bash
   openspec list
   # run from specs/<asset-name>/ — should show your <asset-name>
   ```

2. **Change is valid:**
   ```bash
   openspec validate <asset-name> --strict --no-interactive
   # run from specs/<asset-name>/
   ```

3. **Tasks file exists:**
   ```bash
   ls specs/<asset-name>/openspec/changes/<asset-name>/tasks.md
   # Should exist and contain tasks
   ```

After discovery, determine the execution mode:
- **Single change found** → proceed with single-spec implementation (Step 2a)
- **Multiple changes found** → proceed with parallel multi-spec implementation (Step 2b)

### Step 2a: Implement — Single Spec

**IMPORTANT:** The `openspec-apply-change` skill is an agent skill that contains instructions and workflows, **NOT a bash command or executable script**.

**CRITICAL: Working directory split.** The `openspec-apply-change` skill runs `openspec` CLI commands (e.g. `openspec status`, `openspec instructions apply`, `openspec list`) that require `openspec/config.yaml` to be present in the current working directory. This file lives in `specs/<asset-name>/`, **not** in `assets/<asset-name>/`. Therefore:

- **Set working directory to `specs/<asset-name>/`** when running all `openspec` CLI commands.
- Write all generated code files into `assets/<asset-name>/` (use absolute or workspace-relative paths when creating/editing files).

Load the `openspec-apply-change` skill with `<asset-name>`. This skill guides you through implementing all tasks in `specs/<asset-name>/openspec/changes/<asset-name>/tasks.md`. You **must** complete all tasks. Code is generated into `assets/<asset-name>/`.

### Step 2b: Implement — Multiple Specs (Parallel)

When multiple `(spec-dir, asset-dir, change-id)` tuple exist, launch **parallel sub-agents** — one per tuple. Each sub-agent operates independently:

1. Sets its working directory to `specs/<asset-name>/` (required for all `openspec` CLI commands).
2. Loads the `openspec-apply-change` skill with its specific `<asset-name>`.
3. Implements all tasks from `specs/<asset-name>/openspec/changes/<asset-name>/tasks.md` to completion. Code is generated into `assets/<asset-name>/` (write files using workspace-relative paths).

Sub-agents do not share state and operate on separate asset directories, so they can safely run in parallel.

**Do not mark implementation complete until ALL sub-agents have finished.**

### Step 3: Cross-Implementation Compatibility Check (Multi-Type Only)

**Only perform this step when two or more specs have been implemented.**

After all sub-agents complete, verify that the implemented components are compatible with one another at runtime. This is the implementation-level counterpart to the spec-level compatibility check run by `prd-to-spec` — the goal is to catch any drift between what was specified and what was actually built.

**How to perform the check:**

1. Read the actual implemented code for each asset (focus on interface boundaries: exposed endpoints, client call sites, shared data structures, auth handling, env var names).
2. Cross-check each asset's implementation against the others and identify any runtime incompatibilities. The check is intentionally open-ended — focus on anything that would cause the components to fail when communicating. Examples of what to look for (not exhaustive):
   - If one component calls another over HTTP: does the caller's actual request (path, method, headers, body shape) match what the callee's server actually handles?
   - Are shared data field names and types consistent across implementations (e.g. camelCase vs snake_case, string vs integer)?
   - Are authentication mechanisms aligned (e.g. one component sends a bearer token the other doesn't validate)?
   - Are error responses that one component emits handled gracefully in the other component's client code?
   - Are environment variable names referenced identically on both sides?
3. Produce a **Compatibility Report** listing:
   - **Compatible:** items that are correctly aligned in the implemented code
   - **Incompatible:** each mismatch with: which assets are affected, what the conflict is, and the fix applied

**If incompatibilities are found:**
- Fix the affected code directly.
- Re-run any relevant tests to confirm the fix.
- Re-run the compatibility check until all items are Compatible.

**If all items are Compatible:**
- State the result clearly and proceed to the Completion Checklist.

## What This Skill Does NOT Do

This skill does **NOT** perform the following actions (these are left to the user):

- Create or modify specifications (use `prd-to-spec` for this)
- Commit changes to git
- Push code to remote repositories
- Create pull requests
- Merge branches
- Tag releases

**Rationale:** The user should review all implemented code before committing and sharing it.

## Command Reference

### Verification Commands

| Command                                     | Purpose                                            |
|---------------------------------------------|----------------------------------------------------|
| `openspec list`                             | List all OpenSpec changes (run from `specs/<asset-name>/`)      |
| `openspec show <asset-name>`                | Show change details                                             |
| `openspec validate <asset-name> --strict`   | Validate the change structure (run from `specs/<asset-name>/`)  |
| `cat openspec/changes/<asset-name>/tasks.md`| View implementation tasks (run from `specs/<asset-name>/`)      |

### Agent Skills

**CRITICAL:** These are agent skills that contain instructions and workflows, **NOT bash commands or executable scripts**.

| Skill Name | Purpose |
|---------|---------|
| `openspec-apply-change` | Implement all tasks from tasks.md — Load this skill with `<asset-name>`, working directory set to `specs/<asset-name>/` (required for `openspec` CLI), code written into `assets/<asset-name>/` |

## Relationship with prd-to-spec

This skill is designed to work seamlessly with the `prd-to-spec` skill:

### Full PRD-to-Code Workflow

When a user wants to generate code from a PRD:

1. **First:** Use `prd-to-spec` skill
   - Processes the PRD
   - Generates one spec per asset under `specs/<asset-name>/openspec/`
   - Validates each spec
   - Runs cross-spec compatibility check (when multiple assets)
   - Creates OpenSpec change structure

2. **Then:** Use `spec-to-code` skill (this skill)
   - Discovers all `(spec-dir, asset-dir, change-id)` tuples
   - Implements single spec or launches parallel sub-agents for multiple specs (code goes into `assets/<asset-name>/`)
   - Runs cross-implementation compatibility check (when multiple assets)
   - Verifies all implementations against the completion checklist

### Standalone Spec Implementation

When a user has an existing OpenSpec change (created manually or from another source):

1. **Verify** the change structure exists and is valid under `specs/<asset-name>/openspec/`
2. **Use** `spec-to-code` skill directly to implement tasks (code goes into `assets/<asset-name>/`)

## Troubleshooting

### "OpenSpec change not found"

**Cause:** No change exists with the specified ID

**Solution:**
```bash
# List all changes (run from specs/<asset-name>/)
openspec list

# Verify the spec and change directories exist
ls specs/
ls specs/<asset-name>/openspec/changes/
```

If no changes exist, you need to:
- Run `prd-to-spec` first to create a change from a PRD, or
- Manually create a valid OpenSpec change structure under `specs/<asset-name>/openspec/`

### "tasks.md not found or empty"

**Cause:** The specification doesn't have implementation tasks defined

**Solution:**
- If you used `prd-to-spec`, re-run the spec generation step
- If using a manual spec, create `tasks.md` with implementation tasks
- Validate the change structure: `openspec validate <asset-name> --strict` (from `specs/<asset-name>/`)

### "openspec-apply-change skill not available"

**Cause:** Agent skills haven't been loaded

**Solution:** Instruct the user to run the `setup-workspace.js` script again to load all skills.

### "Validation failed"

**Cause:** The OpenSpec change structure is invalid or incomplete

**Solution:**
```bash
# Run validation with details (from specs/<asset-name>/)
openspec validate <asset-name> --strict

# Fix reported issues in the spec
# Re-validate before attempting implementation
```

## ⚠️ MANDATORY Completion Checklist

**Before marking implementation complete, you MUST verify ALL of the following for EACH change:**

### 1. All Tasks Implemented
- [ ] Every task in `tasks.md` has been implemented (check tasks.md line by line)
- [ ] No tasks marked "TODO" or "pending" remain

### 2. OpenSpec Validation
- [ ] `openspec validate <asset-name> --strict --no-interactive` passes (run from `specs/<asset-name>/`)

### 3. MCP Translation Files (if applicable)
- [ ] MCP translation files generated for all APIs in `specs/<asset-name>/openspec/changes/<asset-name>/api-specs/` (if any exist)
- [ ] Translation files validated and stored in `specs/<asset-name>/openspec/changes/<asset-name>/mcps/`

### 4. Solution Structure
- [ ] `setup-solution` skill executed
- [ ] `solution.yaml` exists and references all assets
- [ ] All MCP server assets created (if applicable)

**If ANY checkbox is unchecked for ANY change, implementation is NOT complete. Go back and finish the missing items.**

**In fast-track mode: Skip questions, NOT this checklist.**

# Next steps

## MCP Translation File Generation (Conditional)

After completing all implementation tasks, check if API spec files exist in `specs/<asset-name>/openspec/changes/<asset-name>/api-specs/`.

- If **yes**: Invoke the `mcp-translation-file` skill. The skill will generate translation files to `specs/<asset-name>/openspec/changes/<asset-name>/mcps/`. Do NOT manually create or edit translation files — the skill handles everything. This step must complete BEFORE `setup-solution` runs.
- If **no**: Skip this section.

## Setup Solution (MANDATORY)

After implementation and MCP translation file generation (if applicable), you **MUST** invoke the `setup-solution` skill to create the full solution structure. This is not optional. Remind the user to review the code changes before deployment.

When using the `setup-solution` skill, ensure the following structure is used:
```
./
├── solution.yaml           # refs ./assets/<asset-name>/asset.yaml
└── assets/
   └── <asset-name>/
      ├── asset.yaml
      └── ...               # asset files
```

For multi-asset solutions, `solution.yaml` must reference all asset YAML files:
```yaml
assets:
  - ref: ./assets/<feature>-agent/asset.yaml
  - ref: ./assets/<feature>-n8n-workflow/asset.yaml
```

## MCP Servers

For every MCP Server that was identified, you need to implement a solution asset. 
If none exists (under `specs/<asset-name>/openspec/changes/<asset-name>/mcps/`), skip this section. Otherwise, follow the guidelines below.

### [MANDATORY] Set up folders
For every Translation File in the `mcps` folder, you need to set up an asset folder in the solution structure. The asset folder should be located at `assets/{mcp-server-name}/` and contain an `asset.yaml` file with the correct metadata and type. Copy the translation file in the spec to this folder as well. (e.g. `specs/<asset-name>/openspec/changes/<asset-name>/mcps/dispute-mcp-server.translation.json` -> `assets/s4-dispute-mcp-server/translation.json`)
The name of the MCP Servers MUST follow the pattern `{domain}-{purpose}-mcp-server` (e.g., `s4-dispute-mcp-server`). If the name cannot be clearly derived, propose a name and ask the user to confirm it.
Note that for a given solution, there should be an MCP Server for each distinct API.

Use the `setup-solution` skill to create the solution structure and the asset folder for the MCP Server. The asset folder should be located at `assets/{mcp-server-name}/`.

After creating the asset, register it in `solution.yaml` under `assets`:
```yaml
assets:
  - ref: ./assets/{mcp-server-name}/asset.yaml
```

Also add every MCP Server asset to the bottom of the agent's `asset.yaml`, e.g. given two new MCP Servers, the `tools` section of the agent asset.yaml should look like this:
```yaml
# ...

tools:
  mcp-servers:
    - sap.mcp:apiResource:dispute-mcp-server:v1
    - sap.mcp:apiResource:invoice-mcp-server:v1
```

Ensure the list of servers match the ORD IDs of the MCP Servers defined in their asset folders.

# Reference

- OpenSpec documentation: See the OpenSpec CLI help (`openspec --help`)
- `prd-to-spec` skill: For creating specs from PRDs
- `setup-solution` skill: For creating solution structure and assets after implementation
- `mcp-translation-file` skill: For implementing MCP translation files if required by the spec
