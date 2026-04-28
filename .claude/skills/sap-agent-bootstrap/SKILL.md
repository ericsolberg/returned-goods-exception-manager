---
name: sap-agent-bootstrap
description: Bootstrap a complete App Foundation agent project. Use when the user wants to create a new AI agent for deployment on SAP App Foundation runtime, or asks to create an agent. Only use during spec or code generation with the `prd-to-spec` or `spec-to-code` skills. Never invoke on its own.
---
# App Foundation Agent Bootstrap

Creates a ready-to-deploy AI agent asset for SAP App Foundation with A2A protocol, LangGraph, SAP AI Core integration, and GitHub Actions CI/CD.

**This skill operates on the current working directory.** The caller is responsible for running it from the correct target directory (e.g. `assets/<asset-name>/`).

## Instructions

Follow these 3 phases in order:

### Phase 1: Collect User Input

Use `question` tool if available or a similar tool that can be used to ask questions to the user to gather exactly 2 values BEFORE any file operations:

```
Question 1: "Please enter your agent name (e.g., expense-tracker-agent):"
Question 2: "Please enter your agent description (e.g., 'An AI agent that tracks business expenses'):"
```

**Example interaction:**
- User wants: "Create an agent to help with travel expenses"
- Agent name: `travel-expense-agent`
- Agent description: `An AI agent that helps employees manage and submit travel expenses`

### Phase 2: Copy Templates (Deterministic)

Run the appropriate shell command based on user's OS:

**macOS/Linux:**
```bash
mkdir -p app .github/workflows
# Search upward from the current directory to find the skill (it lives in .claude/skills/ above assets/agent/)
SEARCH_DIR="."
SKILL_PATH=""
while [ "$(realpath "$SEARCH_DIR")" != "/" ]; do
  SKILL_PATH=$(find "$SEARCH_DIR" -maxdepth 4 -type d -name "sap-agent-bootstrap" -path "*/skills/*" 2>/dev/null | head -1)
  [ -n "$SKILL_PATH" ] && break
  SEARCH_DIR="$SEARCH_DIR/.."
done
if [ -z "$SKILL_PATH" ]; then echo "ERROR: sap-agent-bootstrap skill not found"; exit 1; fi
cp -r "$SKILL_PATH/templates/app/." ./app/
for file in ./app/*.py.template; do [ -f "$file" ] && mv "$file" "${file%.template}"; done
cp "$SKILL_PATH/templates/Dockerfile.template" ./Dockerfile
cp "$SKILL_PATH/templates/requirements.txt.template" ./requirements.txt
cp "$SKILL_PATH/templates/README.md" ./
cp "$SKILL_PATH/templates/.gitignore" ./
cp -r "$SKILL_PATH/templates/.github/." ./.github/
```

**Windows PowerShell:**
```powershell
New-Item -ItemType Directory -Force -Path app, .github/workflows
# Search upward from current directory to find the skill
$SearchDir = Get-Location
$SkillPath = $null
while ($SearchDir -ne $SearchDir.Parent -and $null -eq $SkillPath) {
  $SkillPath = Get-ChildItem -Path $SearchDir -Depth 4 -Recurse -Directory -Filter "sap-agent-bootstrap" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -like "*skills*" } | Select-Object -First 1 -ExpandProperty FullName
  $SearchDir = $SearchDir.Parent
}
if (-not $SkillPath) { Write-Error "ERROR: sap-agent-bootstrap skill not found"; exit 1 }
Get-ChildItem "$SkillPath/templates/app" -Force | Copy-Item -Destination "./app/" -Recurse -Force
Get-ChildItem -Path "./app/*.py.template" | ForEach-Object { Rename-Item -Path $_.FullName -NewName ($_.Name -replace '\.template$', '') }
Copy-Item "$SkillPath/templates/Dockerfile.template" -Destination "./Dockerfile"
Copy-Item "$SkillPath/templates/requirements.txt.template" -Destination "./requirements.txt"
Copy-Item "$SkillPath/templates/README.md" -Destination "./"
Copy-Item "$SkillPath/templates/.gitignore" -Destination "./"
Get-ChildItem "$SkillPath/templates/.github" -Force | Copy-Item -Destination "./.github/" -Recurse -Force
```

### Phase 3: Replace Placeholders (Deterministic)

Use shell commands to replace all placeholders. Derive values from the 2 inputs collected in Phase 1. Refer to "Placeholder Derivation Rules" section for more information

**macOS (sed -i ''):**
```bash
# Replace in README.md
sed -i '' 's/{{AGENT_TITLE}}/<Agent Title>/g' README.md
sed -i '' 's/{{AGENT_DESCRIPTION}}/<agent-description>/g' README.md

# Replace in app/main.py
sed -i '' 's/{{AGENT_ID}}/<agent-name>/g' app/main.py
sed -i '' 's/{{AGENT_NAME}}/<agent-name>/g' app/main.py
sed -i '' 's/{{AGENT_SKILL_DESCRIPTION}}/<agent-description>/g' app/main.py
sed -i '' 's/{{AGENT_CARD_DESCRIPTION}}/<agent-description>/g' app/main.py
sed -i '' 's/{{AGENT_TAGS}}/<tags-list>/g' app/main.py
sed -i '' 's/{{AGENT_EXAMPLES}}/<examples-list>/g' app/main.py

# Replace in app/agent.py
sed -i '' 's/{{SYSTEM_PROMPT}}/<system-prompt>/g' app/agent.py
```

