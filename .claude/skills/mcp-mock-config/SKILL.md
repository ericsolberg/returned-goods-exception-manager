---
name: mcp-mock-config
description: Generate mcp-mock.json from agent specifications (translation.json, api-spec.json). Use when user wants to "generate mcp mock config", "create mcp-mock.json", "mock MCP tools/server responses", "set up deterministic test data", or "test agent without real MCP servers".
tags: [mcp, mocking, json-generation, testing, agent-development]
metadata:
  owner: ibd
  version: "3.0"
---

# MCP Mock Configuration Generator

Generate a single `mcp-mock.json` configuration file from agent MCP specifications. This skill reads `translation.json` and `api-spec.json` to extract tool definitions and create deterministic mock responses for testing agents without real MCP servers.

## Prerequisites

- Agent project directory with MCP tool specifications
- At least one specification file:
  - `translation.json` (required) - Tool names, descriptions, parameters
  - `api-spec.json` (optional) - OpenAPI schemas for response structure

## Inputs

**Required:**
- Agent project directory path
- `translation.json` file containing:
  - `serverInfo`: name, description, version
  - `tools[]`: name, description, parameters, openApiType

**Optional:**
- `api-spec.json` - OpenAPI specification for enhanced schema extraction
- `.mcp.json` - MCP server configuration
- Custom mock value overrides from user

**Input Assumptions:**
- `translation.json` follows standard MCP tool definition format
- `api-spec.json` follows OpenAPI 3.0 specification
- Parameters with `"deactivate": true` should be excluded

## Output

**Primary Artifact:** Single `mcp-mock.json` file

**Structure (servers and tools as hashmaps for O(1) lookup):**
```json
{
  "servers": {
    "server-slug-1": {
      "mcp_server_name": "full.server.name/API_NAME",
      "description": "Server description",
      "tools": {
        "tool_name_1": {
          "description": "tool description",
          "input_schema": { ... },
          "mock_response": { ... }
        },
        "tool_name_2": {
          "description": "tool description",
          "input_schema": { ... },
          "mock_response": { ... }
        }
      }
    },
    "server-slug-2": {
      "mcp_server_name": "another-server",
      "description": "Another server description",
      "tools": {
        "tool_name_3": { ... }
      }
    }
  },
  "metadata": {
    "version": "1.0.0",
    "created_for_agent": "agent-name",
    "mock_mode": true,
    "deterministic": true,
    "total_servers": 2,
    "total_tools": 3,
    "generated_from": ["translation.json", "api-spec.json"],
    "generation_date": "YYYY-MM-DD"
  }
}
```

**Key Design Decisions:**
- **Single file**: One `mcp-mock.json` for the entire agent
- **Servers as hashmap**: `servers` is an object keyed by server slug for O(1) lookup
- **Tools as hashmap**: `tools` within each server is an object keyed by tool name for O(1) lookup
- **Double O(1) lookup**: `mockData.servers["server-slug"].tools["tool-name"]`

**Done Criteria:**
- [ ] Single `mcp-mock.json` created in agent directory
- [ ] All servers stored as hashmap (object, not array)
- [ ] All tools within each server stored as hashmap
- [ ] All tools from all `translation.json` files included
- [ ] Mock responses match expected schema structure
- [ ] JSON is valid (parseable)
- [ ] No agent code modified

## Workflow

### Step 1: Discover Specification Files

**Actions:**
1. Search for specification files:
   - `assets/**/translation.json`
   - `**/translation.json`
   - `assets/**/api-spec.json`
   - `.mcp.json` (root)
2. For each `translation.json` found, extract:
   - `serverInfo.name` → server key (slugified)
   - `serverInfo.description` → description
   - `tools[]` array

**Validation:**
- At least one `translation.json` found
- Each has `serverInfo` section
- Each has `tools` array with at least one entry

**If validation fails:** Ask user for specification file location

### Step 2: Extract Tool Schemas

**Actions:**
1. For each server's `tools[]`:
   - Extract `name`, `description`, `title`
   - Extract `parameters[]` (filter out `deactivate: true`)
   - Note `openApiType.path` for schema lookup

2. Build `input_schema` from parameters:
   ```json
   {
     "type": "object",
     "properties": {
       "param_name": {
         "type": "string",
         "description": "param description"
       }
     },
     "required": []
   }
   ```

3. If `api-spec.json` exists for this server:
   - Match `openApiType.path` to OpenAPI paths
   - Extract response schema from `components/schemas`
   - Get field names, types, and constraints

**Validation:**
- All tools have name and description
- Input schemas built for all tools
- OpenAPI paths matched (if api-spec.json present)

### Step 3: Generate Mock Responses

**Actions:**
1. For each tool, generate mock response based on:
   - Response schema from api-spec.json (if available)
   - Type mapping rules (see `references/type-mapping.md`)
   - SAP OData patterns (see `references/sap-odata-patterns.md`)

