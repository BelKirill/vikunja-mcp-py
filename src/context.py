"""Project context management and context switching cost calculation."""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

from .models import (
    EnergyLevel,
    PartialProject,
    ProjectContext,
    Task,
    WorkMode,
)

logger = logging.getLogger(__name__)

# Pattern for embedded project context metadata in project descriptions
PROJECT_CONTEXT_PATTERN = r"<!--\s*PROJECT_CONTEXT:(.*?):END_CONTEXT\s*-->"


def load_project_config_from_file(config_path: str) -> dict[int, ProjectContext]:
    """Load project context configuration from a JSON file.

    Expected JSON format:
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

    Args:
        config_path: Path to the JSON configuration file

    Returns:
        Dictionary mapping project IDs to ProjectContext objects
    """
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Project config file not found: {config_path}")
        return {}

    try:
        with open(path) as f:
            data = json.load(f)

        config: dict[int, ProjectContext] = {}
        for project_data in data.get("projects", []):
            project_id = project_data.get("project_id")
            if project_id is None:
                logger.warning("Skipping project config without project_id")
                continue

            # Parse energy and mode enums
            energy_str = project_data.get("typical_energy", "medium")
            mode_str = project_data.get("typical_mode", "deep")

            try:
                typical_energy = EnergyLevel(energy_str)
            except ValueError:
                typical_energy = EnergyLevel.MEDIUM

            try:
                typical_mode = WorkMode(mode_str)
            except ValueError:
                typical_mode = WorkMode.DEEP

            ctx = ProjectContext(
                project_id=project_id,
                name=project_data.get("name", f"Project {project_id}"),
                description=project_data.get("description", ""),
                work_type=project_data.get("work_type", "general"),
                domain=project_data.get("domain", ""),
                typical_energy=typical_energy,
                typical_mode=typical_mode,
                context_weight=project_data.get("context_weight", 5),
                requires_tools=project_data.get("requires_tools", []),
                related_projects=project_data.get("related_projects", []),
            )
            config[project_id] = ctx

        logger.info(f"Loaded {len(config)} project contexts from {config_path}")
        return config

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse project config JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load project config: {e}")
        return {}


