"""
Instrumented wrappers for extension calls.

Provides wrapper functions that add OpenTelemetry span attributes when calling
extension tools. Uses the ``extension_context`` context manager from the SAP
Cloud SDK for Python to set OTel **baggage** (propagated to downstream services
via HTTP headers) and explicitly stamps **span attributes** on the agent's own
spans so extension metadata is visible in agent-side traces (Jaeger, Dynatrace,
Grafana, etc.).

When a ``source_mapping`` dict is provided (from
``ext_impl.source.tools``), all seven ``sap.extension.*`` span attributes
are resolved from the source info for *the specific tool* being called,
enabling per-tool telemetry attribution when multiple extensions are merged.

Also provides ``emit_extensions_summary_span`` to emit a sibling
``agent_extensions_summary`` span with aggregate counts and timing for all
extension operations performed during one agent execution.

Tool call metrics (count and wall-clock duration) are automatically
accumulated via a ``ContextVar``-based collector.  Call
``reset_tool_call_metrics()`` before the agent runs and
``get_tool_call_metrics()`` after it completes to retrieve accurate
counts and durations — even when tool calls happen deep inside framework
internals (e.g. PydanticAI's ``agent.run()`` or LangChain's agent loop).

Usage:
    from extension_telemetry import call_extension_tool

    result = await call_extension_tool(
        mcp_client=session,
        tool_info=tool_info,
        args={"param": "value"},
        extension_name="ServiceNow Extension",
        source_mapping=ext_impl.source.tools if ext_impl.source else None,
    )

    # Collect tool call metrics across an execution:
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
"""

import logging
import time
from contextvars import ContextVar
from typing import Any

from sap_cloud_sdk.core.telemetry import (
    ATTR_CAPABILITY_ID,
    ATTR_EXTENSION_ID,
    ATTR_EXTENSION_ITEM_NAME,
    ATTR_EXTENSION_NAME,
    ATTR_EXTENSION_TYPE,
    ATTR_EXTENSION_VERSION,
    ATTR_IS_EXTENSION,
    ExtensionType,
    extension_context,
)
from opentelemetry import trace

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer("sap.cloud_sdk.extension")

# ---------------------------------------------------------------------------
# ContextVar-based tool call metrics accumulator
# ---------------------------------------------------------------------------
# Each framework wrapper appends the wall-clock duration (seconds) of every
# individual tool call into this list.  Because it lives in a ContextVar, it
# is safe across concurrent asyncio tasks — each ``execute()`` gets its own
# accumulator via ``reset_tool_call_metrics()``.

_tool_call_durations: ContextVar[list[float]] = ContextVar("ext_tool_call_durations")


def reset_tool_call_metrics() -> None:
    """Initialise a fresh accumulator for tool call durations.

    Call this at the **start** of ``execute()``, before any hooks or
    ``agent.run()`` invocations.  Each subsequent tool call made by the
    framework wrappers will append its wall-clock duration (seconds) to
    the list stored in the ``ContextVar``.
    """
    _tool_call_durations.set([])


def get_tool_call_metrics() -> tuple[int, float]:
    """Return ``(call_count, total_duration_ms)`` since the last reset.

    Returns the number of actual extension tool calls that were made and
    the aggregate wall-clock time in **milliseconds**.  If
    ``reset_tool_call_metrics`` was never called (backward-compatible
    path), returns ``(0, 0.0)``.
    """
    durations = _tool_call_durations.get([])
    return len(durations), sum(durations) * 1000


