# Extension Model — Shared Data Dictionary

Single source of truth for the extensibility data model used by both the
**define extension capabilities** and **implement extensions** skills.

All types are provided by the SAP Cloud SDK for Python
(`sap_cloud_sdk.extensibility`).

## Composition Hierarchy

```
Agent
  └── ExtensionCapability (exactly 1 per agent)
        ├── Instructions  (0..1 — optional custom prompt text)
        └── Tools         (0..N — MCP tool servers)
        └── Hooks         (0..N — Pre/Post Hooks)
```

An **extension capability** is a named location in the agent's execution flow where
external instructions, MCP tools and Hooks can be injected at runtime. Each agent
exposes exactly one extension capability.

## Extension Capability Definition (Agent-Side)

Defined in the agent's code using `ExtensionCapability` (dataclass):

| Field                  | Type    | Description                                |
| ---------------------- | ------- | ------------------------------------------ |
| `display_name`         | `str`   | Human-friendly name                        |
| `description`          | `str`   | What can be extended                       |
| `id`                   | `str`   | Internal identifier (default: `"default"`) |
| `tools`                | `Tools` | Tool-related configuration                 |
| `instruction_supported`| `bool`  | Whether custom instructions are allowed    |
| `supported_hooks`      | `list[HookCapability]` | Hooks related configuration          |

`Tools` (dataclass):

| Field       | Type            | Description                      |
| ----------- | --------------- | -------------------------------- |
| `additions` | `ToolAdditions` | Configuration for tool additions |

`ToolAdditions` (dataclass):

| Field     | Type   | Description                    |
| --------- | ------ | ------------------------------ |
| `enabled` | `bool` | Whether tool additions allowed |

`HookCapability` (dataclass):

| Field          | Type  | Description                    |
| -------------- | ----- | ------------------------------ |
| `type`         | `str` | Hook type: `"BEFORE"` or `"AFTER"` |
| `id`           | `str` | Internal identifier of the hook |
| `display_name` | `str` | Human-friendly name            |
| `description`  | `str` | What the hook does             |

`Hook` (dataclass):

| Field               | Type   | Description                                              |
| ------------------- | ------ | -------------------------------------------------------- |
| `hook_id`           | `str`  | Unique hook identifier                                   |
| `id`                | `str`  | Internal identifier                                      |
| `ord_id`            | `str`  | ORD identifier of the hook                               |
| `name`              | `str`  | Technical name of the hook                               |
| `type`              | `str`  | Hook timing: `"BEFORE"` or `"AFTER"`                     |
| `deployment_type`   | `str`  | How the hook is deployed (e.g. `"URL"`)                  |
| `url`               | `str`  | Endpoint URL to invoke the hook                          |
| `timeout`           | `int`  | Maximum execution time in seconds                        |
| `execution_mode`    | `str`  | Execution mode (e.g. `"sync"` or `"async"`)              |
| `on_failure`        | `str`  | Failure behaviour (e.g. `"ignore"` or `"abort"`)         |
| `order`             | `int`  | Execution order among hooks of the same type             |
| `can_short_circuit` | `bool` | Whether this hook can block/stop agent execution         |

## A2A Card Representation

The definition is serialized as an `AgentExtension` in the agent card
via `build_extension_capabilities()`:

```json
{
  "uri": "urn:sap:extension-capability:v1:default",
  "description": "...",
  "required": false,
  "params": {
    "instructionSupported": true,
    "displayName": "Default",
    "tools": { "additions": { "enabled": true } },
    "supportedHooks": [
      {
        "type": "BEFORE",
        "id": "hook1",
        "displayName": "Pre Hook",
        "description": "A hook that should be run before agent execution or tool calls"
      },
      {
        "type": "AFTER",
        "id": "hook2",
        "displayName": "Post Hook",
        "description": "A hook that should be run after tool calls"
      }
    ]
  }
}
```

This lives in `capabilities.extensions` on the A2A agent card, making the
extension capability discoverable by the platform.

## Runtime Extension Data (Extensibility Service Response)

When the agent runs, it creates an `ExtensibilityClient` via `create_client()`
and calls `client.get_extension_capability_implementation()`, which returns an
`ExtensionCapabilityImplementation`:

| Field            | Type             | Description                                 |
| ---------------- | ---------------- | ------------------------------------------- |
| `name`           | `str`            | Extension capability name                   |
| `extension_name` | `str \| None`    | Name of the active extension                |
| `instruction`    | `str \| None`    | Custom instructions to append to prompt     |
| `mcp_servers`    | `list[McpServer]`| MCP server metadata with authorized tools   |
| `hooks`          | `list[Hooks]`    | BEFORE/AFTER hooks                          |
| `source`         | `ExtensionSourceMapping \| None` | Per-tool/hook extension attribution mapping |

### McpServer

Each `McpServer` represents a connected MCP tool server with its authorized
tools:

| Field         | Type        | Description                                               |
| ------------- | ----------- | --------------------------------------------------------- |
| `ord_id`      | `str`       | ORD identifier (e.g. `sap.mcp:apiResource:serviceNow:v1`) |
| `url`         | `str`       | MCP server endpoint URL                                   |
| `tool_prefix` | `str`       | Namespace prefix with trailing `_` separator              |
| `tool_names`  | `list[str]` | Approved tool names for this server                       |

### ExtensionSourceMapping

When multiple extensions are merged (multi-extension scenario), the `source`
field maps each tool and hook back to the extension that contributed it.
This enables per-tool/hook telemetry attribution — all seven
`sap.extension.*` span attributes are resolved from the source info for
each specific tool or hook.

| Field   | Type                           | Description                                     |
| ------- | ------------------------------ | ----------------------------------------------- |
| `tools` | `dict[str, ExtensionSourceInfo]` | Prefixed tool name → extension source info    |
| `hooks` | `dict[str, ExtensionSourceInfo]` | Hook name → extension source info             |

When only a single extension is active, `source` may be `None` — in that
case `extension_name` is sufficient for attribution.

### ExtensionSourceInfo

Each value in `source.tools` and `source.hooks` is an `ExtensionSourceInfo`
object (or a dict with the same keys in the raw API response):

| Field              | Type   | Description                                           |
| ------------------ | ------ | ----------------------------------------------------- |
| `extension_name`   | `str`  | Human-readable extension name (e.g. `"ap-invoice-extension"`) |
| `extension_id`     | `str`  | UUID of the extension                                 |
| `extension_version`| `str`  | Version of the extension (e.g. `"1"`)                 |

Raw API response format:

```json
{
  "source": {
    "tools": {
      "sap_mcp_taxvalidator_validate_validate_tax": {
        "extensionName": "asset-agent-tools2",
        "extensionVersion": "1",
        "extensionId": "a1b2c3d4-e5f6-..."
      }
    },
    "hooks": {
      "sap.hook:validateInput:v1": {
        "extensionName": "ap-invoice-extension",
        "extensionVersion": "1",
        "extensionId": "b2c3d4e5-f6a7-..."
      }
    }
  }
}
```

**Convenience methods** on `ExtensionCapabilityImplementation`:

- `get_extension_for_tool(tool_name)` → `str | None` — looks up the tool's
  extension name in `source.tools`, falling back to `extension_name`
- `get_extension_for_hook(hook_ord_id)` → `str | None` — looks up the hook's
  extension name in `source.hooks`, falling back to `extension_name`
- `get_source_info_for_tool(tool_name)` → `ExtensionSourceInfo | None` —
  returns the full source info object for a tool
- `get_source_info_for_hook(hook_ord_id)` → `ExtensionSourceInfo | None` —
  returns the full source info object for a hook

## Tool Namespacing

When multiple MCP servers are connected, tool names may collide. The
Extensibility Service provides a `tool_prefix` on each tool, derived from the
tool's ORD ID on the backend. The prefix includes a trailing `_` separator.

Namespaced name = `tool_prefix` + `name`

Example: ORD ID `sap.mcp:apiResource:serviceNow:v1` produces prefix
`sap_mcp_servicenow_v1_`. A tool named `create_ticket` becomes
`sap_mcp_servicenow_v1_create_ticket`.

## Tool Filtering

An MCP server may expose many tools, but the Extensibility Service only
authorizes a subset for each extension capability. Agents **must filter** tools
from each server to only those listed in the response.

## Instruction Supplementation

Extended instructions **supplement** the agent's existing system prompt —
they never replace it. The agent framework determines how instructions are
merged (e.g. PydanticAI's `instructions=` parameter, LangChain's system
message concatenation).

## Key Constraints

- Agents can have exactly **1 extension capability**
- `instruction_supported` defaults to `True`
- `tools.additions.enabled` defaults to `True`
- Tool names must be unique after prefixing within the agent's tool set
- Each MCP server URL is connected to at most once (deduplicate by URL)
- `capabilities.extensions` is a **shared list** on the A2A agent card — other
  processes may add `AgentExtension` entries with different URIs (e.g.,
  data-only extensions, profile extensions). Extension Capability entries are
  identifiable by the URI prefix `urn:sap:extension-capability:v1:`. When
  adding or updating Extension Capability entries, preserve any existing
  entries with different URI prefixes.

## Extension Override (Request-Time Routing)

When an A2A caller wants to target a specific extension name or version, it
includes an `extension_override` object in the request's `metadata` dict.
The agent extracts this using `get_extension_override()` and passes it to
`get_extension_capability_implementation()` so the extensibility backend
returns the correct extension.

### get_extension_override(context)

Extracts extension override parameters from an A2A `RequestContext`:

```python
from sap_cloud_sdk.extensibility import get_extension_override

override = get_extension_override(context)
ext_impl = client.get_extension_capability_implementation(
    capability_id="default",
    override=override,
)
```

When no `extension_override` metadata is present in the request, all fields
default to `None` / `False` and the extensibility backend uses its default
routing logic.
