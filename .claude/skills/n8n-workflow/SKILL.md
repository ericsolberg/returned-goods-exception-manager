---
name: n8n-workflow
description: Writes or edits n8n workflow JSON files (.n8n.json). Only invoke this skill during spec or code generation (called from prd-to-spec or spec-to-code), or when the user explicitly asks to edit or fix an existing workflow file.
---

# n8n Workflow Skill

## Steps

### **MANDATORY: Verify prerequisites**
Before proceeding, confirm that `tasks.md` exists with implementation tasks. If it is missing, STOP and run the `prd-to-spec` and `spec-to-code` skills first. Also ensure that the solution structure was set up (`solution.yaml`, `assets` folder) by the `setup-solution` skill, otherwise run that skill first.

### **Set up project folder**
If a `assets/n8n/workflows/` folder already exists, use it. Otherwise create it by executing:
   ```bash
   mkdir -p assets/n8n/workflows
   ```

### **MANDATORY: Create asset.yaml if not already there**
If not already there, create the `asset.yaml` file in `assets/n8n/` using the `setup-solution` skill. This asset.yaml must look like the one provided in `assets/n8n/asset.yaml`.

### **MANDATORY: Look up nodes from the catalog (MUST do this for EVERY node)**
Before writing ANY node in the workflow JSON, you MUST look up its exact `type` and `typeVersion` from the catalog. Call the `search-nodes-catalog` MCP tool for all nodes you need:
   - Pass all needed node keywords in a single call (e.g. `webhook`, `http request`, `if`, `schedule`, `slack`, `task center`). The tool searches by displayName, name, and description.
   - Use the returned `name` as `type` and `version` as `typeVersion` in the workflow JSON.
   - NEVER guess node type names or typeVersion — only use values returned by the tool.
   - Custom/SAP nodes (e.g. `CUSTOM.approvalTask`) include full `properties` in the output to help you configure them correctly.
   - If the workflow involves **tasks** (approvals, task assignments, task status updates), search for `"task center"` to find the **SAP Task Center** node.

### **MANDATORY: Create the file to the filesystem**
Write workflow files to `assets/n8n/workflows/`. The file **MUST** use the `.n8n.json` extension (e.g. `my-workflow.n8n.json`). NEVER use MCP to create or update workflows.

### **Validate the workflow**
After writing the workflow file, use the `validate-n8n-workflow` MCP tool to validate the workflow content. If validation returns errors, use the message to fix the workflow. Some errors are expected and cannot be fixed by the agent — for example, missing credentials. In those cases, inform the user and leave the credential configuration to be done manually in the n8n UI.

### **Delete workflows**
Use the n8n MCP tool only for deletion from the remote n8n instance.

## CRITICAL: Node parameter rules

- **ONLY use parameters exactly as shown in the example below**. NEVER invent or add extra parameters.
- **SAP Task Center (`CUSTOM.sapTaskCenter`)**: Use ONLY `{ "taskDefinition": {} }` as parameters. NEVER add `operation`, `subject`, `description`, `priority`, `recipients`, or any other property in the JSON — these cause "Could not find property option" on import. Configure them in the n8n UI after import. DO NOT SET CREDENTIALS IN THE JSON

## Example: Travel Expense Approval with SAP Task Center

