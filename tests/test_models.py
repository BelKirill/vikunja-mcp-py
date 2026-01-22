"""Basic model tests."""

from src.models import (
    EnergyLevel,
    FocusOptions,
    RawTask,
    RelatedTaskInfo,
    RelationKind,
    WorkMode,
)


def test_energy_level_values():
    """Test energy level enum values."""
    assert EnergyLevel.LOW.value == "low"
    assert EnergyLevel.MEDIUM.value == "medium"
    assert EnergyLevel.HIGH.value == "high"


def test_work_mode_values():
    """Test work mode enum values."""
    assert WorkMode.DEEP.value == "deep"
    assert WorkMode.QUICK.value == "quick"
    assert WorkMode.ADMIN.value == "admin"


def test_focus_options_defaults():
    """Test FocusOptions has sensible defaults."""
    options = FocusOptions()
    assert options.energy == EnergyLevel.MEDIUM
    assert options.mode == WorkMode.DEEP
    assert options.max_tasks == 10
    assert options.max_minutes == 300


# =========================================================================
# Dependency extraction tests (Task 95)
# =========================================================================


def test_relation_kind_values():
    """Test RelationKind enum has all Vikunja relation types."""
    assert RelationKind.BLOCKED.value == "blocked"
    assert RelationKind.BLOCKING.value == "blocking"
    assert RelationKind.SUBTASK.value == "subtask"
    assert RelationKind.PARENTTASK.value == "parenttask"


def test_raw_task_no_relations():
    """Test RawTask with no related_tasks."""
    task = RawTask(id=1, project_id=1, title="Test")
    assert task.blocked_by_ids == []
    assert task.blocking_ids == []
    assert task.is_blocked is False


def test_raw_task_with_blocking_relations():
    """Test RawTask correctly parses blocking relations."""
    task_data = {
        "id": 100,
        "project_id": 8,
        "title": "Test Task",
        "related_tasks": {
            "blocked": [
                {"id": 99, "title": "Blocker 1", "done": False, "project_id": 8},
                {"id": 98, "title": "Blocker 2", "done": True, "project_id": 8},
            ],
            "blocking": [
                {"id": 101, "title": "Dependent", "done": False, "project_id": 8}
            ],
        },
    }
    task = RawTask.model_validate(task_data)

    assert task.blocked_by_ids == [99, 98]
    assert task.blocking_ids == [101]
    # is_blocked = True because task 99 is not done
    assert task.is_blocked is True


def test_raw_task_blocked_by_completed_tasks():
    """Test is_blocked is False when all blockers are done."""
    task_data = {
        "id": 100,
        "project_id": 8,
        "title": "Test Task",
        "related_tasks": {
            "blocked": [
                {"id": 99, "title": "Blocker", "done": True, "project_id": 8}
            ]
        },
    }
    task = RawTask.model_validate(task_data)

    assert task.blocked_by_ids == [99]
    # is_blocked = False because the blocking task is done
    assert task.is_blocked is False


def test_raw_task_null_related_tasks():
    """Test RawTask handles null related_tasks from API."""
    task_data = {
        "id": 1,
        "project_id": 1,
        "title": "Test",
        "related_tasks": None,
    }
    task = RawTask.model_validate(task_data)
    assert task.related_tasks == {}
    assert task.is_blocked is False
