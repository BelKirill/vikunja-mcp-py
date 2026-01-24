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


class TestConfigFileLoading:
    """Tests for loading project config from JSON files."""

    def test_load_valid_config_file(self, tmp_path):
        """Valid JSON config file is loaded correctly."""
        from src.context import load_project_config_from_file

        config_file = tmp_path / "projects.json"
        config_file.write_text(
            """{
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
                },
                {
                    "project_id": 9,
                    "name": "Admin Tasks",
                    "work_type": "admin",
                    "typical_energy": "low",
                    "context_weight": 2
                }
            ]
        }"""
        )

        config = load_project_config_from_file(str(config_file))

        assert len(config) == 2
        assert 8 in config
        assert 9 in config

        mcp_ctx = config[8]
        assert mcp_ctx.name == "Vikunja MCP"
        assert mcp_ctx.work_type == "coding"
        assert mcp_ctx.domain == "vikunja-mcp"
        assert mcp_ctx.typical_energy == EnergyLevel.HIGH
        assert mcp_ctx.context_weight == 8
        assert "docker" in mcp_ctx.requires_tools
        assert 9 in mcp_ctx.related_projects

        admin_ctx = config[9]
        assert admin_ctx.typical_energy == EnergyLevel.LOW
        assert admin_ctx.context_weight == 2

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Missing config file returns empty dict."""
        from src.context import load_project_config_from_file

        config = load_project_config_from_file(str(tmp_path / "nonexistent.json"))
        assert config == {}

    def test_load_invalid_json_returns_empty(self, tmp_path):
        """Invalid JSON returns empty dict."""
        from src.context import load_project_config_from_file

        config_file = tmp_path / "invalid.json"
        config_file.write_text("{ this is not valid json }")

        config = load_project_config_from_file(str(config_file))
        assert config == {}

    def test_context_manager_loads_from_path(self, tmp_path):
        """ContextManager loads config from path."""
        config_file = tmp_path / "projects.json"
        config_file.write_text(
            """{
            "projects": [
                {"project_id": 5, "name": "From File", "context_weight": 7}
            ]
        }"""
        )

        manager = ContextManager(config_path=str(config_file))
        partial = PartialProject(id=5, title="Original Name")
        ctx = manager.get_context(partial)

        assert ctx.name == "From File"
        assert ctx.context_weight == 7

    def test_explicit_config_overrides_file(self, tmp_path):
        """Explicitly passed config overrides file config."""
        config_file = tmp_path / "projects.json"
        config_file.write_text(
            """{
            "projects": [
                {"project_id": 5, "name": "From File", "context_weight": 3}
            ]
        }"""
        )

        explicit = {5: ProjectContext(project_id=5, name="Explicit", context_weight=9)}
        manager = ContextManager(config_path=str(config_file), project_config=explicit)

        partial = PartialProject(id=5, title="Original")
        ctx = manager.get_context(partial)

        assert ctx.name == "Explicit"
        assert ctx.context_weight == 9


class TestEmbeddedMetadataParsing:
    """Tests for parsing embedded context from project descriptions."""

    def test_parse_valid_embedded_context(self):
        """Valid embedded context is parsed correctly."""
        from src.context import parse_embedded_project_context

        project = PartialProject(
            id=10,
            title="Test Project",
            description="""
            This is a project description.

            <!-- PROJECT_CONTEXT:{"work_type": "coding", "domain": "test", "context_weight": 7}:END_CONTEXT -->
            """,
        )

        ctx = parse_embedded_project_context(project)

        assert ctx is not None
        assert ctx.project_id == 10
        assert ctx.work_type == "coding"
        assert ctx.domain == "test"
        assert ctx.context_weight == 7
        assert "PROJECT_CONTEXT" not in ctx.description

    def test_parse_full_embedded_context(self):
        """Full embedded context with all fields."""
        from src.context import parse_embedded_project_context

        project = PartialProject(
            id=11,
            title="Full Context",
            description="""<!-- PROJECT_CONTEXT:{"name": "Custom Name", "work_type": "research", "domain": "science", "typical_energy": "high", "typical_mode": "deep", "context_weight": 9, "requires_tools": ["jupyter", "python"], "related_projects": [12, 13]}:END_CONTEXT -->""",
        )

        ctx = parse_embedded_project_context(project)

        assert ctx is not None
        assert ctx.name == "Custom Name"
        assert ctx.work_type == "research"
        assert ctx.typical_energy == EnergyLevel.HIGH
        assert ctx.context_weight == 9
        assert "jupyter" in ctx.requires_tools
        assert 12 in ctx.related_projects

    def test_parse_no_embedded_returns_none(self):
        """Project without embedded context returns None."""
        from src.context import parse_embedded_project_context

        project = PartialProject(
            id=12,
            title="No Metadata",
            description="Just a regular description without metadata.",
        )

        ctx = parse_embedded_project_context(project)
        assert ctx is None

    def test_parse_empty_description_returns_none(self):
        """Empty description returns None."""
        from src.context import parse_embedded_project_context

        project = PartialProject(id=13, title="Empty", description="")
        ctx = parse_embedded_project_context(project)
        assert ctx is None

    def test_parse_invalid_json_returns_none(self):
        """Invalid JSON in embedded context returns None."""
        from src.context import parse_embedded_project_context

        project = PartialProject(
            id=14,
            title="Bad JSON",
            description="<!-- PROJECT_CONTEXT:{invalid json}:END_CONTEXT -->",
        )

        ctx = parse_embedded_project_context(project)
        assert ctx is None

    def test_context_manager_uses_embedded(self):
        """ContextManager parses embedded metadata when no config."""
        project = PartialProject(
            id=20,
            title="Embedded Project",
            description='<!-- PROJECT_CONTEXT:{"work_type": "admin", "context_weight": 3}:END_CONTEXT -->',
        )

        manager = ContextManager()
        ctx = manager.get_context(project)

        assert ctx.work_type == "admin"
        assert ctx.context_weight == 3

    def test_config_takes_priority_over_embedded(self):
        """Pre-configured context takes priority over embedded."""
        project = PartialProject(
            id=21,
            title="Has Both",
            description='<!-- PROJECT_CONTEXT:{"work_type": "embedded", "context_weight": 1}:END_CONTEXT -->',
        )

        config = {21: ProjectContext(project_id=21, name="Config", work_type="config", context_weight=9)}
        manager = ContextManager(project_config=config)
        ctx = manager.get_context(project)

        assert ctx.work_type == "config"
        assert ctx.context_weight == 9
