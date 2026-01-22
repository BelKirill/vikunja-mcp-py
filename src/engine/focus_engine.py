"""AI-powered focus engine for intelligent task selection."""

import json
import logging
import re

from google import genai

from ..config import get_settings
from ..dependencies import DependencyChecker
from ..models import (
    DecisionResponse,
    EnergyLevel,
    FocusOptions,
    HyperFocusMetadata,
    PartialProject,
    RankedTask,
    Task,
    WorkMode,
)

logger = logging.getLogger(__name__)


class FocusEngine:
    """AI-powered task selection and enrichment engine."""

    def __init__(self):
        """Initialize the focus engine with Google Gen AI SDK."""
        settings = get_settings()

        # Initialize Gen AI client for Vertex AI
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project,
            location=settings.gcp_location,
        )
        self.model_name = settings.gemini_model
        self.dependency_checker = DependencyChecker()
        logger.info(f"FocusEngine initialized with model: {self.model_name}")

    async def get_focus_tasks(
        self,
        tasks: list[Task],
        options: FocusOptions,
        projects: list[PartialProject],
    ) -> DecisionResponse:
        """Get AI-ranked tasks for a focus session."""
        logger.info(f"Ranking {len(tasks)} tasks for focus session")

        # Apply pre-filters (now returns actionable and blocked separately)
        actionable_tasks, blocked_tasks = self._apply_filters(tasks, options)

        if not actionable_tasks:
            blocked_msg = (
                f" ({len(blocked_tasks)} tasks are blocked by dependencies)"
                if blocked_tasks
                else ""
            )
            return DecisionResponse(
                ranked_tasks=[],
                reasoning=f"No actionable tasks match current context{blocked_msg}",
                confidence=0.0,
                strategy="contextual_filter",
                fallback=False,
            )

        # Build prompt for AI ranking (only actionable tasks)
        prompt = self._build_ranking_prompt(actionable_tasks, options, projects)

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            result = self._parse_ranking_response(response.text, actionable_tasks)
            logger.info(
                f"AI ranked {len(result.ranked_tasks)} tasks "
                f"({len(blocked_tasks)} blocked tasks excluded)"
            )
            return result
        except Exception as e:
            logger.warning(f"AI ranking failed, using heuristic fallback: {e}")
            return self._heuristic_fallback(actionable_tasks, options)

    async def enrich_task(self, task: Task, available_labels: list[dict]) -> tuple[Task, bool]:
        """Enrich a task with AI-generated metadata if missing."""
        if task.metadata is not None:
            return task, False

        prompt = self._build_enrichment_prompt(task, available_labels)

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            metadata = self._parse_enrichment_response(response.text)
            task.metadata = metadata
            task.raw_task.description = self._embed_metadata(task.clean_description, metadata)
            logger.info(f"Enriched task {task.raw_task.id} with metadata")
            return task, True
        except Exception as e:
            logger.warning(f"Failed to enrich task {task.raw_task.id}: {e}")
            return task, False

    async def suggest_filter(
        self,
        natural_request: str,
        previous_errors: list[dict] | None = None,
    ) -> str:
        """Convert natural language to Vikunja filter expression.

        Args:
            natural_request: The natural language request to convert
            previous_errors: List of previous attempt errors for retry context

        Returns:
            A Vikunja filter expression string
        """
        error_context = ""
        if previous_errors:
            error_context = "\n\nPREVIOUS ATTEMPTS FAILED:\n"
            for i, err in enumerate(previous_errors, 1):
                error_context += f"{i}. Filter: {err['filter']} -> Error: {err['error']}\n"
            error_context += "\nPlease generate a CORRECTED filter avoiding these errors."

        prompt = f"""Convert this natural language request to a Vikunja filter expression.

Request: {natural_request}

Vikunja filter syntax:
- done = false (incomplete tasks)
- priority >= 3 (high priority)
- project_id = 5 (specific project)
- Use && for AND, || for OR
- String values need quotes: title ~ "keyword"
- Date filters: due_date < now (overdue tasks)
{error_context}

Return ONLY the filter expression, nothing else. No markdown, no explanation."""

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            filter_expr = response.text.strip()
            # Clean up any markdown code blocks if present
            if filter_expr.startswith("```"):
                filter_expr = filter_expr.split("\n", 1)[-1]
            if filter_expr.endswith("```"):
                filter_expr = filter_expr.rsplit("```", 1)[0]
            filter_expr = filter_expr.strip()
            logger.info(f"Generated filter: {filter_expr}")
            return filter_expr
        except Exception as e:
            logger.error(f"Failed to generate filter: {e}")
            return "done = false"

    # =========================================================================
    # Private methods
    # =========================================================================

    def _apply_filters(
        self, tasks: list[Task], options: FocusOptions
    ) -> tuple[list[Task], list[Task]]:
        """Apply contextual filters to task list.

        Returns:
            Tuple of (actionable_tasks, blocked_tasks)
        """
        filtered = tasks

        # Filter by projects
        if options.only_projects:
            filtered = [t for t in filtered if t.raw_task.project_id in options.only_projects]
        if options.exclude_projects:
            filtered = [
                t for t in filtered if t.raw_task.project_id not in options.exclude_projects
            ]

        # Filter completed tasks
        filtered = [t for t in filtered if not t.raw_task.done]

        # Filter by energy/mode if metadata available
        filtered = [
            t
            for t in filtered
            if t.metadata is None
            or (
                self._energy_matches(t.metadata.energy, options.energy)
                and self._mode_matches(t.metadata.mode, options.mode)
            )
        ]

        # Separate blocked tasks using DependencyChecker
        actionable, blocked = self.dependency_checker.filter_blocked_tasks(filtered)

        logger.debug(
            f"Filtered {len(tasks)} -> {len(actionable)} actionable, {len(blocked)} blocked"
        )
        return actionable, blocked

    def _energy_matches(self, task_energy: EnergyLevel, user_energy: EnergyLevel) -> bool:
        """Check if task energy requirement matches user's current energy."""
        energy_order = [EnergyLevel.LOW, EnergyLevel.MEDIUM, EnergyLevel.HIGH]
        if task_energy == EnergyLevel.SOCIAL or user_energy == EnergyLevel.SOCIAL:
            return task_energy == user_energy
        return energy_order.index(task_energy) <= energy_order.index(user_energy)

    def _mode_matches(self, task_mode: WorkMode, user_mode: WorkMode) -> bool:
        """Check if task mode matches user's preferred mode."""
        # For now, exact match or admin mode accepts all
        return task_mode == user_mode or user_mode == WorkMode.ADMIN

    def _build_ranking_prompt(
        self,
        tasks: list[Task],
        options: FocusOptions,
        projects: list[PartialProject],
    ) -> str:
        """Build the prompt for task ranking."""
        project_map = {p.id: p.title for p in projects}

        task_list = []
        for i, task in enumerate(tasks):
            project_name = project_map.get(task.raw_task.project_id, "Unknown")
            # Add dependency context
            dep_info = ""
            blocking_count = len(task.raw_task.blocking_ids)
            if blocking_count > 0:
                dep_info = f" [UNBLOCKS {blocking_count} task(s)]"
            task_list.append(
                f"{i}. [{task.raw_task.identifier}] {task.raw_task.title} "
                f"(Project: {project_name}, Priority: {task.raw_task.priority}){dep_info}"
            )

        return f"""You are an ADHD-optimized task selection assistant. \
Rank these tasks for a focus session.

USER CONTEXT:
- Energy level: {options.energy.value}
- Work mode: {options.mode.value}
- Available time: {options.max_minutes} minutes
- Max tasks to return: {options.max_tasks}
- Instructions: {options.instructions}

TASKS:
{chr(10).join(task_list)}

RANKING CRITERIA:
1. Match task to user's energy level (low energy = simple tasks, high = complex)
2. Match task to work mode (deep = focused work, quick = short tasks, admin = emails/admin)
3. Consider task priority
4. Time available should influence task complexity
5. Follow any special instructions
6. PRIORITIZE tasks marked with [UNBLOCKS N task(s)] - completing these enables more work

Return a JSON object with this structure:
{{
  "ranked_tasks": [
    {{"index": 0, "score": 0.95, "reasoning": "High priority, matches deep work mode"}},
    ...
  ],
  "overall_reasoning": "Brief explanation of ranking strategy",
  "confidence": 0.85
}}

Return ONLY valid JSON, no markdown code blocks."""

    def _parse_ranking_response(self, response_text: str, tasks: list[Task]) -> DecisionResponse:
        """Parse the AI ranking response."""
        # Clean up response
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        data = json.loads(text)

        ranked_tasks = []
        for item in data.get("ranked_tasks", [])[:10]:
            idx = item.get("index", 0)
            if 0 <= idx < len(tasks):
                ranked_tasks.append(
                    RankedTask(
                        task=tasks[idx],
                        score=min(1.0, max(0.0, item.get("score", 0.5))),
                        reasoning=item.get("reasoning", ""),
                    )
                )

        # Sort by score descending
        ranked_tasks.sort(key=lambda x: x.score, reverse=True)

        return DecisionResponse(
            ranked_tasks=ranked_tasks,
            reasoning=data.get("overall_reasoning", "AI-ranked tasks"),
            confidence=min(1.0, max(0.0, data.get("confidence", 0.7))),
            strategy="gemini_ranking",
            fallback=False,
        )

    def _heuristic_fallback(self, tasks: list[Task], options: FocusOptions) -> DecisionResponse:
        """Fallback to heuristic ranking when AI fails."""
        # Simple heuristic: sort by priority
        sorted_tasks = sorted(tasks, key=lambda t: t.raw_task.priority, reverse=True)

        ranked_tasks = [
            RankedTask(
                task=task,
                score=0.5 + (task.raw_task.priority * 0.1),
                reasoning="Priority-based heuristic",
            )
            for task in sorted_tasks[: options.max_tasks]
        ]

        return DecisionResponse(
            ranked_tasks=ranked_tasks,
            reasoning="Used heuristic fallback due to AI service unavailability",
            confidence=0.6,
            strategy="heuristic_fallback",
            fallback=True,
        )

    def _build_enrichment_prompt(self, task: Task, available_labels: list[dict]) -> str:
        """Build prompt for task enrichment."""
        return f"""Analyze this task and generate ADHD-optimized metadata.

TASK:
Title: {task.raw_task.title}
Description: {task.clean_description}
Priority: {task.raw_task.priority}

Generate metadata as JSON:
{{
  "energy": "low|medium|high|social",
  "mode": "deep|quick|admin",
  "extend": true/false (can extend beyond 25 min?),
  "minutes": 25 (base pomodoro length),
  "estimate": 60 (total estimated minutes),
  "hyper_focus_comp": 1-5 (hyperfocus compatibility),
  "instructions": "Considerations for this task"
}}

Return ONLY valid JSON, no markdown."""

    def _parse_enrichment_response(self, response_text: str) -> HyperFocusMetadata:
        """Parse enrichment response into metadata."""
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        data = json.loads(text)
        return HyperFocusMetadata(
            energy=EnergyLevel(data.get("energy", "medium")),
            mode=WorkMode(data.get("mode", "deep")),
            extend=data.get("extend", False),
            minutes=data.get("minutes", 25),
            estimate=data.get("estimate", 25),
            hyper_focus_comp=data.get("hyper_focus_comp", 3),
            instructions=data.get("instructions", ""),
        )

    def _embed_metadata(self, description: str, metadata: HyperFocusMetadata) -> str:
        """Embed metadata JSON into task description."""
        metadata_json = metadata.model_dump_json()
        return f"{description}\n\n<!-- HYPERFOCUS_METADATA:{metadata_json}:END_METADATA -->"
