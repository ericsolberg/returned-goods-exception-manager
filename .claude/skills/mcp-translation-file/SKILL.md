---
name: mcp-translation-file
description: Generate an MCP translation file based on API specs (openapi, odata).
metadata:
  owner: mcp-builder
  author: r.costa@sap.com
  version: "2.0"
---

# MCP Translation File Generator

Generate an MCP translation file from an API spec (OpenAPI or OData).

This skill produces exactly **one file** per API spec: `{mcp-server-name}.translation.json` — a metadata file that maps API operations to MCP tools.

**This skill does NOT create an MCP server implementation, asset.yaml, server code, Dockerfiles, or any runtime artifacts.** A separate skill is responsible for taking the translation file and producing the final `asset.yaml` and solution structure.

**Invocation context:** This skill is typically invoked by the `spec-to-code` skill after task implementation, not directly by users. If invoked manually, ensure all prerequisites are met (API specs in place, tasks referencing APIs, etc.).

---

## Terminology

These terms have precise meanings throughout this document:

- **STOP**: Halt execution of this skill entirely. Do not proceed to any subsequent step. Explain to the user what went wrong, what is missing, and how to fix it. If this skill was invoked by another agent or skill, return control to the caller with the error details.
- **Decision log**: When you make a non-trivial choice (e.g. selecting an API type, skipping an endpoint, choosing a tool name), emit a short line in the chat: `[DECISION] <what> — <why>`. This improves debugging and reproducibility.

---

## Phase 1: Gate Checks

Evaluate each gate sequentially. Every gate must pass before proceeding to Phase 2. If any gate fails, follow the specified action — do not skip ahead.

### Gate 1 — OpenSpec change exists

**Check:** A valid OpenSpec change directory exists at `openspec/changes/<change-id>/`.
- If **false** → STOP. Tell the user to run the `prd-to-spec` skill first to create the specification.
- If **true** → Record the `<change-id>` for use in later steps. Proceed.

### Gate 2 — tasks.md exists

**Check:** The file `openspec/changes/<change-id>/tasks.md` exists.
- If **false** → STOP. Tell the user to run `prd-to-spec` and `spec-to-code` first to generate implementation tasks.
- If **true** → Proceed.

### Gate 3 — Task references an API integration

**Check:** At least one task in `tasks.md` references an API integration (e.g., contains phrases like "API", "integration", "OData", "REST", "service", or an ORD ID pattern like `sap.*:apiResource:*`).
- If **false** → STOP. This skill only applies to solutions that integrate with an API. Explain this to the user.
- If **true** → Identify the relevant task(s). Proceed.

### Gate 4 — API specs directory exists

The `prd-to-spec` skill detects API integrations during spec generation. When an integration is needed, it fetches the API specs and places them in `openspec/changes/<change-id>/api-specs/` at the workspace root. The ORD ID and API type are determined from the files in this directory.

**Check:** The directory `openspec/changes/<change-id>/api-specs/` exists at the workspace root and contains at least one spec file.
- If **false** → STOP. The prior `prd-to-spec` step did not detect or fetch any API specs. Tell the user to re-run `prd-to-spec` and ensure the API discovery step completes successfully. Context: This skill was likely invoked by an agent, which means that the agent may need to adjust its prompts or retry the discovery process, otherwise this skill wouldn't be called.
- If **true** → Record every spec file found in this directory. For each file, extract the ORD ID from the task description or from the filename/content. Proceed.

### Gate 5 — Check for existing translation file

**Check:** Look for existing translation files by scanning `openspec/changes/<change-id>/mcps/` for any `*.translation.json` files. Also determine the expected output path (where `{mcp-server-name}` is derived from the ORD ID — see the Server Name Derivation rule in the Reference section):
- `openspec/changes/<change-id>/mcps/{mcp-server-name}.translation.json`

- If **file exists** → Ask the user: "A translation file already exists at `{path}`. What would you like to do?"
  - **Re-validate** → Skip Phase 2 and Phase 3 entirely. Jump directly to **Step 5 — Validate** using the existing file. If validation passes, proceed to Phase 4. If validation fails, follow the normal fix-and-retry loop in Step 5.
  - **Overwrite** → Proceed to Phase 2 (full regeneration from the API spec). The existing file will be replaced in Step 4.
  - **Abort** → STOP.
