"""MCP server for Vikunja integration."""

import asyncio
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import get_settings
from .tools.handlers import ToolHandlers

# Configure logging to stderr (stdout is for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("vikunja-mcp")
    handlers = ToolHandlers()

    # Register tools
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="daily-focus",
                description="Get AI-recommended tasks for focus session based on energy/mode",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "energy": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "social"],
                            "description": "Current energy level",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["deep", "quick", "admin"],
                            "description": "Work mode preference",
                        },
                        "hours": {
                            "type": "number",
                            "description": "Target work hours (default: 5)",
                            "minimum": 1,
                            "maximum": 12,
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum tasks to return (default: 10)",
                            "minimum": 1,
                            "maximum": 50,
                        },
                        "instructions": {
                            "type": "string",
                            "description": "Free text instructions for choosing tasks",
                        },
                        "only_projects": {
                            "type": "array",
                            "description": "Restrict selection to these project IDs",
                            "items": {"type": "integer"},
                        },
                        "exclude_projects": {
                            "type": "array",
                            "description": "Project IDs to exclude from selection",
                            "items": {"type": "integer"},
                        },
                    },
                },
            ),
            Tool(
                name="get-full-task",
                description="Get all details for one task including metadata and comments",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "integer",
                            "description": "Vikunja task ID",
                        },
                    },
                    "required": ["task_id"],
                },
            ),
            Tool(
                name="add-comment",
                description="Add a comment to a task",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "integer",
                            "description": "Vikunja task ID",
                        },
                        "comment": {
                            "type": "string",
                            "description": "The comment to add",
                        },
                    },
                    "required": ["task_id", "comment"],
                },
            ),
            Tool(
                name="get-filtered-tasks",
                description=(
                    "Retrieve tasks using filter expressions or natural language. "
                    "Provide either 'filter' (Vikunja expression) or 'natural_request' "
                    "(AI-generated filter)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": (
                                "Vikunja filter expression "
                                "(e.g., 'done = false && priority >= 3'). "
                                "Use this OR natural_request."
                            ),
                        },
                        "natural_request": {
                            "type": "string",
                            "description": (
                                "Natural language request - AI will generate filter. "
                                "Use this OR filter."
                            ),
                        },
                        "project_id": {
                            "type": "integer",
                            "description": "Project ID to filter tasks within",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum tasks to return (default: 50)",
                            "minimum": 1,
                            "maximum": 200,
                        },
                    },
                },
            ),
            Tool(
                name="upsert-task",
                description=(
                    "Create a new task or update an existing task (including marking complete)"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "integer",
                            "description": "Task ID to update (omit to create new)",
                        },
                        "title": {
                            "type": "string",
                            "description": "Task title",
                        },
                        "done": {
                            "type": "boolean",
                            "description": "Mark task as complete",
                        },
                        "priority": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "description": "Task priority (1-5)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Task description",
                        },
                        "hex_color": {
                            "type": "string",
                            "description": "Colour in hex (6 characters)",
                            "pattern": "^[0-9A-Fa-f]{6}$",
                        },
                        "project_id": {
                            "type": "integer",
                            "description": "Project ID (required for new tasks)",
                        },
                    },
                },
            ),
            Tool(
                name="export-project-json",
                description="Export tasks to local JSON file with enriched metadata",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "output_path": {
                            "type": "string",
                            "description": "Local file path for JSON export",
                        },
                        "project_id": {
                            "type": "integer",
                            "description": "Project ID to export (omit for all)",
                        },
                        "include_completed": {
                            "type": "boolean",
                            "description": "Include completed tasks (default: false)",
                        },
                        "include_comments": {
                            "type": "boolean",
                            "description": "Include task comments (default: false)",
                        },
                        "include_metadata": {
                            "type": "boolean",
                            "description": "Include AI metadata (default: true)",
                        },
                        "custom_filter": {
                            "type": "string",
                            "description": "Vikunja filter expression",
                        },
                        "pretty_print": {
                            "type": "boolean",
                            "description": "Format JSON with indentation (default: true)",
                        },
                    },
                    "required": ["output_path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        logger.info(f"Tool called: {name} with args: {arguments}")

        try:
            if name == "daily-focus":
                result = await handlers.daily_focus(
                    energy=arguments.get("energy", "medium"),
                    mode=arguments.get("mode", "deep"),
                    hours=arguments.get("hours", 5.0),
                    max_items=arguments.get("max_items", 10),
                    instructions=arguments.get(
                        "instructions", "General request, give a good assortment of tasks"
                    ),
                    only_projects=arguments.get("only_projects"),
                    exclude_projects=arguments.get("exclude_projects"),
                )

            elif name == "get-full-task":
                result = await handlers.get_full_task(
                    task_id=arguments["task_id"],
                )

            elif name == "add-comment":
                result = await handlers.add_comment(
                    task_id=arguments["task_id"],
                    comment=arguments["comment"],
                )

            elif name == "get-filtered-tasks":
                result = await handlers.get_filtered_tasks(
                    filter=arguments.get("filter"),
                    natural_request=arguments.get("natural_request"),
                    project_id=arguments.get("project_id"),
                    limit=arguments.get("limit", 50),
                )

            elif name == "upsert-task":
                result = await handlers.upsert_task(
                    task_id=arguments.get("task_id"),
                    project_id=arguments.get("project_id"),
                    title=arguments.get("title"),
                    description=arguments.get("description"),
                    priority=arguments.get("priority"),
                    hex_color=arguments.get("hex_color"),
                    done=arguments.get("done"),
                )

            elif name == "export-project-json":
                result = await handlers.export_project_json(
                    output_path=arguments["output_path"],
                    project_id=arguments.get("project_id"),
                    include_completed=arguments.get("include_completed", False),
                    include_comments=arguments.get("include_comments", False),
                    include_metadata=arguments.get("include_metadata", True),
                    custom_filter=arguments.get("custom_filter"),
                    pretty_print=arguments.get("pretty_print", True),
                )

            else:
                raise ValueError(f"Unknown tool: {name}")

            import json

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            logger.error(f"Tool {name} failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server


async def run_server() -> None:
    """Run the MCP server."""
    settings = get_settings()
    logger.info("Starting Vikunja MCP server")
    logger.info(f"Vikunja URL: {settings.vikunja_url}")
    logger.info(f"Gemini model: {settings.gemini_model}")

    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
