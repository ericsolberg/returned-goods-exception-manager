---
name: create-agent-extension
description: Create an agent extension from scratch. Bootstraps agent extensions with extension points and MCP tools for the Agent Extension Editor. Use this skill when you want to create agent extensions (not full agents) that add capabilities to existing agents.
---

# Create Agent Extension Skill

**This skill operates on the current working directory.** The caller is responsible for running it from the correct target directory (e.g. `assets/agent-extension/`).

## Schema References

All generated files MUST conform to the following JSON Schema definitions.

### `base-agent.yaml` Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Base Agent",
  "description": "Schema for a base agent that can be extended via agent extensions",
  "type": "object",
  "required": ["ordId", "title", "version", "description", "capabilities"],
  "properties": {
    "ordId": {
      "type": "string",
      "description": "Id of the base agent",
      "pattern": "^sap\\.ai:agent:.+:v\\d+$"
    },
    "title": {
      "type": "string",
      "description": "Title of the base agent"
    },
    "version": {
      "type": "string",
      "description": "Version of the base agent"
    },
    "description": {
      "type": "string",
      "description": "Description of the base agent"
    },
    "capabilities": {
      "type": "object",
      "description": "Capabilities provided by the base agent",
      "properties": {
        "extensions": {
          "type": "array",
          "description": "List of extension capabilities",
          "items": {
            "type": "object",
            "required": ["uri"],
            "properties": {
              "description": {
                "type": "string",
                "description": "Description of the extension capability"
              },
              "params": {
                "type": "object",
                "properties": {
                  "capabilityId": {
                    "type": "string",
                    "description": "Identifier for the capability"
                  },
                  "displayName": {
                    "type": "string",
                    "description": "Display name of the capability"
                  },
                  "instructionSupported": {
                    "type": "boolean",
                    "description": "Whether the capability supports custom instructions"
                  },
                  "tools": {
                    "type": "object",
                    "description": "Tool configuration for the capability",
                    "properties": {
                      "additions": {
                        "type": "object",
                        "properties": {
                          "enabled": {
                            "type": "boolean",
                            "description": "Whether tool additions are enabled"
                          }
                        }
                      }
                    }
                  },
                  "supportedHooks": {
                    "type": "array",
                    "description": "Hooks supported by this capability",
                    "items": {
                      "type": "object",
                      "required": ["id", "type"],
                      "properties": {
                        "id": {
                          "type": "string",
                          "description": "Unique identifier for the hook"
                        },
                        "type": {
                          "type": "string",
                          "enum": ["BEFORE", "AFTER"],
                          "description": "Whether the hook runs before or after processing"
                        },
                        "displayName": {
                          "type": "string",
                          "description": "Display name of the hook"
                        },
                        "description": {
                          "type": "string",
                          "description": "Description of the hook"
                        }
                      }
                    }
                  }
                }
              },
              "required": {
                "type": "boolean",
                "description": "Whether this extension capability is required"
              },
              "uri": {
                "type": "string",
                "description": "URN identifying the extension capability"
              }
            }
          }
        }
      }
    }
  }
}
```

### `extension-implementation.yaml` Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Extension Descriptor",
  "description": "Schema for an agent extension descriptor YAML file",
  "type": "object",
  "required": ["_schema-version", "kind", "metadata", "agent", "capabilityImplementations"],
  "properties": {
    "_schema-version": {
      "type": "string",
      "description": "Schema version of the extension descriptor",
      "default": "0.1.0"
    },
    "kind": {
      "type": "string",
      "const": "Extension",
      "description": "Resource type, must be 'Extension'"
    },
    "metadata": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": {
          "type": "string",
          "description": "Name of the extension"
        },
        "isDefault": {
          "type": "boolean",
          "description": "Whether this is the default extension",
          "default": true
        }
      }
    },
    "agent": {
      "type": "object",
      "required": ["ordId", "authIdentifier"],
      "properties": {
        "ordId": {
          "type": "string",
          "description": "ORD ID of the base agent being extended",
          "pattern": "^sap\\.ai:agent:.+:v\\d+$"
        },
        "authIdentifier": {
          "type": "string",
          "description": "Authentication identifier for the base agent",
          "format": "uuid"
        }
      }
    },
    "capabilityImplementations": {
      "type": "array",
      "description": "List of capability implementations provided by this extension",
      "items": {
        "type": "object",
        "required": ["capabilityId"],
        "properties": {
          "capabilityId": {
            "type": "string",
            "description": "Identifier of the capability being implemented"
          },
          "tools": {
            "type": "array",
            "description": "MCP tools provided by this capability implementation",
            "items": {
              "type": "object",
              "required": ["ordId", "mcpToolName", "mcpUrl"],
              "properties": {
                "ordId": {
                  "type": "string",
                  "description": "ORD ID of the MCP tool"
                },
                "mcpToolName": {
                  "type": "string",
                  "description": "Name of the tool as exposed via MCP"
                },
                "mcpUrl": {
                  "type": "string",
                  "description": "URL of the MCP server providing this tool",
                  "format": "uri"
                }
              }
            }
          },
          "hooks": {
            "type": "array",
            "description": "Lifecycle hooks for this capability implementation",
            "items": {
              "type": "object",
              "required": ["hookId", "ordId", "name", "hookType", "deploymentType", "url"],
              "properties": {
                "hookId": {
                  "type": "string",
                  "description": "Unique identifier for the hook"
                },
                "ordId": {
                  "type": "string",
                  "description": "ORD ID of the hook"
                },
                "name": {
                  "type": "string",
                  "description": "Display name of the hook"
                },
                "hookType": {
                  "type": "string",
                  "enum": ["BEFORE", "AFTER"],
                  "description": "Whether the hook runs before or after agent processing"
                },
                "deploymentType": {
                  "type": "string",
                  "enum": ["N8N", "CF", "KYMA"],
                  "description": "Deployment type of the hook implementation"
                },
                "url": {
                  "type": "string",
                  "description": "Webhook URL for the hook",
                  "format": "uri"
                },
                "timeoutMs": {
                  "type": "integer",
                  "description": "Timeout in milliseconds for the hook execution",
                  "default": 5000,
                  "minimum": 0
                },
                "onFailure": {
                  "type": "string",
                  "enum": ["BLOCK", "CONTINUE"],
                  "description": "Behavior when the hook fails: BLOCK stops execution, CONTINUE ignores the failure"
                },
                "order": {
                  "type": "integer",
                  "description": "Execution order when multiple hooks of the same type exist",
                  "default": 0,
                  "minimum": 0
                },
                "canShortCircuit": {
                  "type": "boolean",
                  "description": "Whether the hook can short-circuit the agent pipeline",
                  "default": false
                }
              }
            }
          }
        }
      }
    }
  }
}
```