**Linux (sed -i without quotes):**
```bash
sed -i 's/{{AGENT_TITLE}}/<Agent Title>/g' README.md
# ... same pattern as macOS but targeting app/
```

**Windows PowerShell:**
```powershell
# Replace in README.md
(Get-Content README.md) -replace '{{AGENT_TITLE}}','<Agent Title>' | Set-Content README.md
(Get-Content README.md) -replace '{{AGENT_DESCRIPTION}}','<agent-description>' | Set-Content README.md

# Replace in app/main.py
(Get-Content app/main.py) -replace '{{AGENT_ID}}','<agent-name>' | Set-Content app/main.py
(Get-Content app/main.py) -replace '{{AGENT_NAME}}','<agent-name>' | Set-Content app/main.py
(Get-Content app/main.py) -replace '{{AGENT_SKILL_DESCRIPTION}}','<agent-description>' | Set-Content app/main.py
(Get-Content app/main.py) -replace '{{AGENT_CARD_DESCRIPTION}}','<agent-description>' | Set-Content app/main.py
(Get-Content app/main.py) -replace '{{AGENT_TAGS}}','<tags-list>' | Set-Content app/main.py
(Get-Content app/main.py) -replace '{{AGENT_EXAMPLES}}','<examples-list>' | Set-Content app/main.py

# Replace in app/agent.py
(Get-Content app/agent.py) -replace '{{SYSTEM_PROMPT}}','<system-prompt>' | Set-Content app/agent.py
```

## Placeholder Derivation Rules

Derive all 10 placeholders from the 2 user inputs:

| Placeholder | Derivation | Example Value |
|-------------|------------|---------------|
| `{{AGENT_NAME}}` | Direct from input | `travel-expense-agent` |
| `{{AGENT_NAMESPACE}}` | Same as AGENT_NAME | `travel-expense-agent` |
| `{{AGENT_ID}}` | Same as AGENT_NAME | `travel-expense-agent` |
| `{{AGENT_TITLE}}` | Title-case: replace `-` with space, capitalize | `Travel Expense Agent` |
| `{{AGENT_TAGS}}` | Split AGENT_NAME by `-` into Python list | `["travel", "expense", "agent"]` |
| `{{AGENT_DESCRIPTION}}` | Direct from input | `An AI agent that helps employees manage and submit travel expenses` |
| `{{AGENT_SKILL_DESCRIPTION}}` | Same as AGENT_DESCRIPTION | `An AI agent that helps employees manage and submit travel expenses` |
| `{{AGENT_CARD_DESCRIPTION}}` | Same as AGENT_DESCRIPTION | `An AI agent that helps employees manage and submit travel expenses` |
| `{{SYSTEM_PROMPT}}` | Template: `You are {AGENT_DESCRIPTION}. Help users with their requests.` | `You are an AI agent that helps employees manage and submit travel expenses. Help users with their requests.` |
| `{{AGENT_EXAMPLES}}` | Generate 2 example prompts based on description | `["Help me submit a travel expense", "What are the expense policies?"]` |

## Output Structure

The skill produces the following layout inside the current working directory (e.g. `assets/<asset-name>/`):

```
assets/<asset-name>/
├── .github/workflows/dev-ci-cd.yml
├── .gitignore
├── README.md
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── main.py
    ├── agent_executor.py
    └── agent.py
```

**Note:** `asset.yaml` and `solution.yaml` are NOT created by this skill. They are created later by the `setup-solution` skill, which runs at the end of the full workflow.

## Optional: When using pydantic package in your agent code

Add `pydantic` to `requirements.txt` file, but don't add a package version to avoid conflicts with SAP AI Core's pydantic version.

## Customization

- **Tools**: Extend LangGraph in `agent.py`
- **Skills**: Add `AgentSkill` definitions in `main.py`

## ⚠️ Important: Dependencies

**Note:** Dependencies listed in `requirements.txt` are NOT installed during the bootstrap process. They will be installed:
- **Locally**: When you run the agent using the `sap-agent-run-local` skill
- **In the cluster**: Automatically during the deployment process via CI/CD pipeline

The bootstrap process only creates the project structure and configuration files. No local Python environment setup is performed at this stage.

## ⚠️ Known Deployment Gotchas

These issues have caused real deployment failures and are proven to break the agent on the platform:

1. **`set_aicore_config()` and `auto_instrument()` must be first** — these must be called at the very top of `main.py`, before any AI framework imports (LangChain, LiteLLM, etc.). The platform SDK hooks into the import process; importing AI frameworks first causes telemetry to be missed or misconfigured.

2. **MCP tool loading via `MultiServerMCPClient` must be async and lazy** — `get_tools()` is async and makes real network calls to MCP servers. It cannot be called from `__init__()` and cannot be made sync. Additionally, `async with MultiServerMCPClient(...)` raises `NotImplementedError` — do not use it as a context manager. The correct pattern is:
   ```python
   async def _load_mcp_tools():
       client = MultiServerMCPClient({...})
       return await client.get_tools()

   async def _get_graph(self):
       if self._graph is None:
           tools = await _load_mcp_tools()
           self._graph = create_react_agent(self.llm, tools=tools)
       return self._graph
   ```
   If MCP tools are loaded in `__init__()`, the HTTP server cannot start before the startup probe fires, causing the container to be killed.

## Next Steps

After bootstrapping completes, return control to the calling skill to continue implementation. Do not prompt the user with interactive options — this skill is only invoked as part of the automated `prd-to-spec` → `spec-to-code` chain.
