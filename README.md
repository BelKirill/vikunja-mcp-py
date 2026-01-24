# vikunja-mcp-py

AI-powered MCP server for ADHD-optimized task management using Vikunja and Vertex AI (Gemini).

## Features

- **Daily Focus Sessions**: AI-ranked tasks based on energy level and work mode
- **Dependency Awareness**: Blocked tasks excluded, unblocking tasks prioritized
- **Project Context Switching**: Minimizes cognitive load by grouping tasks intelligently
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

## Project Context System

The server includes intelligent project context awareness to minimize cognitive load from context switching.

### How It Works

- **Context switching costs**: The AI calculates the cognitive cost of switching between projects
- **Task grouping**: Tasks from the same project are grouped together in recommendations
- **Current project continuity**: Use `current_project_id` to prioritize continuing your current work

### Using Current Project

Pass `current_project_id` to `daily-focus` to get recommendations that minimize context switching:

```
daily-focus with energy="high", mode="deep", current_project_id=8
```

This tells the AI you're currently working on project 8, so it will:
1. Prioritize tasks from project 8 first
2. Group other project tasks to minimize switches
3. Consider context weight when ordering tasks

### Context Weight Factors

The system considers several factors when calculating switch costs:

| Factor | Impact |
|--------|--------|
| **Context weight** | Heavy projects (complex codebases) have higher switching costs |
| **Related projects** | Projects that share context have lower switching costs |
| **Same domain** | Projects in the same domain (e.g., "infra") switch easier |
| **Work type match** | Switching between coding/admin/research has overhead |
| **Tool requirements** | Different tool requirements increase switching cost |

### Configuring Project Contexts

You can configure project contexts in three ways (in priority order):

**1. JSON Configuration File**

Set `PROJECT_CONTEXT_CONFIG` environment variable to a JSON file path:

```bash
export PROJECT_CONTEXT_CONFIG=/path/to/projects.json
```

Example `projects.json`:
```json
{
  "projects": [
    {
      "project_id": 8,
      "name": "Vikunja MCP",
      "work_type": "coding",
      "domain": "vikunja-mcp",
      "typical_energy": "high",
      "typical_mode": "deep",
      "context_weight": 8,
      "requires_tools": ["vscode", "docker"],
      "related_projects": [9, 10]
    }
  ]
}
```

**2. Embedded Metadata in Project Descriptions**

Add a metadata block to project descriptions in Vikunja:

```html
<!-- PROJECT_CONTEXT:{"work_type": "coding", "context_weight": 7}:END_CONTEXT -->
```

**3. Defaults from Project Title/Description**

If no configuration is found, projects get default values (context_weight=5, work_type="general").

### ADHD Workflow Tips

- **Set current project**: Always pass `current_project_id` when you're deep in a project
- **Batch by project**: Complete multiple tasks in one project before switching
- **Respect the grouping**: The AI groups tasks to protect your focus
- **Heavy projects need time**: High context-weight projects benefit from longer focus sessions

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