def _resolve_source_info(
    axle_key: str,
    source_mapping: dict[str, Any] | None,
    fallback_name: str,
) -> tuple[str, str, str]:
    """Resolve extension name, id, and version from source mapping.

    Source mapping values may be :class:`ExtensionSourceInfo` dataclass
    instances (SDK v0.5+) with attributes ``extension_name``,
    ``extension_id``, ``extension_version``, **or** plain dicts with
    camelCase keys ``extensionName``, ``extensionId``,
    ``extensionVersion``.  Falls back to ``fallback_name`` for the name
    and empty strings for id/version when the key is not found.

    Returns:
        Tuple of (extension_name, extension_id, extension_version).
    """
    info = (source_mapping or {}).get(axle_key)
    if info is None:
        return (fallback_name or "unknown", "", "")
    # SDK v0.5+ returns ExtensionSourceInfo dataclass instances
    if hasattr(info, "extension_name"):
        return (
            info.extension_name or fallback_name or "unknown",
            info.extension_id or "",
            str(info.extension_version) if info.extension_version else "",
        )
    # Fallback: plain dict (older SDK or manual construction)
    if isinstance(info, dict):
        return (
            info.get("extensionName") or fallback_name or "unknown",
            info.get("extensionId") or "",
            str(info.get("extensionVersion", "")) or "",
        )
    return (fallback_name or "unknown", "", "")


def _build_span_attributes(
    extension_name: str,
    extension_id: str,
    extension_version: str,
    ext_type: ExtensionType,
    capability: str,
    item_name: str,
) -> dict[str, Any]:
    """Build the full set of 7 ``sap.extension.*`` span attributes."""
    return {
        ATTR_IS_EXTENSION: True,
        ATTR_EXTENSION_TYPE: ext_type.value,
        ATTR_CAPABILITY_ID: capability,
        ATTR_EXTENSION_ID: extension_id,
        ATTR_EXTENSION_NAME: extension_name,
        ATTR_EXTENSION_VERSION: extension_version,
        ATTR_EXTENSION_ITEM_NAME: item_name,
    }


async def call_extension_tool(
    mcp_client: Any,
    tool_info: Any,
    args: dict[str, Any],
    extension_name: str,
    capability: str = "default",
    source_mapping: dict[str, Any] | None = None,
    tool_prefix: str = "",
) -> Any:
    """Call an MCP tool with telemetry instrumentation.

    Wraps the tool call with ``extension_context`` (sets OTel baggage for
    downstream propagation) and creates an explicit tracer span with all
    seven ``sap.extension.*`` attributes so the call is visible in
    agent-side traces.

    When ``source_mapping`` is provided, the extension name, id, and version
    are resolved from the source info for *this specific tool*, enabling
    per-tool attribution in multi-extension scenarios.

    Args:
        mcp_client: The MCP client session connected to the tool's server.
            Must have a ``call_tool`` method.
        tool_info: Object with a ``mcp_tool_name`` attribute.
            Typically from iterating an ``McpServer``'s tools.
        args: Dictionary of arguments to pass to the tool.
        extension_name: The human-readable name of the extension
            (from ``ext_impl.extension_name``). Used as fallback when
            ``source_mapping`` does not contain the tool.
        capability: Extension capability name (default: "default").
        source_mapping: Optional mapping of prefixed tool names to source
            info dicts (from ``ext_impl.source.tools``).  Each value is a
            dict with ``extensionName``, ``extensionId``, and
            ``extensionVersion`` keys.
        tool_prefix: The Axle-provided tool prefix (e.g.,
            ``"sap_mcp_servicenow_v1_"``).  Used to reconstruct the key
            for ``source_mapping`` lookup since ``tool_info.mcp_tool_name``
            is the raw MCP tool name (before prefixing).

    Returns:
        The tool's response from the MCP server.

    Example:
        from extension_telemetry import call_extension_tool

        result = await call_extension_tool(
            mcp_client=session,
            tool_info=tool_info,
            args={"query": "Hello"},
            extension_name=ext_impl.extension_name,
            source_mapping=ext_impl.source.tools if ext_impl.source else None,
            tool_prefix=server.tool_prefix,
        )
    """
    # source_mapping keys use the Axle format: tool_prefix + original_name.
    # tool_info.mcp_tool_name is the raw MCP name, so reconstruct the Axle
    # key for lookup.
    axle_key = (
        tool_prefix + tool_info.mcp_tool_name
        if tool_prefix
        else tool_info.mcp_tool_name
    )

    resolved_name, resolved_id, resolved_version = _resolve_source_info(
        axle_key, source_mapping, extension_name
    )
    item_name = tool_info.mcp_tool_name

    _attrs = _build_span_attributes(
        resolved_name,
        resolved_id,
        resolved_version,
        ExtensionType.TOOL,
        capability,
        item_name,
    )

    t0 = time.monotonic()
    try:
        with (
            extension_context(
                capability_id=capability,
                extension_name=resolved_name,
                extension_type=ExtensionType.TOOL,
                extension_id=resolved_id,
                extension_version=resolved_version,
                item_name=item_name,
            ),
            _tracer.start_as_current_span(
                f"extension_tool {tool_info.mcp_tool_name}",
                attributes=_attrs,
            ),
        ):
            logger.info("Calling extension tool: %s", tool_info.mcp_tool_name)
            result = await mcp_client.call_tool(tool_info.mcp_tool_name, args)
            logger.info("Extension tool completed: %s", tool_info.mcp_tool_name)
            return result
    finally:
        durations = _tool_call_durations.get(None)
        if durations is not None:
            durations.append(time.monotonic() - t0)


