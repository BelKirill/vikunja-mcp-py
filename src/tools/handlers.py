"""MCP tool handlers for Vikunja integration."""

import json
import logging
import re
from pathlib import Path
from typing import Any

from ..engine import FocusEngine
from ..models import (
    EnergyLevel,
    FocusOptions,
    HyperFocusMetadata,
    RawTask,
    Task,
    WorkMode,
)
from ..vikunja import VikunjaClient

logger = logging.getLogger(__name__)


class ToolHandlers:
    """Handlers for all MCP tools."""

    def __init__(self):
        """Initialize handlers with dependencies."""
        self.vikunja = VikunjaClient()
        self.engine = FocusEngine()

    async def close(self) -> None:
        """Clean up resources."""
        await self.vikunja.close()

    # =========================================================================
    # Tool handlers
    # =========================================================================

    async def daily_focus(
        self,
        energy: str = "medium",
        mode: str = "deep",
        hours: float = 5.0,
        max_items: int = 10,
        instructions: str = "General request, give a good assortment of tasks",
        only_projects: list[int] | None = None,
        exclude_projects: list[int] | None = None,
    ) -> dict[str, Any]:
        """Get AI-recommended tasks for focus session."""
        logger.info(f"daily_focus called: energy={energy}, mode={mode}")

        options = FocusOptions(
            energy=EnergyLevel(energy),
            mode=WorkMode(mode),
            max_minutes=int(hours * 60),
            max_tasks=max_items,
            instructions=instructions,
            only_projects=only_projects or [],
            exclude_projects=exclude_projects or [],
        )

        # Get incomplete tasks
        raw_tasks = await self.vikunja.get_incomplete_tasks()
        logger.info(f"Fetched {len(raw_tasks)} incomplete tasks")

        # Enrich tasks with metadata
        tasks = await self._enrich_tasks(raw_tasks)

        # Get projects for context
        projects = await self.vikunja.get_all_projects()

        # Get AI-ranked tasks
        decision = await self.engine.get_focus_tasks(tasks, options, projects)

        return {
            "message": "Focus tasks retrieved successfully",
            "summary": {
                "total_tasks": len(decision.ranked_tasks),
                "energy_filter": energy,
                "mode_filter": mode,
                "target_hours": hours,
                "strategy": decision.strategy,
                "confidence": decision.confidence,
            },
            "reasoning": decision.reasoning,
            "tasks": [
                {
                    "task_id": rt.task.raw_task.id,
                    "identifier": rt.task.raw_task.identifier,
                    "title": rt.task.raw_task.title,
                    "description": rt.task.clean_description,
                    "priority": rt.task.raw_task.priority,
                    "project_id": rt.task.raw_task.project_id,
                    "score": rt.score,
                    "reasoning": rt.reasoning,
                    "metadata": rt.task.metadata.model_dump() if rt.task.metadata else None,
                }
                for rt in decision.ranked_tasks
            ],
        }

    async def get_full_task(self, task_id: int) -> dict[str, Any]:
        """Get full details for a specific task."""
        logger.info(f"get_full_task called: task_id={task_id}")

        raw_task = await self.vikunja.get_task_by_id(task_id)
        task = self._parse_task(raw_task)

        # Enrich if needed
        labels = await self.vikunja.get_all_labels()
        task, enriched = await self.engine.enrich_task(task, [lbl.model_dump() for lbl in labels])

        if enriched:
            await self.vikunja.update_task(task_id, {"description": task.raw_task.description})

        # Get comments
        comments = await self.vikunja.get_task_comments(task_id)

        # Get project
        project = await self.vikunja.get_project(raw_task.project_id)

        return {
            "task_id": task.raw_task.id,
            "identifier": task.raw_task.identifier,
            "title": task.raw_task.title,
            "description": task.clean_description,
            "hex_color": task.raw_task.hex_color,
            "done": task.raw_task.done,
            "priority": task.raw_task.priority,
            "has_hyperfocus_data": task.metadata is not None,
            "metadata": task.metadata.model_dump() if task.metadata else None,
            "comments": [c.model_dump() for c in comments],
            "project": project.model_dump(),
            "created": task.raw_task.created,
            "updated": task.raw_task.updated,
            "labels": [lbl.model_dump() for lbl in task.raw_task.labels],
        }

    async def add_comment(self, task_id: int, comment: str) -> dict[str, Any]:
        """Add a comment to a task."""
        logger.info(f"add_comment called: task_id={task_id}")

        if not comment:
            raise ValueError("Comment cannot be empty")

        task_comment = await self.vikunja.add_comment(task_id, comment)

        return {
            "status": "succeeded",
            "task_id": task_id,
            "comment": task_comment.model_dump(),
        }

    async def get_filtered_tasks(
        self,
        filter: str | None = None,
        natural_request: str | None = None,
        project_id: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get tasks using filter expressions or natural language.

        Implements retry logic with error context for natural language filters.
        If filter generation/execution fails, retries up to 3 times with error
        feedback to help AI correct the filter expression.
        """
        logger.info(f"get_filtered_tasks called: filter={filter}, natural={natural_request}")

        if not filter and not natural_request:
            raise ValueError("Either 'filter' or 'natural_request' must be provided")

        max_retries = 3
        attempts: list[dict[str, str]] = []

        # Direct filter expression - single attempt
        if filter:
            final_filter = filter
            if project_id:
                final_filter = f"({final_filter}) && project_id = {project_id}"

            try:
                raw_tasks = await self.vikunja.get_filtered_tasks(final_filter)
                return self._build_filter_response(raw_tasks[:limit], "expression", final_filter)
            except Exception as e:
                raise ValueError(f"Invalid filter expression: {filter}. Error: {e}") from e

        # Natural language - retry with error context
        for attempt in range(max_retries):
            try:
                # Generate filter, passing previous errors for context
                previous_errors = attempts if attempts else None
                final_filter = await self.engine.suggest_filter(
                    natural_request,  # type: ignore
                    previous_errors=previous_errors,
                )

                # Add project filter if specified
                if project_id:
                    final_filter = f"({final_filter}) && project_id = {project_id}"

                logger.info(f"Attempt {attempt + 1}/{max_retries}: trying filter '{final_filter}'")

                # Execute filter
                raw_tasks = await self.vikunja.get_filtered_tasks(final_filter)

                # Success - include retry info if we had to retry
                response = self._build_filter_response(
                    raw_tasks[:limit], "natural_language", final_filter
                )
                if attempts:
                    response["summary"]["retry_attempts"] = len(attempts)
                    response["summary"]["previous_errors"] = attempts
                return response

            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"Filter attempt {attempt + 1}/{max_retries} failed: "
                    f"filter='{final_filter}', error={error_msg}"
                )
                attempts.append({"filter": final_filter, "error": error_msg})

        # All retries exhausted - return comprehensive error report
        error_report = {
            "error": "Failed to generate valid filter after maximum retries",
            "original_request": natural_request,
            "total_attempts": max_retries,
            "attempts": attempts,
            "suggestion": (
                "Try rephrasing your request or use a direct filter expression. "
                "Examples: 'done = false', 'priority >= 3', 'project_id = 5'"
            ),
        }
        raise ValueError(json.dumps(error_report, indent=2))

    def _build_filter_response(
        self,
        tasks: list[RawTask],
        filter_type: str,
        filter_used: str,
    ) -> dict[str, Any]:
        """Build standardized response for filtered tasks."""
        return {
            "message": "Filtered tasks retrieved successfully",
            "summary": {
                "total_tasks": len(tasks),
                "filter_type": filter_type,
                "filter_used": filter_used,
            },
            "tasks": [t.model_dump() for t in tasks],
        }

    async def bulk_update_tasks(
        self,
        task_ids: list[int],
        done: bool | None = None,
        priority: int | None = None,
        hex_color: str | None = None,
    ) -> dict[str, Any]:
        """Bulk update multiple tasks with the same changes.

        Supports updating: done status, priority, hex_color.
        Excludes title/description to prevent accidental overwrites.

        Args:
            task_ids: List of task IDs to update
            done: Mark all tasks as done/not done
            priority: Set priority for all tasks (1-5)
            hex_color: Set color for all tasks (6-char hex)

        Returns:
            Summary with success/failure counts and details
        """
        logger.info(f"bulk_update_tasks called: {len(task_ids)} tasks")

        if not task_ids:
            raise ValueError("task_ids list cannot be empty")

        # Build updates dict - only include specified fields
        updates: dict[str, Any] = {}
        if done is not None:
            updates["done"] = done
        if priority is not None:
            if not 1 <= priority <= 5:
                raise ValueError("priority must be between 1 and 5")
            updates["priority"] = priority
        if hex_color is not None:
            if len(hex_color) != 6 or not all(c in "0123456789ABCDEFabcdef" for c in hex_color):
                raise ValueError("hex_color must be 6 hex characters (e.g., 'FF5733')")
            updates["hex_color"] = hex_color

        if not updates:
            raise ValueError(
                "At least one update field (done, priority, hex_color) must be provided"
            )

        # Process in batches of 20 to avoid API overload
        batch_size = 20
        results: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for i in range(0, len(task_ids), batch_size):
            batch = task_ids[i : i + batch_size]

            for task_id in batch:
                try:
                    result = await self.vikunja.update_task(task_id, updates)
                    results.append(
                        {
                            "task_id": result.id,
                            "identifier": result.identifier,
                            "title": result.title,
                            "status": "updated",
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to update task {task_id}: {e}")
                    failed.append(
                        {
                            "task_id": task_id,
                            "status": "failed",
                            "error": str(e),
                        }
                    )

        return {
            "message": f"Bulk update completed: {len(results)} succeeded, {len(failed)} failed",
            "summary": {
                "total_requested": len(task_ids),
                "succeeded": len(results),
                "failed": len(failed),
                "updates_applied": updates,
            },
            "updated_tasks": results,
            "failed_tasks": failed if failed else None,
        }

    async def upsert_task(
        self,
        task_id: int | None = None,
        project_id: int | None = None,
        title: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        hex_color: str | None = None,
        done: bool | None = None,
    ) -> dict[str, Any]:
        """Create or update a task."""
        logger.info(f"upsert_task called: task_id={task_id}")

        action = "updated" if task_id else "created"

        if task_id:
            # Update existing task
            updates: dict[str, Any] = {}
            if title is not None:
                updates["title"] = title
            if description is not None:
                updates["description"] = description
            if priority is not None:
                updates["priority"] = priority
            if hex_color is not None:
                updates["hex_color"] = hex_color
            if done is not None:
                updates["done"] = done

            result = await self.vikunja.update_task(task_id, updates)
        else:
            # Create new task
            if not project_id:
                raise ValueError("project_id is required for new tasks")
            if not title:
                raise ValueError("title is required for new tasks")

            task = RawTask(
                id=0,
                project_id=project_id,
                title=title,
                description=description or "",
                priority=priority or 0,
                hex_color=hex_color or "",
                done=done or False,
            )
            result = await self.vikunja.upsert_task(task)

        return {
            "success": True,
            "action": action,
            "task": {
                "task_id": result.id,
                "identifier": result.identifier,
                "title": result.title,
                "done": result.done,
                "priority": result.priority,
                "description": result.description,
                "hex_color": result.hex_color,
                "project_id": result.project_id,
            },
            "message": f"Task {action} successfully",
        }

    async def export_project_json(
        self,
        output_path: str,
        project_id: int | None = None,
        include_completed: bool = False,
        include_comments: bool = False,
        include_metadata: bool = True,
        custom_filter: str | None = None,
        pretty_print: bool = True,
    ) -> dict[str, Any]:
        """Export tasks to JSON file."""
        logger.info(f"export_project_json called: output_path={output_path}")

        # Build filter
        filters = []
        if not include_completed:
            filters.append("done = false")
        if project_id:
            filters.append(f"project_id = {project_id}")
        if custom_filter:
            filters.append(f"({custom_filter})")

        filter_expr = " && ".join(filters) if filters else None

        # Get tasks
        if filter_expr:
            raw_tasks = await self.vikunja.get_filtered_tasks(filter_expr)
        else:
            raw_tasks = await self.vikunja.get_all_tasks()

        # Enrich and export
        tasks = await self._enrich_tasks(raw_tasks)

        export_data = {
            "exported_at": str(__import__("datetime").datetime.now().isoformat()),
            "task_count": len(tasks),
            "tasks": [
                {
                    "id": t.raw_task.id,
                    "identifier": t.raw_task.identifier,
                    "title": t.raw_task.title,
                    "description": t.clean_description,
                    "done": t.raw_task.done,
                    "priority": t.raw_task.priority,
                    "project_id": t.raw_task.project_id,
                    "metadata": (
                        t.metadata.model_dump() if t.metadata and include_metadata else None
                    ),
                }
                for t in tasks
            ],
        }

        # Add comments if requested
        if include_comments:
            for i, task in enumerate(tasks):
                comments = await self.vikunja.get_task_comments(task.raw_task.id)
                export_data["tasks"][i]["comments"] = [c.model_dump() for c in comments]

        # Write to file
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w") as f:
            if pretty_print:
                json.dump(export_data, f, indent=2)
            else:
                json.dump(export_data, f)

        return {
            "success": True,
            "file_path": str(output),
            "task_count": len(tasks),
            "file_size": output.stat().st_size,
        }

    # =========================================================================
    # Private helpers
    # =========================================================================

    async def _enrich_tasks(self, raw_tasks: list[RawTask]) -> list[Task]:
        """Parse and optionally enrich a list of tasks."""
        tasks = [self._parse_task(rt) for rt in raw_tasks]
        # Note: For bulk operations, we skip AI enrichment to save API calls
        # Tasks get enriched when accessed individually via get_full_task
        return tasks

    def _parse_task(self, raw_task: RawTask) -> Task:
        """Parse a raw task and extract any embedded metadata."""
        clean_desc, metadata = self._extract_metadata(raw_task.description)

        return Task(
            identifier=raw_task.identifier,
            raw_task=raw_task,
            metadata=metadata,
            clean_description=clean_desc,
        )

    def _extract_metadata(self, description: str) -> tuple[str, HyperFocusMetadata | None]:
        """Extract embedded metadata from task description."""
        pattern = r"<!-- HYPERFOCUS_METADATA:(.*?):END_METADATA -->"
        match = re.search(pattern, description, re.DOTALL)

        if not match:
            return description, None

        try:
            metadata_json = match.group(1)
            data = json.loads(metadata_json)
            metadata = HyperFocusMetadata(
                energy=EnergyLevel(data.get("energy", "medium")),
                mode=WorkMode(data.get("mode", "deep")),
                extend=data.get("extend", False),
                minutes=data.get("minutes", 25),
                estimate=data.get("estimate", 25),
                hyper_focus_comp=data.get("hyper_focus_comp", 3),
                instructions=data.get("instructions", ""),
            )
            clean_desc = re.sub(pattern, "", description).strip()
            return clean_desc, metadata
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse metadata: {e}")
            return description, None
