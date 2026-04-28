# Extension Capability Configuration Examples

All types are imported from the SAP Cloud SDK for Python:

```python
from sap_cloud_sdk.extensibility import (
    ExtensionCapability,
    Tools,
    ToolAdditions,
    HookCapability
)
```

## Full Extensibility (tools + instructions + hooks)

```python
ExtensionCapability(
    display_name="Default",
    description="Allows adding tools and additional instruction for the agent.",
    instruction_supported=True,
    tools=Tools(additions=ToolAdditions(enabled=True)),
    supported_hooks=[PRE_HOOK, POST_HOOK]
)
```

Produces this A2A agent card entry:

```json
{
  "uri": "urn:sap:extension-capability:v1:default",
  "description": "Allows adding tools and additional instruction for the agent.",
  "required": false,
  "params": {
    "capabilityId": "default",
    "instructionSupported": true,
    "displayName": "Default",
    "tools": { "additions": { "enabled": true } },
    "supported_hooks": [
      {
        "type": "BEFORE",
        "id": "agent_pre_hook",
        "displayName": "Pre Hook",
        "description": "A hook that should be run before agent execution or tool calls"
      },
      {
        "type": "AFTER",
        "id": "agent_post_hook",
        "displayName": "Post Hook",
        "description": "A hook that should be run after tool calls"
      }
    ]
  }
}
```

## Tools Only (no instructions, no hooks)

```python
ExtensionCapability(
    display_name="Default",
    description="Allows adding custom tools to extend the agent's capabilities.",
    instruction_supported=False,
    tools=Tools(additions=ToolAdditions(enabled=True)),
    supported_hooks=[]
)
```

## Instructions Only (no tools, no hooks)

```python
ExtensionCapability(
    display_name="Default",
    description="Allows providing additional instructions and context to the agent.",
    instruction_supported=True,
    tools=Tools(additions=ToolAdditions(enabled=False)),
    supported_hooks=[]
)
```

## Hooks Only (no tools, no instructions)

```python
ExtensionCapability(
    display_name="Default",
    description="Allows providing additional instructions and context to the agent.",
    instruction_supported=False,
    tools=Tools(additions=ToolAdditions(enabled=False)),
    supported_hooks=[
      {
        "type": "BEFORE",
        "id": "agent_pre_hook",
        "displayName": "Pre Hook",
        "description": "A hook that should be run before agent execution or tool calls"
      },
      {
        "type": "AFTER",
        "id": "agent_post_hook",
        "displayName": "Post Hook",
        "description": "A hook that should be run after tool calls"
      }
    ]
)
```

## Coexistence with Other Extensions

The `capabilities.extensions` list on the A2A agent card can contain entries
from multiple sources. Extension Capability entries use the URI prefix
`urn:sap:extension-capability:v1:` and can coexist with other extension types:

```json
"extensions": [
  {
    "uri": "https://example.com/ext/traceability/v1",
    "description": "Enables traceability headers for audit trails.",
    "required": false,
    "params": { "traceIdHeader": "X-Trace-ID" }
  },
  {
    "uri": "urn:sap:extension-capability:v1:default",
    "description": "Allows adding tools and additional instruction for the agent.",
    "required": false,
    "params": {
      "capabilityId": "default",
      "instructionSupported": true,
      "displayName": "Default",
      "tools": { "additions": { "enabled": true } }
    }
  }
]
```

When the extensibility skill adds or updates Extension Capability entries, it
must preserve entries with other URI prefixes. Use the `merge_extensions()`
helper from `extension_capabilities.py` to handle this automatically:

```python
from extension_capabilities import EXTENSION_CAPABILITIES, merge_extensions

extensions=merge_extensions(
    existing_extensions,
    build_extension_capabilities(EXTENSION_CAPABILITIES),
)
```
