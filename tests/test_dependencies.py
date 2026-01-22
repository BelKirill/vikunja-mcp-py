"""Tests for dependency checker module."""

import pytest

from src.dependencies import DependencyChecker
from src.models import RawTask, RelatedTaskInfo


@pytest.fixture
def checker():
    """Create a DependencyChecker instance."""
    return DependencyChecker()


@pytest.fixture
def sample_tasks():
    """Create a sample set of tasks with dependencies."""
    # Task 1 blocks Task 2, Task 2 blocks Task 3 (chain)
    return [
        RawTask(
            id=1,
            project_id=8,
            title="First task (root)",
            done=True,
            related_tasks={
                "blocking": [RelatedTaskInfo(id=2, title="Second", done=False)]
            },
        ),
        RawTask(
            id=2,
            project_id=8,
            title="Second task (middle)",
            done=False,
            related_tasks={
                "blocked": [RelatedTaskInfo(id=1, title="First", done=True)],
                "blocking": [RelatedTaskInfo(id=3, title="Third", done=False)],
            },
        ),
        RawTask(
            id=3,
            project_id=8,
            title="Third task (end)",
            done=False,
            related_tasks={
                "blocked": [RelatedTaskInfo(id=2, title="Second", done=False)]
            },
        ),
        RawTask(
            id=4,
            project_id=8,
            title="Independent task",
            done=False,
            related_tasks={},
        ),
    ]


class TestFilterBlockedTasks:
    """Tests for filter_blocked_tasks method."""

    def test_filters_blocked_from_actionable(self, checker, sample_tasks):
        """Blocked tasks should be separated from actionable."""
        actionable, blocked = checker.filter_blocked_tasks(sample_tasks)

        # Task 1 (done), Task 2 (blocked by done task = not blocked), Task 4 (no deps)
        # Task 3 is blocked by incomplete task 2
        actionable_ids = [t.id for t in actionable]
        blocked_ids = [t.id for t in blocked]

        # Task 3 is blocked (task 2 not done)
        assert 3 in blocked_ids
        # Task 4 is actionable (no dependencies)
        assert 4 in actionable_ids
        # Task 1 is actionable (done, no blockers)
        assert 1 in actionable_ids
        # Task 2 is actionable (blocker task 1 is done)
        assert 2 in actionable_ids

    def test_empty_list_returns_empty(self, checker):
        """Empty input returns empty outputs."""
        actionable, blocked = checker.filter_blocked_tasks([])
        assert actionable == []
        assert blocked == []

    def test_all_actionable_when_no_blockers(self, checker):
        """Tasks with no blockers are all actionable."""
        tasks = [
            RawTask(id=1, project_id=1, title="Task 1"),
            RawTask(id=2, project_id=1, title="Task 2"),
        ]
        actionable, blocked = checker.filter_blocked_tasks(tasks)
        assert len(actionable) == 2
        assert len(blocked) == 0


class TestGetBlockingInfo:
    """Tests for get_blocking_info method."""

    def test_identifies_incomplete_blockers(self, checker, sample_tasks):
        """Should identify incomplete blocking tasks."""
        task3 = sample_tasks[2]  # Blocked by task 2
        info = checker.get_blocking_info(task3, sample_tasks)

        assert info.is_blocked is True
        assert 2 in info.blocked_by_incomplete
        assert info.blocked_by_complete == []

    def test_identifies_complete_blockers(self, checker, sample_tasks):
        """Should identify complete blocking tasks."""
        task2 = sample_tasks[1]  # Blocked by task 1 (done)
        info = checker.get_blocking_info(task2, sample_tasks)

        assert info.is_blocked is False  # Blocker is done
        assert 1 in info.blocked_by_complete
        assert info.blocked_by_incomplete == []

    def test_identifies_blocked_others(self, checker, sample_tasks):
        """Should identify tasks this one blocks."""
        task2 = sample_tasks[1]  # Blocks task 3
        info = checker.get_blocking_info(task2, sample_tasks)

        assert 3 in info.blocks_others