2. Apply type-specific mock values:
   - `string` → field-appropriate value
   - `string` + `format: decimal` → `"75000.00"`
   - `string` + date example → `/Date(timestamp)/`
   - `integer` → reasonable number
   - `array` → 1-2 mock items with full structure
   - `object` → nested mock structure

3. For list operations (path ends without key):
   - Wrap in `{"results": [...]}`
   - Include 2 mock items for variety

4. For single-entity operations (path has key parameters):
   - Return single object (no wrapper)

**Validation:**
- Mock response has all required fields from schema
- Data types match schema definitions
- Arrays have at least one item

### Step 4: Write mcp-mock.json

**Actions:**
1. Build unified structure with all servers as hashmap
2. Generate server slugs from `serverInfo.name`:
   - `com.sap.s4/API_SUPPLIERINVOICE_PROCESS_SRV` → `s4-supplier-invoice`
   - `n8n-workflow-mcp` → `n8n-workflow`
   - `ibd-mcp-server` → `ibd`
3. Add metadata with totals
4. Write single `mcp-mock.json` file to agent root
5. Validate JSON syntax

**Slug Generation Rules:**
- Remove common prefixes (`com.sap.`, `API_`, etc.)
- Extract meaningful name
- Convert to kebab-case
- Ensure uniqueness

**Validation:**
- File created at agent root
- JSON is valid (can be parsed)
- Confirm before overwriting existing file

## References

Domain-specific patterns are in the `references/` folder:
- `references/output-schema.json` - JSON schema for mcp-mock.json validation
- `references/type-mapping.md` - OpenAPI type to mock value rules
- `references/sap-odata-patterns.md` - SAP-specific mock patterns

## Guardrails

### Communication Guidelines

- Report discovered specification files before proceeding
- Show number of servers and tools found for confirmation
- Display output file location when complete
- Ask before overwriting existing mcp-mock.json

### Safety Guardrails

**CRITICAL - This skill MUST NOT:**
- ❌ Modify any agent code (agent.py, tools.py, main.py)
- ❌ Edit translation.json or api-spec.json
- ❌ Create Python files or implementation code
- ❌ Add imports, wrappers, or decorators
- ❌ Modify .mcp.json configuration

**This skill ONLY:**
- ✅ Reads specification files
- ✅ Creates single `mcp-mock.json` configuration file

### Scope Guardrails

**What this skill does:**
- Generates `mcp-mock.json` configuration file only
- The JSON file is consumed by a proxy program in the agent's sandbox
- The proxy intercepts MCP server requests and returns mock responses from this JSON

**What this skill does NOT do:**
- Do not create proxy implementation code
- Do not create tool wrappers or decorators
- Do not modify agent initialization code
- Do not modify how the agent calls MCP tools

**Only output:** Single `mcp-mock.json` configuration file

## Gotchas / Pitfalls

### 1. Deactivated Parameters
**Problem:** Including parameters marked `"deactivate": true`
**Detection:** Check each parameter for deactivate flag
**Solution:** Filter out deactivated parameters from input_schema

### 2. Wrong Response Structure
**Problem:** List operations not wrapped in `{"results": [...]}`
**Detection:** Check if `openApiType.path` has key parameters
**Solution:** Use `results` wrapper for list operations, single object for by-key operations

### 3. SAP Date Format
**Problem:** Using ISO date format instead of SAP `/Date(timestamp)/`
**Detection:** Check for `example: "/Date(...)/` in api-spec.json
**Solution:** Use SAP date format for all date fields

### 4. Decimal as Number
**Problem:** Using JSON number for decimal amounts
**Detection:** Check `format: decimal` in api-spec.json
**Solution:** SAP uses string type for decimals: `"75000.00"`

### 5. Missing Schema Fields
**Problem:** Mock response missing required fields from schema
**Detection:** Compare mock fields to api-spec.json properties
**Solution:** Include all non-nullable fields from schema

### 6. Duplicate Server Slugs
**Problem:** Two servers generate the same slug
**Detection:** Check for slug collisions after generation
**Solution:** Append numeric suffix: `sap-invoice`, `sap-invoice-2`

## Examples

### Example 1: Single MCP Server

**Input:** User asks to "generate mcp mock config" for invoice-monitor agent

**Discovered files:**
- `assets/s4-supplier-invoice-mcp-server/translation.json`
- `assets/s4-supplier-invoice-mcp-server/api-spec.json`

