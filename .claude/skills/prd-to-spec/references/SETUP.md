# Setup Reference

Detailed setup instructions for the PRD-to-Spec skill.

## Prerequisites

### 1. OpenSpec Skills (Required)

The OpenSpec agent skills are installed automatically by the workspace setup script.

**Required skills:**
- `openspec-propose` - Create a new change and generate all artifacts (proposal, design, specs, tasks) in one step
- `openspec-apply-change` - Apply specifications to implement code

If these skills are not installed, run the workspace setup script to install them.

### 2. Node.js and npm (Required for OpenSpec auto-installation)

Node.js and npm are required **only if OpenSpec CLI is not already installed**. The setup script needs npm to auto-install OpenSpec.

**Check installation:**
```bash
npm --version
node --version
```

**Install Node.js:**
- Download from https://nodejs.org/ (includes npm)
- macOS: `brew install node`
- Windows: Use the installer from nodejs.org
- Linux: Use your distribution's package manager

### 3. OpenSpec CLI (Auto-installed)

OpenSpec CLI is **automatically installed** by the setup script if not found. You do not need to install it manually.

**The setup script will:**
1. Check if `openspec` command is available
2. If not found, automatically install it using: `npm install -g @fission-ai/openspec@latest`
3. Verify the installation succeeded

**Manual installation (if auto-install fails):**
```bash
npm install -g @fission-ai/openspec@latest
```

**Verify installation:**
```bash
openspec --version
```

## Running the Setup Script

The setup script handles all prerequisites, OpenSpec installation, and project initialization in a single command.

**IMPORTANT:** You must provide a task type parameter when running the setup script.

**Usage:**
```bash
node /path/to/skills/prd-to-spec/scripts/setup.mjs <task_type>
```

**Valid task types:**
- `agent` - Pro-Code AI Agent for SAP App Foundation using A2A protocol
- `cap` - Side-by-side extension with CAP and custom UI5
- `n8n-workflow` - n8n workflow automation flow

**Examples:**
```bash
# For an AI agent
node /path/to/skills/prd-to-spec/scripts/setup.mjs agent

# For a CAP project
node /path/to/skills/prd-to-spec/scripts/setup.mjs cap

# For an n8n workflow
node /path/to/skills/prd-to-spec/scripts/setup.mjs n8n-workflow
```

**What the setup script does:**

1. **Validates task type parameter**
   - Ensures a valid task type is provided
   - Exits with error if missing or invalid

2. **Checks OpenSpec skills are installed**
   - Verifies `openspec-propose`, `openspec-apply-change` are present
   - Exits with error if skills are missing (directs user to run the workspace setup script)

3. **Installs or verifies OpenSpec**
   - Checks if `openspec` command is available
   - If not found, automatically installs via npm:
     - Verifies npm is installed
     - Runs `npm install -g @fission-ai/openspec@latest`
     - Verifies installation succeeded
   - If already installed, displays version
   - Disables telemetry
   - Exits with error if npm is not available

4. **Initializes project based on task type**
   - Copies task-specific config file to `openspec/config.yaml` (in the spec directory, i.e. `specs/<asset-name>/openspec/config.yaml`)
   - Copies project stub files for the selected task type to the corresponding `assets/<asset-name>/` directory (if a project stub exists for the task type)
   - Creates necessary directory structure
   - Displays summary with task type and next steps

## Project Initialization

The setup script initializes the project directly from assets bundled with the skill:

### Config Files

Task-specific OpenSpec configuration files are stored in `assets/config_files/` (within the skill) and copied to `openspec/config.yaml` (in the spec directory, i.e. `specs/<asset-name>/openspec/config.yaml`):
- `config-agent.yaml` - Configuration for AI agent projects
- `config-cap.yaml` - Configuration for CAP projects
- `config-n8n-workflow.yaml` - Configuration for n8n workflow projects

### Project Stubs

Task-specific project stub files are stored in `assets/project_stubs/<task_type>/` (within the skill) and copied to the corresponding `assets/<asset-name>/` directory:
- Boilerplate code and structure for the selected task type
- If no stub exists for a task type, this step is skipped with a note

## Workflow Summary

```bash
# 1. Navigate to your spec directory (asset-name = <feature>-<task-type>, e.g. purchase-order-approval-agent)
cd /path/to/workspace/specs/<asset-name>

# 2. Run setup with your task type
node /path/to/skills/prd-to-spec/scripts/setup.mjs agent

# 3. Follow the instructions in the openspec-propose skill

# 4. Validate
openspec validate <asset-name> --strict

# 5. Review spec files
ls -la openspec/changes/<asset-name>/

# 6. Review asset files (stubs are copied to assets/<asset-name>/)
ls -la ../../assets/<asset-name>/
```
