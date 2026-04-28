---
name: sap-agent-extensibility
description: >
  Add end-to-end extensibility to an A2A agent: define extension capabilities,
  add telemetry instrumentation, and implement runtime instructions, tools and hooks
  loading. Use when making an agent extensible by customers with additional
  tools and/or instructions and/or hooks.
compatibility: >
  Requires Python 3.11+, sap-cloud-sdk and opentelemetry-api.
metadata:
  author: sap
  version: "1.0"
---

# Agent Extensibility

Read [references/extension-model.md](references/extension-model.md)
for the data model (composition hierarchy, A2A card schema, tool metadata,
namespacing, hooks and constraints).

This skill makes an existing A2A agent fully extensible so that customers can
extend it with additional **tools** (via MCP servers), **instructions**
(injected into the system prompt) and/or **hooks** — with zero code changes for each new extension.

The skill has **three phases** that must be executed in order. Phases 2 and 3
are **conditional** based on the user's choices in Phase 1 (tools, instructions, hooks
or any combination of the 3):

1. **Phase 1 — Define Extension Capabilities**: Register extension capabilities
   in the agent card so the platform can discover them.
2. **Phase 2 — Add Telemetry Instrumentation** _(tools only)_: Generate
   instrumented wrapper functions that add OpenTelemetry span attributes for
   extension tool tracking. **Skip if tool extensibility is not enabled.**
3. **Phase 3 — Implement Runtime Extension Loading**: Wire up runtime fetching
   of extensions and integrate them into the agent's execution loop. Steps
   within this phase are conditional on which extension types are enabled.

---

## Prerequisites

Before running this skill, ensure the SDK dependency is installed and the ORD endpoint is configured.

### Verify SDK Dependency

Ensure the project depends on the SAP Cloud SDK **extensibility contrib build**.
This is a special pre-release build of `sap-cloud-sdk` that adds
`build_extension_capabilities()`, `create_client()` / `ExtensibilityClient`,
and the `extension_context` context manager used throughout all three phases.

> **Important**: The extensibility contrib build is a **pre-release** version.
> Package managers require explicit opt-in to install pre-release versions.

#### For `requirements.txt` projects (pip)

pip cannot resolve PEP 440 **local version segments** (`+...`) from Simple API
indices. Use a **direct URL reference** (PEP 440 §4) to the wheel on
Artifactory instead of a version pin:

```
sap-cloud-sdk @ https://common.repositories.cloud.sap/artifactory/api/pypi/application-foundation-sdk-python/sap-cloud-sdk/0.6.1.dev20260410+contribs.sapphire.internal.testing.42f21d5/sap_cloud_sdk-0.6.1.dev20260410+contribs.sapphire.internal.testing.42f21d5-py3-none-any.whl
```

Because the URL points to a private Artifactory, pip needs credentials for the
download. In a `Dockerfile`, create a `.netrc` file alongside `pip.conf` so
that both index lookups and direct URL downloads are authenticated:

```dockerfile
RUN pip install --no-cache-dir --upgrade pip && \
    mkdir -p /root/.pip && \
    printf "[global]\nindex-url = https://%s:%s@common.repositories.cloud.sap/artifactory/api/pypi/application-foundation-sdk-python/simple\nextra-index-url = https://pypi.org/simple\n" \
    "$ARTIFACTORY_USER" "$ARTIFACTORY_TOKEN" > /root/.pip/pip.conf && \
    printf "machine common.repositories.cloud.sap\nlogin %s\npassword %s\n" \
    "$ARTIFACTORY_USER" "$ARTIFACTORY_TOKEN" > /root/.netrc && \
    chmod 600 /root/.netrc && \
    pip install --no-cache-dir --pre -r requirements.txt && \
    rm -rf /root/.pip /root/.netrc
```

> **Why not `==` version pinning?** pip's Simple API client strips local
> version segments during index queries, so it never sees the
> `+contribs-sapphire-internal-testing.*` build even with `--pre`. uv does not have this
> limitation.

> **Note**: The `--index-url` path `application-foundation-sdk-python` is the
> name of the **Artifactory repository**, not a pip package. The actual pip
> package is `sap-cloud-sdk`.

#### For `pyproject.toml` projects (uv)

```bash
uv add sap-cloud-sdk==0.6.1.dev20260410+contribs-sapphire-internal-testing.42f21d5 --index https://common.repositories.cloud.sap/artifactory/api/pypi/application-foundation-sdk-python/simple/
```

This adds the dependency to `pyproject.toml` and registers the SAP Artifactory PyPI index. The resulting `pyproject.toml` entries will look like:

```toml
dependencies = [
    "sap-cloud-sdk==0.6.1.dev20260410+contribs-sapphire-internal-testing.42f21d5"
]

[[tool.uv.index]]
name = "application-foundation-sdk-python"
url = "https://common.repositories.cloud.sap/artifactory/api/pypi/application-foundation-sdk-python/simple/"
```

This specific version provides the `extension_context` context manager,
`build_extension_capabilities()`, and `client.get_extension_capability_implementation()`
used throughout all three phases (where `client = create_client()`).

`uv` handles pre-release versions automatically when an exact `==` pin is
used, so no extra flags are needed.

> **Important**: If the project uses a `uv.lock` lockfile and the container
> build uses `uv sync --frozen`, you **must** run `uv lock` after modifying
> `pyproject.toml` to regenerate the lockfile. Without this, the frozen build
> will install the old SDK version from the stale lockfile, causing
> `ImportError` at runtime.

### Discover ORD Configuration

1. **Read the `sap-agent-ord-endpoint` skill** (`.claude/skills/sap-agent-ord-endpoint/SKILL.md`) to understand:
   - The current ORD document structure
   - Expected file locations for ORD documents
   - How to identify ORD documents with an `agents` section

2. **Inspect the agent's ORD implementation** based on the skill's guidance.

3. **If the ORD skill doesn't help locate the files**, search the `app/` directory for:
   - ORD route files (e.g., files containing `open-resource-discovery` routes)
   - ORD document files (e.g., JSON files with `"openResourceDiscovery"` or `"agents"` sections)
   - **Dynamic ORD builders**: if no static JSON files are found, search for a Python function or dict that constructs the ORD response inline (e.g., a function named `build_ord_response`, or a route handler that returns a dict containing an `"agents"` key). The inline Python dict **is** the ORD document — patch the `labels` key within it directly rather than editing a JSON file.

### Verify ORD Requirements

Confirm **both** of the following:

- ORD endpoint is configured (routes exist to serve ORD documents)
- At least one ORD document exists with an `agents` section

**Note the locations of all ORD documents for Phase 1, Step 5.**

### If ORD is NOT configured:

> **Stop**: Inform the user that this skill cannot proceed without a configured
> ORD endpoint. Suggest that they can run the `sap-agent-ord-endpoint` skill
> separately to set up ORD, and then return to this skill afterward.
> Do **not** invoke the `sap-agent-ord-endpoint` skill from within this skill.

**If both requirements are met, proceed to Phase 1.**

---

## Phase 1 — Define Extension Capabilities

This phase adds an extension capability to the agent so that it is exposed in
the agent card's `capabilities.extensions` field, making it discoverable by the
platform.

### Step 1: Gather Configuration (REQUIRED — DO NOT SKIP)

**You MUST ask the user these three questions and wait for their response before proceeding:**

Ask the user:

1. "Should customers be able to extend the agent with additional tools?"
2. "Should customers be able to provide additional instructions?"
3. "Should customers be able to extend the agent with hooks?"

Provide options: `["Yes", "No"]` for each question.

**Important:**
- Do NOT proceed to Step 2 until the user has answered all 3 questions
- Do NOT assume defaults without explicitly asking
- If the user says "use defaults" or similar, then use: tools=yes, instructions=yes, hooks=yes

### Step 2: Inspect Existing Agent

Read `app/main.py` to understand:

- The agent's name and description (for customizing the extension capability description)
- The current `AgentCapabilities` configuration
- Verify the agent has the expected project structure (e.g., `app/main.py` as the
  entrypoint with `AgentCapabilities` configuration)
- Check if the `AgentCapabilities` instantiation already includes an `extensions=`
  parameter. If present, note the existing extensions — they will need to be
  preserved in Step 4b unless they are Extension Capability entries (identifiable
  by the URI prefix `urn:sap:extension-capability:v1:`), which will be replaced
  by the new configuration.

### Step 3: Create or patch extension_capabilities.py

**Check whether the file already exists:**

```bash
ls app/extension_capabilities.py
```

---

#### Case A — File does not exist (fresh setup)

Copy the template and customize it:

```bash
cp .claude/skills/sap-agent-extensibility/templates/extension_capabilities.py app/extension_capabilities.py
```

Then replace the placeholders:

| Placeholder                 | Value                                                    |
| --------------------------- | -------------------------------------------------------- |
| `{{TOOL_ADDITIONS_ENABLED}}`| `True` or `False` based on user input                    |
| `{{INSTRUCTION_SUPPORTED}}` | `True` or `False` based on user input                    |
| `{{EXTENSION_DESCRIPTION}}` | Customized based on agent purpose                        |
| `{{SUPPORTED_HOOKS}}`       | `[PRE_HOOK, POST_HOOK]` if hooks enabled, otherwise `[]` |

#### Case B — File already exists

**Do NOT overwrite the file.** Instead:

1. **Read the template** at `.claude/skills/sap-agent-extensibility/templates/extension_capabilities.py`
2. **Read the existing file** at `app/extension_capabilities.py`
3. **Diff them** — identify what is present in the template but missing from the existing file based on what the user has enabled
4. **Apply only the missing parts** as minimal surgical edits — do not touch anything already present

Common things that may need adding:

- A missing import (e.g. `HookCapability`, `Tools`, `ToolAdditions`):

```python
from sap_cloud_sdk.extensibility import HookCapability, HookType
```

- Missing constants (e.g. `PRE_HOOK`, `POST_HOOK`) — insert before `EXTENSION_CAPABILITIES`:

```python
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
```

- A field not yet set in the `ExtensionCapability(...)` block (e.g. `supported_hooks`, `tools`, `instruction_supported`) — patch **only that field**, leave all others untouched:

```python
# Before:
supported_hooks=[]

# After:
supported_hooks=[PRE_HOOK, POST_HOOK]
```

