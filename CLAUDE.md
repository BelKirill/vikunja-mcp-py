# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

vikunja-mcp-py is a Python rewrite of vikunja-mcp - an AI-powered MCP server for ADHD-optimized task management using Vikunja and Vertex AI (Gemini).

## Development Commands

```bash
make install    # Install production dependencies
make dev        # Install dev dependencies (includes ruff, pytest, mypy)
make lint       # Run linter
make format     # Auto-fix lint issues
make test       # Run tests
make docker     # Build Docker image
make run        # Run MCP server locally
```

## Architecture

```
src/
├── server.py           # MCP server entry point
├── config.py           # Pydantic settings
├── models.py           # Data models (Task, ProjectContext, etc.)
├── context.py          # Project context & switching cost calculation
├── dependencies.py     # Task dependency checker
├── tools/
│   └── handlers.py     # MCP tool implementations
├── vikunja/
│   └── client.py       # Vikunja API client
└── engine/
    └── focus_engine.py # Gemini-powered task ranking
```

## Key Components

- **MCP Server**: Uses official `mcp` Python SDK over stdio
- **Vikunja Client**: Async HTTP client with retry logic (httpx)
- **Focus Engine**: Vertex AI / Gemini for task ranking and enrichment
- **Context Manager**: Project context awareness and switching cost calculation
- **Dependency Checker**: Task blocking/unblocking analysis
- **Tool Handlers**: Business logic for each MCP tool

## Environment Variables

Required:
- `VIKUNJA_URL` - Vikunja instance URL
- `VIKUNJA_TOKEN` - API token

Optional:
- `GCP_PROJECT` - Google Cloud project for Vertex AI
- `GCP_LOCATION` - Vertex AI location (default: us-central1)
- `GEMINI_MODEL` - Model name (default: gemini-2.0-flash)
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON

## MCP Tools

| Tool | Purpose |
|------|---------|
| `daily-focus` | AI-ranked tasks for focus session |
| `get-full-task` | Full task details with metadata |
| `get-filtered-tasks` | Query tasks with filter or natural language |
| `upsert-task` | Create/update tasks |
| `add-comment` | Add comment to task |
| `export-project-json` | Export to JSON file |

## Testing

```bash
pytest -v                    # Run all tests
pytest -v -k "test_client"   # Run specific tests
```

## Docker

```bash
make docker
docker run --rm -i \
  -e VIKUNJA_URL=https://tasks.example.com \
  -e VIKUNJA_TOKEN=your-token \
  vikunja-mcp-py:latest
```

## Git Workflow

All work follows this flow: **Issue → Ticket → Branch → PR**

### Ticket Tracking
- Every issue is tracked as a task in **Vikunja project 8**
- Use the vikunja-mcp tools to query tasks: `get-filtered-tasks` with `project_id: 8`

### Branch Naming
**Format:** `mcp-<ticket-number>-<short-description>`

**Examples:**
- `mcp-156-ai-rating-engine`
- `mcp-112-bulk-update-tool`
- `mcp-149-retry-logic`

### Commit Messages
**Format:** `<type>: <description>`

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

**Examples:**
- `feat: implement bulk update tool`
- `fix: add retry logic for 400 errors`
- `docs: update comment system documentation`

### Workflow Steps
1. Find/create task in Vikunja project 8
2. Create branch: `git checkout -b mcp-<task-id>-<description>`
3. Implement changes with atomic commits
4. **Before pushing:** Run format, lint, and tests
   ```bash
   .venv/bin/ruff format src/
   .venv/bin/ruff check src/ --fix
   .venv/bin/pytest tests/ -v
   ```
5. Push and create PR
6. Mark task done after merge

### Pre-Push Checklist
- [ ] Format passes: `.venv/bin/ruff format src/`
- [ ] Lint passes: `.venv/bin/ruff check src/`
- [ ] All tests pass: `.venv/bin/pytest tests/ -v`
- [ ] Only relevant files staged (no unrelated changes)

## PLAN.md Usage

PLAN.md is the implementation roadmap. It organizes tasks into 6 sequential phases.

### Structure
- **Executive Summary**: Total tasks, completion status, phase count
- **Phases 1-6**: Sequential work packages with dependencies
- **Quick Reference**: Tasks grouped by energy level (low/medium/high/social)
- **Dependency Graph**: Visual representation of task blocking relationships
- **Daily Focus Recommendations**: Pre-selected task bundles

### How to Use

**Before starting work:**
1. Check PLAN.md for current phase and next available tasks
2. Verify task dependencies are complete (check "Blocks" column)
3. Match task to current energy level using Quick Reference

**During work:**
1. Reference task ID when creating branch: `mcp-<task-id>-desc`
2. Update task status in PLAN.md when complete (pending → **DONE**)
3. Check off completion criteria as they're met

**Updating PLAN.md:**
- Mark completed tasks with **DONE** in Status column
- Update completion criteria checkboxes `[x]`
- Update "Total Open Tasks" and "Completed" counts in header

### Phase Dependencies
Each phase depends on the previous:
- Phase 1: Foundation (CI/CD) - no dependencies
- Phase 2: Core API - requires Phase 1
- Phase 3: Dependency Management - requires Phase 2
- Phase 4: Project Context - requires Phase 3
- Phase 5: Sessions & Labels - requires Phase 4
- Phase 6: Analytics & Docs - requires Phase 5

### Energy-Based Task Selection
Use when unsure what to work on:
- **Low energy**: Documentation, simple updates, validation
- **Medium energy**: Implementation, integration, testing
- **High energy**: Core logic, complex algorithms, architecture
- **Social energy**: Presentations, demos
