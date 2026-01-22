# vikunja-mcp-py

AI-powered MCP server for ADHD-optimized task management using Vikunja and Vertex AI (Gemini).

## Features

- **Daily Focus Sessions**: AI-ranked tasks based on energy level and work mode
- **Dependency Awareness**: Blocked tasks excluded, unblocking tasks prioritized
- **Smart Filtering**: Natural language to Vikunja filter expression conversion
- **Task Enrichment**: Automatic metadata generation for ADHD workflows
- **Full MCP Integration**: Works with Claude, OpenAI, and other MCP-compatible clients

## Quick Start

### Environment Variables

```bash
export VIKUNJA_URL=https://tasks.example.com
export VIKUNJA_TOKEN=your-api-token

# Optional: Vertex AI for AI features
export GCP_PROJECT=your-project
export GCP_LOCATION=us-central1
export GEMINI_MODEL=gemini-2.0-flash
```

### Run with Docker

```bash
docker pull ghcr.io/belkirill/vikunja-mcp-py:main

docker run --rm -i \
  -e VIKUNJA_URL=https://tasks.example.com \
  -e VIKUNJA_TOKEN=your-token \
  ghcr.io/belkirill/vikunja-mcp-py:main
```

### Claude Code Configuration

Add to your `~/.claude.json` or project `.mcp.json`:

```json
{
  "mcpServers": {
    "vikunja-mcp": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "VIKUNJA_URL",
        "-e", "VIKUNJA_TOKEN",
        "ghcr.io/belkirill/vikunja-mcp-py:main"
      ],
      "env": {
        "VIKUNJA_URL": "https://tasks.example.com",
        "VIKUNJA_TOKEN": "your-api-token"
      }
    }
  }
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `daily-focus` | Get AI-recommended tasks for focus session based on energy/mode |
| `get-full-task` | Get all details for one task including metadata and comments |
| `get-filtered-tasks` | Retrieve tasks using filter expressions or natural language |
| `upsert-task` | Create a new task or update an existing task |
| `add-comment` | Add a comment to a task |
| `bulk-update-tasks` | Update multiple tasks at once (done, priority, color) |
| `export-project-json` | Export tasks to local JSON file with enriched metadata |

## Comment System

The comment system helps you track progress and maintain context on tasks:

### Adding Comments

```
Use the add-comment tool with task_id and your comment text.
```

Comments are useful for:
- Documenting progress on long-running tasks
- Recording blockers or decisions
- Leaving context for when you return to a task later

### Comment Integration

- **daily-focus**: Shows comment counts and recent comment previews for recommended tasks
- **get-full-task**: Returns all comments with full details
- **upsert-task**: Suggests adding a comment when marking tasks complete

### ADHD Workflow Tips

1. **Start sessions with context**: Check recent comments on tasks you're picking up
2. **Document blockers immediately**: When stuck, add a comment before switching tasks
3. **End sessions with notes**: Use comments to capture where you left off

## Dependency Management

The server automatically tracks task dependencies from Vikunja's related_tasks API:

### How It Works

- **Blocked tasks excluded**: Tasks blocked by incomplete dependencies are automatically excluded from `daily-focus` recommendations
- **Unblocking priority**: Tasks that unblock others are highlighted and prioritized by AI ranking
- **Chain context**: `get-full-task` shows dependency chain progress (e.g., "2/5 completed")

### Dependency Fields in Responses

**daily-focus** tasks include:
- `is_blocked`: Whether task is blocked by incomplete dependencies
- `blocked_by_ids`: List of blocking task IDs
- `blocking_ids`: List of task IDs this task blocks
- `unlocks_tasks`: True if completing this task unblocks others

**get-full-task** includes full dependency context:
```json
{
  "dependencies": {
    "is_blocked": false,
    "blocked_by": [{"id": 99, "title": "Setup infra", "done": true}],
    "blocking": [{"id": 101, "title": "Deploy app", "done": false}],
    "chain_context": {
      "progress": "2/5",
      "progress_percent": 40.0,
      "next_actionable_ids": [100]
    }
  }
}
```

### Setting Up Dependencies in Vikunja

1. Open a task in Vikunja
2. Add a relation with type "blocked by" or "blocks"
3. The MCP server automatically reads these relationships

### ADHD Workflow Tips

- **Focus on unblocking tasks**: Completing tasks that unlock others creates momentum
- **Use chain progress**: See where you are in multi-step projects
- **Trust the filter**: Blocked tasks are hidden so you don't get distracted

## Development

```bash
# Create virtual environment
uv venv && source .venv/bin/activate

# Install dev dependencies
uv pip install -e ".[dev]"

# Run linter
ruff check src/
ruff format src/

# Run tests
pytest -v

# Build Docker image
docker build -t vikunja-mcp-py:latest .
```

## License

Apache-2.0