If the user's answers from Step 1 imply a description update is appropriate, ask them first before changing `description`.

### Step 4: Patch main.py

#### 4a. Add imports (after existing imports, before the main function)

```python
from sap_cloud_sdk.extensibility import build_extension_capabilities, create_client
from extension_capabilities import EXTENSION_CAPABILITIES
```

#### 4b. Modify AgentCapabilities

Find the `AgentCapabilities` instantiation and set the `extensions` parameter
using a **merge-safe** approach. The `capabilities.extensions` list on the A2A
agent card is a shared list — other processes may add their own
`AgentExtension` entries with different URIs (e.g., data-only extensions,
profile extensions). Extension Capability entries are identifiable by the URI
prefix `urn:sap:extension-capability:v1:`.

**Case 1 — No existing `extensions` parameter:**

Simply add the parameter:

**Before:**

```python
capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
```

**After:**

```python
capabilities=AgentCapabilities(
    streaming=True,
    pushNotifications=False,
    extensions=build_extension_capabilities(EXTENSION_CAPABILITIES),
),
```

**Case 2 — Existing `extensions` parameter present:**

Preserve any non-Extension-Capability entries (entries whose `uri` does **not**
start with `urn:sap:extension-capability:v1:`) and replace any existing
Extension Capability entries with the new ones. Add a helper function and
constant in `extension_capabilities.py` (alongside the existing
`EXTENSION_CAPABILITIES`):

```python
from a2a.types import AgentExtension

_EXTENSION_CAPABILITY_URI_PREFIX = "urn:sap:extension-capability:v1:"


def merge_extensions(
    existing: list[AgentExtension],
    capability_extensions: list[AgentExtension],
) -> list[AgentExtension]:
    """Merge extension capability entries into an existing extensions list.

    Preserves non-Extension-Capability entries (other URI prefixes) and
    replaces any existing Extension Capability entries with the new ones.
    """
    other = [
        ext for ext in existing
        if not ext.uri.startswith(_EXTENSION_CAPABILITY_URI_PREFIX)
    ]
    return other + capability_extensions
```

Then import and use it in the `AgentCapabilities` instantiation in `main.py`:

```python
from extension_capabilities import EXTENSION_CAPABILITIES, merge_extensions
```

```python
capabilities=AgentCapabilities(
    streaming=True,
    pushNotifications=False,
    extensions=merge_extensions(
        existing_extensions,
        build_extension_capabilities(EXTENSION_CAPABILITIES),
    ),
),
```

Where `existing_extensions` is the current value of the `extensions` parameter.
If the existing extensions are defined inline, extract them into a variable
first.

### Step 5: Update ORD Documents with isExtensible Label

For each ORD document identified in Prerequisites that contains an `agents` section, add `"isExtensible": ["true"]` to the `agents[0].labels` object:

**Before:**

```json
"labels": {
  "interactionMode": ["conversational"]
}
```

**After:**

```json
"labels": {
  "interactionMode": ["conversational"],
  "isExtensible": ["true"]
}
```

### Step 6: Bump ORD Versions for UMS (Conditional)

> **Why this matters:** Adding extensibility changes the agent card content
> (served as an `a2a-agent-card` blob referenced in
> `apiResources[0].resourceDefinitions`) and adds a label to the agent
> resource. UMS uses version fields during aggregation to determine whether
> it needs to re-fetch resources. Without a version bump, UMS will **not**
> pick up the changes made in Steps 4 and 5.

**Ask the user** whether the agent is already registered in UMS:

> "Is this agent already registered in UMS? (i.e., has it been deployed and
> aggregated by UMS before?)"
>
> Options: `["Yes", "No"]`

- If **No** — skip this step. The initial versions are correct for first
  deployment.
- If **Yes** — perform both version bumps below.

#### 6a. Bump the A2A API resource version

For each ORD document, find the entry in the `apiResources` array where
`"apiProtocol": "a2a"`. This is the entry whose `resourceDefinitions`
contains the `a2a-agent-card` blob. Read its current `version` value,
parse it as semver, and increment the **patch** component.

This is **mandatory**. The agent card is an `a2a-agent-card` blob in
`resourceDefinitions`, and bumping the API resource version is the **only**
mechanism that guarantees the ORD aggregator will re-fetch it.

> **Important:** Only bump the A2A API resource — do **not** modify the
> version of other API resources in the `apiResources` array.

**Before:**

```json
{
  "ordId": "...",
  "apiProtocol": "a2a",
  "version": "1.0.0",
  "resourceDefinitions": [
    { "type": "a2a-agent-card", ... }
  ],
  ...
}
```

**After:**

```json
{
  "ordId": "...",
  "apiProtocol": "a2a",
  "version": "1.0.1",
  "resourceDefinitions": [
    { "type": "a2a-agent-card", ... }
  ],
  ...
}
```

#### 6b. Bump `agents[0].version`

For each ORD document that contains an `agents` section, read the current
`version` value, parse it as semver, and increment the **patch** component.

The `isExtensible` label added in Step 5 is ORD information on the agent
resource. The ORD spec states that the version "SHOULD be changed if the
ORD information or referenced resource definitions changed." Labels are ORD
information, so the agent version must be bumped.

**Before:**

```json
"agents": [
  {
    "ordId": "...",
    "version": "1.0.0",
    ...
  }
]
```

**After:**

```json
"agents": [
  {
    "ordId": "...",
    "version": "1.0.1",
    ...
  }
]
```

#### Consistency

Both `document-system-version.json` and `document-system-instance.json`
(and any other ORD documents with `agents`/`apiResources` sections) must
receive the same version bumps to stay in sync.

### Step 7: Verify

Confirm:

1. `app/extension_capabilities.py` exists with correct configuration
2. `app/main.py` imports `EXTENSION_CAPABILITIES` and `build_extension_capabilities`
3. `AgentCapabilities` includes `extensions=` with the result of `build_extension_capabilities(EXTENSION_CAPABILITIES)` — either assigned directly (Case 1) or merged via `merge_extensions()` (Case 2)
4. If pre-existing non-Extension-Capability extensions were present on `AgentCapabilities` (entries whose `uri` does not start with `urn:sap:extension-capability:v1:`), verify they are preserved in the merged `extensions` list
5. All ORD documents with an `agents` section contain `"isExtensible": ["true"]` in the labels
6. (If agent is already in UMS) The A2A API resource version (the `apiProtocol: "a2a"` entry in `apiResources`) has been incremented in all ORD documents
7. (If agent is already in UMS) `agents[0].version` has been incremented in all ORD documents

### Project Structure After Phase 1

```
app/
  main.py                    <- patched with extension capability integration
  extension_capabilities.py  <- new: extension capability definitions
  agent_executor.py
  agent.py
  ...
```

### Example Configurations

See [references/examples.md](references/examples.md) for full extensibility
(tools + instructions + hooks), tools-only, instructions-only and hooks-only configurations.

---

## Phase 2 — Add Telemetry Instrumentation

> **Condition**: This phase applies **only when tool additions are enabled**
> (`tool_additions_enabled=True` in `extension_capabilities.py`). The
> telemetry module instruments MCP tool calls — if the agent is extensible
> via instructions only, there are no tool calls to instrument.
> **Skip to Phase 3 if tools are not enabled.**

This phase provides instrumented wrapper functions and a toolset
for extension tool calls. When extension tools are invoked through these
wrappers, OpenTelemetry span attributes are automatically added to track
extension usage.

### How Telemetry Works

The wrapper functions use the `extension_context` context manager from the
SAP Cloud SDK for Python to set OTel **baggage** (propagated to downstream
services via HTTP headers). In addition, the wrappers **explicitly set span
attributes** on the agent's own spans, because baggage alone is not recorded
on agent-side traces. This dual approach ensures extension metadata is visible
both in downstream MCP server traces (via baggage) and in the agent's own
traces in your observability platform (Jaeger, Dynatrace, Grafana, etc.).

Each wrapper creates a dedicated named span (e.g., `extension_tool <name>`)
with the following attributes:

| Attribute                            | Type      | Description                                                                        |
| ------------------------------------ | --------- | ---------------------------------------------------------------------------------- |
| `sap.extension.isExtension`          | `boolean` | Always `True` for extension calls                                                  |
| `sap.extension.extensionType`        | `string`  | Extension type: `"tool"`, `"instruction"`, or `"hook"`                             |
| `sap.extension.capabilityId`         | `string`  | Extension capability name (e.g. `"default"`)                                       |
| `sap.extension.extensionId`          | `string`  | UUID of the extension (resolved per-tool/hook from `source_mapping`)               |
| `sap.extension.extensionName`        | `string`  | Human-readable name of the extension (e.g. `"ap-invoice-extension"`)               |
| `sap.extension.extensionVersion`     | `string`  | Version of the extension (e.g. `"2"`)                                              |
| `sap.extension.extension.item.name`  | `string`  | Raw MCP tool name or hook name (e.g. `"validate_tax"`, `"Pre Invoice Hook"`)       |

These attributes enable filtering and analysis of extension usage in your
observability platform.

#### Execution Summary Span

In addition to per-call spans, the telemetry library provides
`emit_extensions_summary_span()` to emit a sibling
`agent_extensions_summary` span with aggregate metrics for one agent
execution. This span sits alongside (not as a parent of) the individual
`extension_tool` / `extension_hook` spans and is emitted once at the end
of the agent's `execute()` method.

| Attribute                                      | Type      | Description                                                        |
| ---------------------------------------------- | --------- | ------------------------------------------------------------------ |
| `sap.extension.summary.totalOperationCount`    | `int`     | Total extension operations (tool calls + hook calls + instruction) |
| `sap.extension.summary.totalDurationMs`        | `float`   | Wall-clock sum (ms) of all extension operations (hooks + tools)    |
| `sap.extension.summary.toolCallCount`          | `int`     | Actual extension tool calls made (not registered tool names)       |
| `sap.extension.summary.hookCallCount`          | `int`     | Number of hook calls executed (pre + post)                         |
| `sap.extension.summary.hasInstruction`         | `boolean` | Whether an extension instruction was injected into the prompt      |

### Telemetry Prerequisites

1. **Auto-instrumentation**: OpenTelemetry auto-instrumentation is initialized
   in your agent (see `sap-agent-instrumentation` skill)

