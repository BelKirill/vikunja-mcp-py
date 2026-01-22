"""Tests for project context management and context switching."""

import pytest

from src.context import ContextManager
from src.models import (
    EnergyLevel,
    PartialProject,
    ProjectContext,
    RawTask,
    Task,
    WorkMode,
)


class TestProjectContext:
    """Tests for ProjectContext model."""

    def test_from_partial_creates_defaults(self):
        """ProjectContext.from_partial creates context with defaults."""
        partial = PartialProject(
            id=1,
            title="Test Project",
            description="A test project",
        )
        ctx = ProjectContext.from_partial(partial)

        assert ctx.project_id == 1
        assert ctx.name == "Test Project"
        assert ctx.description == "A test project"
        assert ctx.work_type == "general"
        assert ctx.typical_energy == EnergyLevel.MEDIUM
        assert ctx.typical_mode == WorkMode.DEEP
        assert ctx.context_weight == 5

    def test_project_context_with_custom_values(self):
        """ProjectContext accepts custom values."""
        ctx = ProjectContext(
            project_id=5,
            name="Heavy Project",
            work_type="coding",
            domain="infra",
            typical_energy=EnergyLevel.HIGH,
            typical_mode=WorkMode.DEEP,
            context_weight=9,
            requires_tools=["vscode", "kubectl"],
            related_projects=[6, 7],
        )

        assert ctx.project_id == 5
        assert ctx.context_weight == 9
        assert "kubectl" in ctx.requires_tools
        assert 6 in ctx.related_projects


class TestContextSwitchingCost:
    """Tests for context switching cost calculation."""

    @pytest.fixture
    def context_manager(self):
        return ContextManager()

    @pytest.fixture
    def light_project(self):
        return ProjectContext(
            project_id=1,
            name="Light Project",
            work_type="admin",
            context_weight=2,
            typical_energy=EnergyLevel.LOW,
        )

    @pytest.fixture
    def heavy_project(self):
        return ProjectContext(
            project_id=2,
            name="Heavy Project",
            work_type="coding",
            domain="infra",
            context_weight=9,
            typical_energy=EnergyLevel.HIGH,
            requires_tools=["vscode", "kubectl"],
        )

    @pytest.fixture
    def related_project(self, heavy_project):
        return ProjectContext(
            project_id=3,
            name="Related Project",
            work_type="coding",
            domain="infra",
            context_weight=7,
            typical_energy=EnergyLevel.HIGH,
            requires_tools=["vscode"],
            related_projects=[2],  # Related to heavy_project
        )

    def test_same_project_zero_cost(self, context_manager, heavy_project):
        """Switching to same project has zero cost."""
        cost = context_manager.calculate_switch_cost(heavy_project, heavy_project)
        assert cost == 0.0

    def test_no_current_project_partial_cost(self, context_manager, heavy_project):
        """Starting fresh has partial cost based on context weight."""
        cost = context_manager.calculate_switch_cost(None, heavy_project)
        assert 0.0 < cost <= 0.5  # Max 0.5 for initial load

    def test_light_to_heavy_higher_cost(self, context_manager, light_project, heavy_project):
        """Switching from light to heavy project has higher cost."""
        cost = context_manager.calculate_switch_cost(light_project, heavy_project)
        assert cost > 0.3  # Should be significant

    def test_related_projects_lower_cost(self, context_manager, heavy_project, related_project):
        """Switching between related projects has lower cost."""
        cost_related = context_manager.calculate_switch_cost(related_project, heavy_project)
        cost_unrelated = context_manager.calculate_switch_cost(
            ProjectContext(project_id=99, name="Unrelated", context_weight=7),
            heavy_project,
        )
        assert cost_related < cost_unrelated

    def test_same_domain_lower_cost(self, context_manager, heavy_project, related_project):
        """Switching within same domain has lower cost."""
        different_domain = ProjectContext(
            project_id=4,
            name="Different Domain",
            domain="marketing",
            context_weight=heavy_project.context_weight,
        )
        cost_same_domain = context_manager.calculate_switch_cost(related_project, heavy_project)
        cost_diff_domain = context_manager.calculate_switch_cost(different_domain, heavy_project)
        assert cost_same_domain < cost_diff_domain

    def test_cost_never_exceeds_one(self, context_manager):
        """Cost is always capped at 1.0."""
        worst_case = ProjectContext(
            project_id=1,
            name="Worst From",
            work_type="coding",
            domain="a",
            typical_energy=EnergyLevel.HIGH,
            context_weight=10,
            requires_tools=["tool1", "tool2"],
        )
        opposite = ProjectContext(
            project_id=2,
            name="Worst To",
            work_type="admin",
            domain="b",
            typical_energy=EnergyLevel.LOW,
            context_weight=1,
            requires_tools=["tool3"],
        )
        cost = context_manager.calculate_switch_cost(worst_case, opposite)
        assert cost <= 1.0