- If **no file exists** → Proceed to Phase 2.

---

## Phase 2: Input Resolution

At this point all gates have passed. You have recorded: `<change-id>` and the list of spec files from `openspec/changes/<change-id>/api-specs/`. Now resolve the remaining inputs for each spec file.

If there are multiple spec files, repeat Phase 2 and Phase 3 for each one, producing one translation file per API spec.

### Resolve this skill's directory path

To resolve the skill directory path, search for the `SKILL.md` file that matches this skill's name and remember it:

```bash
SKILL_DIR="$(dirname "$(find . -path '*/mcp-translation-file/SKILL.md' -type f 2>/dev/null | head -1)")"
```

This will be relevant since there are steps that require reading files from this skill's subdirectories (e.g., JSON schemas, example files, scripts, etc.).

### Resolve the API spec content

Read each spec file from the `openspec/changes/<change-id>/api-specs/` directory.

If a spec file cannot be parsed as valid JSON or XML → STOP.

### Resolve the API type

Determine whether the API is OData or OpenAPI. Use this decision chain:

1. If the task description explicitly states the type → Use it.
2. If the spec content contains a root element `edmx:Edmx` or `<edmx:Edmx` → Type is `edmx`.
3. If the spec content contains a top-level `openapi` or `swagger` field → Type is `openapi-v3`.
4. If the type still cannot be determined → Ask the user: "Is this an OData (EDMX) or OpenAPI (REST) spec?"
   - If the user says **neither** or cannot answer → STOP.

### Resolve the ORD ID

Extract the ORD ID for the source API. Search in this order:
1. The task description in `tasks.md` (look for a pattern like `sap.*:apiResource:*`).
2. Metadata or annotations inside the spec file itself.
3. The filename of the spec file (e.g., `dispute-service.edmx` → derive from naming convention).

- If **found** → Record the ORD ID. Proceed.
- If **not found** → Ask the user: "What is the ORD ID of the source API? (e.g., `sap.s4:apiResource:dispute-service:v1`)"
  - If the user cannot provide one → STOP.
  - If the user provides one → Record it. Proceed.

Log the decisions: `[DECISION] API type: {type} — {reason}` and `[DECISION] ORD ID: {ordId} — {source}`.

---

## Phase 3: Generate the Translation File

### Step 1 — Parse the API spec

Extract all endpoints, entity sets, operations, parameters, and descriptions from the spec.

**For OData (edmx):**
- Identify all EntitySets, their EntityTypes, key properties, and navigation properties.
- Identify all unbound Actions and Functions (including V2 Function Imports).
- Identify all bound Actions and Functions on each EntityType.

**For OpenAPI (openapi-v3):**
- Identify all paths and their HTTP methods.
- Identify path parameters, query parameters, header parameters, and request bodies.
- Identify operationIds where available.

**Success criterion:** You can enumerate every endpoint/operation the API exposes.

### Step 2 — Generate the tools array

Generate one MCP tool per endpoint/operation. Follow the naming and structure rules in the Reference section below.

**For OData — tool generation rules:**
- For each EntitySet, generate:
  - `read` (list) tool — always
  - `readByKey` (get by key) tool — always
  - `create` tool — only if the spec indicates write access (no `Org.OData.Core.V1.ReadOnly` annotation, or explicitly writable)
  - `update` tool — only if the spec indicates write access
  - `delete` tool — only if the spec indicates write access
- For each unbound Action or Function → generate one tool (only if it looks relevant to the use case, otherwise log a decision to skip)
- For each bound Action or Function → generate one tool (scoped to its bound EntitySet; only if it looks relevant to the use case, otherwise log a decision to skip)
- Log decisions for any endpoint you skip: `[DECISION] Skipped {endpoint} — {reason}`

If there are bound/unbound operations that you are unsure about their relevance, and it doesn't negatively impact the Step 3 below, ask the user if they want to include them or not.