2. **OpenTelemetry API**: `opentelemetry-api` is installed (typically already
   present via `auto_instrument()`)

3. **JSON logging library**: `python-json-logger>=3.3.0` is installed for
   structured JSON log output. This is required for Kyma's log pipeline to
   parse extension log attributes into `log.attributes.*` fields.

   ```bash
   pip install "python-json-logger>=3.3.0"
   ```

   Or with `uv`:

   ```bash
   uv add "python-json-logger>=3.3.0"
   ```

   > Remember to run `uv lock` after adding dependencies if the project uses
   > a lockfile with `uv sync --frozen` in the container build.

### Step 1: Ensure OpenTelemetry auto-instrumentation is present

Check `app/main.py` (or the agent's main entrypoint) for an existing
`auto_instrument()` call. Bootstrapped agents and agents that have run the
`sap-agent-instrumentation` skill will already have this.

**If `auto_instrument()` is already present** — skip to Step 2.

**If `auto_instrument()` is NOT present** — add the following to the **top of
the main entrypoint**, **before** any AI framework imports (PydanticAI,
LiteLLM, etc.):

```python
from sap_cloud_sdk.core.telemetry import auto_instrument
auto_instrument()
```

> `auto_instrument()` must be called before importing AI frameworks so that
> their HTTP clients and other internals are patched by OpenTelemetry. See the
> `sap-agent-instrumentation` skill for advanced instrumentation scenarios
> (custom spans, manual token tracking, etc.).

Without auto-instrumentation, no spans will be emitted and the extension
telemetry attributes added by the wrappers below will have nowhere to attach.

### Step 2: Copy the telemetry library

Copy the bundled extension telemetry library into your application source
directory. Only copy the **core files** and the **framework-specific module**
that matches the agent's AI framework — do not copy modules for other
frameworks.

#### Core files (always required)

```bash
mkdir -p app/extension_telemetry
SRC=.claude/skills/sap-agent-extensibility/templates/extension_telemetry
cp "$SRC/__init__.py" "$SRC/log_filter.py" "$SRC/wrappers.py" app/extension_telemetry/
```

#### Framework-specific file (copy exactly ONE)

| Agent framework      | File to copy                                                              |
| -------------------- | ------------------------------------------------------------------------- |
| **PydanticAI**       | `cp "$SRC/_pydantic_ai.py" "$SRC/toolset.py" app/extension_telemetry/`   |
| **LangChain**        | `cp "$SRC/_langchain.py" app/extension_telemetry/`                        |
| **OpenAI Agents SDK**| `cp "$SRC/_openai_agents.py" app/extension_telemetry/`                    |

> **Why selective copy?** The templates directory contains modules for every
> supported framework. Copying all of them adds unnecessary files that will
> never be imported. The `__init__.py` uses lazy imports, so missing modules
> do not cause errors — they simply raise a clear `ImportError` if someone
> tries to access a name from an uninstalled framework.

The library **must** be placed inside the application directory (e.g., `app/`)
so that it is included in container images without requiring Dockerfile changes.
Do **not** place it at the project root as a sibling of `app/` — this causes
deployment failures because the directory won't be copied into the container.

Expected structure (PydanticAI example):

```
app/
├── agent.py
├── main.py
├── extension_telemetry/
│   ├── __init__.py
│   ├── log_filter.py         # ExtensionContextLogFilter (OTel baggage → LogRecord)
│   ├── wrappers.py          # Framework-agnostic (generic MCP SDK)
│   ├── _pydantic_ai.py      # PydanticAI InstrumentedToolset
│   └── toolset.py           # Backward-compat shim (re-exports _pydantic_ai)
├── ...
```

For LangChain agents, replace `_pydantic_ai.py` + `toolset.py` with
`_langchain.py`. For OpenAI Agents SDK agents, use `_openai_agents.py`
instead.

The framework-specific modules use **lazy imports** — importing the package
never fails regardless of which files are present. Users only hit an
`ImportError` when they reference a name that requires a framework module
that wasn't copied, with a clear error message indicating which package to
install.

Since agents run with `app/` as the working directory (or on `sys.path`),
the import `from extension_telemetry import ...` works without any
`sys.path` manipulation.

### Step 3: Replace direct MCP calls with instrumented wrappers

For agents that call MCP tools directly (not through a framework's built-in
toolset mechanism), replace direct calls with the instrumented wrapper
functions.

#### Before (without telemetry):

```python
# Direct MCP tool call - no telemetry
result = await mcp_client.call_tool(tool_name, args)
```

#### After (with telemetry):

```python
from extension_telemetry import call_extension_tool

# Instrumented call - adds telemetry attributes + baggage
result = await call_extension_tool(mcp_client, tool_info, args)
```

### Step 3b: For PydanticAI agents — Use InstrumentedToolset

PydanticAI agents use the toolset mechanism (`.filtered()`, `.prefixed()`)
which handles MCP tool calls internally. To add telemetry, wrap the
filtered+prefixed toolset with `InstrumentedToolset`:

```python
from extension_telemetry import InstrumentedToolset

# After filtering and prefixing the MCP server toolset:
filtered_server = mcp_server.filtered(
    lambda _ctx, tool_def, _allowed=allowed_names: tool_def.name in _allowed
)
prefixed_server = filtered_server.prefixed(server.tool_prefix)

# Wrap with telemetry instrumentation
instrumented_server = InstrumentedToolset(
    wrapped=prefixed_server,
    extension_name=ext_impl.extension_name,
    tool_prefix=server.tool_prefix,
    capability="default",
    source_mapping=ext_impl.source.tools if ext_impl.source else None,
)
toolsets.append(instrumented_server)
```

This creates an `extension_tool <prefixed_name>` span with all seven
`sap.extension.*` attributes for every tool call.

### Step 3c: For LangChain / LangGraph agents — Use wrap_tool_with_telemetry

LangChain agents using `langchain-mcp-adapters` get tools via
`client.get_tools()`. Wrap each tool with telemetry after filtering:

```python
from extension_telemetry import wrap_tool_with_telemetry

# After filtering and prefixing MCP tools:
for tool in filtered_tools:
    wrap_tool_with_telemetry(
        tool,
        extension_name=ext_impl.extension_name,
        source_mapping=ext_impl.source.tools if ext_impl.source else None,
        tool_prefix=server.tool_prefix,
    )
```

This monkey-patches each tool's `invoke` and `ainvoke` methods to create an
`extension_tool <name>` span with `sap.extension.*` attributes and sets
OTel baggage for downstream propagation. Both sync and async paths are
patched because LangGraph's `create_react_agent` uses `ainvoke` internally.

### Step 3d: For OpenAI Agents SDK — Use create_instrumented_tool_filter

The OpenAI Agents SDK uses `tool_filter` on MCP server constructors. Use
`create_instrumented_tool_filter` which combines filtering and telemetry:

```python
from extension_telemetry import create_instrumented_tool_filter

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
```

This replaces `create_static_tool_filter` — it filters to allowed tools
**and** adds telemetry in a single step.

### Step 4: Configure Extension Log Attributes

The telemetry wrappers emit `logger.info()` calls inside the
`extension_context()` block (e.g., `"Calling extension tool: <name>"`).
The bundled `ExtensionContextLogFilter` reads the seven `sap.extension.*`
OTel baggage values from the current context and injects them as `ext_*`
attributes on Python `LogRecord` objects. Combined with a JSON formatter,
these attributes are serialised into each JSON log line and **automatically
promoted** to `log.attributes.*` by Kyma's Fluent Bit log pipeline — making
them queryable in SAP Cloud Logging (OpenSearch) without any pod annotations.

| Log Attribute            | Value                                                       |
| ------------------------ | ----------------------------------------------------------- |
| `ext_is_extension`       | `"true"`                                                    |
| `ext_extension_type`     | `"tool"` | `"instruction"` | `"hook"`                       |
| `ext_capability_id`      | `"default"`                                                 |
| `ext_extension_id`       | Extension UUID                                              |
| `ext_extension_name`     | Extension name (e.g., `"invoice-tax-validation-extension"`) |
| `ext_extension_version`  | Extension version (e.g., `"2"`)                             |
| `ext_item_name`          | Raw tool name or hook name                                  |

#### Determine Current Logging Setup

Inspect the agent's main entrypoint (typically `app/main.py`) and determine
which case applies:

**Case 1 — `logging.basicConfig()` only (bootstrap default):**

Most agents bootstrapped with `sap-agent-bootstrap` have only:

```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

Replace with a direct JSON handler setup:

```python
from pythonjsonlogger.json import JsonFormatter
from extension_telemetry.log_filter import ExtensionContextLogFilter

# Configure structured JSON logging so Kyma's log pipeline can parse each line
# and promote JSON keys into OTLP log.attributes.*.  The
# ExtensionContextLogFilter adds ext_* fields to the LogRecord only when inside
# an extension_context() block; the JSON formatter serialises them automatically.
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

json_formatter = JsonFormatter(
    fmt="%(levelname)s %(name)s %(message)s",
    rename_fields={"levelname": "level"},
)
json_handler = logging.StreamHandler()
json_handler.setFormatter(json_formatter)
# CRITICAL: Add the filter to the *handler*, not the logger.
# Logger-level filters are only checked in Logger.handle(), which is NOT called
# when a child logger's record propagates up via callHandlers().  Handler-level
# filters are checked in Handler.handle(), which runs for every record.
json_handler.addFilter(ExtensionContextLogFilter())
root_logger.addHandler(json_handler)

logger = logging.getLogger(__name__)
```

**Case 2 — Custom handler chain already exists:**

If the agent already has custom `logging.Handler` instances (e.g., a
`RotatingFileHandler`, a custom `StreamHandler`, etc.), do NOT replace them.
Instead, add `ExtensionContextLogFilter` to **each existing handler**:

```python
from extension_telemetry.log_filter import ExtensionContextLogFilter

ext_filter = ExtensionContextLogFilter()
for handler in logging.getLogger().handlers:
    handler.addFilter(ext_filter)
```

> **Note**: `ext_*` attributes only appear in log output if the handler's
> formatter serialises extra `LogRecord` attributes. JSON formatters (like
> `python-json-logger`) do this automatically. Plain-text formatters (the
> default `logging.Formatter`) do **not** — they will silently ignore the
> extra attributes. If you need `ext_*` in logs but cannot switch to JSON
> formatting, create a custom `Formatter` that reads these attributes from the
> `LogRecord`.

**Case 3 — No logging setup at all:**

Add `logging.basicConfig(level=logging.INFO)` first, then apply Case 1.

#### Why Handler-Level, Not Logger-Level

The filter **must** be added to the **handler**, not the logger
(`root_logger.addFilter(...)` does **not** work).

When a child logger (e.g., `extension_telemetry._langchain`) emits a record,
it propagates to the root logger via `callHandlers()`. `callHandlers()`
calls `handler.handle()` on each handler in the chain — but it does **not**
call `root.handle()`, so root logger-level filters are **never invoked** for
propagated records. Handler-level filters run in `Handler.handle()` for
every record regardless of origin.

### Step 5: Verify telemetry in traces

After integrating the wrappers, extension calls will appear in your traces
with dedicated spans carrying `sap.extension.*` attributes. You can:

- **Filter traces** by `sap.extension.isExtension = true` to see only
  extension-related spans
- **Group by extension** using `sap.extension.extensionName` to analyze usage
  per extension
- **Segment by type** using `sap.extension.extensionType` to compare tool vs
  instruction vs hook usage
- **Filter by capability** using `sap.extension.capabilityId`
- **Drill into versions** using `sap.extension.extensionVersion`
- **Identify specific tools/hooks** using `sap.extension.extension.item.name`

Example Dynatrace query:

```
fetch spans
| filter sap.extension.isExtension == true
| summarize count() by sap.extension.extensionName, sap.extension.extensionType
```

Example Dynatrace queries for the summary span:

```
# View aggregate extension metrics per execution:
fetch spans
| filter span.name == "agent_extensions_summary"
| fields sap.extension.summary.totalOperationCount,
         sap.extension.summary.totalDurationMs,
         sap.extension.summary.toolCallCount,
         sap.extension.summary.hookCallCount

# Alert on high extension overhead (> 5 seconds):
fetch spans
| filter span.name == "agent_extensions_summary"
| filter sap.extension.summary.totalDurationMs > 5000
```

Expected span hierarchy:

```
agent_run
  ├── extension_tool concur_receipts_get_receipt (sap.cloud_sdk.extension)
  │     ├── sap.extension.isExtension = true
  │     ├── sap.extension.extensionType = "tool"
  │     ├── sap.extension.capabilityId = "default"
  │     ├── sap.extension.extensionId = "a1b2c3d4-..."
  │     ├── sap.extension.extensionName = "Concur Receipts Extension"
  │     ├── sap.extension.extensionVersion = "2"
  │     ├── sap.extension.extension.item.name = "get_receipt"
  │     └── get_receipt.tool (opentelemetry.instrumentation.mcp)
  └── agent_extensions_summary (sap.cloud_sdk.extension)
        ├── sap.extension.summary.totalOperationCount = 1
        ├── sap.extension.summary.totalDurationMs = 523.4
        ├── sap.extension.summary.toolCallCount = 1
        ├── sap.extension.summary.hookCallCount = 0
        └── sap.extension.summary.hasInstruction = false
```

### Telemetry API Reference

All framework-specific wrappers are **lazy-loaded** — importing the
`extension_telemetry` package never fails. An `ImportError` with a helpful
message is raised only when a framework-specific name is accessed without the
corresponding framework installed.

`ExtensionContextLogFilter` and `ExtensionType` are always available (direct
imports — they only depend on `opentelemetry-api`).

#### `ExtensionContextLogFilter`

A `logging.Filter` subclass that reads `sap.extension.*` OTel baggage from
the current context and injects `ext_*` attributes onto `LogRecord` objects.

**Usage:** Add to each **handler** (not the logger) at startup:

```python
from extension_telemetry import ExtensionContextLogFilter

handler.addFilter(ExtensionContextLogFilter())
````

**Behavior:** When a log statement is emitted inside an `extension_context()`
block, the filter reads the seven baggage values and sets them as extra
attributes on the `LogRecord`. Outside any `extension_context()` block,
no `ext_*` attributes are added, keeping non-extension log lines clean.

**Log attributes added (inside extension context only):**

- `ext_is_extension`: `"true"`
- `ext_extension_type`: `"tool"`, `"instruction"`, or `"hook"`
- `ext_capability_id`: capability identifier (usually `"default"`)
- `ext_extension_id`: extension UUID
- `ext_extension_name`: human-readable extension name
- `ext_extension_version`: extension version
- `ext_item_name`: raw tool name or hook name

#### `InstrumentedToolset`

**PydanticAI** (requires `pydantic-ai`). A `WrapperToolset` subclass that
intercepts every `call_tool` invocation to add extension telemetry.

**Constructor parameters:**

- `wrapped`: The inner toolset (typically a filtered + prefixed MCP server)
- `extension_name`: `str` — Human-readable name of the extension
  (from `ext_impl.extension_name`)
- `tool_prefix`: `str` — The prefix applied by `.prefixed()` (without
  trailing underscore — PydanticAI adds the `_` separator automatically)
- `capability`: `str` — Extension capability name (default: `"default"`)
- `source_mapping`: `dict[str, Any] | None` — Optional mapping of prefixed
  tool names to source info dicts (from `ext_impl.source.tools`). Each
  value is a dict with `extensionName`, `extensionId`, and
  `extensionVersion` keys. When provided, all seven `sap.extension.*`
  attributes are resolved per-tool (default: `None`)

**Behavior:** For each `call_tool`, creates an `extension_tool <name>` span
with all seven `sap.extension.*` attributes. Also sets OTel baggage via
`extension_context` for downstream propagation. When `source_mapping` is
provided, resolves the extension name, id, and version for _this specific
tool_, falling back to `extension_name`.

#### `wrap_tool_with_telemetry(tool, extension_name, capability="default", source_mapping=None, tool_prefix="")`

**LangChain** (requires `langchain-core`). Wraps a LangChain tool's `invoke`
and `ainvoke` methods with extension telemetry. Both paths must be patched
because LangGraph's `create_react_agent` uses `ainvoke` internally when the
agent is called via `agent.ainvoke()`.

**Parameters:**

- `tool`: A LangChain `BaseTool` instance (from `langchain-mcp-adapters`)
- `extension_name`: Human-readable name of the extension
- `capability`: Extension capability name (default: `"default"`)
- `source_mapping`: `dict[str, Any] | None` — Optional mapping of prefixed
  tool names to source info dicts (from `ext_impl.source.tools`). Each
  value is a dict with `extensionName`, `extensionId`, and
  `extensionVersion` keys. When provided, all seven `sap.extension.*`
  attributes are resolved per-tool (default: `None`)
- `tool_prefix`: `str` — The Axle-provided tool prefix (e.g.,
  `"sap_mcp_servicenow_v1_"`). Used to reconstruct the key for
  `source_mapping` lookup since this function is called before the tool
  name is prefixed (default: `""`)

**Returns:** The same tool with its `invoke` and `ainvoke` methods wrapped.

**Behavior:** Creates an `extension_tool <name>` span with `sap.extension.*`
attributes and sets OTel baggage on every `invoke` or `ainvoke` call. When
`source_mapping` is provided, resolves the extension name, id, and version
for _this specific tool_, falling back to `extension_name`.

#### `create_instrumented_tool_filter(allowed_tool_names, extension_name, capability="default", source_mapping=None, tool_prefix="")`

**OpenAI Agents SDK** (requires `openai-agents`). Creates a tool filter that
combines allowlist filtering with telemetry instrumentation.

**Parameters:**

- `allowed_tool_names`: List of tool names to allow
- `extension_name`: Human-readable name of the extension
- `capability`: Extension capability name (default: `"default"`)
- `source_mapping`: `dict[str, Any] | None` — Optional mapping of prefixed
  tool names to source info dicts (from `ext_impl.source.tools`). Each
  value is a dict with `extensionName`, `extensionId`, and
  `extensionVersion` keys. When provided, all seven `sap.extension.*`
  attributes are resolved per-tool (default: `None`)
- `tool_prefix`: `str` — The Axle-provided tool prefix (e.g.,
  `"sap_mcp_servicenow_v1_"`). Used to reconstruct the key for
  `source_mapping` lookup since the filter receives the raw MCP tool
  name (before prefixing) (default: `""`)

**Returns:** An async callable compatible with `MCPServerStreamableHTTP`'s
`tool_filter` parameter.

**Behavior:** Filters tools to the allowed set and creates an
`extension_tool <name>` span with `sap.extension.*` attributes for each
allowed tool. When `source_mapping` is provided, resolves the extension name,
id, and version for _this specific tool_, falling back to `extension_name`.
Note: the span is created at filter time, not call time (see the OpenAI
Agents SDK reference for details on this limitation).

> **OpenAI Agents SDK limitation:** The `ContextVar`-based tool call
> duration captured by this filter reflects **filter evaluation time**, not
> actual tool execution time. The SDK's `Runner.run()` makes the real MCP
> calls later, outside any extension context. As a result,
> `sap.extension.summary.toolCallCount` will correctly count filter
> invocations (one per tool call), but tool durations in
> `sap.extension.summary.totalDurationMs` will only include filter overhead
> — not true tool execution time.

#### `call_extension_tool(mcp_client, tool_info, args, extension_name, capability="default", source_mapping=None, tool_prefix="")`

Calls an MCP tool with telemetry instrumentation.

**Parameters:**

- `mcp_client`: The MCP client session connected to the tool's server
- `tool_info`: Object with a `mcp_tool_name` attribute
- `args`: Dictionary of arguments to pass to the tool
- `extension_name`: Human-readable name of the extension
  (from `ext_impl.extension_name`)
- `capability`: Extension capability name (default: `"default"`)
- `source_mapping`: `dict[str, Any] | None` — Optional mapping of prefixed
  tool names to source info dicts (from `ext_impl.source.tools`). Each
  value is a dict with `extensionName`, `extensionId`, and
  `extensionVersion` keys. When provided, all seven `sap.extension.*`
  attributes are resolved per-tool (default: `None`)
- `tool_prefix`: `str` — The Axle-provided tool prefix (e.g.,
  `"sap_mcp_servicenow_v1_"`). Used to reconstruct the key for
  `source_mapping` lookup since `tool_info.mcp_tool_name` is the raw
  MCP tool name (before prefixing) (default: `""`)

**Returns:** The tool's response

**Span created:** `extension_tool <tool_name>`

**Telemetry attributes:**

- `sap.extension.isExtension`: `True` (boolean)
- `sap.extension.extensionType`: `"tool"`
- `sap.extension.capabilityId`: capability name
- `sap.extension.extensionId`: extension UUID (from source info)
- `sap.extension.extensionName`: extension name (or fallback `extension_name` param)
- `sap.extension.extensionVersion`: extension version number
- `sap.extension.extension.item.name`: raw MCP tool name

#### `emit_extensions_summary_span(*, tool_call_count, hook_call_count, has_instruction, total_duration_ms)`

Emits a sibling summary span with aggregate extension metrics for one agent
execution. The span is created via `start_span()` (not
`start_as_current_span`) and immediately ended, so it never becomes a parent
or alters the existing span hierarchy.

Call this **once** at the end of the agent's `execute()` method, after all
extension operations have completed.

**Parameters (keyword-only):**

- `tool_call_count`: `int` — Number of extension tool calls made
- `hook_call_count`: `int` — Number of hook calls executed (pre + post)
- `has_instruction`: `bool` — Whether an extension instruction was injected
- `total_duration_ms`: `float` — Wall-clock sum (milliseconds) of all
  extension operations, measured via `time.monotonic()`

**Returns:** `None`

**Span created:** `agent_extensions_summary`

**Summary attributes:**

- `sap.extension.summary.totalOperationCount`: `int` — total operations
  (`tool_call_count + hook_call_count + (1 if has_instruction else 0)`)
- `sap.extension.summary.totalDurationMs`: `float` — wall-clock sum in ms
- `sap.extension.summary.toolCallCount`: `int`
- `sap.extension.summary.hookCallCount`: `int`
- `sap.extension.summary.hasInstruction`: `boolean`

#### `reset_tool_call_metrics()`

Initialises a fresh `ContextVar` accumulator for tool call durations. Call
this at the **start** of `execute()`, before any hooks or `agent.run()`
invocations.

**Parameters:** None

**Returns:** `None`

#### `get_tool_call_metrics() -> tuple[int, float]`

Returns `(call_count, total_duration_ms)` since the last
`reset_tool_call_metrics()` call. The count reflects **actual tool calls
made** (not registered tool names), and the duration is the aggregate
wall-clock time in milliseconds. If `reset_tool_call_metrics` was never
called, returns `(0, 0.0)`.

**Parameters:** None

**Returns:** Tuple of `(int, float)` — call count and total duration in ms

---

## Phase 3 — Implement Runtime Extension Loading

This phase wires up the runtime fetching of extensions and integrates them
into the agent's execution loop. Which steps to implement depends on the
extension types enabled in Phase 1:

| Configuration | Steps to implement |
|---|---|
| Tools + Instructions + Hooks | Steps 1–6 (all) |
| Tools + Instructions | Steps 1–5 (skip Step 6) |
| Tools only | Steps 1, 2, 3, 5 (skip Steps 4, 6) |
| Instructions only | Steps 1, 2, 3, 4 (skip Steps 5, 6) |
| Hooks only | Steps 1, 2, 3, 6 (skip Steps 4, 5) |
| Tools + Hooks | Steps 1, 2, 3, 5, 6 (skip Step 4) |
| Instructions + Hooks | Steps 1, 2, 3, 4, 6 (skip Step 5) |

> **Important**: Check `extension_capabilities.py` from Phase 1 to determine
> which extension types are enabled (`instruction_supported`,
> `tool_additions_enabled`, and whether `supported_hooks` is non-empty).
> Only implement the steps relevant to the enabled extension types.

After integration, the agent receives
**custom instructions** (injected into the system prompt) and/or **MCP tool
servers** (added to the agent's tool loop) and/or **pre/post hooks**
(invoked around the agent's execution) from the Extensibility Service,
with zero code changes for each new extension.

### How It Works

The SAP Cloud SDK calls a single API endpoint. The response contains:

- **`instruction`** — an optional string to append to the agent's system prompt
- **`mcp_servers`** — a list of `McpServer` objects with their allowed tool
  names and prefix
- **`hooks`** — a list of `Hooks` objects with configuration

The agent fetches this once per request, merges it into its configuration,
and proceeds normally. If the service is unavailable, the agent falls back
to default behavior (graceful degradation).

### Step 1: Check Destination Service in `app.yaml`

Ensure `spec.requires` contains a destination service entry:

```yaml
spec:
  requires:
    - name: default
      service: destination
      plan: lite
```

### Step 2: Identify Extension Points

The extension capabilities defined in Phase 1 are already in the agent card.
Identify where in the agent's code the main execution loop(s) are located, as
there the agent needs to fetch the capabilities implementation from the SDK and
merge instructions/tools/hooks into the prompt, tool and hook loop.

Search the codebase for the agent's main execution loop(s):

- `agent.run(` / `agent.arun(` (PydanticAI)
- `chain.invoke(` / `chain.ainvoke(` (LangChain)
- `client.chat.completions.create(` (OpenAI SDK)
- `Runner.run(` (OpenAI Agents SDK)
- `execute(` (A2A `AgentExecutor` — hooks integrate here)

If there is uncertainty about where to integrate the extension capabilities, ask the user for clarification.

### Step 3: Create Client and Fetch Extension Data

#### 3a. Check for an existing client in `agent.py`

Before creating a new client, check whether `app/agent.py` (or the agent's main module) already creates an `ExtensibilityClient`. Search for:
- A module-level `create_client()` call (e.g. `client = create_client()` or `extensibility_client = create_client()`)
- An `__init__` assignment like `self.client = create_client()`

**If a client is already present**, import it from `agent.py` rather than creating a second one:

```python
# In agent_executor.py — reuse the client created in agent.py
from agent import client  # or whichever name is used
```

Then use that imported name everywhere a client is needed (capability lookup, hook calls, etc.). Skip the `create_client()` call entirely in `agent_executor.py`.

**If no client exists in `agent.py`**, create one in `agent_executor.py` as described below.

#### 3b. Create the client (only if not already present in `agent.py`)

At each extension point, create an `ExtensibilityClient` and call
`get_extension_capability_implementation()` on it. Use `get_extension_override()`
to extract any caller-supplied extension override from the A2A request context
so the extensibility backend returns the correct extension for each invocation:

```python
from sap_cloud_sdk.extensibility import create_client, get_extension_override

client = create_client()

# Inside the request handler where RequestContext is available:
override = get_extension_override(context)
ext_impl = client.get_extension_capability_implementation(
    capability_id="default",
    override=override,
)
# ext_impl.instruction — optional str
# ext_impl.mcp_servers — list of McpServer (with url, tool_names, tool_prefix, ord_id)
# ext_impl.hooks - list of Hook (with id, ord_id, type etc)
```

`get_extension_override()` reads the `extension_override` key from the A2A
request's `metadata` dict and returns an `ExtensionOverrides` TypedDict with
`extension_name_override`, `extension_version_override`, and `isolated` fields.
When no override metadata is present, all fields default to `None` / `False`.
The returned dict is passed directly to
`get_extension_capability_implementation()` via the `override` parameter.

`create_client()` builds the destination-backed HTTP transport. It raises
`ClientCreationError` if the destination service is unavailable.

By default, `create_client()` resolves a BTP destination named
`EXTENSIBILITY_SERVICE`. If the agent's destination has a different name,
pass an `ExtensibilityConfig`:

```python
from sap_cloud_sdk.extensibility import create_client, ExtensibilityConfig

client = create_client(
    config=ExtensibilityConfig(destination_name="my-agent-axle")
)
```

`client.get_extension_capability_implementation()` returns an
`ExtensionCapabilityImplementation` with an empty `mcp_servers` list on
failure — no try/except needed. The method is **synchronous**.

#### Client Lifecycle

Creating a client rebuilds the BTP Destination-backed transport, so create
the client **once at application startup** (module level or in the class
constructor) and reuse it for the lifetime of the process. Do not recreate
the client per request or per capability lookup call.

#### Override Extraction

`get_extension_override()` must be called where the A2A `RequestContext` is
available — typically in the agent executor's `execute()` method. The override
is then passed down to `get_extension_capability_implementation()`.

### Step 4: Add Instructions to the Agent's Prompt

> **Condition**: Perform this step only if `instruction_supported=True` in
> `extension_capabilities.py`. Skip if the agent is extensible via tools only.

If `ext_impl.instruction` is not `None`, incorporate it as a supplement
(never a replacement) to the existing system prompt. The approach depends on
the framework — see the framework-specific references below.

### Step 5: Add MCP Tools to the Agent Loop

> **Condition**: Perform this step only if `tool_additions_enabled=True` in
> `extension_capabilities.py`. Skip if the agent is extensible via
> instructions only.

If `ext_impl.mcp_servers` is not empty:

1. **Iterate** `ext_impl.mcp_servers` — each `McpServer` contains the URL,
   authorized tool names, prefix, and ORD ID
2. **Detect transport** — URLs ending in `/sse` use SSE, others use Streamable HTTP
3. **Connect** to each `server.url`
4. **Filter** each server's tools to only those in `server.tool_names`
5. **Prefix** tool names using `server.tool_prefix`
6. **Manage lifecycles** with `contextlib.AsyncExitStack`

See the framework-specific references for complete integration patterns:

- [references/pydantic-ai.md](references/pydantic-ai.md) — PydanticAI (built-in `.filtered()` + `.prefixed()`)
- [references/langchain.md](references/langchain.md) — LangChain / LangGraph (manual filtering)
- [references/openai-agents-sdk.md](references/openai-agents-sdk.md) — OpenAI Agents SDK (`create_static_tool_filter`)
- [references/generic-mcp-sdk.md](references/generic-mcp-sdk.md) — Generic Python with `mcp` SDK

### Step 6: Integrate Pre/Post Hooks

> **Condition**: Perform this step only if hooks are enabled (`supported_hooks`
> is non-empty in `extension_capabilities.py`). Skip if neither BEFORE nor
> AFTER hooks were requested.

Hooks wrap the agent's execution: BEFORE hooks run before the agent and may
enrich the incoming message or block the request; AFTER hooks run after the
agent and may transform the response. Hook logic is implemented directly
in `agent_executor.py`.

#### 6a. Assess patching strategy for `agent_executor.py`

> **Before making any edits**, check whether the existing `execute()` method already contains hook integration points (pre/post-hook loops).
> - **If hook structure is already present**: apply the changes below incrementally (add imports, patch `execute()`).
> - **If `execute()` has no prior hook structure** (e.g., a plain streaming loop with no hook calls): replace the entire file with the complete hooks example from the [Complete Example](#complete-example) section at the bottom of this skill. A full rewrite is safer than piecemeal edits when the existing structure diverges significantly from the hooks pattern.

#### 6b. Add imports in `agent_executor.py`

```python
import uuid
from a2a.types import Message, Part, TextPart, DataPart, InternalError
from a2a.utils.errors import ServerError
from a2a.utils.message import get_message_text
from sap_cloud_sdk.extensibility.exceptions import TransportError
```

> Only add imports that are not already present.

#### 6c. Ensure the `ExtensibilityClient` is available

First check whether the agent already exposes a client (see Step 3a). Then:

**If reusing a client from `agent.py`** (e.g. a module-level `client` or `extensibility_client`):

```python
from agent import client  # use the existing client — no create_client() here
from sap_cloud_sdk.extensibility import get_extension_override

# In __init__:
self.extensibility_client = client
```

**If creating a new client** (no existing client found in `agent.py`), add after `self.agent = ...`:

```python
from sap_cloud_sdk.extensibility import create_client, get_extension_override

# In __init__:
self.extensibility_client = create_client()
```

#### 6d. Implement the full pipeline in `execute()`

Rewrite `execute()` to follow this pipeline:

**Step A — Extract incoming message and tenant ID**
```python
incoming_message = context.message
query = context.get_user_input()
```

**Step B — Initialize task and updater** *(must happen before the pre-hook stop_execution guard, because the early-return path also uses `updater`)*
```python
task = context.current_task
is_new_task = task is None
if not task:
    task = new_task(context.message)
    await event_queue.enqueue_event(task)

updater = TaskUpdater(event_queue, task.id, task.context_id)
```

**Step C — Add the shared `_run_hooks` helper**

Extract the hook-execution loop into a reusable method. Both pre-hooks and
post-hooks use identical logic — only the hook type filter differs.

The method returns the total wall-clock duration (in seconds) of all hook
calls executed, so the caller can accumulate it for the summary span.

```python
async def _run_hooks(
    self,
    hooks: list,
    hook_type: HookType,
    message: Message,
    updater: TaskUpdater,
    task,
    ext_impl=None,
) -> float:
    """Run all hooks of the given type against *message*.

    Appends hook-contributed parts to *message* in place.
    When *ext_impl* is provided, each hook call is wrapped with
    ``extension_context`` and a dedicated ``extension_hook`` tracer span
    carrying all seven ``sap.extension.*`` attributes.

    Returns:
        Total wall-clock duration (seconds) of all hook calls executed.

    Raises:
        ServerError: if a hook blocks execution (stop_execution + canShortCircuit)
                     or if a TransportError occurs and onFailure is BLOCK.
    """
    import time
    from sap_cloud_sdk.core.telemetry import ExtensionType, extension_context
    from opentelemetry import trace

    _tracer = trace.get_tracer("sap.cloud_sdk.extension")

    filtered = [h for h in hooks if h.type == hook_type]
    phase = "pre" if hook_type == HookType.BEFORE else "post"
    logger.info("Found %d %s-execution hook(s)", len(filtered), phase)

    total_duration = 0.0

    for hook in filtered:
        hook_name = hook.name or hook.id or "unknown"
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(f"Executing {phase}-execution hook: {hook_name}", task.context_id, task.id),
        )

        # Resolve per-hook telemetry source info
        source_info = None
        if ext_impl and ext_impl.source:
            source_info = ext_impl.get_source_info_for_hook(hook.ord_id)
        resolved_name = source_info.extension_name if source_info else (ext_impl.extension_name if ext_impl else "unknown")
        resolved_id = source_info.extension_id if source_info else ""
        resolved_version = source_info.extension_version if source_info else ""
        capability = "default"

        t0 = time.monotonic()
        try:
            with (
                extension_context(
                    capability_id=capability,
                    extension_name=resolved_name,
                    extension_type=ExtensionType.HOOK,
                    extension_id=resolved_id,
                    extension_version=resolved_version,
                    item_name=hook_name,
                ),
                _tracer.start_as_current_span(
                    f"extension_hook {hook_name}",
                    attributes={
                        "sap.extension.isExtension": True,
                        "sap.extension.extensionType": ExtensionType.HOOK.value,
                        "sap.extension.capabilityId": capability,
                        "sap.extension.extensionId": resolved_id,
                        "sap.extension.extensionName": resolved_name,
                        "sap.extension.extensionVersion": resolved_version,
                        "sap.extension.extension.item.name": hook_name,
                    },
                ),
            ):
                response = self.extensibility_client.call_hook(hook, message)
                if response is not None:
                    logger.info("Hook '%s' returned a response", hook_name)
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(f"Processing {hook_name} response…", task.context_id, task.id),
                    )
                    metadata = response.metadata or {}
                    if metadata.get("stop_execution"):
                        if hook.can_short_circuit:
                            stop_reason = metadata.get("stop_execution_reason") or (
                                f"Hook '{hook_name}' blocked execution."
                            )
                            logger.warning("Hook '%s' blocked execution: %s", hook_name, stop_reason)
                            raise ServerError(InternalError(message=stop_reason))
                        else:
                            logger.info("Hook '%s' signalled stop_execution but canShortCircuit=false — ignoring", hook_name)

                    if response.parts:
                        message.parts.extend(response.parts)
                        logger.info("Hook '%s' appended %d part(s)", hook_name, len(response.parts))

        except TransportError as e:
            logger.error("Error calling hook '%s': %s", hook_name, e)
            if hook.on_failure == OnFailure.BLOCK:
                raise ServerError(InternalError(
                    message=f"Hook '{hook_name}' failed: {e}"
                ))
            # Default: CONTINUE (fail-open) — skip this hook and proceed
        finally:
            total_duration += time.monotonic() - t0

    return total_duration
```

**Step D — Run pre-hooks**

Use `self.extensibility_client` (or the imported `client` from `agent.py` — whichever was chosen in Step 6c). Do **not** call `create_client()` here; the client is already initialised in `__init__`.

Extract the extension override from the request context and pass it to `get_extension_capability_implementation()` so the extensibility backend returns the correct extension for each invocation.

Hooks only run for new tasks — follow-up messages (continuing an `input_required` conversation) skip hook execution to avoid re-enriching or re-validating an already-started task.

```python
override = get_extension_override(context)
ext_impl = self.extensibility_client.get_extension_capability_implementation(
    capability_id="default",
    override=override,
)

# ── Accumulate extension metrics for summary span ──
reset_tool_call_metrics()
total_ext_duration = 0.0
hook_call_count = 0

if not is_new_task:
    logger.info("Skipping pre-execution hooks — ongoing task %s", task.id)
else:
    pre_hooks = [h for h in ext_impl.hooks if h.type == HookType.BEFORE]
    hook_call_count += len(pre_hooks)
    pre_duration = await self._run_hooks(ext_impl.hooks, HookType.BEFORE, incoming_message, updater, task, ext_impl=ext_impl)
    total_ext_duration += pre_duration
```

**Step E — Run the agent with the hook-enriched context**

After the pre-hook loop, `incoming_message` contains the original user parts
plus any parts appended by pre-hooks. Extract the combined text to pass to
the agent:

```python
query = get_message_text(incoming_message) or query
```

**Hook contract (pre-hook returns only its contribution):**
```javascript
return {
  "parts": [
    {
      "kind": "text",
      "text": "Stream this response"
    }
  ],
  "metadata" : {
    "stop_execution" : true
    "stop_execution_reason" : "Request blocked by pre-hook." 
  }
};
```

The loop appends these parts to the existing message. After the loop
completes, `incoming_message.parts` contains the full sequential chain:

```
parts[0] → user query (TextPart)
parts[1] → pre-hook 1 contribution (TextPart or DataPart)
parts[2] → pre-hook 2 contribution (TextPart or DataPart)
...
```

Pass the enriched `Message` directly to the agent's `stream()` method:

```python
async for item in self.agent.stream(query, task.context_id):
    ...
```

The agent concatenates all parts into its LLM prompt automatically:

| Part type  | How it appears in the prompt        |
|------------|-------------------------------------|
| `TextPart` | Appended as plain text              |
| `DataPart` | Appended as `[Context Data: {...}]` |

This means hook context (e.g. repository ID, permissions, tenant metadata)
flows naturally to the LLM without any special wiring in `agent_executor.py`.

**Step F — Run post-hooks and return the final response**

Inside the `if item["is_task_complete"]` branch, run AFTER hooks using the
same `_run_hooks` method:

```python
# Build result Message: all pre-hook Parts + agent TextPart
agent_result_message = Message(
    message_id=str(uuid.uuid4()),
    context_id=task.context_id,
    role="agent",
    kind="message",
    parts=[
        *incoming_message.parts,
        Part(root=TextPart(kind="text", text=item["content"]))
    ]
)

post_hooks = [h for h in ext_impl.hooks if h.type == HookType.AFTER]
hook_call_count += len(post_hooks)
post_duration = await self._run_hooks(ext_impl.hooks, HookType.AFTER, agent_result_message, updater, task, ext_impl=ext_impl)
total_ext_duration += post_duration

# ── Retrieve actual tool call metrics and emit summary span ──
tool_call_count, tool_duration_ms = get_tool_call_metrics()
total_ext_duration += tool_duration_ms / 1000
emit_extensions_summary_span(
    tool_call_count=tool_call_count,
    hook_call_count=hook_call_count,
    has_instruction=ext_impl.instruction is not None,
    total_duration_ms=total_ext_duration * 1000,
)

# Use the last TextPart as the definitive user-facing response
final_text_parts = [p.root for p in agent_result_message.parts if isinstance(p.root, TextPart)]
final_text = final_text_parts[-1].text if final_text_parts else item["content"]

await updater.add_artifact(
    [Part(root=TextPart(text=final_text))], name="agent_result"
)
await updater.complete()
break
```

**Step G — Add imports for summary span and tool call metrics**

Add the imports for `emit_extensions_summary_span`, `reset_tool_call_metrics`,
and `get_tool_call_metrics` alongside the existing extension telemetry imports
in `agent_executor.py`:

```python
from extension_telemetry import (
    emit_extensions_summary_span,
    reset_tool_call_metrics,
    get_tool_call_metrics,
)
```

**Step H — Top-level exception handler**

Wrap the entire body of `execute()` (Steps A–G) in a `try` block so that
`ServerError` raised by `_run_hooks` propagates cleanly, while any other
unexpected exception is converted into a JSON-RPC `InternalError`:

```python
async def execute(self, context, event_queue):
    try:
        # … Steps A–F …
    except ServerError:
        raise
    except Exception as e:
        logger.exception("Agent execution error")
        raise ServerError(error=InternalError()) from e
```

#### Key Hook Behaviors

- **BEFORE hooks** chain: each hook receives the full `Message` (with all
  accumulated `Part`s) and returns only its own new parts `{"result": {"parts": [...]}}`.
  `_run_hooks` appends them to `message.parts` before passing the updated
  `Message` to the next hook.
- **AFTER hooks** use the same `_run_hooks` method with `HookType.AFTER` —
  identical chaining semantics, identical error handling.
- **`stop_execution`** — a hook may block execution only if its
  record has `can_short_circuit: true`; otherwise the signal is logged and ignored.
- **`onFailure`** — controls what happens when a hook fails (HTTP error, timeout, or exception):
  - `CONTINUE` *(default)*: the hook is skipped and execution continues with the next hook or the agent — fail-open.
  - `BLOCK`: execution is stopped immediately and the failure reason is returned to the caller as the response.
  Set `onFailure=BLOCK` only for hooks that are mandatory for correctness or security.
- **No-op when unconfigured** — if destination service isn't configured correctly, `ext_impl.hooks` is empty and the loops are no-ops — the agent runs unchanged.
- **Fail-open** — hooks with no `onFailure` value set default to `CONTINUE` (fail-open) automatically.

### Request Flow Summary

**Tools + Instructions + Hooks (all enabled):**
```
1.  Receive user request
2.  Extract extension override from request context via get_extension_override()
3.  Call client.get_extension_capability_implementation(capability_id="default", override=override)
    on the application-scoped ExtensibilityClient
4.  Run BEFORE hooks (filter by HookType.BEFORE, call_hook each)
    └── If stop_execution → return hook message, skip agent AND post-hooks
5.  If instruction exists, add to system prompt
6.  If mcp_servers exist: connect, filter, prefix, add to agent loop
7.  Run agent with extended prompt + tools
8.  Build result Message (pre-hook Parts + agent TextPart)
9.  Run AFTER hooks (filter by HookType.AFTER, call_hook each)
10. Extract last TextPart as final response
11. Return response (MCP connections close automatically)
```

**Tools + Instructions (hooks not enabled):**
```
1. Receive user request
2. Extract extension override from request context via get_extension_override()
3. Call client.get_extension_capability_implementation(capability_id="default", override=override)
   on the application-scoped ExtensibilityClient
4. If instruction exists, add to system prompt
5. If mcp_servers exist: connect, filter, prefix, add to agent loop
6. Run agent with extended prompt + tools
7. Return response (MCP connections close automatically)
```

**Tools only:**
```
1. Receive user request
2. Extract extension override from request context via get_extension_override()
3. Call client.get_extension_capability_implementation(capability_id="default", override=override)
   on the application-scoped ExtensibilityClient
4. If mcp_servers exist: connect, filter, prefix, add to agent loop
5. Run agent with extended tools
6. Return response (MCP connections close automatically)
```


**Instructions only:**
```
1. Receive user request
2. Extract extension override from request context via get_extension_override()
3. Call client.get_extension_capability_implementation(capability_id="default", override=override)
   on the application-scoped ExtensibilityClient
4. If instruction exists, add to system prompt
5. Run agent with extended prompt
6. Return response
```

**Hooks only:**
```
1. Receive user request
2. Extract extension override from request context via get_extension_override()
3. Call client.get_extension_capability_implementation(capability_id="default", override=override)
   on the application-scoped ExtensibilityClient
4. Run BEFORE hooks (filter by HookType.BEFORE, call_hook each)
   └── If stop_execution → return hook message, skip agent AND post-hooks
5. Run agent normally
6. Build result Message (pre-hook Parts + agent TextPart)
7. Run AFTER hooks (filter by HookType.AFTER, call_hook each)
8. Extract last TextPart as final response
```

### Environment Variables Reference

The SDK handles destination resolution and authentication internally. No
manual destination configuration environment variables are needed when
deployed on SAP BTP.

---

## Complete Example

> **Note**: The example below shows the **tools + instructions** case (both
> enabled). For **tools only**, omit the instruction handling. For
> **instructions only**, omit the MCP connection logic, tool filtering,
> `extension_telemetry` imports, and `AsyncExitStack` — only fetch
> `ext_impl.instruction` and pass it to the agent's prompt.
> For **hooks**, see the hooks-specific snippet below the main example.

Here's how all three phases integrate in a working agent (full extensibility):

```python
import contextlib
from sap_cloud_sdk.extensibility import create_client, get_extension_override
from extension_telemetry import call_extension_tool
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Create the client once at application startup (module level)
extensibility_client = create_client()

async def process_with_extensions(context, query: str, capability: str = "default"):
    """Process a query using extensions with full telemetry."""

    # Extract extension override from the A2A request context
    override = get_extension_override(context)

    # Fetch extension capability implementation
    ext_impl = extensibility_client.get_extension_capability_implementation(
        capability_id=capability,
        override=override,
    )

    # Connect to MCP servers and call tools with telemetry
    async with contextlib.AsyncExitStack() as stack:
        for server in ext_impl.mcp_servers:
            # Connect to MCP server
            read, write, _ = await stack.enter_async_context(
                streamablehttp_client(server.url)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            # Call each approved tool with telemetry instrumentation
            for tool_name in server.tool_names or []:
                tool_info_obj = type("ToolInfo", (), {
                    "mcp_tool_name": tool_name,
                })()

                result = await call_extension_tool(
                    mcp_client=session,
                    tool_info=tool_info_obj,
                    args={"query": query},
                    extension_name=ext_impl.extension_name,
                    capability=capability,
                    source_mapping=ext_impl.source.tools if ext_impl.source else None,
                    tool_prefix=server.tool_prefix,
                )

                # Process result...
```

### Hooks Example (pre/post hooks)

When hooks are enabled, the `execute()` method in `agent_executor.py` follows
this pattern (shown standalone for clarity; combine with tools/instructions
steps as needed):

```python
import logging
import uuid
from a2a.types import Message, Part, TextPart, DataPart, InternalError
from a2a.utils.errors import ServerError
from a2a.utils.message import get_message_text
from sap_cloud_sdk.extensibility import create_client, get_extension_override, HookType, OnFailure
from sap_cloud_sdk.extensibility.exceptions import TransportError

logger = logging.getLogger(__name__)

class AgentExecutor:
    def __init__(self, agent):
        self.agent = agent
        # If agent.py already creates a client (e.g. `client = create_client()`),
        # import and reuse it: `from agent import client`
        self.extensibility_client = create_client()

    async def _run_hooks(self, hooks, hook_type, message, updater, task, ext_impl=None) -> float:
        """Run all hooks of the given type against *message*.

        Appends hook-contributed parts to *message* in place.
        When *ext_impl* is provided, each hook call is wrapped with
        ``extension_context`` and a dedicated ``extension_hook`` tracer span
        carrying all seven ``sap.extension.*`` attributes.

        Returns:
            Total wall-clock duration (seconds) of all hook calls executed.

        Raises:
            ServerError: if a hook blocks execution (stop_execution + canShortCircuit)
                         or if a TransportError occurs and onFailure is BLOCK.
        """
        import time
        from sap_cloud_sdk.core.telemetry import ExtensionType, extension_context
        from opentelemetry import trace

        _tracer = trace.get_tracer("sap.cloud_sdk.extension")

        filtered = [h for h in hooks if h.type == hook_type]
        phase = "pre" if hook_type == HookType.BEFORE else "post"
        logger.info("Found %d %s-execution hook(s)", len(filtered), phase)

        total_duration = 0.0

        for hook in filtered:
            hook_name = hook.name or hook.id or "unknown"
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(f"Executing {phase}-execution hook: {hook_name}", task.context_id, task.id),
            )

            # Resolve per-hook telemetry source info
            source_info = None
            if ext_impl and ext_impl.source:
                source_info = ext_impl.get_source_info_for_hook(hook.ord_id)
            resolved_name = source_info.extension_name if source_info else (ext_impl.extension_name if ext_impl else "unknown")
            resolved_id = source_info.extension_id if source_info else ""
            resolved_version = source_info.extension_version if source_info else ""
            capability = "default"

            t0 = time.monotonic()
            try:
                with (
                    extension_context(
                        capability_id=capability,
                        extension_name=resolved_name,
                        extension_type=ExtensionType.HOOK,
                        extension_id=resolved_id,
                        extension_version=resolved_version,
                        item_name=hook_name,
                    ),
                    _tracer.start_as_current_span(
                        f"extension_hook {hook_name}",
                        attributes={
                            "sap.extension.isExtension": True,
                            "sap.extension.extensionType": ExtensionType.HOOK.value,
                            "sap.extension.capabilityId": capability,
                            "sap.extension.extensionId": resolved_id,
                            "sap.extension.extensionName": resolved_name,
                            "sap.extension.extensionVersion": resolved_version,
                            "sap.extension.extension.item.name": hook_name,
                        },
                    ),
                ):
                    response = self.extensibility_client.call_hook(hook, message)
                    if response is not None:
                        logger.info("Hook '%s' returned a response", hook_name)
                        await updater.update_status(
                            TaskState.working,
                            new_agent_text_message(f"Processing {hook_name} response…", task.context_id, task.id),
                        )
                        metadata = response.metadata or {}
                        if metadata.get("stop_execution"):
                            if hook.can_short_circuit:
                                stop_reason = metadata.get("stop_execution_reason") or (
                                    f"Hook '{hook_name}' blocked execution."
                                )
                                logger.warning("Hook '%s' blocked execution: %s", hook_name, stop_reason)
                                raise ServerError(InternalError(message=stop_reason))
                            else:
                                logger.info("Hook '%s' signalled stop_execution but canShortCircuit=false — ignoring", hook_name)

                        if response.parts:
                            message.parts.extend(response.parts)
                            logger.info("Hook '%s' appended %d part(s)", hook_name, len(response.parts))

            except TransportError as e:
                logger.error("Error calling hook '%s': %s", hook_name, e)
                if hook.on_failure == OnFailure.BLOCK:
                    raise ServerError(InternalError(
                        message=f"Hook '{hook_name}' failed: {e}"
                    ))
            finally:
                total_duration += time.monotonic() - t0

        return total_duration

    async def execute(self, context, event_queue):
        from extension_telemetry import (
            emit_extensions_summary_span,
            reset_tool_call_metrics,
            get_tool_call_metrics,
        )

        try:
            incoming_message = context.message
            query = context.get_user_input()

            task = context.current_task
            is_new_task = task is None
            if not task:
                task = new_task(context.message)
                await event_queue.enqueue_event(task)
            updater = TaskUpdater(event_queue, task.id, task.context_id)

            # Extract extension override from the A2A request context
            override = get_extension_override(context)
            ext_impl = self.extensibility_client.get_extension_capability_implementation(
                capability_id="default",
                override=override,
            )

            # ── Accumulate extension metrics for summary span ──
            reset_tool_call_metrics()
            total_ext_duration = 0.0
            hook_call_count = 0

            # ── BEFORE hooks ── only for new tasks ──
            if not is_new_task:
                logger.info("Skipping pre-execution hooks — ongoing task %s", task.id)
            else:
                pre_hooks = [h for h in ext_impl.hooks if h.type == HookType.BEFORE]
                hook_call_count += len(pre_hooks)
                pre_duration = await self._run_hooks(ext_impl.hooks, HookType.BEFORE, incoming_message, updater, task, ext_impl=ext_impl)
                total_ext_duration += pre_duration

            query = get_message_text(incoming_message) or query

            async for item in self.agent.stream(query, task.context_id):
                if not item["is_task_complete"] and not item["require_user_input"]:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(item["content"], task.context_id, task.id),
                    )
                elif item["require_user_input"]:
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(item["content"], task.context_id, task.id),
                        final=True,
                    )
                    break
                else:
                    # ── AFTER hooks ──
                    agent_result_message = Message(
                        message_id=str(uuid.uuid4()),
                        context_id=task.context_id,
                        role="agent",
                        kind="message",
                        parts=[
                            *incoming_message.parts,
                            Part(root=TextPart(kind="text", text=item["content"]))
                        ]
                    )

                    post_hooks = [h for h in ext_impl.hooks if h.type == HookType.AFTER]
                    hook_call_count += len(post_hooks)
                    post_duration = await self._run_hooks(ext_impl.hooks, HookType.AFTER, agent_result_message, updater, task, ext_impl=ext_impl)
                    total_ext_duration += post_duration

                    # ── Retrieve actual tool call metrics and emit summary span ──
                    tool_call_count, tool_duration_ms = get_tool_call_metrics()
                    total_ext_duration += tool_duration_ms / 1000
                    emit_extensions_summary_span(
                        tool_call_count=tool_call_count,
                        hook_call_count=hook_call_count,
                        has_instruction=ext_impl.instruction is not None,
                        total_duration_ms=total_ext_duration * 1000,
                    )

                    final_text_parts = [p.root for p in agent_result_message.parts if isinstance(p.root, TextPart)]
                    final_text = final_text_parts[-1].text if final_text_parts else item["content"]
                    await updater.add_artifact(
                        [Part(root=TextPart(text=final_text))], name="agent_result"
                    )
                    await updater.complete()
                    break
        except ServerError:
            raise
        except Exception as e:
            logger.exception("Agent execution error")
            raise ServerError(error=InternalError()) from e
```

### Project Structure After All Phases (full extensibility)

```
app/
  main.py                    <- patched: extension capability + auto_instrument
  extension_capabilities.py  <- extension capability definitions (tools, instructions, hooks)
  agent_executor.py          <- patched: hook pipeline (Phase 3, Step 6)
  extension_telemetry/       <- new: OTel instrumentation for tool calls (Phase 2)
  agent.py
  ...
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `ClientCreationError` from `create_client()` | Destination service not bound or misconfigured | Check destination service binding in `app.yaml` and verify BTP environment |
| No `sap.extension.*` attributes in spans | SDK version too old | Install the extensibility contrib build of `sap-cloud-sdk` via direct wheel URL (for pip) or `==` pin (for uv) — see Prerequisites |
| `ImportError: cannot import extension_context` | SDK missing telemetry module | Verify SDK installation and version |
| `ImportError: cannot import create_client` | SDK version too old (pre-client pattern) | Update to the latest SDK version that exports `create_client` |
| `agent_extensions_summary` span missing | `emit_extensions_summary_span()` not called or import missing | Add `from extension_telemetry import emit_extensions_summary_span` and call it after post-hooks in `execute()` (see Step F and Step G) |
| `totalDurationMs` is always 0 | `_run_hooks` return value not captured or `reset_tool_call_metrics()` not called | Ensure `pre_duration` / `post_duration` are captured from `await self._run_hooks(...)`, call `reset_tool_call_metrics()` before hooks/agent run, and add `tool_duration_ms / 1000` from `get_tool_call_metrics()` to `total_ext_duration` |
| `toolCallCount` is always 0 | `reset_tool_call_metrics()` not called before `agent.run()` | Call `reset_tool_call_metrics()` at the start of `execute()`, before any hooks or `agent.run()` invocations — the ContextVar accumulator must be initialised for wrappers to record calls |
| `toolCallCount` shows registered names, not actual calls | Using old `sum(len(s.tool_names))` pattern instead of `get_tool_call_metrics()` | Replace `sum(len(s.tool_names or []) for s in ext_impl.mcp_servers)` with `tool_call_count, tool_duration_ms = get_tool_call_metrics()` — this counts actual tool calls made, not registered tool names |
| OpenAI Agents SDK `totalDurationMs` excludes tool time | Architectural limitation — `tool_filter` runs at filter time, not execution time | This is expected. The SDK's `Runner.run()` makes MCP calls outside extension context. `toolCallCount` is accurate but tool durations reflect filter evaluation time only |
| Attributes not appearing in traces | Auto-instrumentation not initialized | Call `auto_instrument()` before AI framework imports |
| Attributes appear as baggage but not on spans | Using `extension_context()` without explicit span attributes | Use the wrapper functions which set both baggage and span attributes |
| Empty extension name in attributes | `ext_impl.extension_name` is None | Check extensibility service configuration |
| `InstrumentedToolset` not wrapping calls | Wrong toolset chain order | Ensure chain is: `.filtered()` → `.prefixed()` → `InstrumentedToolset(wrapped=...)` |
| `TransportError` | Destination service not bound or network issue | Check destination service binding in `app.yaml` and network connectivity |
| Empty tools/instruction | No extensions configured | Configure extension capability in the Extensibility Service |
| MCP connection timeout | Network or URL issue | Check MCP server URL, increase timeout, check network |
| Hooks not executing | destination not configured or hooks not registered | Verify destination is set up and hooks are registered correctly |
| `stop_execution` from hook is ignored | Hook's record missing `canShortCircuit: true` | Set `canShortCircuit: true` on the hook's registry entry |
| Hook times out | Slow hook implementation | Default timeout is 120 s; timed-out hooks are skipped (fail-open) — check hook implementation |
| No hooks discovered | `SUPPORTED_HOOKS` missing BEFORE/AFTER entries | Verify `extension_capabilities.py` has both `HookType.BEFORE` and `HookType.AFTER` in `supported_hooks` |
| Agent works but hooks are skipped | destination service configuration is incorrect | Expected behavior in incorrect environments — hooks integration is a no-op when unconfigured |
| Hook failure stops the agent unexpectedly | Hook has `onFailure=BLOCK` in registry | Expected when `onFailure=BLOCK` is set — the hook is mandatory. Fix the hook or change `onFailure` to `CONTINUE` in the registry if the hook is optional |
| Hook failure is silently skipped when it should block | Hook is missing `onFailure=BLOCK` in registry | Set `onFailure=BLOCK` on the hook's registry entry to make failures halt execution |
| UMS does not pick up extensibility changes | ORD resource versions not bumped after changes | Bump the A2A API resource version (the `apiProtocol: "a2a"` entry in `apiResources`) and `agents[0].version` in all ORD documents (see Phase 1, Step 6) |
| UMS still does not pick up changes after version bump | Agent not redeployed or UMS aggregation not triggered | Deploy the agent with the updated ORD documents and ensure UMS aggregation runs afterward — UMS only detects version changes when it re-aggregates the ORD endpoint |
| `ext_*` attributes missing from logs | `ExtensionContextLogFilter` not added or added to logger instead of handler | Add `handler.addFilter(ExtensionContextLogFilter())` to each **handler**, not the logger. Logger-level filters are skipped when child logger records propagate via `callHandlers()` |
| `ext_*` attributes not visible in log output | Plain-text formatter ignores extra LogRecord attributes | Switch to a JSON formatter (e.g., `python-json-logger`) that serialises all LogRecord attributes, or create a custom `Formatter` |
| `ext_*` attributes not appearing as `log.attributes.*` in SAP Cloud Logging | Log lines not valid JSON | Ensure the handler uses `JsonFormatter` from `python-json-logger`. Kyma's Fluent Bit only promotes JSON keys to `log.attributes.*` when the entire log line is valid JSON |
| `ModuleNotFoundError: pythonjsonlogger` | `python-json-logger` not installed | Install with `pip install "python-json-logger>=3.3.0"` or `uv add "python-json-logger>=3.3.0"` |
| `ext_*` attributes only appear on some log lines | Log statement is outside `extension_context()` block | The filter only injects `ext_*` when OTel baggage `sap.extension.isExtension` is present — this is by design. Only log statements inside `extension_context()` get the attributes |
| Override routing not working (always returns default extension)             | `get_extension_override(context)` not called, or `override` not passed      | Ensure `get_extension_override(context)` is called where the A2A `RequestContext` is available and the result is passed as `override=override` to `get_extension_capability_implementation()` |
