---
name: deploy-solution
description: Deploys the solution to SAP App Foundation. Requires solution.yaml per skill `setup-solution`.
---

# Deploy Solution

**This skill is not to be used by the webagent if the `deploy_solution` tool is available. If the `deploy_solution` tool is available, the webagent should use that instead of this skill.**

## Define parameters

- For $APP_FND_DEPLOYMENT_URL, use: "https://deployer-api.c7fbaa2.stage.kyma.ondemand.com/v1" (demo environment)

- For `solution_id`, generate a UUID, e.g. with
```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

- For `user_id`, use the known workspace user ID: `141ee0bf-6f31-4b6d-b36f-033804eeb607` — no need to generate a new one.

## Create the ZIP package and create the deployment job

Depending on the shell, use corresponding commands (e.g. for PowerShell).

Upload the solution with

```bash
zip -r solution.zip solution.yaml assets/ && curl -X POST "$APP_FND_DEPLOYMENT_URL/solutions" -F "file=@solution.zip" -F "user_id=141ee0bf-6f31-4b6d-b36f-033804eeb607" -F "solution_id=<solution-id>" -o deploy_result.json && cat deploy_result.json
```

Note: Always zip from the project root, including `solution.yaml` and the `assets/` folder. Exclude any files/folders not needed at runtime (e.g. `*.pyc`, `__pycache__`, `.venv`, test files, local config).
Always store the result in `deploy_result.json`.

## Check Deployment Status

Check the status (poll) with

```bash
curl "$APP_FND_DEPLOYMENT_URL/solutions/$(grep -o '"solution_id":"[^"]*"' deploy_result.json | sed 's/"solution_id":"\(.*\)"/\1/')"
```

Allowed methods: POST, GET, DELETE
Relative endpoints: jobs, jobs/<job_id>, solutions, solutions/<solution_id>

## Debugging

If the deployment fails or the agent does not start, fetch the job logs:

```bash
curl "$APP_FND_DEPLOYMENT_URL/jobs/<job_id>/logs"
```

## Verification

After the solution status shows as running, confirm the agent is live by hitting its agent card endpoint:

```bash
curl https://<deployed-agent-url>/.well-known/agent.json
```

A valid JSON response confirms the agent is up and responding to probes.
