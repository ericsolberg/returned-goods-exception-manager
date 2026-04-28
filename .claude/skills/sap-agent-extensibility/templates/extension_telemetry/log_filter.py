"""
Logging filter that injects extension context from OTel baggage into log records.

When a log statement is emitted inside an ``extension_context()`` block, the
filter reads the seven ``sap.extension.*`` baggage values from the current OTel
context and sets them as extra attributes on the ``LogRecord``.  Combined with
a JSON formatter, these attributes are serialised into the JSON log line and
automatically promoted to ``log.attributes.*`` by Kyma's log pipeline.

When the current context has **no** extension baggage (i.e. outside any
``extension_context()`` block), the filter does **not** add ``ext_*``
attributes at all, keeping non-extension log lines clean.

Usage (applied once at startup to each **handler**, not the logger)::

    import logging
    from extension_telemetry.log_filter import ExtensionContextLogFilter

    handler = logging.StreamHandler()
    handler.addFilter(ExtensionContextLogFilter())
    logging.getLogger().addHandler(handler)

.. warning::

    The filter **must** be added to the **handler**, not the logger.
    Logger-level filters are only checked in ``Logger.handle()``, which is
    **not** called when a child logger's record propagates up via
    ``callHandlers()``.  Handler-level filters are checked in
    ``Handler.handle()``, which runs for every record regardless of origin.

The following attributes are added to the ``LogRecord`` only when inside an
extension context:

    - ``ext_is_extension``      (str): ``"true"``
    - ``ext_extension_type``    (str): ``"tool"`` | ``"instruction"`` | ``"hook"``
    - ``ext_capability_id``     (str): capability identifier (usually ``"default"``)
    - ``ext_extension_id``      (str): UUID of the extension
    - ``ext_extension_name``    (str): human-readable extension name
    - ``ext_extension_version`` (str): extension version
    - ``ext_item_name``         (str): raw tool name or hook name
"""

import logging

from opentelemetry import baggage, context

# Mapping: OTel baggage key -> LogRecord attribute name
_BAGGAGE_FIELDS = [
    ("sap.extension.isExtension", "ext_is_extension"),
    ("sap.extension.extensionType", "ext_extension_type"),
    ("sap.extension.capabilityId", "ext_capability_id"),
    ("sap.extension.extensionId", "ext_extension_id"),
    ("sap.extension.extensionName", "ext_extension_name"),
    ("sap.extension.extensionVersion", "ext_extension_version"),
    ("sap.extension.extension.item.name", "ext_item_name"),
]


class ExtensionContextLogFilter(logging.Filter):
    """Injects ``sap.extension.*`` OTel baggage values into log records.

    Attributes are only set when the ``sap.extension.isExtension`` baggage
    value is present and truthy, so non-extension log records remain clean.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = context.get_current()
        is_extension = baggage.get_baggage("sap.extension.isExtension", context=ctx)
        if is_extension:
            for baggage_key, attr_name in _BAGGAGE_FIELDS:
                value = baggage.get_baggage(baggage_key, context=ctx)
                setattr(record, attr_name, value or "")
        return True