class TestChainAnalysis:
    """Tests for chain analysis methods."""

    def test_chain_progress(self, checker, sample_tasks):
        """Should calculate chain progress correctly."""
        progress = checker.calculate_chain_progress(sample_tasks)

        # Tasks 1, 2, 3 form a chain with task 1 done
        # Progress should be 1/3 for each task in the chain
        if 1 in progress:
            assert "1/3" in progress[1]

    def test_get_unblocking_tasks(self, checker, sample_tasks):
        """Should identify tasks that unblock others."""
        unblocking = checker.get_unblocking_tasks(sample_tasks)

        # Task 2 blocks task 3, so it should be in the list
        unblocking_ids = [t.id for t in unblocking]
        assert 2 in unblocking_ids

    def test_unblocking_sorted_by_impact(self, checker):
        """Tasks should be sorted by number of tasks they unblock."""
        tasks = [
            RawTask(
                id=1,
                project_id=1,
                title="Blocks 1",
                related_tasks={"blocking": [RelatedTaskInfo(id=10)]},
            ),
            RawTask(
                id=2,
                project_id=1,
                title="Blocks 3",
                related_tasks={
                    "blocking": [
                        RelatedTaskInfo(id=11),
                        RelatedTaskInfo(id=12),
                        RelatedTaskInfo(id=13),
                    ]
                },
            ),
        ]
        unblocking = checker.get_unblocking_tasks(tasks)

        # Task 2 should come first (blocks more)
        assert unblocking[0].id == 2
        assert unblocking[1].id == 1


class TestEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_circular_dependency_handling(self, checker):
        """Should handle circular dependencies without infinite loop."""
        # Task A blocks B, B blocks A (circular)
        tasks = [
            RawTask(
                id=1,
                project_id=1,
                title="Task A",
                related_tasks={
                    "blocked": [RelatedTaskInfo(id=2, done=False)],
                    "blocking": [RelatedTaskInfo(id=2)],
                },
            ),
            RawTask(
                id=2,
                project_id=1,
                title="Task B",
                related_tasks={
                    "blocked": [RelatedTaskInfo(id=1, done=False)],
                    "blocking": [RelatedTaskInfo(id=1)],
                },
            ),
        ]
        # Should not hang - both are blocked
        actionable, blocked = checker.filter_blocked_tasks(tasks)
        assert len(blocked) == 2

    def test_long_dependency_chain(self, checker):
        """Should handle long dependency chains."""
        # 1 -> 2 -> 3 -> 4 -> 5
        tasks = []
        for i in range(1, 6):
            related = {}
            if i > 1:
                related["blocked"] = [RelatedTaskInfo(id=i - 1, done=i == 2)]
            if i < 5:
                related["blocking"] = [RelatedTaskInfo(id=i + 1)]
            tasks.append(
                RawTask(
                    id=i, project_id=1, title=f"Task {i}", done=i == 1, related_tasks=related
                )
            )

        progress = checker.calculate_chain_progress(tasks)
        # All tasks in the chain should have progress info
        assert len(progress) > 0

    def test_task_with_all_blockers_done(self, checker):
        """Task should be actionable when all blockers are done."""
        tasks = [
            RawTask(
                id=1,
                project_id=1,
                title="Blocked task",
                related_tasks={
                    "blocked": [
                        RelatedTaskInfo(id=10, done=True),
                        RelatedTaskInfo(id=11, done=True),
                        RelatedTaskInfo(id=12, done=True),
                    ]
                },
            ),
        ]
        actionable, blocked = checker.filter_blocked_tasks(tasks)
        assert len(actionable) == 1
        assert len(blocked) == 0

    def test_mixed_blockers_some_done(self, checker):
        """Task should be blocked if any blocker is not done."""
        tasks = [
            RawTask(
                id=1,
                project_id=1,
                title="Blocked task",
                related_tasks={
                    "blocked": [
                        RelatedTaskInfo(id=10, done=True),
                        RelatedTaskInfo(id=11, done=False),  # This one isn't done
                        RelatedTaskInfo(id=12, done=True),
                    ]
                },
            ),
        ]
        actionable, blocked = checker.filter_blocked_tasks(tasks)
        assert len(actionable) == 0
        assert len(blocked) == 1
