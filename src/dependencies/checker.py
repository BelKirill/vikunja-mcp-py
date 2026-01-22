"""Dependency checker for task blocking and chain analysis."""

import logging
from dataclasses import dataclass
from typing import TypeVar

from ..models import RawTask, RelationKind, Task

logger = logging.getLogger(__name__)

T = TypeVar("T", RawTask, Task)


@dataclass
class DependencyChain:
    """Represents a chain of dependent tasks."""

    root_task_id: int
    chain_tasks: list[int]  # Ordered list of task IDs in the chain
    total_tasks: int
    completed_tasks: int
    progress_percent: float
    next_actionable_ids: list[int]  # Tasks that can be worked on now


@dataclass
class BlockingInfo:
    """Detailed blocking information for a task."""

    task_id: int
    is_blocked: bool
    blocked_by_incomplete: list[int]  # IDs of incomplete blocking tasks
    blocked_by_complete: list[int]  # IDs of completed blocking tasks
    blocks_others: list[int]  # IDs of tasks this task blocks
    chain_context: DependencyChain | None = None


class DependencyChecker:
    """Core logic for analyzing task dependencies."""

    def filter_blocked_tasks(self, tasks: list[T]) -> tuple[list[T], list[T]]:
        """Filter tasks into actionable and blocked lists.

        Args:
            tasks: List of tasks to filter (RawTask or Task)

        Returns:
            Tuple of (actionable_tasks, blocked_tasks)
        """
        actionable: list[T] = []
        blocked: list[T] = []

        for task in tasks:
            raw = task.raw_task if hasattr(task, "raw_task") else task
            if raw.is_blocked:
                blocked.append(task)
            else:
                actionable.append(task)

        logger.info(
            f"Filtered {len(tasks)} tasks: {len(actionable)} actionable, {len(blocked)} blocked"
        )
        return actionable, blocked

    def get_blocking_info(self, task: RawTask, all_tasks: list[RawTask]) -> BlockingInfo:
        """Get detailed blocking information for a task.

        Args:
            task: The task to analyze
            all_tasks: All tasks for context (to resolve blocking task details)

        Returns:
            BlockingInfo with detailed dependency information
        """
        task_map = {t.id: t for t in all_tasks}

        blocked_by_incomplete: list[int] = []
        blocked_by_complete: list[int] = []

        # Analyze tasks that block this one
        blocked_tasks = task.related_tasks.get(RelationKind.BLOCKED.value, [])
        for blocker in blocked_tasks:
            if blocker.done:
                blocked_by_complete.append(blocker.id)
            else:
                blocked_by_incomplete.append(blocker.id)

        # Get tasks that this task blocks
        blocks_others = task.blocking_ids

        # Try to identify chain context
        chain = self._analyze_chain(task, task_map)

        return BlockingInfo(
            task_id=task.id,
            is_blocked=task.is_blocked,
            blocked_by_incomplete=blocked_by_incomplete,
            blocked_by_complete=blocked_by_complete,
            blocks_others=blocks_others,
            chain_context=chain,
        )

    def _analyze_chain(self, task: RawTask, task_map: dict[int, RawTask]) -> DependencyChain | None:
        """Analyze if task is part of a dependency chain.

        Walks the blocking relationships to find chain structure.
        """
        # Find the root of the chain (task with no blockers)
        root_id = self._find_chain_root(task, task_map, visited=set())
        if root_id is None:
            return None

        # Build chain from root
        chain_tasks = self._build_chain_order(root_id, task_map, visited=set())
        if len(chain_tasks) < 2:
            # Not really a chain if it's just one task
            return None

        # Calculate progress
        completed = sum(1 for tid in chain_tasks if task_map.get(tid, task).done)
        total = len(chain_tasks)

        # Find next actionable tasks (not blocked, not done)
        next_actionable = []
        for tid in chain_tasks:
            t = task_map.get(tid)
            if t and not t.done and not t.is_blocked:
                next_actionable.append(tid)

        return DependencyChain(
            root_task_id=root_id,
            chain_tasks=chain_tasks,
            total_tasks=total,
            completed_tasks=completed,
            progress_percent=round((completed / total) * 100, 1) if total > 0 else 0,
            next_actionable_ids=next_actionable,
        )

    def _find_chain_root(
        self, task: RawTask, task_map: dict[int, RawTask], visited: set[int]
    ) -> int | None:
        """Find the root task of a dependency chain (task with no blockers)."""
        if task.id in visited:
            return None  # Circular dependency
        visited.add(task.id)

        blocked_by = task.related_tasks.get(RelationKind.BLOCKED.value, [])
        if not blocked_by:
            # This task has no blockers, it's the root
            return task.id

        # Walk up to find root
        for blocker_info in blocked_by:
            blocker = task_map.get(blocker_info.id)
            if blocker:
                root = self._find_chain_root(blocker, task_map, visited)
                if root is not None:
                    return root

        return task.id  # Fallback if blockers not in task_map

    def _build_chain_order(
        self, start_id: int, task_map: dict[int, RawTask], visited: set[int]
    ) -> list[int]:
        """Build ordered list of tasks in a chain starting from root."""
        if start_id in visited:
            return []
        visited.add(start_id)

        task = task_map.get(start_id)
        if not task:
            return [start_id]

        result = [start_id]

        # Add tasks that this one blocks (next in chain)
        for blocked_id in task.blocking_ids:
            result.extend(self._build_chain_order(blocked_id, task_map, visited))

        return result

    def calculate_chain_progress(self, tasks: list[RawTask]) -> dict[int, str]:
        """Calculate progress strings for tasks that are part of chains.

        Returns:
            Dict mapping task_id to progress string like "2/5 (40%)"
        """
        task_map = {t.id: t for t in tasks}
        progress_map: dict[int, str] = {}

        for task in tasks:
            chain = self._analyze_chain(task, task_map)
            if chain:
                progress_map[task.id] = (
                    f"{chain.completed_tasks}/{chain.total_tasks} ({chain.progress_percent}%)"
                )

        return progress_map

    def get_unblocking_tasks(self, tasks: list[RawTask]) -> list[RawTask]:
        """Get tasks that would unblock other tasks when completed.

        These are high-priority tasks because completing them enables more work.

        Returns:
            List of tasks sorted by number of tasks they unblock (descending)
        """
        unblocking: list[tuple[RawTask, int]] = []

        for task in tasks:
            if task.done:
                continue
            blocking_count = len(task.blocking_ids)
            if blocking_count > 0:
                unblocking.append((task, blocking_count))

        # Sort by number of tasks blocked (descending)
        unblocking.sort(key=lambda x: x[1], reverse=True)

        return [t for t, _ in unblocking]
