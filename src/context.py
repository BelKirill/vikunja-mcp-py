"""Project context management and context switching cost calculation."""

import logging
from collections import defaultdict

from .models import (
    EnergyLevel,
    PartialProject,
    ProjectContext,
    Task,
)

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages project context and calculates context switching costs."""

    def __init__(self, project_config: dict[int, ProjectContext] | None = None):
        """Initialize the context manager.

        Args:
            project_config: Optional pre-configured project contexts.
                           Keys are project IDs, values are ProjectContext objects.
        """
        self._config: dict[int, ProjectContext] = project_config or {}
        self._current_project_id: int | None = None

    def set_current_project(self, project_id: int | None) -> None:
        """Set the current active project context."""
        self._current_project_id = project_id

    def get_context(self, project: PartialProject) -> ProjectContext:
        """Get rich context for a project.

        Uses pre-configured context if available, otherwise creates default.
        """
        if project.id in self._config:
            return self._config[project.id]
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
