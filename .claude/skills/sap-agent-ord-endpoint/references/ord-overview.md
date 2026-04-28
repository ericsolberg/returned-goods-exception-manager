# ORD (Open Resource Discovery) Overview

## What is ORD?

**Open Resource Discovery (ORD)** is an SAP standard protocol that enables applications to expose machine-readable metadata about their APIs, events, and capabilities. It allows SAP platform services to automatically discover and catalog what an application offers — without manual registration.

ORD is defined at version **1.14** and is used across SAP BTP to power:

- **UMS (Unified Metadata Service)** — discovers available agents before provisioning, enabling administrators to browse and provision agents
- **Joule** — recommends agents to users based on conversation context, using ORD metadata to understand what each agent can do

---

## How ORD Works for Agents

An agent exposes four HTTP endpoints across two **perspectives**:

```
Static (system-version) perspective:
  GET /static/.well-known/open-resource-discovery          → ORD config entry point
  GET /static/open-resource-discovery/v1/documents/system-version  → static ORD document

Dynamic (system-instance) perspective:
  GET /dynamic/.well-known/open-resource-discovery         → ORD config entry point
  GET /dynamic/open-resource-discovery/v1/documents/system-instance → dynamic ORD document
```

### Two Perspectives

| Perspective       | Purpose                                                                     | Caching       |
| ----------------- | --------------------------------------------------------------------------- | ------------- |
| `system-version`  | Describes the system **type** — version-independent, same for all instances | `max-age=300` |
| `system-instance` | Describes the specific **deployed instance** — instance-specific data       | `no-cache`    |

### Discovery Flow

```
UMS / Joule
    │
    ├─► GET /static/.well-known/open-resource-discovery
    │       Returns: location of system-version ORD document
    │
    └─► GET /static/open-resource-discovery/v1/documents/system-version
            Returns: full ORD document with agent metadata
                     including agents section, entry points,
                     consumption bundle, and API resource descriptions
```

---

## ORD Configuration Document

The well-known endpoint returns a configuration document using the `openResourceDiscoveryV1` wrapper:

```json
{
  "openResourceDiscoveryV1": {
    "documents": [
      {
        "url": "https://<agent-url>/static/open-resource-discovery/v1/documents/system-version",
        "accessStrategies": [
          {
            "type": "open"
          }
        ],
        "perspective": "system-version"
      }
    ]
  }
}
```

> **Note:** The `openResourceDiscoveryV1` wrapper (not `openResourceDiscovery`) is the correct format for the well-known config endpoint.

---

## ORD Document Structure

The ORD document describes the agent's resources. For an App Foundation agent, it contains five main sections:

### 1. Document-Level Fields

```json
{
  "openResourceDiscovery": "1.14",
  "$schema": "https://open-resource-discovery.org/spec-v1/interfaces/Document.schema.json",
  "perspective": "system-version",
  "policyLevels": ["sap:ai:v1"],
  "describedSystemInstance": {
    "baseUrl": "https://<agent-url>"
  },
  "describedSystemVersion": {
    "version": "1.0.0"
  }
}
```

### 2. Packages

Groups related resources together. Each agent has one package with `policyLevel: "sap:ai:v1"` and a `vendor` field:

```json
{
  "ordId": "<namespace>:package:<agent-id>:v1",
  "title": "<Agent Title> Package",
  "shortDescription": "<description>",
  "version": "1.0.0",
  "policyLevel": "sap:ai:v1",
  "vendor": "sap:vendor:SAP:"
}
```

### 3. Consumption Bundles

Describes how consumers authenticate to use the agent:

```json
{
  "ordId": "<namespace>:consumptionBundle:<agent-id>-api:v1",
  "title": "<Agent Title> API",
  "shortDescription": "<description>",
  "version": "1.0.0"
}
```

### 4. Agents ⭐

The `agents` section is the **primary resource type for AI agents**. It describes the agent's capabilities, links to its API resource, and lists its integration dependencies:

```json
{
  "ordId": "<namespace>:agent:<agent-id>:v1",
  "title": "<Agent Title>",
  "shortDescription": "<description>",
  "description": "<description>",
  "version": "1.0.0",
  "visibility": "public",
  "releaseStatus": "active",
  "partOfPackage": "<namespace>:package:<agent-id>:v1",
  "exposedApiResources": [
    { "ordId": "<namespace>:apiResource:<agent-id>-api:v1" }
  ],
  "integrationDependencies": ["<namespace>:integrationDependency:<dep-id>:v1"],
  "labels": {
    "interactionMode": ["conversational"],
    "llmModel": ["anthropic--claude-4.5-sonnet"],
    "framework": ["langgraph"]
  },
  "tags": ["sap", "ai-agent", "a2a"]
}
```

