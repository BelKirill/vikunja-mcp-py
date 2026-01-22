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
├── models.py           # Data models
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