**Output:** `mcp-mock.json`
```json
{
  "servers": {
    "s4-supplier-invoice": {
      "mcp_server_name": "com.sap.s4/API_SUPPLIERINVOICE_PROCESS_SRV",
      "description": "MCP server for reading supplier invoice data...",
      "tools": {
        "list_supplier_invoices": {
          "description": "Retrieve a list of supplier invoices...",
          "input_schema": {
            "type": "object",
            "properties": {
              "$top": {"type": "string", "description": "Maximum number..."},
              "$filter": {"type": "string", "description": "OData filter..."},
              "$select": {"type": "string", "description": "Fields to return..."},
              "$orderby": {"type": "string", "description": "Sort order..."}
            },
            "required": []
          },
          "mock_response": {
            "results": [
              {
                "SupplierInvoice": "5100000001",
                "FiscalYear": "2026",
                "CompanyCode": "1000",
                "InvoiceGrossAmount": "75000.00",
                "DocumentCurrency": "USD",
                "CreationDate": "/Date(1744588800000)/",
                "SupplierInvoiceApprovalStatus": "Pending",
                "InvoicingParty": "VENDOR-1001"
              }
            ]
          }
        },
        "get_supplier_invoice_by_key": {
          "description": "Retrieve a single supplier invoice...",
          "input_schema": {
            "type": "object",
            "properties": {
              "SupplierInvoice": {"type": "string", "description": "Invoice number"},
              "FiscalYear": {"type": "string", "description": "Fiscal year"}
            },
            "required": ["SupplierInvoice", "FiscalYear"]
          },
          "mock_response": {
            "SupplierInvoice": "5100000001",
            "FiscalYear": "2026",
            "CompanyCode": "1000",
            "InvoiceGrossAmount": "75000.00",
            "DocumentCurrency": "USD",
            "CreationDate": "/Date(1744588800000)/",
            "SupplierInvoiceApprovalStatus": "Pending",
            "InvoicingParty": "VENDOR-1001"
          }
        }
      }
    }
  },
  "metadata": {
    "version": "1.0.0",
    "created_for_agent": "invoice-monitor",
    "mock_mode": true,
    "deterministic": true,
    "total_servers": 1,
    "total_tools": 2,
    "generated_from": ["translation.json", "api-spec.json"],
    "generation_date": "2026-04-15"
  }
}
```

**Usage - O(1) Lookup:**
```javascript
const mockData = require('./mcp-mock.json');

// Direct access: server → tool → response
const tool = mockData.servers["s4-supplier-invoice"].tools["list_supplier_invoices"];
const response = tool.mock_response;
```

### Example 2: Multiple MCP Servers

**Input:** Agent uses multiple MCP servers (SAP + n8n + ibd)

**Discovered files:**
- `assets/s4-supplier-invoice-mcp-server/translation.json`
- `assets/n8n-workflow-mcp/translation.json`
- `.mcp.json` referencing `ibd` server

**Output:** Single `mcp-mock.json` with all servers:
```json
{
  "servers": {
    "s4-supplier-invoice": {
      "mcp_server_name": "com.sap.s4/API_SUPPLIERINVOICE_PROCESS_SRV",
      "description": "SAP S/4HANA supplier invoice operations",
      "tools": {
        "list_supplier_invoices": { ... },
        "get_supplier_invoice_by_key": { ... }
      }
    },
    "n8n-workflow": {
      "mcp_server_name": "n8n-workflow-mcp",
      "description": "n8n workflow automation",
      "tools": {
        "trigger_workflow": { ... },
        "get_workflow_status": { ... },
        "list_workflows": { ... }
      }
    },
    "ibd": {
      "mcp_server_name": "ibd-mcp-server",
      "description": "Intent-based development tools",
      "tools": {
        "create_intent": { ... },
        "analyze_code": { ... }
      }
    }
  },
  "metadata": {
    "version": "1.0.0",
    "created_for_agent": "multi-server-agent",
    "mock_mode": true,
    "deterministic": true,
    "total_servers": 3,
    "total_tools": 7,
    "generated_from": ["translation.json", "api-spec.json"],
    "generation_date": "2026-04-15"
  }
}
```

**Usage:**
```javascript
const mockData = require('./mcp-mock.json');

// Access any server's tool directly
const sapTool = mockData.servers["s4-supplier-invoice"].tools["list_supplier_invoices"];
const n8nTool = mockData.servers["n8n-workflow"].tools["trigger_workflow"];
const ibdTool = mockData.servers["ibd"].tools["create_intent"];

// Iterate all servers
for (const [serverSlug, server] of Object.entries(mockData.servers)) {
  console.log(`Server: ${server.mcp_server_name}`);
  for (const [toolName, tool] of Object.entries(server.tools)) {
    console.log(`  Tool: ${toolName}`);
  }
}
```

**Benefits:**
- **Single file**: One file to manage, version, and deploy
- **O(1) lookup**: Both servers and tools are hashmaps
- **Self-contained**: All mock data in one place
- **Easy to query**: Direct path to any tool's mock response

## Related Skills

- `agent-development`: Create agents that use this mock config
- `mcp-integration`: Set up real MCP server connections
- `sap-agent-bootstrap`: Bootstrap SAP agents with mocking ready

## Next Steps

After generating `mcp-mock.json`:
1. Inform user of file location, server count, and tool count
2. Suggest: "Test agent behavior with mock data"
3. Recommend: "Create integration tests using mock config"
4. Optional: "Generate additional mock scenarios (error cases)"
