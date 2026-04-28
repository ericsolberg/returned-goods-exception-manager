---
name: sap-agent-ord-endpoint
description: Add an ORD (Open Resource Discovery) endpoint to an App Foundation agent. Use when the user wants to expose their agent's metadata so UMS can discover it before provisioning, or so Joule can recommend it based on conversation context.
---

# ORD Endpoint for App Foundation Agents

Adds an **Open Resource Discovery (ORD)** endpoint to an existing App Foundation agent. ORD is the SAP standard protocol that allows UMS to discover available agents before provisioning and enables Joule to recommend agents based on conversation context.

## What Gets Added

Three new HTTP endpoints on the agent:

| Endpoint                                                    | Description                                                           |
| ----------------------------------------------------------- | --------------------------------------------------------------------- |
| `GET /.well-known/open-resource-discovery`                  | ORD config — lists both ORD documents                                 |
| `GET /open-resource-discovery/v1/documents/system-version`  | Static ORD document — describes the agent's APIs and metadata         |
| `GET /open-resource-discovery/v1/documents/system-instance` | Dynamic ORD document — tenant-aware view (accepts `?local-tenant-id`) |

All ORD endpoints are **open** (no authentication required). This is required by the ORD specification so UMS can discover the agent. The A2A agent endpoints remain protected by the App Foundation gateway's JWT authentication.

Three new files are created in the agent project:

```
app/
├── ord.py                              # ORD endpoint handlers (loads JSON files)
└── ord/
    ├── document-system-version.json    # Static ORD document (system/provider level)
    └── document-system-instance.json  # Dynamic ORD document (tenant instance level)
```

---

## Phase 1: Read Existing Agent Configuration

Before making any changes, read the existing agent files to extract the required values.

```bash
cat app.yaml
cat app/main.py
```

Extract the following values:

| Value                 | Where to find it                              | Example                     |
| --------------------- | --------------------------------------------- | --------------------------- |
| **Agent name**        | `metadata.name` in `app.yaml`                 | `travel-expense-agent`      |
| **Agent title**       | `AgentCard(name=...)` in `app/main.py`        | `Travel Expense Agent`      |
| **Agent description** | `AgentCard(description=...)` in `app/main.py` | `An AI agent that helps...` |

Then ask the developer:

> "What is your **CPA (Cloud Platform Application) namespace**?
>
> This is the ORD namespace registered for your application in the SAP ecosystem (e.g., `sap.appfnd`, `sap.s4`, `customer.mycompany`). It is **not** the Kubernetes namespace from `app.yaml`.
>
> If you are unsure, check with your team or the SAP BTP cockpit where your application namespace was registered."

Use the value provided by the developer as `{{AGENT_NAMESPACE}}`.

If any other value cannot be found, ask the user to provide it.

---

## Phase 1.5: Collect Dependencies

Create an example `ord-dependencies.json` file at the project root using `write_to_file`:

```json
{
  "_instructions": "Fill in your agent's integration dependencies below. Remove this _instructions field and any example entries that do not apply. If your agent has no dependencies, set the 'dependencies' array to [].",
  "dependencies": [
    {
      "ordId": "sap.aicore:apiResource:inference:v1",
      "title": "SAP AI Core Inference API",
      "description": "LLM inference service used for AI responses",
      "mandatory": true
    },
    {
      "ordId": "sap.objectstore:apiResource:object-store:v1",
      "title": "SAP Object Store",
      "description": "Object storage service used for file persistence",
      "mandatory": false
    }
  ]
}
```

Then ask the developer:

> "I've created `ord-dependencies.json` in your project root with example entries.
>
> Please open the file and:
>
> - Replace the example entries with your agent's actual dependencies
> - For each dependency, provide the ORD ID, title, description, and whether it is mandatory
> - If your agent has no dependencies, set `"dependencies": []`
> - Remove the `_instructions` field when done
>
> Reply here when you have finished editing the file."

