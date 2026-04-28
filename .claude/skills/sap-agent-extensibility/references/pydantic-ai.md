# PydanticAI Integration

Full integration pattern for a PydanticAI agent with extensibility support.
This is the most battle-tested pattern — the reference onboarding agent uses
this approach.

> **Note**: This reference assumes Phase 2 (Add Telemetry Instrumentation) of the
> `sap-agent-extensibility` skill has been completed, which generates the
> `extension_telemetry/` module with OTEL-instrumented wrappers.

> **Conditionality**: This reference shows the full tools + instructions case.
> When implementing, only include the sections relevant to your configuration:
>
> - **Tools only**: Include MCP toolset building and telemetry, but omit the
>   `instructions=ext_impl.instruction` parameter from `agent.run()`.
> - **Instructions only**: Include `instructions=ext_impl.instruction` in
>   `agent.run()`, but omit `_build_mcp_toolsets()`, the `AsyncExitStack`,
>   `InstrumentedToolset`, and the `toolsets=` parameter entirely. Phase 2
>   (telemetry) should also have been skipped.

## Additional dependencies

PydanticAI has built-in MCP support. Ensure you have:

```
pydantic-ai-slim[mcp]>=0.0.20
```

## Complete example

```python
import contextlib
import logging

from collections.abc import AsyncGenerator

import httpx

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP

from sap_cloud_sdk.extensibility import (
    ExtensionCapabilityImplementation,
    create_client,
    get_extension_override,
)

logger = logging.getLogger(__name__)


class MyAgent:
    def __init__(self):
        self.agent = Agent(
            model="your-model",
            system_prompt="Your base system prompt here.",
        )
        # Create extensibility client once, reuse across requests
        self.extensibility_client = create_client()
        self._register_tools()

    def _register_tools(self):
        """Register the agent's built-in tools."""

        @self.agent.tool
        async def my_tool(ctx, param: str) -> str:
            """A built-in tool."""
            return f"Result: {param}"

    async def _build_mcp_toolsets(
        self,
        ext_impl: ExtensionCapabilityImplementation,
        stack: contextlib.AsyncExitStack,
    ) -> list:
        """Build MCP server toolsets from extension capability implementation.

        Connects to each MCP server, filters its tools to only the
        approved subset, prefixes tool names, and wraps with telemetry.

        Automatically selects the transport based on the URL path:
        - URLs ending in /sse use MCPServerSSE (Server-Sent Events transport)
        - All other URLs use MCPServerStreamableHTTP (Streamable HTTP transport)
        """
        from extension_telemetry import InstrumentedToolset

        toolsets = []

        for server in ext_impl.mcp_servers:
            try:
                # SSE connections are long-lived streams — use a generous read
                # timeout while keeping short connect/write/pool timeouts.
                timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
                http_client = httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=timeout,
                )

                if server.url.rstrip("/").endswith("/sse"):
                    logger.info(f"Using SSE transport for {server.url}")
                    mcp_server = MCPServerSSE(server.url, http_client=http_client)
                else:
                    logger.info(f"Using Streamable HTTP transport for {server.url}")
                    mcp_server = MCPServerStreamableHTTP(server.url, http_client=http_client)

                await stack.enter_async_context(mcp_server)
                tools = await mcp_server.list_tools()
                tool_names = [t.name for t in tools]
                logger.info(f"Connected to MCP server at {server.url}, tools: {tool_names}")

                # Filter to only the tools approved by the extensibility service
                allowed_names = set(server.tool_names)
                filtered_server = mcp_server.filtered(
                    lambda _ctx, tool_def, _allowed=allowed_names: tool_def.name in _allowed
                )

                # Namespace tools using the prefix provided by the backend
                prefixed_server = filtered_server.prefixed(server.tool_prefix)

                # Wrap tool calls with telemetry instrumentation
                instrumented_server = InstrumentedToolset(
                    wrapped=prefixed_server,
                    extension_name=ext_impl.extension_name,
                    tool_prefix=server.tool_prefix,
                    capability="default",
                    source_mapping=ext_impl.source.tools if ext_impl.source else None,
                )

                logger.info(
                    f"Filtering to allowed tools: {sorted(allowed_names)}, "
                    f"prefix: {server.tool_prefix!r}"
                )
                toolsets.append(instrumented_server)

            except BaseException as e:
                logger.warning(f"Failed to connect to MCP server at {server.url}: {e}")

        return toolsets

    async def stream(self, query: str, context=None) -> AsyncGenerator[dict, None]:
        """Stream responses with extensibility support."""
        yield {"is_task_complete": False, "content": "Processing..."}

        try:
            # Extract extension override from the A2A request context
            override = get_extension_override(context) if context else {}

            # Fetch extensions for this extension capability
            ext_impl = self.extensibility_client.get_extension_capability_implementation(
                capability_id="default",
                override=override,
            )

            # Connect to MCP servers and run agent
            async with contextlib.AsyncExitStack() as stack:
                toolsets = await self._build_mcp_toolsets(ext_impl, stack)
                result = await self.agent.run(
                    query,
                    toolsets=toolsets,
                    instructions=ext_impl.instruction,
                )

            yield {"is_task_complete": True, "content": result.output}

        except Exception as e:
            logger.exception("Error during agent execution")
            yield {"is_task_complete": True, "content": f"Error: {e!s}"}
```

