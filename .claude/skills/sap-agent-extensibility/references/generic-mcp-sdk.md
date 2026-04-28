# Generic Python Integration (MCP SDK)

For frameworks without built-in MCP support, use the `mcp` Python SDK directly
to connect to MCP servers and convert tools to your framework's format.
Includes manual tool filtering and prefixing using the backend-provided
`tool_prefix`.

> **Note**: This reference assumes Phase 2 (Add Telemetry Instrumentation) of the
> `sap-agent-extensibility` skill has been completed, which generates the
> `extension_telemetry/` module with OTEL-instrumented wrappers.

> **Conditionality**: This reference shows the full tools + instructions case.
> When implementing, only include the sections relevant to your configuration:
>
> - **Tools only**: Include MCP connection, tool filtering, prefixing, and
>   telemetry, but omit the instruction handling sections.
> - **Instructions only**: Include the instruction handling section only. Omit
>   all MCP connection logic, `mcp` SDK imports, tool filtering/prefixing,
>   session management, and telemetry wrapping. Phase 2 (telemetry) should also
>   have been skipped.

## Complete example

```python
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client

from sap_cloud_sdk.extensibility import (
    ExtensionCapabilityImplementation,
    create_client,
    get_extension_override,
)

logger = logging.getLogger(__name__)


async def get_mcp_tools(ext_impl: ExtensionCapabilityImplementation):
    """Connect to MCP servers and retrieve filtered, prefixed tools.

    Returns a list of (session, transport, filtered_tools) tuples. The caller
    is responsible for keeping the sessions alive during agent execution.

    Args:
        ext_impl: ExtensionCapabilityImplementation with tool metadata.
    """
    results = []

    for server in ext_impl.mcp_servers:
        try:
            if server.url.rstrip("/").endswith("/sse"):
                transport = sse_client(server.url)
            else:
                transport = streamablehttp_client(server.url)

            read, write, _ = await transport.__aenter__()
            session = ClientSession(read, write)
            await session.__aenter__()
            await session.initialize()

            tools_response = await session.list_tools()
            all_tool_names = [t.name for t in tools_response.tools]
            logger.info(f"Connected to {server.url}, tools: {all_tool_names}")

            # Filter to only approved tools
            allowed_names = set(server.tool_names)
            filtered_tools = [t for t in tools_response.tools if t.name in allowed_names]

            # Prefix tool names using the backend-provided prefix
            for t in filtered_tools:
                t.name = f"{server.tool_prefix}{t.name}"

            logger.info(
                f"Filtered to {len(filtered_tools)}/{len(all_tool_names)} tools, "
                f"prefix: {server.tool_prefix!r}"
            )
            results.append((session, transport, filtered_tools))

        except Exception as e:
            logger.warning(f"Failed to connect to MCP server at {server.url}: {e}")

    return results


async def call_mcp_tool(
    session: ClientSession, tool_info, arguments: dict, extension_name: str,
    source_mapping: dict[str, str] | None = None,
    tool_prefix: str = "",
):
    """Call a tool on an MCP server with telemetry instrumentation.

    Uses the extension_telemetry wrapper to automatically add OTEL span
    attributes for extension tracking.

    Args:
        session: The MCP client session.
        tool_info: Object with a ``mcp_tool_name`` attribute.
        arguments: Dictionary of arguments to pass to the tool.
        extension_name: Human-readable name of the extension
            (from ``ext_impl.extension_name``).
        source_mapping: Optional mapping of prefixed tool names to extension
            names (from ``ext_impl.source.tools``).
        tool_prefix: The Axle-provided tool prefix (e.g.,
            ``"sap_mcp_servicenow_v1_"``). Used to reconstruct the key
            for ``source_mapping`` lookup.
    """
    from extension_telemetry import call_extension_tool

    result = await call_extension_tool(
        session, tool_info, arguments, extension_name,
        source_mapping=source_mapping,
        tool_prefix=tool_prefix,
    )
    return result
```

## Key points

- You manage the MCP session lifecycle yourself (enter/exit context managers)
- Use **`session.list_tools()`** to discover available tools on each server
- Use **`session.call_tool(name, arguments=...)`** to invoke a tool
- Convert the MCP tool schemas to your framework's tool format as needed
- Remember to close sessions and transports when done
- Tools are **filtered** manually to only the subset approved by the extensibility
  service
- Tools are **prefixed** using the backend-provided `tool_prefix` (which includes
  a trailing `_` separator) to prevent naming conflicts across servers
- `create_client()` is called once at application startup;
  `client.get_extension_capability_implementation()` is **synchronous** — no `await`
- Use `get_extension_override(context)` to extract caller-supplied override
  metadata from the A2A `RequestContext` and pass it via the `override` parameter

