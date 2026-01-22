"""Basic model tests."""

from src.models import EnergyLevel, WorkMode, FocusOptions


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
