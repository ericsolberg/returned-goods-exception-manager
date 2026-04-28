"""
LangChain tool wrapper with extension telemetry instrumentation.

Provides ``wrap_tool_with_telemetry``, a function that wraps a LangChain tool's
``invoke`` and ``ainvoke`` methods to add OpenTelemetry extension attributes.
This is the recommended way to add extension telemetry when using LangChain /
LangGraph with ``langchain-mcp-adapters``.

When a ``source_mapping`` dict is provided (from
``ext_impl.source.tools``), all seven ``sap.extension.*`` span attributes
are resolved from the source info for *the specific tool* being called,
enabling per-tool telemetry attribution when multiple extensions are merged.

Usage:
    from extension_telemetry import wrap_tool_with_telemetry

    for tool in mcp_tools:
        wrap_tool_with_telemetry(
            tool,
            extension_name="ServiceNow Extension",
            source_mapping=ext_impl.source.tools if ext_impl.source else None,
        )
"""

import logging
import time
from functools import wraps
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


def wrap_tool_with_telemetry(
    tool: Any,
    extension_name: str,
    capability: str = "default",
    source_mapping: dict[str, Any] | None = None,
    tool_prefix: str = "",
) -> Any:
    """Wrap a LangChain tool's ``invoke`` and ``ainvoke`` with extension telemetry.

    Monkey-patches the tool's ``invoke`` and ``ainvoke`` methods to create both
    OTel *baggage* (via the SDK's ``extension_context``, propagated to downstream
    services) and a dedicated tracer span with all seven ``sap.extension.*``
    attributes so extension metadata is visible in the agent's own traces.

    Both sync and async paths are wrapped because LangGraph's
    ``create_react_agent`` calls ``tool.ainvoke()`` when the agent runs via
    ``agent.ainvoke()``.

    When ``source_mapping`` is provided, the extension name, id, and version
    are resolved from the source info for *this specific tool*, enabling
    per-tool attribution in multi-extension scenarios.

    .. note::

        This function should be called **before** prefixing the tool name,
        since ``source_mapping`` keys use the Axle format
        (``tool_prefix + original_name``), not the raw MCP tool name.

    Args:
        tool: A LangChain ``BaseTool`` instance (from
            ``langchain-mcp-adapters``'s ``client.get_tools()``).
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
            for ``source_mapping`` lookup since this function is called
            before the tool name is prefixed.

    Returns:
        The same tool object with its ``invoke`` and ``ainvoke`` methods wrapped.

    Example:
        from extension_telemetry import wrap_tool_with_telemetry

        for tool in mcp_tools:
            wrap_tool_with_telemetry(
                tool,
                extension_name=ext_impl.extension_name,
                source_mapping=ext_impl.source.tools if ext_impl.source else None,
                tool_prefix=server.tool_prefix,
            )
    """
    # source_mapping keys use the Axle format: tool_prefix + original_name.
    # At this point tool.name is the raw MCP name (before prefixing), so
    # reconstruct the Axle key for lookup.
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

    # Wrap synchronous invoke
    original_invoke = tool.invoke

    @wraps(original_invoke)
    def instrumented_invoke(*args: Any, **kwargs: Any) -> Any:
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
                logger.info("Calling extension tool: %s", tool.name)
                result = original_invoke(*args, **kwargs)
                logger.info("Extension tool completed: %s", tool.name)
                return result
        finally:
            durations = _tool_call_durations.get(None)
            if durations is not None:
                durations.append(time.monotonic() - t0)

    # Wrap async ainvoke
    original_ainvoke = tool.ainvoke

    @wraps(original_ainvoke)
    async def instrumented_ainvoke(*args: Any, **kwargs: Any) -> Any:
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
                logger.info("Calling extension tool: %s", tool.name)
                result = await original_ainvoke(*args, **kwargs)
                logger.info("Extension tool completed: %s", tool.name)
                return result
        finally:
            durations = _tool_call_durations.get(None)
            if durations is not None:
                durations.append(time.monotonic() - t0)

    # Use object.__setattr__ to bypass Pydantic v2's __setattr__ guard,
    # which rejects attributes not declared as model fields.
    object.__setattr__(tool, "invoke", instrumented_invoke)
    object.__setattr__(tool, "ainvoke", instrumented_ainvoke)
    return tool