## How instructions are added

For direct OpenAI SDK usage, append as an additional system message:

```python
messages = [{"role": "system", "content": base_system_prompt}]
if ext_impl.instruction:
    messages.append({"role": "system", "content": ext_impl.instruction})
messages.append({"role": "user", "content": query})
```

For other frameworks, concatenate with the existing system prompt string:

```python
system_prompt = base_system_prompt
if ext_impl.instruction:
    system_prompt += f"\n\n{ext_impl.instruction}"
```

## How MCP tools are added

The generic pattern requires you to bridge between MCP tool schemas and your
framework's tool format. Here's the general approach:

```python
from extension_telemetry import call_extension_tool

# 1. Connect, filter, and prefix tools
connections = await get_mcp_tools(ext_impl)

# 2. For each connection, convert filtered tools to your framework's format
for session, transport, filtered_tools in connections:
    for tool in filtered_tools:
        # tool.name — the prefixed tool name (e.g. "sap_mcp_servicenow_v1_create_ticket")
        # tool.description — human-readable description
        # tool.inputSchema — JSON Schema for the tool's parameters
        # Convert these to your framework's tool definition format
        pass

# 3. When the agent wants to call a tool, find the matching server
#    and use the telemetry wrapper
for server in ext_impl.mcp_servers:
    for tool_name in server.tool_names:
        if prefixed_name == f"{server.tool_prefix}{tool_name}":
            # call_extension_tool automatically wraps with OTEL telemetry
            result = await call_extension_tool(
                session, server, tool_name,
                extension_name=ext_impl.extension_name,
                source_mapping=ext_impl.source.tools if ext_impl.source else None,
            )
            break

# 4. Clean up when done
for session, transport, _ in connections:
    await session.__aexit__(None, None, None)
    await transport.__aexit__(None, None, None)
```

## How tools are filtered

The MCP SDK does not have a built-in tool filter. Filter the result of
`session.list_tools()` manually using `server.tool_names`:

```python
allowed_names = set(server.tool_names)
filtered_tools = [t for t in tools_response.tools if t.name in allowed_names]
```

## How tools are namespaced

The extensibility service provides a `tool_prefix` on each `McpServer`, derived
from the tool's ORD ID. The prefix already includes a trailing `_` separator.

Rename tools manually by mutating their `name` attribute after filtering:

```python
for t in filtered_tools:
    t.name = f"{server.tool_prefix}{t.name}"
# Tool "create_ticket" becomes "sap_mcp_servicenow_v1_create_ticket"
```

When calling a tool via `session.call_tool()`, remember to strip the prefix
back to the original name that the MCP server expects.

## Using with `contextlib.AsyncExitStack`

For cleaner lifecycle management, use an `AsyncExitStack`:

```python
import contextlib

async with contextlib.AsyncExitStack() as stack:
    sessions = []

    for server in ext_impl.mcp_servers:
        if server.url.rstrip("/").endswith("/sse"):
            transport = sse_client(server.url)
        else:
            transport = streamablehttp_client(server.url)

        read, write, _ = await stack.enter_async_context(transport)
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        # Filter and prefix tools
        all_tools = await session.list_tools()
        allowed_names = set(server.tool_names)
        filtered = [t for t in all_tools if t.name in allowed_names]
        for t in filtered:
            t.name = f"{server.tool_prefix}{t.name}"

        sessions.append((session, filtered))

    # Use sessions during agent execution...
    # All sessions and transports close automatically when the stack exits
```

## Graceful degradation

All integration patterns benefit from the built-in graceful degradation of
`client.get_extension_capability_implementation()`. The method never raises for
runtime errors — it returns an empty result and logs the error. Note that
`create_client()` itself _does_ raise `ClientCreationError` if the destination
service is unavailable. Here's an explicit pattern for additional control:

```python
from sap_cloud_sdk.extensibility import create_client, get_extension_override

# Application-scoped client (created once at startup)
extensibility_client = create_client()

# Per-request: extract override and fetch extension data
override = get_extension_override(context)
ext_impl = extensibility_client.get_extension_capability_implementation(
    capability_id="default",
    override=override,
)

# These checks are optional — the SDK already returns safe defaults
has_instruction = ext_impl.instruction is not None
has_servers = len(ext_impl.mcp_servers) > 0

if has_instruction:
    logger.info(f"Loaded {len(ext_impl.instruction)} chars of custom instructions")
if has_servers:
    logger.info(f"Loaded {len(ext_impl.mcp_servers)} MCP server(s)")
if not has_instruction and not has_servers:
    logger.info("No extensions configured — using default agent behavior")
```

The agent always works, whether extensions are configured or not. This is by
design — extensibility is additive, never breaking.