### After the developer confirms

Read the file to get the dependency data:

```bash
cat ord-dependencies.json
```

Parse the `dependencies` array from the file contents.

### If the dependencies array is empty

Note this for Phase 2. The `integrationDependencies` arrays in the JSON files will be left empty.

### If the dependencies array has entries

Note the dependency details for Phase 2. After creating the JSON files, update both `integrationDependencies` arrays using `replace_in_file`:

**In `agents[0].integrationDependencies`** — add the ORD IDs as strings:

```json
"integrationDependencies": [
  "<namespace>:integrationDependency:<dep-id>:v0",
  "<namespace>:integrationDependency:<dep-id-2>:v0"
]
```

**In the top-level `integrationDependencies`** — add the full dependency objects:

```json
"integrationDependencies": [
  {
    "ordId": "<namespace>:integrationDependency:<dep-id>:v0",
    "title": "<Dependency Title>",
    "shortDescription": "<description>",
    "description": "<description>",
    "version": "1.0.0",
    "visibility": "public",
    "releaseStatus": "active",
    "mandatory": true,
    "partOfPackage": "<namespace>:package:<agent-id>:v0",
    "aspects": [
      {
        "title": "<Aspect Title>",
        "description": "<aspect description>",
        "mandatory": true,
        "apiResources": [
          {
            "ordId": "<external-resource-ord-id>",
            "minVersion": "1.0.0"
          }
        ]
      }
    ]
  }
]
```

**Example** — agent that uses SAP AI Core (mandatory) and Object Store (optional):

```json
"integrationDependencies": [
  {
    "ordId": "sap.travelexpenseagent:integrationDependency:sap-ai-core:v1",
    "title": "SAP AI Core Inference API",
    "shortDescription": "LLM inference service used for AI responses",
    "description": "LLM inference service used for AI responses",
    "version": "1.0.0",
    "visibility": "public",
    "releaseStatus": "active",
    "mandatory": true,
    "partOfPackage": "sap.travelexpenseagent:package:travel-expense-agent:v1",
    "aspects": [
      {
        "title": "AI Inference Access",
        "description": "Access to LLM inference via SAP AI Core",
        "mandatory": true,
        "apiResources": [
          {
            "ordId": "sap.aicore:apiResource:inference:v1",
            "minVersion": "1.0.0"
          }
        ]
      }
    ]
  }
]
```

> **Note on ORD IDs:** If the developer does not know the exact ORD ID of a dependency, use the best available identifier and note that it should be confirmed with the dependency's owner.

---

## Phase 2: Create ORD Files

### 2a. Create the `app/ord/` directory and copy JSON templates

**macOS/Linux:**

```bash
mkdir -p app/ord
SKILL_PATH=$(find . -type d -name "sap-agent-ord-endpoint" -path "*/skills/*" 2>/dev/null | head -1)
cp "$SKILL_PATH/templates/app/ord/document-system-version.json" app/ord/document-system-version.json
cp "$SKILL_PATH/templates/app/ord/document-system-instance.json" app/ord/document-system-instance.json
```

**Windows PowerShell:**

```powershell
New-Item -ItemType Directory -Force -Path app/ord
$SkillPath = Get-ChildItem -Path . -Recurse -Directory -Filter "sap-agent-ord-endpoint" | Where-Object { $_.FullName -like "*skills*" } | Select-Object -First 1 -ExpandProperty FullName
Copy-Item "$SkillPath/templates/app/ord/document-system-version.json" -Destination "app/ord/document-system-version.json"
Copy-Item "$SkillPath/templates/app/ord/document-system-instance.json" -Destination "app/ord/document-system-instance.json"
```

### 2b. Replace placeholders in both JSON files

Replace placeholders using the values extracted in Phase 1. Run the same substitution for **both** JSON files:

**macOS (sed -i ''):**

