# OpenAI Agents SDK Integration

Integration pattern using the OpenAI Agents SDK (`openai-agents`). Uses the
SDK's built-in `create_static_tool_filter` for filtering and the server `name`
parameter for namespacing.

> **Note**: This reference assumes Phase 2 (Add Telemetry Instrumentation) of the
> `sap-agent-extensibility` skill has been completed, which generates the
> `extension_telemetry/` module with OTEL-instrumented wrappers.

> **Conditionality**: This reference shows the full tools + instructions case.
> When implementing, only include the sections relevant to your configuration:
>
> - **Tools only**: Include MCP server construction, tool filtering, and
>   namespacing, but omit the instruction concatenation.
> - **Instructions only**: Include the instruction concatenation, but omit
>   `MCPServerStreamableHTTP`, `create_static_tool_filter`, the `mcp_servers=`
>   parameter, and telemetry wrapping entirely. Phase 2 (telemetry) should also
>   have been skipped.

## Complete example

```python
import logging

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHTTP, create_static_tool_filter

from sap_cloud_sdk.extensibility import create_client, get_extension_override

logger = logging.getLogger(__name__)

BASE_INSTRUCTIONS = "You are a helpful assistant."

# Create extensibility client once at module level
extensibility_client = create_client()


async def run_agent(query: str, context=None) -> str:
    """Run the OpenAI Agents SDK agent with extensibility support."""

    # Step 1: Extract override and fetch extensions
    override = get_extension_override(context) if context else {}
    ext_impl = extensibility_client.get_extension_capability_implementation(
        capability_id="default",
        override=override,
    )

    # Step 2: Build instructions with extensions
    instructions = BASE_INSTRUCTIONS
    if ext_impl.instruction:
        instructions += f"\n\n{ext_impl.instruction}"

    # Step 3: Build MCP server list with filtering and namespacing
    mcp_servers = []
    for server in ext_impl.mcp_servers:
        mcp_servers.append(
            MCPServerStreamableHTTP(
                url=server.url,
                # Use backend-provided prefix (strip trailing '_' for server name)
                name=server.tool_prefix.rstrip("_"),
                # Filter to only approved tools
                tool_filter=create_static_tool_filter(allowed_tool_names=server.tool_names),
            )
        )

    # Step 4: Create and run agent
    agent = Agent(
        name="my-agent",
        instructions=instructions,
        mcp_servers=mcp_servers,
    )
    result = await Runner.run(agent, input=query)
    return result.final_output
```

## Key points

- MCP servers are passed directly to the `Agent` constructor via **`mcp_servers=`**
- The SDK manages MCP connection lifecycle internally via `Runner.run()`
- Extended instructions are concatenated with the base instructions string
- Tools are **filtered** using the SDK's built-in `create_static_tool_filter`
  with `server.tool_names` from each `McpServer`
- Servers are **namespaced** via the `name` parameter using the backend-provided
  `tool_prefix` (with trailing `_` stripped for use as a server name)
- `create_client()` is called once at module level;
  `client.get_extension_capability_implementation()` is **synchronous** — no `await`
- Use `get_extension_override(context)` to extract caller-supplied override
  metadata from the A2A `RequestContext` and pass it via the `override` parameter

## How instructions are added

The Agents SDK uses a plain string for instructions. Concatenate the extended
instructions:

```python
instructions = BASE_INSTRUCTIONS
if ext_impl.instruction:
    instructions += f"\n\n{ext_impl.instruction}"

agent = Agent(name="my-agent", instructions=instructions, ...)
```

## How MCP tools are added

MCP servers are first-class in the Agents SDK. Pass them at agent construction
time — the SDK handles connection management:

```python
from agents.mcp import MCPServerStreamableHTTP

mcp_servers = []
for server in ext_impl.mcp_servers:
    mcp_servers.append(
        MCPServerStreamableHTTP(
            url=server.url,
            name=server.tool_prefix.rstrip("_"),
        )
    )

agent = Agent(
    name="my-agent",
    instructions=instructions,
    mcp_servers=mcp_servers,
)
```

## How tools are filtered

The OpenAI Agents SDK provides `create_static_tool_filter` for allowlist-based
filtering. Pass it as `tool_filter` when creating an MCP server, using
`server.tool_names`:

