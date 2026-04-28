"""Extension capability definitions for agent extensibility.

This module defines the extension capability that allows customers to extend
this agent with additional tools and/or instructions.

The EXTENSION_CAPABILITIES list is used to build A2A AgentExtension objects
that are included in the agent card's capabilities.
"""

from sap_cloud_sdk.extensibility import (
    ExtensionCapability,
    Tools,
    ToolAdditions,
    HookCapability,
    HookType,
)

# Hooks available for this agent extension.
# Hooks are imported from sap_cloud_sdk.extensibility — no local dataclass needed.

PRE_HOOK = HookCapability(
        type=HookType.BEFORE,
        id="agent_pre_hook",
        display_name="Before Hook",
        description="Executed before the main agent logic runs.",
    )

POST_HOOK = HookCapability(
        type=HookType.AFTER,
        id="agent_post_hook",
        display_name="After Hook",
        description="Executed after the main agent logic runs.",
    )

# Extension capability definition for this agent
EXTENSION_CAPABILITIES: list[ExtensionCapability] = [
    ExtensionCapability(
        display_name="Default",
        description="{{EXTENSION_DESCRIPTION}}",
        instruction_supported={{INSTRUCTION_SUPPORTED}},
        tools=Tools(additions=ToolAdditions(enabled={{TOOL_ADDITIONS_ENABLED}})),
        supported_hooks={{SUPPORTED_HOOKS}},
    ),
]