"""
PydanticAI toolset wrapper with extension telemetry instrumentation.

Provides ``InstrumentedToolset``, a ``WrapperToolset`` subclass that intercepts
every ``call_tool`` invocation to add OpenTelemetry extension attributes.  This
is the recommended way to add extension telemetry when using PydanticAI's
built-in MCP toolset support (``.filtered()``, ``.prefixed()``).

When a ``source_mapping`` dict is provided (from
``ext_impl.source.tools``), all seven ``sap.extension.*`` span attributes
are resolved from the source info for *the specific tool* being called,
enabling per-tool telemetry attribution when multiple extensions are merged.

Usage:
    from extension_telemetry import InstrumentedToolset

    instrumented = InstrumentedToolset(
        wrapped=prefixed_server,
        extension_name="ServiceNow Extension",
        tool_prefix="concur_receipts",
        source_mapping=ext_impl.source.tools if ext_impl.source else None,
    )
"""

import logging
import time
from dataclasses import dataclass
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
from pydantic_ai.toolsets.wrapper import WrapperToolset

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


@dataclass
class InstrumentedToolset(WrapperToolset):
    """Toolset wrapper that adds OTel extension attributes on every tool call.

    Intercepts ``call_tool`` to set both OTel *baggage* (via the SDK's
    ``extension_context``) and explicit span attributes so extension
    metadata is visible in the agent's own traces.

    Creates a dedicated ``extension_tool <name>`` span for each call with
    all seven ``sap.extension.*`` attributes:

    - ``sap.extension.isExtension``: ``True``
    - ``sap.extension.extensionType``: ``"tool"``
    - ``sap.extension.capabilityId``: Extension capability name
    - ``sap.extension.extensionId``: UUID of the contributing extension
    - ``sap.extension.extensionName``: Human-readable extension name
    - ``sap.extension.extensionVersion``: Extension version number
    - ``sap.extension.extension.item.name``: Raw MCP tool name

    Args:
        wrapped: The inner toolset (typically a filtered + prefixed MCP server).
        extension_name: Human-readable name of the extension
            (from ``ext_impl.extension_name``).
        tool_prefix: The prefix applied by ``.prefixed()`` (without trailing
            underscore — PydanticAI adds the ``_`` separator automatically).
        capability: Extension capability name (default: ``"default"``).
        source_mapping: Optional mapping of prefixed tool names to source
            info dicts (from ``ext_impl.source.tools``).  Each value is a
            dict with ``extensionName``, ``extensionId``, and
            ``extensionVersion`` keys.
    """

    extension_name: str = ""
    tool_prefix: str = ""
    capability: str = "default"
    source_mapping: dict[str, Any] | None = None

    async def call_tool(self, name: str, tool_args: Any, ctx: Any, tool: Any) -> Any:
        """Call a tool with extension telemetry instrumentation.

        Strips the prefix from the tool name to recover the original MCP tool
        name, and wraps the call with both ``extension_context`` (baggage) and
        an explicit tracer span with all seven attributes.

        When ``source_mapping`` is provided, resolves the extension name, id,
        and version for *this specific tool*, falling back to
        ``self.extension_name``.
        """
        # PydanticAI's .prefixed() joins as f"{prefix}_{name}", adding an
        # extra "_" separator.  Axle's source.tools keys use the toolPrefix
        # directly (which already ends with "_").  Reconstruct the Axle key
        # so the source_mapping lookup matches.
        original_tool_name = name.removeprefix(self.tool_prefix + "_")
        axle_key = self.tool_prefix + original_tool_name

        resolved_name, resolved_id, resolved_version = _resolve_source_info(
            axle_key, self.source_mapping, self.extension_name
        )
        item_name = original_tool_name

        _attrs = {
            ATTR_IS_EXTENSION: True,
            ATTR_EXTENSION_TYPE: ExtensionType.TOOL.value,
            ATTR_CAPABILITY_ID: self.capability,
            ATTR_EXTENSION_ID: resolved_id,
            ATTR_EXTENSION_NAME: resolved_name,
            ATTR_EXTENSION_VERSION: resolved_version,
            ATTR_EXTENSION_ITEM_NAME: item_name,
        }

        t0 = time.monotonic()
        try:
            with (
                extension_context(
                    capability_id=self.capability,
                    extension_name=resolved_name,
                    extension_type=ExtensionType.TOOL,
                    extension_id=resolved_id,
                    extension_version=resolved_version,
                    item_name=item_name,
                ),
                _tracer.start_as_current_span(
                    f"extension_tool {name}",
                    attributes=_attrs,
                ),
            ):
                logger.info("Calling extension tool: %s", name)
                result = await super().call_tool(name, tool_args, ctx, tool)
                logger.info("Extension tool completed: %s", name)
                return result
        finally:
            durations = _tool_call_durations.get(None)
            if durations is not None:
                durations.append(time.monotonic() - t0)