## Step 1: Fetch Agent Information

**IMPORTANT: Always fetch agent information first** to get the correct `ordId` and `description` for the agent to be extended.

#### When User Provides a Specific ordId

If the user provides a specific ordId (e.g., `sap.joule:agent:employee-onboarding:v1`), fetch that specific agent using the `ums_query` tool:

```graphql
query {
  ORD__AgentInstances(
    filters: { ordIdEquals: "<USER_PROVIDED_ORDID>" }
  ) {
    edges {
      node {
        id ordId title description shortDescription
        version releaseStatus
        uclSystemInstanceId
        uclSystemInstance { localTenantId }
        partOfPackage { title version }
        systemType { systemNamespace }
        partOfProducts { edges { node { title } } }
        exposedApiResources {
          edges {
            node {
              id ordId title apiProtocol
              resourceDefinitions {
                edges {
                  node {
                    linkToAgentCard: url
                  }
                }
              }
            }
          }
        }
        integrationDependencies { edges { node { id ordId title mandatory } } }
      }
    }
  }
}
```

Replace `<USER_PROVIDED_ORDID>` with the actual ordId provided by the user.

#### Default Query (No ordId Provided)

Use the `ums_query` tool with this GraphQL query to fetch all extendable agents:

```graphql
query {
  ORD__AgentInstances(
    filters: {
      labels:[{key:"isExtensible", value:"true"}]
    }
  ) {
    edges {
      node {
        id ordId title description shortDescription
        version releaseStatus
        uclSystemInstanceId
        uclSystemInstance { localTenantId }
        partOfPackage { title version }
        systemType { systemNamespace }
        partOfProducts { edges { node { title } } }
        exposedApiResources {
          edges {
            node {
              id ordId title apiProtocol
              resourceDefinitions {
                edges {
                  node {
                    linkToAgentCard: url
                  }
                }
              }
            }
          }
        }
        integrationDependencies { edges { node { id ordId title mandatory } } }
      }
    }
  }
}
```

#### Custom Query

If the user provides a dedicated GraphQL query, pass it directly to the `ums_query` tool.

#### Extract Agent Information