> **Note:** `integrationDependencies` in the `agents` section is a **list of ORD ID strings** (not full objects). The full dependency definitions are in the top-level `integrationDependencies` array.

### 5. API Resources

Describes the agent's A2A API. Key differences from generic APIs:

- `apiProtocol` must be `"a2a"` (not `"rest"`)
- `resourceDefinitions` must include a reference to the agent card

```json
{
  "ordId": "<namespace>:apiResource:<agent-id>-api:v1",
  "title": "<Agent Title> A2A API",
  "version": "1.0.0",
  "visibility": "public",
  "releaseStatus": "active",
  "partOfPackage": "<namespace>:package:<agent-id>:v1",
  "partOfConsumptionBundles": [
    { "ordId": "<namespace>:consumptionBundle:<agent-id>-api:v1" }
  ],
  "apiProtocol": "a2a",
  "extensible": { "supported": "no" },
  "resourceDefinitions": [
    {
      "type": "a2a-agent-card",
      "mediaType": "application/json",
      "url": "https://<agent-url>/agent-card",
      "accessStrategies": [{ "type": "open" }]
    }
  ]
}
```

---

## ORD IDs

Every ORD resource has a globally unique `ordId` following this pattern:

```
<namespace>:<resourceType>:<resourceId>:<version>
```

| Component      | Description                           | Example                                                                         |
| -------------- | ------------------------------------- | ------------------------------------------------------------------------------- |
| `namespace`    | Application namespace from `app.yaml` | `travel-expense-agent`                                                          |
| `resourceType` | Type of resource                      | `package`, `consumptionBundle`, `agent`, `apiResource`, `integrationDependency` |
| `resourceId`   | Unique resource identifier            | `travel-expense-agent`                                                          |
| `version`      | Semantic version prefix               | `v1`                                                                            |

**Examples:**

- `travel-expense-agent:agent:travel-expense-agent:v1`
- `travel-expense-agent:apiResource:travel-expense-agent-api:v1`
- `travel-expense-agent:integrationDependency:sap-ai-core:v1`

---

## Authentication

ORD endpoints are **open** (no authentication required). This is required by the ORD specification — UMS must be able to discover the agent's ORD documents without credentials.

In `app.yaml`, set `no_auth` for all paths:

```yaml
service:
  apiAuth:
    - path: /*
      type: no_auth
```

If specific business routes require JWT, protect only those paths:

```yaml
service:
  apiAuth:
    - path: /v1/data/{**}
      type: jwt
    - path: /*
      type: no_auth
```

The `accessStrategies: [{type: "open"}]` in the ORD config document signals to UMS that the ORD documents are accessible without a token.

---

## Environment Variables

The ORD implementation reads these environment variables at runtime:

| Variable           | Description                                  | Set by                        |
| ------------------ | -------------------------------------------- | ----------------------------- |
| `AGENT_PUBLIC_URL` | The agent's public URL (provider tenant URL) | App Foundation at deploy time |

The `{{AGENT_BASE_URL}}` placeholder in the JSON templates is replaced at **runtime** (not build time) by `ord.py` using this variable. This ensures the ORD document always contains the correct deployed URL.

---

## Integration Dependencies

The `integrationDependencies` section declares which external services or APIs the agent depends on. This allows UMS and other platform tools to understand the agent's runtime requirements.

### Two-Level Structure

Dependencies appear in **two places** in the ORD document:

1. **In `agents[0].integrationDependencies`** — a list of ORD ID strings (references):

   ```json
   "integrationDependencies": [
     "travel-expense-agent:integrationDependency:sap-ai-core:v1"
   ]
   ```