## Key points

- **`toolsets=`** parameter on `agent.run()` adds MCP tools alongside built-in tools
- **`instructions=`** parameter adds extra instructions alongside the `system_prompt`
- **`AsyncExitStack`** manages MCP connection lifecycles — connections close
  automatically when the stack exits
- Tools are **filtered** to only the subset approved by the extensibility service
- Tools are **prefixed** using the backend-provided `tool_prefix` to prevent
  naming conflicts (the prefix includes a trailing `_` separator)
- `create_client()` is called once at application startup (in `__init__`);
  `client.get_extension_capability_implementation()` is **synchronous** — no `await`
- Use `get_extension_override(context)` to extract caller-supplied override
  metadata from the A2A `RequestContext` and pass it via the `override` parameter

## How instructions are added

PydanticAI's `instructions` parameter supplements the `system_prompt` set at
agent construction time. No string concatenation needed:

```python
result = await self.agent.run(
    query,
    instructions=ext_impl.instruction,  # Added alongside system_prompt
)
```

## How MCP tools are added

MCP servers are passed as `toolsets` — PydanticAI treats them as additional tool
sources alongside tools registered with `@agent.tool`:

```python
result = await self.agent.run(
    query,
    toolsets=toolsets,  # MCP servers from _build_mcp_toolsets()
)
```

## How tools are filtered

PydanticAI's `.filtered()` method accepts a predicate that receives the run
context and tool definition. Only tools where the predicate returns `True` are
exposed to the agent:

```python
allowed_names = set(server.tool_names)
filtered_server = mcp_server.filtered(
    lambda _ctx, tool_def, _allowed=allowed_names: tool_def.name in _allowed
)
```

The `_allowed=allowed_names` default-argument trick captures the correct set
for each loop iteration.

## How tools are namespaced

The extensibility service provides a `tool_prefix` on each `McpServer`, derived
from the tool's ORD ID. The prefix already includes a trailing `_` separator.

PydanticAI's `.prefixed()` method adds this prefix to all tool names from
a toolset. Chained after `.filtered()`, it ensures unique names across servers:

```python
prefixed_server = filtered_server.prefixed(server.tool_prefix)
# Tool "create_ticket" becomes "sap_mcp_servicenow_v1_create_ticket"
```

## How telemetry is added

PydanticAI handles MCP tool calls internally through its toolsets mechanism.
To add OTEL telemetry for extension tracking, use the pre-built
`InstrumentedToolset` from the `extension_telemetry` module (generated by
Phase 2 of the `sap-agent-extensibility` skill). This is a `WrapperToolset`
subclass that intercepts `call_tool()` to create a dedicated tracer span with
extension attributes.

> **Important**: The SDK's `extension_context()` sets OTel _baggage_ only
> (propagated to downstream services via HTTP headers). It does **not** set
> span attributes on the agent's own spans. `InstrumentedToolset` handles
> both: baggage via `extension_context()` and explicit span attributes via
> `tracer.start_as_current_span()`.

```python
from extension_telemetry import InstrumentedToolset

# After filtering and prefixing the MCP server toolset:
instrumented_server = InstrumentedToolset(
    wrapped=prefixed_server,
    extension_name=ext_impl.extension_name,
    tool_prefix=server.tool_prefix,
    capability="default",
    source_mapping=ext_impl.source.tools if ext_impl.source else None,
)
```

The complete example above already includes `InstrumentedToolset` in
`_build_mcp_toolsets`. The resulting span hierarchy in traces:

```
agent run
  └── extension_tool concur_receipts_get_receipt_data
        ├── sap.extension.isExtension = true
        ├── sap.extension.extensionId = "Concur Receipts Extension"
        ├── sap.extension.extensionType = "tool"
        ├── sap.extension.capabilityId = "default"
        └── get_receipt_data (MCP tool call)
```

This approach:

- Uses a `WrapperToolset` subclass to intercept `call_tool()` — **not**
  `.wrapped()` (which does not exist as a chainable method)
- Sets OTel baggage via `extension_context()` for downstream propagation
- Creates a dedicated named span with explicit `sap.extension.*` attributes
  so extension metadata is visible in the agent's own traces (Jaeger, Dynatrace)
- Preserves the original tool call behavior
