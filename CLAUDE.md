# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Is

This is an **Intent-Based Development (IBD) skills repository** for building SAP solutions. It contains no application code itself — instead, it provides 20 AI-driven skills (agent instructions) that automate the full lifecycle from business intent to deployed solution.

## IBD Workflow

The core skill chain for building a new solution:

```
intent-analysis
  → product-requirements-document
  → prd-to-spec (generates OpenSpec)
  → spec-to-code (implements via openspec-apply-change)
  → setup-solution + deploy-solution
```

Always start with `intent-analysis` for any new user request before any other skill.

## Skills Overview

Skills live in `.claude/skills/`. Each has a `SKILL.md` with its detailed instructions.

**Discovery & Specification:**
- `intent-analysis` — captures challenge in `intent.md`, runs LeanIX + EKX fit-gap analysis
- `product-requirements-document` — transforms `intent.md` into a PRD
- `prd-to-spec` — generates OpenSpec from PRD; handles `agent`, `cap`, `n8n-workflow` task types
- `openspec-propose` — creates a full OpenSpec change (proposal → design → spec → tasks) in one step
- `openspec-apply-change` — implements tasks from an OpenSpec change

**Code Generation:**
- `sap-agent-bootstrap` — scaffolds Python A2A agents (LangGraph, GitHub Actions CI/CD)
- `cap-development` — scaffolds CAP Node.js apps (CDS modeling, handlers)
- `n8n-workflow` — generates n8n workflow JSON files (`.n8n.json`)

**Solution & Deployment:**
- `setup-solution` — creates `solution.yaml` and `assets/` structure
- `deploy-solution` — deploys to SAP App Foundation (requires `solution.yaml`)

**Agent Features:**
- `sap-agent-run-local` — runs agents locally (Python 3.13+, venv or Docker)
- `sap-agent-test-remote` — tests deployed agents via A2A protocol
- `sap-agent-instrumentation` — adds OpenTelemetry custom spans and token tracking
- `sap-agent-extensibility` — adds end-to-end customer extensibility (tools, hooks, runtime instructions)
- `sap-agent-ord-endpoint` — adds ORD (Open Resource Discovery) endpoint for agent discoverability

**Integrations & Extensions:**
- `mcp-translation-file` — generates MCP translation files from OpenAPI/OData specs
- `mcp-mock-config` — generates `mcp-mock.json` for deterministic MCP testing
- `create-agent-extension` — bootstraps agent extensions (extension points + MCP tools)
- `data-product-generation` — generates derived data products and analytical cubes

## MCP Servers

Three MCP servers are configured in `.mcp.json`:
- `ibd` (remote HTTP + OAuth) — business analysis via LeanIX and EKX
- `n8n` (remote HTTP) — n8n workflow automation
- `cds-mcp` (local stdio) — CAP/CDS model queries and documentation search

## OpenSpec Structure

OpenSpec changes live at `specs/<asset-name>/openspec/changes/<change-id>/` and contain:
- `proposal.md` — business case and approach
- `design.md` — technical design decisions
- `spec.md` — detailed specification
- `tasks.md` — implementation tasks (drives `openspec-apply-change`)

Validate with: `openspec validate <asset-name> --strict`

## Solution Structure

```
solution.yaml
assets/
  <asset-name>/
    asset.yaml
    ... (generated code)
```

Multi-asset solutions can combine: Agent + n8n Workflow, Agent + MCP Servers, multiple agents, UI + CAP backend.

## Agent Stack

Agents bootstrapped by `sap-agent-bootstrap` use:
- **Runtime:** SAP AI Core on SAP App Foundation
- **Framework:** LangGraph (graph-based orchestration)
- **Protocol:** A2A (Agent-to-Agent, JSON-RPC)
- **Language:** Python 3.13+
- **PyPI:** SAP internal proxy only (no external PyPI)
- **CI/CD:** GitHub Actions
