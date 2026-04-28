# LangChain / LangGraph Integration

Integration pattern using LangChain with `langchain-mcp-adapters` for MCP tool
support. Includes manual tool filtering and prefixing using the backend-provided
`tool_prefix` (LangChain does not provide built-in support for either).

> **Note**: This reference assumes Phase 2 (Add Telemetry Instrumentation) of the
> `sap-agent-extensibility` skill has been completed, which generates the
> `extension_telemetry/` module with OTEL-instrumented wrappers.

> **Conditionality**: This reference shows the full tools + instructions case.
> When implementing, only include the sections relevant to your configuration:
>
> - **Tools only**: Include MCP server config, tool filtering, prefixing, and
>   telemetry, but omit the instruction concatenation to the system prompt.
> - **Instructions only**: Include the instruction concatenation to the system
>   prompt, but omit `langchain-mcp-adapters`, `MultiServerMCPClient`, tool
>   filtering/prefixing, and telemetry wrapping entirely. Phase 2 (telemetry)
>   should also have been skipped.

## Complete example

```python
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from sap_cloud_sdk.extensibility import create_client, get_extension_override

logger = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = "You are a helpful assistant."

# Create extensibility client once at module level
extensibility_client = create_client()


async def run_agent(query: str, context=None) -> str:
    """Run the LangChain agent with extensibility support."""

    # Step 1: Extract override and fetch extensions
    override = get_extension_override(context) if context else {}
    ext_impl = extensibility_client.get_extension_capability_implementation(
        capability_id="default",
        override=override,
    )

    # Step 2: Build system prompt with extended instructions
    system_prompt = BASE_SYSTEM_PROMPT
    if ext_impl.instruction:
        system_prompt += f"\n\n## Extended Instructions\n{ext_impl.instruction}"

    # Step 3: Build MCP server config
    mcp_servers = {}
    for server in ext_impl.mcp_servers:
        transport = "sse" if server.url.rstrip("/").endswith("/sse") else "streamable_http"
        server_key = server.tool_prefix.rstrip("_") or server.url.split("/")[-1] or "ext"
        mcp_servers[server_key] = {
            "url": server.url,
            "transport": transport,
        }

    model = ChatOpenAI(model="gpt-4o")

    # Step 4: Connect to MCP servers, filter tools, and create agent
    if mcp_servers:
        client = MultiServerMCPClient(mcp_servers)
        mcp_tools = await client.get_tools()

        # Build a lookup from tool name -> server for filtering and prefixing
        tool_name_to_server = {}
        for server in ext_impl.mcp_servers:
            for name in server.tool_names:
                tool_name_to_server[name] = server

        # Filter to only approved tools and prefix with backend-provided prefix
        filtered_tools = []
        for t in mcp_tools:
            if t.name in tool_name_to_server:
                server = tool_name_to_server[t.name]
                t.name = f"{server.tool_prefix}{t.name}"
                filtered_tools.append(t)

        agent = create_react_agent(model, filtered_tools)
        result = await agent.ainvoke({
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query),
            ]
        })
    else:
        # No MCP tools — run without them
        agent = create_react_agent(model, [])
        result = await agent.ainvoke({
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query),
            ]
        })

    return result["messages"][-1].content
```

## Key points

- **`langchain-mcp-adapters`** provides `MultiServerMCPClient` for connecting to
  multiple MCP servers simultaneously
- Extended instructions are appended to the system message
- MCP tools from `await client.get_tools()` can be mixed with native LangChain tools
- `MultiServerMCPClient` is instantiated directly (not as a context manager).
  Call `await client.get_tools()` to connect and retrieve tools
- Tools are **filtered** manually to only the subset approved by the extensibility
  service (LangChain has no built-in tool filter)
- Tools are **prefixed** using the backend-provided `tool_prefix` (which includes
  a trailing `_` separator) to prevent naming conflicts across servers
- `create_client()` is called once at module level;
  `client.get_extension_capability_implementation()` is **synchronous** — no `await`
- Use `get_extension_override(context)` to extract caller-supplied override
  metadata from the A2A `RequestContext` and pass it via the `override` parameter
- By default, `create_client()` resolves a BTP destination named
  `EXTENSIBILITY_SERVICE`. To use a custom destination name, pass an
  `ExtensibilityConfig`:

  ```python
  from sap_cloud_sdk.extensibility import create_client, ExtensibilityConfig

  extensibility_client = create_client(
      config=ExtensibilityConfig(destination_name="my-agent-axle")
  )
  ```

## How instructions are added

LangChain doesn't have a separate instructions parameter. Append extended
instructions to the system message:

```python
system_prompt = BASE_SYSTEM_PROMPT
if ext_impl.instruction:
    system_prompt += f"\n\n## Extended Instructions\n{ext_impl.instruction}"
```

## How MCP tools are added

