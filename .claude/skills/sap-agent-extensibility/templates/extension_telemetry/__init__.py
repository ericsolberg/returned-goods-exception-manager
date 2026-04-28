"""
Extension Telemetry - Instrumented wrappers for extension calls.

Provides framework-agnostic and framework-specific wrappers that automatically
add OpenTelemetry span attributes when calling extension tools.  Uses the
``extension_context`` context manager from the SAP Cloud SDK for Python to set
OTel baggage, and explicitly stamps span attributes on the agent's own spans for
visibility in agent-side traces.

Also provides ``emit_extensions_summary_span`` to emit a sibling
``agent_extensions_summary`` span with aggregate counts and timing for all
extension operations performed during one agent execution.

Also provides ``ExtensionContextLogFilter``, a logging filter that injects
``ext_*`` attributes from OTel baggage into Python ``LogRecord`` objects.
Combined with a JSON formatter, these attributes are serialised into log lines
and automatically promoted to ``log.attributes.*`` by Kyma's log pipeline.

Framework-agnostic (always available):
    from extension_telemetry import call_extension_tool, ExtensionType

    result = await call_extension_tool(
        mcp_client, tool_info, {"param": "value"},
        extension_name="ServiceNow Extension",
    )

Tool call metrics (always available — ContextVar-based accumulator):
    from extension_telemetry import (
        reset_tool_call_metrics,
        get_tool_call_metrics,
        emit_extensions_summary_span,
    )

    reset_tool_call_metrics()
    # ... run hooks, agent.run() (which triggers tool calls internally) ...
    tool_call_count, tool_duration_ms = get_tool_call_metrics()

    emit_extensions_summary_span(
        tool_call_count=tool_call_count,
        hook_call_count=2,
        has_instruction=True,
        total_duration_ms=hook_duration_ms + tool_duration_ms,
    )

Log filter (always available — depends only on opentelemetry-api):
    from extension_telemetry import ExtensionContextLogFilter

    handler = logging.StreamHandler()
    handler.addFilter(ExtensionContextLogFilter())
    logging.getLogger().addHandler(handler)

PydanticAI (requires ``pydantic-ai``):
    from extension_telemetry import InstrumentedToolset

    instrumented = InstrumentedToolset(
        wrapped=prefixed_server,
        extension_name="ServiceNow Extension",
        tool_prefix="vendor_prefix",
    )

LangChain (requires ``langchain-core``):
    from extension_telemetry import wrap_tool_with_telemetry

    for tool in mcp_tools:
        wrap_tool_with_telemetry(tool, extension_name="ServiceNow Extension")

OpenAI Agents SDK (requires ``openai-agents``):
    from extension_telemetry import create_instrumented_tool_filter

    server = MCPServerStreamableHTTP(
        url=server.url,
        tool_filter=create_instrumented_tool_filter(
            allowed_tool_names=server.tool_names,
            extension_name="ServiceNow Extension",
        ),
    )

Telemetry attributes added to spans (7 total):
    - sap.extension.isExtension: True  (boolean)
    - sap.extension.extensionType: tool | instruction | hook
    - sap.extension.capabilityId: <capability name>
    - sap.extension.extensionId: <extension UUID>
    - sap.extension.extensionName: <extension name>
    - sap.extension.extensionVersion: <version number>  (int on spans)
    - sap.extension.extension.item.name: <raw tool name or hook name>

Summary attributes added to the ``agent_extensions_summary`` span (5 total):
    - sap.extension.summary.totalOperationCount: <int>  (tools + hooks + instruction)
    - sap.extension.summary.totalDurationMs: <float>  (wall-clock ms sum)
    - sap.extension.summary.toolCallCount: <int>
    - sap.extension.summary.hookCallCount: <int>
    - sap.extension.summary.hasInstruction: <bool>

Log attributes added to LogRecords (inside extension_context only, 7 total):
    - ext_is_extension: "true"
    - ext_extension_type: "tool" | "instruction" | "hook"
    - ext_capability_id: <capability name>
    - ext_extension_id: <extension UUID>
    - ext_extension_name: <extension name>
    - ext_extension_version: <version string>
    - ext_item_name: <raw tool name or hook name>
"""

from .log_filter import ExtensionContextLogFilter
from .wrappers import (
    ExtensionType,
    call_extension_tool,
    emit_extensions_summary_span,
    get_tool_call_metrics,
    reset_tool_call_metrics,
)

# Framework-specific wrappers are loaded lazily so that importing this package
# never fails due to a missing AI framework dependency.  Users only hit an
# ImportError when they actually reference a name that requires a framework
# they haven't installed.

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # (module_path, attribute_name)
    "InstrumentedToolset": ("._pydantic_ai", "InstrumentedToolset"),
    "wrap_tool_with_telemetry": ("._langchain", "wrap_tool_with_telemetry"),
    "create_instrumented_tool_filter": (
        "._openai_agents",
        "create_instrumented_tool_filter",
    ),
}

_FRAMEWORK_HINTS: dict[str, str] = {
    "InstrumentedToolset": "pydantic-ai  (pip install pydantic-ai)",
    "wrap_tool_with_telemetry": "langchain-core  (pip install langchain-core)",
    "create_instrumented_tool_filter": "openai-agents  (pip install openai-agents)",
}


def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        try:
            import importlib

            module = importlib.import_module(module_path, package=__name__)
            value = getattr(module, attr_name)
            # Cache on the module so __getattr__ is not called again
            globals()[name] = value
            return value
        except ImportError as exc:
            hint = _FRAMEWORK_HINTS.get(name, "")
            raise ImportError(
                f"'{name}' requires {hint} to be installed. Install it and try again."
            ) from exc
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Framework-agnostic (always available)
    "ExtensionType",
    "call_extension_tool",
    "emit_extensions_summary_span",
    "reset_tool_call_metrics",
    "get_tool_call_metrics",
    # Log filter (always available)
    "ExtensionContextLogFilter",
    # PydanticAI (lazy)
    "InstrumentedToolset",
    # LangChain (lazy)
    "wrap_tool_with_telemetry",
    # OpenAI Agents SDK (lazy)
    "create_instrumented_tool_filter",
]