```python
from agents.mcp import MCPServerStreamableHTTP, create_static_tool_filter

server = MCPServerStreamableHTTP(
    url=server.url,
    tool_filter=create_static_tool_filter(allowed_tool_names=server.tool_names),
)
```

For dynamic filtering based on runtime context, use a callable instead:

```python
from agents.mcp import ToolFilterContext

async def context_aware_filter(context: ToolFilterContext, tool) -> bool:
    return tool.name in allowed_names

server = MCPServerStreamableHTTP(url=server.url, tool_filter=context_aware_filter)
```

## How tools are namespaced

The extensibility service provides a `tool_prefix` on each `McpServer`, derived
from the tool's ORD ID. The prefix includes a trailing `_` separator.

The `name` parameter on MCP server constructors gives each server a unique
identity. Use the backend-provided prefix (with trailing `_` stripped) as the
server name:

```python
server = MCPServerStreamableHTTP(
    url=server.url,
    name=server.tool_prefix.rstrip("_"),
    # e.g. "sap_mcp_servicenow_v1"
)
```

## Mixing with native tools

You can combine MCP servers with function tools:

```python
from agents import Agent, function_tool

@function_tool
def my_native_tool(param: str) -> str:
    """A native tool."""
    return f"Result: {param}"

agent = Agent(
    name="my-agent",
    instructions=instructions,
    tools=[my_native_tool],
    mcp_servers=mcp_servers,
)
```

## How telemetry is added

The OpenAI Agents SDK handles MCP tool calls internally. To add OTEL telemetry
for extension tracking, use the pre-built `create_instrumented_tool_filter`
from the `extension_telemetry` module (generated by Phase 2 of the
`sap-agent-extensibility` skill). It replaces `create_static_tool_filter` —
combining allowlist filtering with telemetry instrumentation in a single step.

> **Important**: The SDK's `extension_context()` sets OTel _baggage_ only
> (propagated to downstream services via HTTP headers). It does **not** set
> span attributes on the agent's own spans. `create_instrumented_tool_filter`
> handles both: baggage via `extension_context()` and explicit span attributes
> via `tracer.start_as_current_span()`.

> **Limitation**: The OpenAI Agents SDK does not expose a hook that runs
> _during_ tool execution — `tool_filter` runs at filter time (before the
> actual MCP call). The `extension_context` sets baggage that propagates
> correctly to the MCP server, but the tracer span created here will close
> before the tool executes. This is architecturally imperfect but acceptable
> as the baggage propagation (the primary purpose) works correctly.

```python
from extension_telemetry import create_instrumented_tool_filter


async def run_agent_with_telemetry(query: str, context=None) -> str:
    """Run the agent with telemetry-instrumented tools."""
    override = get_extension_override(context) if context else {}
    ext_impl = extensibility_client.get_extension_capability_implementation(
        capability_id="default",
        override=override,
    )

    mcp_servers = []
    for server in ext_impl.mcp_servers:
        mcp_servers.append(
            MCPServerStreamableHTTP(
                url=server.url,
                name=server.tool_prefix.rstrip("_"),
                # Use instrumented filter instead of static filter
                tool_filter=create_instrumented_tool_filter(
                    allowed_tool_names=server.tool_names,
                    extension_name=ext_impl.extension_name,
                    source_mapping=ext_impl.source.tools if ext_impl.source else None,
                    tool_prefix=server.tool_prefix,
                ),
            )
        )

    agent = Agent(
        name="my-agent",
        instructions=instructions,
        mcp_servers=mcp_servers,
    )
    result = await Runner.run(agent, input=query)
    return result.final_output
```

This approach:

- Uses the pre-built `create_instrumented_tool_filter` from `extension_telemetry`
  (no need to define filter functions inline)
- Replaces `create_static_tool_filter` — filters **and** instruments in one step
- Creates both `extension_context` (baggage) and an explicit tracer span
  (attributes) for each allowed tool
- Extension metadata is visible in the agent's own traces, not just propagated
  to downstream services
- Preserves the original filtering behavior while adding telemetry
- See the limitation note above about filter-time vs call-time execution