The `MultiServerMCPClient` connects to all MCP servers and exposes their tools
as LangChain-compatible tool objects:

```python
client = MultiServerMCPClient(mcp_servers)
mcp_tools = await client.get_tools()
# Mix with any existing native tools
all_tools = native_tools + mcp_tools
agent = create_react_agent(model, all_tools)
```

## How tools are filtered

LangChain does not have a built-in tool filtering mechanism for MCP servers.
Filter the tool list manually after loading all tools from `get_tools()`,
using `server.tool_names` from each `McpServer`:

```python
# Build a lookup from tool name -> server
tool_name_to_server = {}
for server in ext_impl.mcp_servers:
    for name in server.tool_names:
        tool_name_to_server[name] = server

mcp_tools = await client.get_tools()
filtered_tools = [t for t in mcp_tools if t.name in tool_name_to_server]
```

Because `get_tools()` returns tools from all connected servers together, match
each tool's name against the lookup to determine which server it belongs to.

## How tools are namespaced

The extensibility service provides a `tool_prefix` on each `McpServer`, derived
from the tool's ORD ID. The prefix already includes a trailing `_` separator.

LangChain does not provide built-in tool name prefixing. Rename tools manually
by mutating their `name` attribute after loading:

```python
for t in filtered_tools:
    server = tool_name_to_server[t.name]
    t.name = f"{server.tool_prefix}{t.name}"
# Tool "create_ticket" becomes "sap_mcp_servicenow_v1_create_ticket"
```

## Mixing with native LangChain tools

You can combine filtered MCP tools with `@tool`-decorated functions:

```python
from langchain_core.tools import tool

@tool
def my_native_tool(param: str) -> str:
    """A native LangChain tool."""
    return f"Result: {param}"

client = MultiServerMCPClient(mcp_servers)
mcp_tools = await client.get_tools()
# Filter and prefix MCP tools using ext_impl.mcp_servers (see above)
filtered_tools = filter_and_prefix(mcp_tools, ext_impl.mcp_servers)
all_tools = [my_native_tool] + filtered_tools
agent = create_react_agent(model, all_tools)
```

## How telemetry is added

LangChain's `langchain-mcp-adapters` handles MCP tool calls internally. To add
OTEL telemetry for extension tracking, use the pre-built `wrap_tool_with_telemetry`
function from the `extension_telemetry` module (generated by Phase 2 of the
`sap-agent-extensibility` skill). It wraps each tool's `invoke` and `ainvoke`
methods to create a dedicated tracer span with explicit extension attributes.
Both sync and async paths must be patched because LangGraph's
`create_react_agent` uses `ainvoke` internally when the agent is called via
`agent.ainvoke()`.

> **Important**: The SDK's `extension_context()` sets OTel _baggage_ only
> (propagated to downstream services via HTTP headers). It does **not** set
> span attributes on the agent's own spans. `wrap_tool_with_telemetry` handles
> both: baggage via `extension_context()` and explicit span attributes via
> `tracer.start_as_current_span()`.

```python
from extension_telemetry import wrap_tool_with_telemetry


async def run_agent_with_telemetry(query: str, context=None) -> str:
    """Run the LangChain agent with telemetry-instrumented tools."""
    override = get_extension_override(context) if context else {}
    ext_impl = extensibility_client.get_extension_capability_implementation(
        capability_id="default",
        override=override,
    )

    client = MultiServerMCPClient(mcp_servers)
    mcp_tools = await client.get_tools()

    # Filter, wrap with telemetry, and prefix
    instrumented_tools = []
    for t in mcp_tools:
        if t.name in tool_name_to_server:
            server = tool_name_to_server[t.name]
            # Wrap with telemetry before prefixing
            wrap_tool_with_telemetry(
                t,
                extension_name=ext_impl.extension_name,
                source_mapping=ext_impl.source.tools if ext_impl.source else None,
                tool_prefix=server.tool_prefix,
            )
            # Then prefix the name
            t.name = f"{server.tool_prefix}{t.name}"
            instrumented_tools.append(t)

    agent = create_react_agent(model, instrumented_tools)
    result = await agent.ainvoke({"messages": [...]})

    return result["messages"][-1].content
```

This approach:

- Uses the pre-built `wrap_tool_with_telemetry` from `extension_telemetry`
  (no need to define wrapper functions inline)
- Wraps each tool's `invoke` and `ainvoke` methods with both `extension_context`
  (baggage) and a dedicated tracer span (explicit `sap.extension.*` attributes).
  Both paths are patched because LangGraph's `create_react_agent` uses the async
  path (`ainvoke`) internally when the agent is called via `agent.ainvoke()`.
- Extension metadata is visible in the agent's own traces, not just propagated
  to downstream services
- Uses `ext_impl.extension_name` to identify the extension in telemetry
- Preserves the original tool behavior while adding telemetry
