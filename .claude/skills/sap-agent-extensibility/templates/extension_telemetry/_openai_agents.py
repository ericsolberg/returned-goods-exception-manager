"""
OpenAI Agents SDK tool filter with extension telemetry instrumentation.

Provides ``create_instrumented_tool_filter``, a factory that returns an
async tool filter function compatible with the OpenAI Agents SDK's
``MCPServerStreamableHTTP(tool_filter=...)`` parameter.  The filter adds
OpenTelemetry extension attributes while filtering to only approved tools.

When a ``source_mapping`` dict is provided (from
``ext_impl.source.tools``), all seven ``sap.extension.*`` span attributes
are resolved from the source info for *the specific tool* being called,
enabling per-tool telemetry attribution when multiple extensions are merged.

Usage:
    from extension_telemetry import create_instrumented_tool_filter

    server = MCPServerStreamableHTTP(
        url=server.url,
        name=server.tool_prefix.rstrip("_"),
        tool_filter=create_instrumented_tool_filter(
            allowed_tool_names=server.tool_names,
            extension_name="ServiceNow Extension",
            source_mapping=ext_impl.source.tools if ext_impl.source else None,
        ),
    )

.. note::

    The OpenAI Agents SDK does not expose a hook that runs *during* tool
    execution — ``tool_filter`` runs at filter time (before the actual MCP
    call).  The ``extension_context`` sets baggage that propagates correctly
    to the MCP server, but the tracer span created here will close before the
    tool executes.  This is architecturally imperfect but acceptable as the
    baggage propagation (the primary purpose) works correctly.

.. warning::

    The ``ContextVar``-based tool call duration captured here reflects
    **filter evaluation time**, not actual tool execution time.  The OpenAI
    Agents SDK's ``Runner.run()`` makes the real MCP calls later, outside
    any extension context.  There is no integration point in the SDK to
    capture actual tool execution duration.  As a result,
    ``sap.extension.summary.toolCallCount`` will reflect actual filter
    invocations (one per tool call), but
    ``sap.extension.summary.totalDurationMs`` will only include filter
    overhead for the OpenAI Agents SDK — not true tool execution time.
"""

import logging
import time
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

from .wrappers import _tool_call_durations

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer("sap.cloud_sdk.extension")


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


def create_instrumented_tool_filter(
    allowed_tool_names: list[str],
    extension_name: str,
    capability: str = "default",
    source_mapping: dict[str, Any] | None = None,
    tool_prefix: str = "",
) -> Any:
    """Create a tool filter that adds telemetry instrumentation.

    Creates both OTel baggage (via ``extension_context``) and a dedicated
    tracer span with all seven ``sap.extension.*`` attributes.

    When ``source_mapping`` is provided, the extension name, id, and version
    are resolved from the source info for *this specific tool*, enabling
    per-tool attribution in multi-extension scenarios.

    Args:
        allowed_tool_names: List of tool names to allow.
        extension_name: Human-readable name of the extension
            (from ``ext_impl.extension_name``).  Used as fallback when
            ``source_mapping`` does not contain the tool.
        capability: Extension capability name (default: ``"default"``).
        source_mapping: Optional mapping of prefixed tool names to source
            info dicts (from ``ext_impl.source.tools``).  Each value is a
            dict with ``extensionName``, ``extensionId``, and
            ``extensionVersion`` keys.
        tool_prefix: The Axle-provided tool prefix (e.g.,
            ``"sap_mcp_servicenow_v1_"``).  Used to reconstruct the key
            for ``source_mapping`` lookup since the filter receives the
            raw MCP tool name (before prefixing).

    Returns:
        An async callable compatible with the ``tool_filter`` parameter of
        ``MCPServerStreamableHTTP``.

    Example:
        from extension_telemetry import create_instrumented_tool_filter
        from agents.mcp import MCPServerStreamableHTTP

        server = MCPServerStreamableHTTP(
            url=server.url,
            name=server.tool_prefix.rstrip("_"),
            tool_filter=create_instrumented_tool_filter(
                allowed_tool_names=server.tool_names,
                extension_name=ext_impl.extension_name,
                source_mapping=ext_impl.source.tools if ext_impl.source else None,
                tool_prefix=server.tool_prefix,
            ),
        )
    """
    allowed_set = set(allowed_tool_names)

    async def instrumented_filter(context: Any, tool: Any) -> bool:
        if tool.name not in allowed_set:
            return False

        # source_mapping keys use the Axle format: tool_prefix + original_name.
        # The filter receives the raw MCP tool name, so reconstruct the Axle
        # key for lookup.
        axle_key = tool_prefix + tool.name if tool_prefix else tool.name

        resolved_name, resolved_id, resolved_version = _resolve_source_info(
            axle_key, source_mapping, extension_name
        )
        item_name = tool.name

        _attrs = {
            ATTR_IS_EXTENSION: True,
            ATTR_EXTENSION_TYPE: ExtensionType.TOOL.value,
            ATTR_CAPABILITY_ID: capability,
            ATTR_EXTENSION_ID: resolved_id,
            ATTR_EXTENSION_NAME: resolved_name,
            ATTR_EXTENSION_VERSION: resolved_version,
            ATTR_EXTENSION_ITEM_NAME: item_name,
        }

        # Add telemetry context for this tool call
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
                    f"extension_tool {tool.name}",
                    attributes=_attrs,
                ),
            ):
                logger.info("Extension tool filter matched: %s", tool.name)
                return True
        finally:
            durations = _tool_call_durations.get(None)
            if durations is not None:
                durations.append(time.monotonic() - t0)

    return instrumented_filter