```json
{
  "name": "Travel Expense Approval",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "travel-expense",
        "responseMode": "responseNode",
        "options": {}
      },
      "id": "ae96169f-0022-42b6-9b76-82dab157289e",
      "name": "Expense Submitted",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2.1,
      "position": [-688, -80],
      "webhookId": "e57d9e77-30a3-4b7f-bad5-1e3288f68617"
    },
    {
      "parameters": {
        "conditions": {
          "options": {
            "caseSensitive": true,
            "leftValue": "",
            "typeValidation": "strict"
          },
          "conditions": [
            {
              "id": "condition1",
              "leftValue": "={{ $json.body.amount }}",
              "rightValue": 50,
              "operator": {
                "type": "number",
                "operation": "lt"
              }
            }
          ],
          "combinator": "and"
        },
        "options": {}
      },
      "id": "70a54920-0cca-42f2-b83d-5e1c34798c8f",
      "name": "Amount Below 50 EUR?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2.3,
      "position": [-448, -80]
    },
    {
      "parameters": {
        "assignments": {
          "assignments": [
            { "id": "field1", "name": "status", "value": "approved", "type": "string" },
            { "id": "field2", "name": "message", "value": "=Expense of {{ $('Expense Submitted').item.json.body.amount }} EUR auto-approved (below 50 EUR threshold).", "type": "string" },
            { "id": "field3", "name": "expenseId", "value": "={{ $('Expense Submitted').item.json.body.expenseId }}", "type": "string" }
          ]
        },
        "options": {}
      },
      "id": "f523ae00-f38d-45a8-9ab5-d3caac947fcf",
      "name": "Set Auto-Approved",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [-208, -192]
    },
    {
      "parameters": {
        "taskDefinition": {}
      },
      "type": "CUSTOM.sapTaskCenter",
      "typeVersion": 1,
      "position": [-208, 64],
      "id": "608234f3-90d5-4312-9caa-16179ab2e012",
      "name": "SAP Task Center",
      "webhookId": "515abf90-3602-472a-96e6-4163feeba231"
    },
    {
      "parameters": {
        "assignments": {
          "assignments": [
            { "id": "field1", "name": "status", "value": "approved", "type": "string" },
            { "id": "field2", "name": "message", "value": "=Expense of {{ $('Expense Submitted').item.json.body.amount }} EUR approved by manager.", "type": "string" },
            { "id": "field3", "name": "expenseId", "value": "={{ $('Expense Submitted').item.json.body.expenseId }}", "type": "string" }
          ]
        },
        "options": {}
      },
      "id": "d0e9872c-b5c0-4c8a-9781-0e818d6c6908",
      "name": "Set Manager Approved",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [32, -32]
    },
    {
      "parameters": {
        "assignments": {
          "assignments": [
            { "id": "field1", "name": "status", "value": "rejected", "type": "string" },
            { "id": "field2", "name": "message", "value": "=Expense of {{ $('Expense Submitted').item.json.body.amount }} EUR rejected by manager.", "type": "string" },
            { "id": "field3", "name": "expenseId", "value": "={{ $('Expense Submitted').item.json.body.expenseId }}", "type": "string" }
          ]
        },
        "options": {}
      },
      "id": "683cb123-ea14-4bb8-8c9a-abdb9183887f",
      "name": "Set Manager Rejected",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [32, 144]
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify({ expenseId: $json.expenseId, status: $json.status, message: $json.message }) }}",
        "options": {
          "responseCode": 200
        }
      },
      "id": "8e3c6e9d-9139-4c6e-b801-4fa72bbf755c",
      "name": "Respond to Requester",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.5,
      "position": [272, -80]
    }
  ],
  "connections": {
    "Expense Submitted": {
      "main": [[{ "node": "Amount Below 50 EUR?", "type": "main", "index": 0 }]]
    },
    "Amount Below 50 EUR?": {
      "main": [
        [{ "node": "Set Auto-Approved", "type": "main", "index": 0 }],
        [{ "node": "SAP Task Center", "type": "main", "index": 0 }]
      ]
    },
    "SAP Task Center": {
      "main": [
        [{ "node": "Set Manager Approved", "type": "main", "index": 0 }],
        [{ "node": "Set Manager Rejected", "type": "main", "index": 0 }]
      ]
    },
    "Set Auto-Approved": {
      "main": [[{ "node": "Respond to Requester", "type": "main", "index": 0 }]]
    },
    "Set Manager Approved": {
      "main": [[{ "node": "Respond to Requester", "type": "main", "index": 0 }]]
    },
    "Set Manager Rejected": {
      "main": [[{ "node": "Respond to Requester", "type": "main", "index": 0 }]]
    }
  },
  "pinData": {},
  "meta": {
    "templateCredsSetupCompleted": true
  }
}
```