**For OpenAPI — tool generation rules:**
- For each path+method combination → generate one tool
- Include `operationId` if the spec provides one
- Include `requestBody` config for methods that accept a body (POST, PUT, PATCH)
- Log decisions for any endpoint you skip: `[DECISION] Skipped {path} {method} — {reason}`

### Step 3 — Check tool count

**Check:** Count the total number of generated tools.
- If **more than 10** → Warn the user: "This API produces {N} tools. More than 10 tools may impact MCP server performance. Do you want to proceed, or select a subset of endpoints?"
  - If the user wants to **proceed** → Continue.
  - If the user wants to **select a subset** → Ask which endpoints to include. Regenerate the tools array with only those endpoints.

### Step 4 — Assemble and write the translation file

Build the complete `translation.json` object following the structure defined in the Reference section. Read the schema file at `assets/translation.schema.json` (relative to this skill's directory) to ensure full compliance. **If there is any discrepancy between this document and the schema, the schema wins.**

Write the file to:
```
openspec/changes/<change-id>/mcps/{mcp-server-name}.translation.json
```

Create the directory if it does not exist (`mkdir -p`).

### Step 5 — Validate

Run the schema validation script. To resolve the skill directory path, use the directory that contains this SKILL.md file.

```bash
node "$SKILL_DIR/scripts/validate-schema.mjs" \
  "openspec/changes/<change-id>/mcps/{mcp-server-name}.translation.json" \
  "$SKILL_DIR/assets/translation.schema.json"
```

- If **0 errors** → Proceed to Phase 4.
- If **errors found** → Read the error messages. Fix each error in the generated file. Re-run validation. Repeat until 0 errors.
- If **you cannot fix all errors after 3 attempts** → Provide the full error report to the user and ask them to fix the remaining issues manually. Tell the user: "After fixing the issues, re-run this skill (`mcp-translation-file`). It will detect the existing file and offer a **Re-validate** option that skips straight to validation without regenerating." STOP.

---

## Phase 4: Post-Checks

Verify both conditions before reporting success:

1. **Translation file exists** at `openspec/changes/<change-id>/mcps/{mcp-server-name}.translation.json`.
2. **Validation passes** with 0 errors (already confirmed in Step 5).

If both are true → Report success to the user with the file path.
If either is false → STOP with an explanation of what failed.

---
---

## Reference

> **This section is reference material.** Do not execute it as sequential steps. Consult it when building the translation file in Phase 3.

### Translation File Structure

The output file must conform to `assets/translation.schema.json`. Always read the schema to ensure compliance.

#### Required Root Fields

```json
{
  "mcpTranslationVersion": "0.1",
  "target": {
    "ordId": "<source-api-ord-id>",
    "type": "edmx | openapi-v3"
  },
  "serverInfo": {
    "name": "<namespace>/<server-name>",
    "title": "<Display Title>",
    "version": "1.0.0",
    "description": "<description>"
  },
  "tools": [ ... ]
}
```

#### Field Rules

| Field | Rule |
|---|---|
| `mcpTranslationVersion` | Always `"0.1"` |
| `target.ordId` | The ORD ID resolved in Phase 2 (e.g., `sap.s4:apiResource:dispute-service:v1`) |
| `target.type` | `"edmx"` for OData, `"openapi-v3"` for OpenAPI |
| `serverInfo.name` | Reverse-DNS format with exactly one `/`: `{namespace}/{server-name}`. Pattern: `^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$` |
| `serverInfo.version` | Semver `x.y.z` (e.g., `"1.0.0"`) |

#### Server Name Derivation

Derive the `serverInfo.name` and the `{mcp-server-name}` filename segment from the ORD ID:

| ORD ID | `serverInfo.name` | `{mcp-server-name}` (filename) |
|---|---|---|
| `sap.s4:apiResource:dispute-service:v1` | `com.sap.s4/dispute-service` | `dispute-service` |
| `sap.s4:apiResource:business-partner-api:v1` | `com.sap.s4/business-partner-api` | `business-partner-api` |

### Tool Naming Conventions

Tool names MUST match pattern: `^[a-z][a-z0-9_]*$` (lowercase snake_case only).

| API Type | Convention | Examples |
|---|---|---|
| OData EntitySet CRUD | `{verb}_{entity_snake}` | `list_disputes`, `get_dispute_by_key`, `create_dispute`, `delete_dispute` |
| OData Operations | `{operation_name_snake}` | `activate_business_partner`, `approve_purchase_order` |
| OpenAPI | `{method}_{path_snake}` | `get_business_partner`, `post_documents`, `list_business_partners` |

### OData Tools (`odataType`)

Use `odataType` for OData (EDMX) APIs. Each tool must define exactly one of: `entitySet`, `operation`, or `metadataRequest`.

**`entitySet`** — Reference an OData EntitySet:
- `name`: Fully qualified EntitySet name (e.g., `DisputeService.EntityContainer.Disputes`)
- `crudOperation`: One of `create`, `read`, `readByKey`, `update`, `delete`, `count`
- `operation`: Bound action/function on the entity set (mutually exclusive with `crudOperation` and `navigationProperty`)
- `navigationProperty`: Navigate to related entity, supports recursive nesting (mutually exclusive with `crudOperation` and `operation`)
- `parameters`: Scoped parameter overrides for this entity level (key properties, query options)

**`operation`** — Unbound OData action/function (including V2 Function Imports):
- `name`: Operation name
- `type`: `"action"` or `"function"`
- `parameters`: Scoped parameter overrides for operation parameters

**`metadataRequest`** — Exposes a subset of the OData `$metadata` endpoint for context. Empty object `{}`.

**Parameter scoping:** Parameters are scoped per level: `entitySet.parameters`, `navigationProperty.parameters`, `operation.parameters`. The flat MCP tool parameter list is the union of all levels. When a tool uses nested levels (entitySet + navigationProperty), list ALL parameters from all levels in the tool description.

### OpenAPI Tools (`openApiType`)

Use `openApiType` for REST (OpenAPI v3) APIs.

- `path`: API path (e.g., `/BusinessPartner/{BusinessPartner}`)
- `method`: HTTP method (`get`, `post`, `put`, `patch`, `delete`)
- `operationId`: Optional, the OpenAPI operationId string
- `requestBody`: Config for request body (`contentType`, defaults to `application/json`). Required for POST/PUT/PATCH operations that accept a body.
- `parameters`: Array of parameter overrides with `name`, optional `in` (only to disambiguate same-name params across locations)

### Parameter Overrides (Both OData and OpenAPI)

| Override | Field | Effect |
|---|---|---|
| Rename | `newParameterName` | MCP client sees new name; API receives original |
| Hide | `deactivate: true` | Parameter not exposed (only for optional params) |
| Hardcode | `value` | Fixed string value, not exposed to MCP client |
| Enhance | `description` | Better context for LLMs |

**Constraints:**
- `deactivate` and `value` are mutually exclusive — never set both on the same parameter.
- `value` is always a string. Use JSON encoding for complex types (e.g., `"10"`, `"{\"key\": \"value\"}"`).

### Prompts (Optional)

The translation file can optionally include a `prompts` array with reusable prompt templates, e.g.:

```json
{
  "prompts": [
    {
      "name": "summarize_disputes",
      "title": "Summarize Disputes",
      "description": "Generates a summary of open dispute cases",
      "arguments": [
        { "name": "status", "description": "Filter by status", "required": false }
      ],
      "messages": [
        { "role": "user", "content": { "type": "text", "text": "Summarize all {status} disputes" } }
      ]
    }
  ]
}
```

Include prompts if they are available from the spec or task context. If not, omit the `prompts` field entirely.
Prompt names must match pattern: `^[a-z][a-z0-9_]*$` (same as tool names).

### Examples

See `assets/examples/` (relative to this skill's directory) for complete input/output samples:
- `odata-dispute-service/` — OData API with entitySet CRUD operations and scoped parameters
- `openapi-business-partner/` — OpenAPI with path+method, operationId, requestBody, parameter renaming and deactivation
