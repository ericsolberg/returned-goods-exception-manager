"""
Backward-compatibility shim — imports from ``_pydantic_ai``.

.. deprecated::
    Import ``InstrumentedToolset`` directly from ``extension_telemetry`` instead
    of ``extension_telemetry.toolset``.
"""

from ._pydantic_ai import InstrumentedToolset

__all__ = ["InstrumentedToolset"]