def parse_embedded_project_context(
    project: PartialProject,
) -> ProjectContext | None:
    """Parse embedded context metadata from project description.

    Looks for a JSON block in the format:
    <!-- PROJECT_CONTEXT:{"work_type": "coding", ...}:END_CONTEXT -->

    Args:
        project: The project with potential embedded metadata

    Returns:
        ProjectContext if metadata found, None otherwise
    """
    if not project.description:
        return None

    match = re.search(PROJECT_CONTEXT_PATTERN, project.description, re.DOTALL)
    if not match:
        return None

    try:
        metadata_json = match.group(1).strip()
        data = json.loads(metadata_json)

        # Parse energy and mode enums
        energy_str = data.get("typical_energy", "medium")
        mode_str = data.get("typical_mode", "deep")

        try:
            typical_energy = EnergyLevel(energy_str)
        except ValueError:
            typical_energy = EnergyLevel.MEDIUM

        try:
            typical_mode = WorkMode(mode_str)
        except ValueError:
            typical_mode = WorkMode.DEEP

        # Extract clean description (without metadata block)
        clean_desc = re.sub(PROJECT_CONTEXT_PATTERN, "", project.description).strip()

        return ProjectContext(
            project_id=project.id,
            name=data.get("name", project.title),
            description=clean_desc,
            work_type=data.get("work_type", "general"),
            domain=data.get("domain", ""),
            typical_energy=typical_energy,
            typical_mode=typical_mode,
            context_weight=data.get("context_weight", 5),
            requires_tools=data.get("requires_tools", []),
            related_projects=data.get("related_projects", []),
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse embedded project context for {project.id}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error parsing project context for {project.id}: {e}")
        return None


class ContextManager:
    """Manages project context and calculates context switching costs."""

    def __init__(
        self,
        project_config: dict[int, ProjectContext] | None = None,
        config_path: str | None = None,
    ):
        """Initialize the context manager.

        Args:
            project_config: Optional pre-configured project contexts.
                           Keys are project IDs, values are ProjectContext objects.
            config_path: Optional path to JSON config file. If provided,
                        loads project contexts from the file.
        """
        self._config: dict[int, ProjectContext] = {}
        self._current_project_id: int | None = None

        # Load from config file if provided
        if config_path:
            self._config = load_project_config_from_file(config_path)

        # Override with explicitly provided config
        if project_config:
            self._config.update(project_config)

    def set_current_project(self, project_id: int | None) -> None:
        """Set the current active project context."""
        self._current_project_id = project_id

    def get_context(self, project: PartialProject) -> ProjectContext:
        """Get rich context for a project.

        Priority order:
        1. Pre-configured context (from file or explicit config)
        2. Embedded metadata in project description
        3. Default context from project title/description
        """
        # Check pre-configured contexts first
        if project.id in self._config:
            return self._config[project.id]

        # Try to parse embedded metadata from description
        embedded_ctx = parse_embedded_project_context(project)
        if embedded_ctx:
            # Cache for future lookups
            self._config[project.id] = embedded_ctx
            return embedded_ctx

        # Fall back to default
        return ProjectContext.from_partial(project)

    def enrich_projects(
        self,
        projects: list[PartialProject],
    ) -> list[ProjectContext]:
        """Enrich a list of projects with context."""
        return [self.get_context(p) for p in projects]

    def calculate_switch_cost(
        self,
        from_project: ProjectContext | None,
        to_project: ProjectContext,
    ) -> float:
        """Calculate cognitive cost of switching between projects.

        Returns a value from 0.0 (no cost) to 1.0 (maximum cognitive cost).

        Factors considered:
        - Same project: 0.0 (no switching)
        - Related projects: lower cost (shared context)
        - Context weight difference: higher weight = more mental loading
        - Different work types: adds switching cost
        - Different energy requirements: adds adjustment cost
        """
        if from_project is None:
            # No current context, switching cost is based on loading the new context
            return to_project.context_weight / 20.0  # Max 0.5 for initial load

        if from_project.project_id == to_project.project_id:
            return 0.0  # Same project, no cost

        # Base cost from context weight
        base_cost = abs(from_project.context_weight - to_project.context_weight) / 10.0

        # Related project discount
        if to_project.project_id in from_project.related_projects:
            base_cost *= 0.5

        # Same domain discount
        if from_project.domain and from_project.domain == to_project.domain:
            base_cost *= 0.7

        # Work type mismatch penalty
        work_type_cost = 0.0
        if from_project.work_type != to_project.work_type:
            work_type_cost = 0.15

        # Energy level mismatch penalty
        energy_cost = 0.0
        if from_project.typical_energy != to_project.typical_energy:
            energy_order = [EnergyLevel.LOW, EnergyLevel.MEDIUM, EnergyLevel.HIGH]
            try:
                diff = abs(
                    energy_order.index(from_project.typical_energy)
                    - energy_order.index(to_project.typical_energy)
                )
                energy_cost = diff * 0.1
            except ValueError:
                # SOCIAL energy doesn't fit in the order
                energy_cost = 0.2

        # Tool switching penalty
        tool_cost = 0.0
        if from_project.requires_tools and to_project.requires_tools:
            shared_tools = set(from_project.requires_tools) & set(to_project.requires_tools)
            if not shared_tools:
                tool_cost = 0.1

        total_cost = min(1.0, base_cost + work_type_cost + energy_cost + tool_cost)
        logger.debug(f"Switch cost {from_project.name} -> {to_project.name}: {total_cost:.2f}")
        return total_cost

    def group_tasks_by_project(
        self,
        tasks: list[Task],
        projects: list[ProjectContext],
    ) -> dict[int, list[Task]]:
        """Group tasks by project ID."""
        project_map = {p.project_id: p for p in projects}
        grouped: dict[int, list[Task]] = defaultdict(list)

        for task in tasks:
            project_id = task.raw_task.project_id
            if project_id in project_map:
                grouped[project_id].append(task)
            else:
                grouped[0].append(task)  # Unknown project bucket

        return dict(grouped)

    def optimize_task_order(
        self,
        tasks: list[Task],
        projects: list[ProjectContext],
        current_project_id: int | None = None,
    ) -> list[Task]:
        """Reorder tasks to minimize context switching.

        Uses a greedy algorithm to group tasks by project while
        respecting score/priority ordering within each group.

        Args:
            tasks: List of tasks to reorder (assumed pre-sorted by score)
            projects: List of enriched project contexts
            current_project_id: Optional current project for continuity

        Returns:
            Reordered task list minimizing context switches
        """
        if len(tasks) <= 1:
            return tasks

        project_map = {p.project_id: p for p in projects}
        grouped = self.group_tasks_by_project(tasks, projects)

        # If we have a current project, prioritize those tasks
        reordered: list[Task] = []
        if current_project_id and current_project_id in grouped:
            reordered.extend(grouped.pop(current_project_id))

        # Sort remaining project groups by lowest switch cost from current/last
        last_project = project_map.get(current_project_id) if current_project_id else None

        while grouped:
            # Find project with lowest switch cost
            min_cost = float("inf")
            best_project_id = None

            for pid in grouped:
                ctx = project_map.get(pid)
                if ctx:
                    cost = self.calculate_switch_cost(last_project, ctx)
                    if cost < min_cost:
                        min_cost = cost
                        best_project_id = pid
                else:
                    # Unknown project, default medium cost
                    if 0.5 < min_cost:
                        min_cost = 0.5
                        best_project_id = pid

            if best_project_id is not None:
                reordered.extend(grouped.pop(best_project_id))
                last_project = project_map.get(best_project_id)

        return reordered

    def format_context_for_prompt(
        self,
        projects: list[ProjectContext],
        current_project_id: int | None = None,
    ) -> str:
        """Format project contexts for inclusion in AI prompts.

        Returns a string suitable for embedding in ranking prompts.
        """
        if not projects:
            return "No project context available."

        lines = ["PROJECT CONTEXT:"]
        for ctx in projects:
            current_marker = " [CURRENT]" if ctx.project_id == current_project_id else ""
            lines.append(
                f"- {ctx.name} (ID: {ctx.project_id}){current_marker}: "
                f"type={ctx.work_type}, energy={ctx.typical_energy.value}, "
                f"context_weight={ctx.context_weight}/10"
            )
            if ctx.domain:
                lines[-1] += f", domain={ctx.domain}"
            if ctx.requires_tools:
                lines[-1] += f", tools={','.join(ctx.requires_tools)}"

        lines.append("")
        lines.append(
            "CONTEXT SWITCHING GUIDANCE: "
            "Prioritize completing multiple tasks in the same project before switching. "
            "Higher context_weight projects require more cognitive loading."
        )

        return "\n".join(lines)