From the UMS response, extract and store these values for later use:

| UMS Response Field | Usage |
|---|---|
| `node.ordId` | → `base-agent.yaml: ordId` and `extension-implementation.yaml: agent.ordId` |
| `node.title` | → `base-agent.yaml: title` |
| `node.version` | → `base-agent.yaml: version` |
| `node.description` | → `base-agent.yaml: description` |
| `node.exposedApiResources...linkToAgentCard` | → URL to fetch A2A agent card in Step 2 |
| `node.uclSystemInstance.localTenantId` | → `extension-implementation.yaml: agent.authIdentifier` (fallback: `64f8e467-084b-465f-8a77-8bedf7d49120` if null or missing) |

#### Handle Multiple Versions

If the query returns **multiple versions** of the same agent (e.g., `sap.joule:agent:employee-onboarding:v1` and `sap.joule:agent:employee-onboarding:v2`), you **MUST ask the user which version to use** before proceeding. Present the versions clearly:

- List each version with its `ordId`, `version`, `releaseStatus`, and `shortDescription`
- Highlight differences between versions if apparent (e.g., different exposed APIs, different release status)
- **Do NOT default to the latest version silently** — always let the user decide

## Step 2: Fetch A2A Agent Card

Use the `get_agent_card` tool with the `linkToAgentCard` URL extracted in Step 1 to fetch the full A2A agent card.

From the A2A agent card response, extract:

| A2A Agent Card Field | Usage |
|---|---|
| `capabilities.extensions[]` | → `base-agent.yaml: capabilities.extensions[]` |
| `capabilities.extensions[].params.capabilityId` | → `extension-implementation.yaml: capabilityImplementations[].capabilityId` |
| `capabilities.extensions[].params.supportedHooks` | → determines which hooks can be defined in `extension-implementation.yaml` |
| `capabilities.extensions[].params.tools.additions.enabled` | → determines if tools can be added in `extension-implementation.yaml` |

## Step 3: Generate `base-agent.yaml`

Create `assets/<agent-extension>/base-agent.yaml` conforming to the `base-agent.yaml` schema above.

This file merges data from the UMS query and the A2A agent card:

```yaml
# Fields from UMS query (Step 1)
ordId: "<from UMS: node.ordId>"
title: "<from UMS: node.title>"
version: "<from UMS: node.version>"
description: "<from UMS: node.description>"

# Fields from A2A agent card (Step 2)
capabilities:
  extensions:
    - description: "<from A2A: capabilities.extensions[].description>"
      params:
        capabilityId: "<from A2A: capabilities.extensions[].params.capabilityId>"
        displayName: "<from A2A: capabilities.extensions[].params.displayName>"
        instructionSupported: <from A2A: capabilities.extensions[].params.instructionSupported>
        tools:
          additions:
            enabled: <from A2A: capabilities.extensions[].params.tools.additions.enabled>
        supportedHooks:
          - id: "<from A2A: ...supportedHooks[].id>"
            type: "<from A2A: ...supportedHooks[].type>"
            displayName: "<from A2A: ...supportedHooks[].displayName>"
            description: "<from A2A: ...supportedHooks[].description>"
      required: <from A2A: capabilities.extensions[].required>
      uri: "<from A2A: capabilities.extensions[].uri>"
```

## Step 4: Generate `extension-implementation.yaml`

Create `assets/<agent-extension>/extension-implementation.yaml` conforming to the `extension-implementation.yaml` schema above.

This file defines what the extension actually provides. Map fields as follows:

```yaml
_schema-version: "0.1.0"
kind: Extension

metadata:
  name: "<agent-extension-name>-hooks"
  isDefault: true

agent:
  ordId: "<from UMS: node.ordId>"
  authIdentifier: "<from UMS: node.uclSystemInstance.localTenantId, fallback: 64f8e467-084b-465f-8a77-8bedf7d49120>"

capabilityImplementations:
  - capabilityId: "<from A2A: capabilities.extensions[].params.capabilityId>"
    tools: []
    hooks: []
```

**Important rules for extension-implementation.yaml:**
- Always include an empty `tools: []` array and an empty `hooks: []` array — even if no tools or hooks are configured yet
- The `capabilityId` must match the `params.capabilityId` from the base agent's capabilities

## Step 5: Setup Solution

After bootstrapping, automatically execute the `setup-solution` skill to create an `asset.yaml` in this same directory with `buildPath: .` and `/.well-known/agent.json` health probes.