class TestTaskOrdering:
    """Tests for context-aware task ordering."""

    @pytest.fixture
    def context_manager(self):
        return ContextManager()

    @pytest.fixture
    def projects(self):
        return [
            ProjectContext(project_id=1, name="Project A", context_weight=3),
            ProjectContext(project_id=2, name="Project B", context_weight=8),
            ProjectContext(project_id=3, name="Project C", context_weight=5),
        ]

    def _make_task(self, task_id: int, project_id: int, title: str) -> Task:
        """Create a test task."""
        raw = RawTask(
            id=task_id,
            title=title,
            project_id=project_id,
            identifier=f"TST-{task_id}",
        )
        return Task(identifier=raw.identifier, raw_task=raw)

    def test_group_tasks_by_project(self, context_manager, projects):
        """Tasks are grouped by project."""
        tasks = [
            self._make_task(1, 1, "Task A1"),
            self._make_task(2, 2, "Task B1"),
            self._make_task(3, 1, "Task A2"),
            self._make_task(4, 3, "Task C1"),
        ]
        grouped = context_manager.group_tasks_by_project(tasks, projects)

        assert len(grouped[1]) == 2  # Two tasks in project 1
        assert len(grouped[2]) == 1
        assert len(grouped[3]) == 1

    def test_optimize_order_groups_by_project(self, context_manager, projects):
        """Optimized order groups tasks from same project."""
        tasks = [
            self._make_task(1, 1, "Task A1"),
            self._make_task(2, 2, "Task B1"),
            self._make_task(3, 1, "Task A2"),
            self._make_task(4, 2, "Task B2"),
        ]
        optimized = context_manager.optimize_task_order(tasks, projects)

        # Check that same-project tasks are adjacent
        project_sequence = [t.raw_task.project_id for t in optimized]
        # Should be grouped, not interleaved
        assert project_sequence != [1, 2, 1, 2]

    def test_optimize_order_respects_current_project(self, context_manager, projects):
        """Optimization prioritizes current project tasks first."""
        tasks = [
            self._make_task(1, 1, "Task A1"),
            self._make_task(2, 2, "Task B1"),
            self._make_task(3, 3, "Task C1"),
        ]
        optimized = context_manager.optimize_task_order(
            tasks, projects, current_project_id=2
        )

        # Task from current project should be first
        assert optimized[0].raw_task.project_id == 2


class TestContextFormatting:
    """Tests for prompt formatting."""

    def test_format_context_for_prompt(self):
        """Context is formatted correctly for AI prompts."""
        manager = ContextManager()
        projects = [
            ProjectContext(
                project_id=1,
                name="Test Project",
                work_type="coding",
                domain="test",
                context_weight=7,
            ),
        ]
        formatted = manager.format_context_for_prompt(projects, current_project_id=1)

        assert "PROJECT CONTEXT:" in formatted
        assert "Test Project" in formatted
        assert "[CURRENT]" in formatted
        assert "context_weight=7/10" in formatted
        assert "CONTEXT SWITCHING GUIDANCE" in formatted

    def test_format_empty_projects(self):
        """Empty projects list returns message."""
        manager = ContextManager()
        formatted = manager.format_context_for_prompt([])
        assert "No project context available" in formatted


class TestConfiguredContexts:
    """Tests for pre-configured project contexts."""

    def test_configured_contexts_used(self):
        """Pre-configured contexts are used when available."""
        config = {
            5: ProjectContext(
                project_id=5,
                name="Custom Config",
                work_type="research",
                context_weight=9,
            )
        }
        manager = ContextManager(project_config=config)

        partial = PartialProject(id=5, title="Original Name")
        ctx = manager.get_context(partial)

        assert ctx.name == "Custom Config"
        assert ctx.work_type == "research"
        assert ctx.context_weight == 9

    def test_unconfigured_uses_defaults(self):
        """Unconfigured projects get default context."""
        config = {
            5: ProjectContext(project_id=5, name="Configured", context_weight=9)
        }
        manager = ContextManager(project_config=config)

        partial = PartialProject(id=99, title="Unconfigured Project")
        ctx = manager.get_context(partial)

        assert ctx.name == "Unconfigured Project"
        assert ctx.context_weight == 5  # Default

    def test_enrich_projects_uses_config(self):
        """enrich_projects uses configured contexts."""
        config = {
            1: ProjectContext(project_id=1, name="Config A", context_weight=8),
        }
        manager = ContextManager(project_config=config)

        partials = [
            PartialProject(id=1, title="Project A"),
            PartialProject(id=2, title="Project B"),
        ]
        enriched = manager.enrich_projects(partials)

        assert enriched[0].name == "Config A"
        assert enriched[0].context_weight == 8
        assert enriched[1].name == "Project B"
        assert enriched[1].context_weight == 5  # Default