```bash
for file in app/ord/document-system-version.json app/ord/document-system-instance.json; do
  sed -i '' \
    -e 's/{{AGENT_ORD_ID}}/<agent-name>/g' \
    -e 's/{{AGENT_NAMESPACE}}/<agent-namespace>/g' \
    -e 's/{{AGENT_TITLE}}/<Agent Title>/g' \
    -e 's/{{AGENT_LONG_DESCRIPTION}}/<agent-long-description>/g' \
    -e 's/{{AGENT_DESCRIPTION}}/<agent-description>/g' \
    "$file"
done
```

**Linux (sed -i without quotes):**

```bash
for file in app/ord/document-system-version.json app/ord/document-system-instance.json; do
  sed -i \
    -e 's/{{AGENT_ORD_ID}}/<agent-name>/g' \
    -e 's/{{AGENT_NAMESPACE}}/<agent-namespace>/g' \
    -e 's/{{AGENT_TITLE}}/<Agent Title>/g' \
    -e 's/{{AGENT_LONG_DESCRIPTION}}/<agent-long-description>/g' \
    -e 's/{{AGENT_DESCRIPTION}}/<agent-description>/g' \
    "$file"
done
```

**Windows PowerShell:**

```powershell
foreach ($file in @("app/ord/document-system-version.json", "app/ord/document-system-instance.json")) {
  (Get-Content $file) `
    -replace '{{AGENT_ORD_ID}}','<agent-name>' `
    -replace '{{AGENT_NAMESPACE}}','<agent-namespace>' `
    -replace '{{AGENT_TITLE}}','<Agent Title>' `
    -replace '{{AGENT_LONG_DESCRIPTION}}','<agent-long-description>' `
    -replace '{{AGENT_DESCRIPTION}}','<agent-description>' |
    Set-Content $file
}
```

> **Note:** The `{{AGENT_BASE_URL}}` placeholder is **not** replaced at build time — it is injected at runtime from the `AGENT_PUBLIC_URL` environment variable by `ord.py`. This ensures the ORD documents always contain the correct provider tenant URL.

### 2c. Copy `app/ord.py`

**macOS/Linux:**

```bash
SKILL_PATH=$(find . -type d -name "sap-agent-ord-endpoint" -path "*/skills/*" 2>/dev/null | head -1)
cp "$SKILL_PATH/templates/app/ord.py" app/ord.py
```

**Windows PowerShell:**

```powershell
$SkillPath = Get-ChildItem -Path . -Recurse -Directory -Filter "sap-agent-ord-endpoint" | Where-Object { $_.FullName -like "*skills*" } | Select-Object -First 1 -ExpandProperty FullName
Copy-Item "$SkillPath/templates/app/ord.py" -Destination "app/ord.py"
```

### 2d. Customize agent labels

Both JSON files contain an `agents[].labels` section with `"interactionMode": ["conversational"]`. Optionally extend this with agent-specific labels using `replace_in_file`:

```json
"labels": {
  "interactionMode": ["conversational"],
  "llmModel": ["anthropic--claude-4.5-sonnet"],
  "framework": ["langgraph"]
}
```

Common label keys:

- `llmModel` — the LLM model used (e.g., `anthropic--claude-4.5-sonnet`, `gpt-4o`)
- `framework` — the agent framework (e.g., `langgraph`, `autogen`, `semantic-kernel`)

Apply the same change to **both** `document-system-version.json` and `document-system-instance.json`.

### 2e. Add dependencies (if any from Phase 1.5)

If the `ord-dependencies.json` file contained any entries, update the `integrationDependencies` arrays in **both** JSON files using `replace_in_file` as described in Phase 1.5.

## Placeholder Derivation Rules

| Placeholder                  | Derivation                                                                                                                                                                                                                                                                                                               | Example                                                                                                                                                                  |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `{{AGENT_ORD_ID}}`           | Same as `metadata.name` in `app.yaml`                                                                                                                                                                                                                                                                                    | `travel-expense-agent`                                                                                                                                                   |
| `{{AGENT_NAMESPACE}}`        | The CPA (Cloud Platform Application) namespace registered for the application in the SAP ecosystem. **Must be provided by the developer** — it cannot be inferred from project files. Must be lowercase alphanumeric with exactly one dot (e.g., `sap.appfnd`). Do **not** use the Kubernetes namespace from `app.yaml`. | `sap.appfnd`                                                                                                                                                             |
| `{{AGENT_TITLE}}`            | Title-case: replace `-` with space, capitalize each word                                                                                                                                                                                                                                                                 | `Travel Expense Agent`                                                                                                                                                   |
| `{{AGENT_DESCRIPTION}}`      | Same as `AgentCard(description=...)` in `app/main.py`                                                                                                                                                                                                                                                                    | `An AI agent that helps employees manage travel expenses`                                                                                                                |
| `{{AGENT_LONG_DESCRIPTION}}` | A longer description of the agent that expands on its purpose, capabilities, and integration context. Must **not** contain the `{{AGENT_DESCRIPTION}}` text verbatim (required by `sap-ord-description-unique` rule). Write 1–2 sentences describing what the agent does, who uses it, and how it integrates.            | `The Travel Expense Agent automates the submission and approval of employee travel expense reports by integrating with SAP Concur and ERP systems via the A2A protocol.` |

---

## Phase 3: Update `app/main.py`

Add the ORD routes to the agent by modifying `app/main.py`. The ORD routes are mounted alongside the existing A2A application.

### 3a. Add imports

Add these imports near the top of `app/main.py`, after the existing imports:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from ord import create_ord_routes
```

