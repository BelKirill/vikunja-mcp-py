"""Data models for Vikunja MCP."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def _coerce_list(v: list | None) -> list:
    """Convert None to empty list."""
    return v if v is not None else []


def _coerce_dict(v: dict | None) -> dict:
    """Convert None to empty dict."""
    return v if v is not None else {}


class EnergyLevel(str, Enum):
    """User energy levels for task matching."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SOCIAL = "social"


class WorkMode(str, Enum):
    """Work mode preferences."""

    DEEP = "deep"
    QUICK = "quick"
    ADMIN = "admin"


class FocusOptions(BaseModel):
    """Options for focus task selection."""

    energy: EnergyLevel = EnergyLevel.MEDIUM
    mode: WorkMode = WorkMode.DEEP
    max_minutes: int = Field(default=300, ge=5, le=480)
    max_tasks: int = Field(default=10, ge=1, le=50)
    instructions: str = "General request, give a good assortment of tasks"
    exclude_projects: list[int] = Field(default_factory=list)
    only_projects: list[int] = Field(default_factory=list)


class Dependencies(BaseModel):
    """Task dependency tracking."""

    blocked_by: list[int] = Field(default_factory=list)
    blocks: list[int] = Field(default_factory=list)


class ContextualHints(BaseModel):
    """Chain/sequence tracking for tasks."""

    is_part_of_chain: bool = False
    next_in_chain: list[int] = Field(default_factory=list)
    chain_progress: str = ""
    chain_name: str = ""
    chain_description: str = ""


class HyperFocusMetadata(BaseModel):
    """ADHD-optimized task metadata embedded in task descriptions."""

    energy: EnergyLevel = EnergyLevel.MEDIUM
    mode: WorkMode = WorkMode.DEEP
    extend: bool = False
    minutes: int = Field(default=25, ge=5)
    estimate: int = Field(default=25, ge=5)
    hyper_focus_comp: int = Field(default=3, ge=1, le=5)
    instructions: str = ""
    dependencies: Dependencies = Field(default_factory=Dependencies)
    contextual_hints: ContextualHints = Field(default_factory=ContextualHints)


class RelationKind(str, Enum):
    """Vikunja task relation types."""

    SUBTASK = "subtask"
    PARENTTASK = "parenttask"
    RELATED = "related"
    DUPLICATEOF = "duplicateof"
    DUPLICATES = "duplicates"
    BLOCKING = "blocking"  # This task blocks the other
    BLOCKED = "blocked"  # This task is blocked by the other
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    COPIEDFROM = "copiedfrom"
    COPIEDTO = "copiedto"


class RelatedTaskInfo(BaseModel):
    """Minimal info about a related task (from Vikunja related_tasks field)."""

    id: int
    title: str = ""
    done: bool = False
    project_id: int = 0


class PartialLabel(BaseModel):
    """Partial label data from Vikunja."""

    id: int
    title: str
    hex_color: str = ""


class PartialProject(BaseModel):
    """Partial project data from Vikunja."""

    id: int
    title: str
    description: str = ""
    hex_color: str = ""
    parent_project_id: int | None = None


class ProjectContext(BaseModel):
    """Rich project context for AI decision-making.

    This model extends basic project data with work categorization
    and context switching metadata to enable intelligent task grouping
    and minimize cognitive load during focus sessions.
    """

    project_id: int
    name: str
    description: str = ""

    # Work categorization
    work_type: str = "general"  # coding, writing, admin, learning, research
    domain: str = ""  # e.g., "vikunja-mcp", "infra", "fairgen"
    typical_energy: EnergyLevel = EnergyLevel.MEDIUM
    typical_mode: WorkMode = WorkMode.DEEP

    # Context switching metadata
    context_weight: int = Field(default=5, ge=1, le=10)  # How heavy is the context
    requires_tools: list[str] = Field(default_factory=list)  # IDEs, clusters, etc.
    related_projects: list[int] = Field(default_factory=list)  # Projects with shared context

    @classmethod
    def from_partial(cls, project: "PartialProject") -> "ProjectContext":
        """Create ProjectContext from PartialProject with defaults."""
        return cls(
            project_id=project.id,
            name=project.title,
            description=project.description,
        )


class RawTask(BaseModel):
    """Raw task data from Vikunja API."""

    id: int
    title: str
    description: str = ""
    done: bool = False
    hex_color: str = ""
    identifier: str = ""
    priority: int = 0
    project_id: int
    created: str = ""
    updated: str = ""
    labels: Annotated[list[PartialLabel], BeforeValidator(_coerce_list)] = Field(
        default_factory=list
    )
    # related_tasks is a map: {relation_kind: [list of related task info]}
    related_tasks: Annotated[dict[str, list[RelatedTaskInfo]], BeforeValidator(_coerce_dict)] = (
        Field(default_factory=dict)
    )

    @property
    def blocked_by_ids(self) -> list[int]:
        """Get IDs of tasks that block this task."""
        if not self.related_tasks:
            return []
        blocked_tasks = self.related_tasks.get(RelationKind.BLOCKED.value, [])
        return [t.id for t in blocked_tasks]

    @property
    def blocking_ids(self) -> list[int]:
        """Get IDs of tasks that this task blocks."""
        if not self.related_tasks:
            return []
        blocking_tasks = self.related_tasks.get(RelationKind.BLOCKING.value, [])
        return [t.id for t in blocking_tasks]

    @property
    def is_blocked(self) -> bool:
        """Check if this task is blocked by any incomplete task."""
        if not self.related_tasks:
            return False
        blocked_tasks = self.related_tasks.get(RelationKind.BLOCKED.value, [])
        # Task is blocked if any blocking task is not done
        return any(not t.done for t in blocked_tasks)


class Task(BaseModel):
    """Enriched task with parsed hyperfocus metadata."""

    identifier: str
    raw_task: RawTask
    metadata: HyperFocusMetadata | None = None
    clean_description: str = ""
    focus_score: float = 0.0


class RankedTask(BaseModel):
    """Task with AI-assigned ranking score."""

    task: Task
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class DecisionResponse(BaseModel):
    """Response from the AI decision engine."""

    ranked_tasks: list[RankedTask]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    strategy: str
    fallback: bool = False


class CommentAuthor(BaseModel):
    """Author details for a comment."""

    id: int = 0
    name: str = ""
    username: str = ""


def _coerce_author(v: dict | str | None) -> CommentAuthor:
    """Convert author field to CommentAuthor."""
    if v is None:
        return CommentAuthor()
    if isinstance(v, str):
        return CommentAuthor(name=v)
    if isinstance(v, dict):
        return CommentAuthor.model_validate(v)
    return CommentAuthor()


class Comment(BaseModel):
    """Task comment from Vikunja."""

    id: int
    comment: str
    author: Annotated[CommentAuthor, BeforeValidator(_coerce_author)] = Field(
        default_factory=CommentAuthor
    )
    created: str = ""
    updated: str = ""


class ExportOptions(BaseModel):
    """Options for task export."""

    output_path: str
    include_completed: bool = False
    include_comments: bool = False
    include_metadata: bool = True
    custom_filter: str = ""
    pretty_print: bool = True