# ---------------------------------------------------------------------------
# Aggregate summary span
# ---------------------------------------------------------------------------

# Attribute constants for the summary span.  These use the
# ``sap.extension.summary.*`` namespace to distinguish them from the
# per-call ``sap.extension.*`` attributes on individual tool/hook spans.
ATTR_SUMMARY_TOTAL_OPERATION_COUNT = "sap.extension.summary.totalOperationCount"
ATTR_SUMMARY_TOTAL_DURATION_MS = "sap.extension.summary.totalDurationMs"
ATTR_SUMMARY_TOOL_CALL_COUNT = "sap.extension.summary.toolCallCount"
ATTR_SUMMARY_HOOK_CALL_COUNT = "sap.extension.summary.hookCallCount"
ATTR_SUMMARY_HAS_INSTRUCTION = "sap.extension.summary.hasInstruction"


def emit_extensions_summary_span(
    *,
    tool_call_count: int,
    hook_call_count: int,
    has_instruction: bool,
    total_duration_ms: float,
) -> None:
    """Emit a sibling summary span with aggregate extension metrics.

    Creates a zero-duration ``agent_extensions_summary`` span carrying
    aggregate counts and timing for all extension operations performed
    during one agent execution.  The span is created via ``start_span``
    (not ``start_as_current_span``) and immediately ended, so it appears
    as a **sibling** of the individual ``extension_tool`` /
    ``extension_hook`` spans — it never becomes a parent or alters the
    existing span hierarchy.

    This function should be called **once** at the end of the agent's
    ``execute()`` method, after all extension operations (hooks, tools,
    instruction injection) have completed.

    Args:
        tool_call_count: Number of extension tool calls made.
        hook_call_count: Number of hook calls executed (pre + post).
        has_instruction: Whether an extension instruction was injected
            into the system prompt.
        total_duration_ms: Wall-clock sum (milliseconds) of all
            extension operations, measured via ``time.monotonic()``.

    Example:
        import time
        from extension_telemetry import emit_extensions_summary_span

        t0 = time.monotonic()
        # ... run hooks, connect MCP servers, call tools ...
        total_ms = (time.monotonic() - t0) * 1000

        emit_extensions_summary_span(
            tool_call_count=3,
            hook_call_count=2,
            has_instruction=True,
            total_duration_ms=total_ms,
        )
    """
    total = tool_call_count + hook_call_count + (1 if has_instruction else 0)
    attrs = {
        ATTR_SUMMARY_TOTAL_OPERATION_COUNT: total,
        ATTR_SUMMARY_TOTAL_DURATION_MS: total_duration_ms,
        ATTR_SUMMARY_TOOL_CALL_COUNT: tool_call_count,
        ATTR_SUMMARY_HOOK_CALL_COUNT: hook_call_count,
        ATTR_SUMMARY_HAS_INSTRUCTION: has_instruction,
    }
    # start_span() (not start_as_current_span) ensures this span is never
    # set as the active context — it cannot become a parent of subsequent
    # spans.  Calling end() immediately makes it a zero-duration marker.
    span = _tracer.start_span("agent_extensions_summary", attributes=attrs)
    span.end()