### 3b. Replace the `uvicorn.run` call

Find the existing `uvicorn.run(server.build(), ...)` line and replace it with:

```python
    # Build A2A app
    a2a_app = server.build()

    # Combine ORD routes with A2A app
    # ORD routes are matched first, then all other requests go to the A2A app
    combined_app = Starlette(
        routes=[
            *create_ord_routes(),
            Mount("/", app=a2a_app),
        ]
    )

    logger.info(f"Starting agent with ORD endpoint at http://{host}:{port}/.well-known/open-resource-discovery")
    uvicorn.run(combined_app, host=host, port=port)
```

---

## Phase 4: Update `app.yaml` Authentication

ORD endpoints must be **open** (no authentication) so UMS can discover the agent. Update `app.yaml` to use `no_auth` for all paths, while keeping JWT for any paths that require it (e.g., business API routes).

### For a basic agent (bootstrapped with `sap-agent-bootstrap`)

Change the `apiAuth` section from a single object to an array:

**Before:**

```yaml
service:
  apiAuth:
    path: /*
    type: jwt
```

**After:**

```yaml
service:
  apiAuth:
    - path: /*
      type: no_auth
```

### For an agent with authenticated business routes

If the agent has routes that require JWT (e.g., `/v1/data/{**}`), protect only those paths:

```yaml
service:
  apiAuth:
    - path: /v1/data/{**}
      type: jwt
    - path: /*
      type: no_auth
```

> **Why `no_auth` for ORD?** The ORD specification requires that ORD documents be discoverable without authentication. UMS uses the `accessStrategies` in the ORD config to know how to access each document. The A2A agent protocol handles its own authentication separately.

---

## Phase 5: Test the ORD Endpoint

### Local Testing

Start the agent locally first (see `sap-agent-run-local` skill), then:

```bash
# Test ORD well-known configuration
curl -s http://localhost:9000/.well-known/open-resource-discovery | python3 -m json.tool

# Test ORD system-version document (static)
curl -s http://localhost:9000/open-resource-discovery/v1/documents/system-version | python3 -m json.tool

# Test ORD system-instance document (dynamic) — via query param
curl -s "http://localhost:9000/open-resource-discovery/v1/documents/system-instance?local-tenant-id=T1" | python3 -m json.tool

# Test ORD system-instance document (dynamic) — via header (query param takes priority)
curl -s -H "local-tenant-id: T1" "http://localhost:9000/open-resource-discovery/v1/documents/system-instance" | python3 -m json.tool
```