2. **In the top-level `integrationDependencies`** — full dependency objects with `aspects`:
   ```json
   "integrationDependencies": [
     {
       "ordId": "travel-expense-agent:integrationDependency:sap-ai-core:v1",
       "title": "SAP AI Core Inference API",
       "shortDescription": "LLM inference service",
       "description": "LLM inference service used for AI responses",
       "version": "1.0.0",
       "visibility": "public",
       "releaseStatus": "active",
       "mandatory": true,
       "partOfPackage": "travel-expense-agent:package:travel-expense-agent:v1",
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

### `mandatory` Field

| Value   | Meaning                                                               |
| ------- | --------------------------------------------------------------------- |
| `true`  | The agent cannot function without this dependency                     |
| `false` | The dependency is optional — the agent degrades gracefully without it |

---

## Complete ORD Document Example

```json
{
  "openResourceDiscovery": "1.14",
  "$schema": "https://open-resource-discovery.org/spec-v1/interfaces/Document.schema.json",
  "perspective": "system-version",
  "policyLevels": ["sap:ai:v1"],
  "describedSystemInstance": {
    "baseUrl": "https://travel-expense-agent.cluster-id.stage.kyma.ondemand.com"
  },
  "describedSystemVersion": {
    "version": "1.0.0"
  },
  "packages": [
    {
      "ordId": "travel-expense-agent:package:travel-expense-agent:v1",
      "title": "Travel Expense Agent Package",
      "shortDescription": "Package for Travel Expense Agent and related resources",
      "description": "An AI agent that helps employees manage travel expenses",
      "version": "1.0.0",
      "policyLevel": "sap:ai:v1",
      "vendor": "sap:vendor:SAP:"
    }
  ],
  "consumptionBundles": [
    {
      "ordId": "travel-expense-agent:consumptionBundle:travel-expense-agent-api:v1",
      "title": "Travel Expense Agent API",
      "shortDescription": "Consumption bundle for Travel Expense Agent A2A API",
      "description": "This consumption bundle provides access to the Travel Expense Agent via the A2A protocol.",
      "version": "1.0.0"
    }
  ],
  "agents": [
    {
      "ordId": "travel-expense-agent:agent:travel-expense-agent:v1",
      "title": "Travel Expense Agent",
      "shortDescription": "An AI agent that helps employees manage travel expenses",
      "description": "An AI agent that helps employees manage travel expenses",
      "version": "1.0.0",
      "visibility": "public",
      "releaseStatus": "active",
      "partOfPackage": "travel-expense-agent:package:travel-expense-agent:v1",
      "exposedApiResources": [
        {
          "ordId": "travel-expense-agent:apiResource:travel-expense-agent-api:v1"
        }
      ],
      "integrationDependencies": [
        "travel-expense-agent:integrationDependency:sap-ai-core:v1"
      ],
      "labels": {
        "interactionMode": ["conversational"],
        "llmModel": ["anthropic--claude-4.5-sonnet"],
        "framework": ["langgraph"]
      },
      "tags": ["sap", "ai-agent", "a2a"]
    }
  ],
  "apiResources": [
    {
      "ordId": "travel-expense-agent:apiResource:travel-expense-agent-api:v1",
      "title": "Travel Expense Agent A2A API",
      "shortDescription": "A2A API for interacting with the Travel Expense Agent",
      "description": "Agent-to-Agent (A2A) protocol API that enables interaction with the Travel Expense Agent.",
      "version": "1.0.0",
      "visibility": "public",
      "releaseStatus": "active",
      "partOfPackage": "travel-expense-agent:package:travel-expense-agent:v1",
      "partOfConsumptionBundles": [
        {
          "ordId": "travel-expense-agent:consumptionBundle:travel-expense-agent-api:v1"
        }
      ],
      "apiProtocol": "a2a",
      "extensible": { "supported": "no" },
      "resourceDefinitions": [
        {
          "type": "a2a-agent-card",
          "mediaType": "application/json",
          "url": "https://travel-expense-agent.cluster-id.stage.kyma.ondemand.com/agent-card",
          "accessStrategies": [{ "type": "open" }]
        }
      ],
      "tags": ["a2a", "agent-api"]
    }
  ],
  "integrationDependencies": [
    {
      "ordId": "travel-expense-agent:integrationDependency:sap-ai-core:v1",
      "title": "SAP AI Core Inference API",
      "shortDescription": "LLM inference service used for AI responses",
      "description": "LLM inference service used for AI responses",
      "version": "1.0.0",
      "visibility": "public",
      "releaseStatus": "active",
      "mandatory": true,
      "partOfPackage": "travel-expense-agent:package:travel-expense-agent:v1",
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
}
```

---

## Further Reading

- [SAP ORD Specification](https://sap.github.io/open-resource-discovery/)
- [ORD GitHub Repository](https://github.com/SAP/open-resource-discovery)
