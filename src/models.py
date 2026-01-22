"""Data models for Vikunja MCP."""

from enum import Enum

from pydantic import BaseModel, Field


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
    labels: list[PartialLabel] | None = Field(default_factory=list)

    def model_post_init(self, _context):
        """Ensure labels is never None after init."""
        if self.labels is None:
            self.labels = []


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


class Comment(BaseModel):
    """Task comment from Vikunja."""

    id: int
    comment: str
    author: str = ""
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