**Expected response for well-known endpoint:**

```json
{
  "openResourceDiscoveryV1": {
    "documents": [
      {
        "url": "/open-resource-discovery/v1/documents/system-version",
        "accessStrategies": [{ "type": "open" }],
        "perspective": "system-version"
      },
      {
        "url": "/open-resource-discovery/v1/documents/system-instance",
        "accessStrategies": [
          {
            "type": "custom",
            "customType": "sap.xref:open-global-tenant-id:v1",
            "customDescription": "..."
          },
          {
            "type": "custom",
            "customType": "sap.xref:open-local-tenant-id:v1",
            "customDescription": "..."
          }
        ],
        "perspective": "system-instance"
      }
    ]
  }
}
```

**Expected response for ORD system-version document:**

```json
{
  "openResourceDiscovery": "1.14",
  "perspective": "system-version",
  "policyLevels": ["sap:ai:v1"],
  "describedSystemInstance": { "baseUrl": "http://localhost:9000" },
  "agents": [
    {
      "ordId": "<namespace>:agent:<agent-id>:v1",
      "title": "<Agent Title>",
      ...
    }
  ],
  "apiResources": [
    {
      "apiProtocol": "a2a",
      "resourceDefinitions": [
        { "type": "a2a-agent-card", "url": "http://localhost:9000/agent-card" }
      ],
      ...
    }
  ]
}
```

**Expected response for ORD system-instance document:**

```json
{
  "openResourceDiscovery": "1.14",
  "perspective": "system-instance",
  "policyLevels": ["sap:ai:v1"],
  "describedSystemInstance": { "localId": "T1" },
  ...
}
```

> **Note:** `describedSystemInstance.localId` is populated at request time from the `?local-tenant-id=T1` query parameter. If no tenant ID is provided, `localId` will be an empty string.

**Verify the ORD documents contain:**

- ✅ `"openResourceDiscovery": "1.14"` (correct version)
- ✅ `agents` section with the agent's ORD ID
- ✅ `apiResources` with `"apiProtocol": "a2a"`
- ✅ `resourceDefinitions` with `"type": "a2a-agent-card"` pointing to `/agent-card`
- ✅ `describedSystemInstance.baseUrl` contains the correct URL
- ✅ `integrationDependencies` populated (if dependencies were provided)
- ✅ `system-version` document has `"perspective": "system-version"`
- ✅ `system-instance` document has `"perspective": "system-instance"`

### Deployed Testing

After deploying the agent, test without authentication (ORD endpoints are open):

```bash
# Test ORD well-known endpoint (no token needed)
curl -s "https://<agent-url>/.well-known/open-resource-discovery" | python3 -m json.tool

# Test ORD system-version document
curl -s "https://<agent-url>/open-resource-discovery/v1/documents/system-version" | python3 -m json.tool

# Test ORD system-instance document
curl -s "https://<agent-url>/open-resource-discovery/v1/documents/system-instance?local-tenant-id=T1" | python3 -m json.tool
```

Verify that `describedSystemInstance.baseUrl` and `resourceDefinitions[].url` contain the correct deployed URL (set from `AGENT_PUBLIC_URL` environment variable).

---

## Reference

For more details on the ORD specification and document structure, see [references/ord-overview.md](references/ord-overview.md).

## Next Steps

After adding the ORD endpoint:

1. **Deploy** — Push to GitHub to trigger CI/CD deployment
2. **Register with UMS** — Provide the static ORD well-known URL to UMS for agent discovery: `https://<agent-url>/.well-known/open-resource-discovery`
3. **Test remotely** — Use the `sap-agent-test-remote` skill to verify the full agent works after deployment
