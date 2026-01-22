"""Tests for tool handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.handlers import ToolHandlers


class TestGetFilteredTasks:
    """Tests for get_filtered_tasks retry logic."""

    @pytest.fixture
    def mock_handlers(self):
        """Create handlers with mocked dependencies."""
        with patch.object(ToolHandlers, "__init__", lambda self: None):
            handlers = ToolHandlers()
            handlers.vikunja = AsyncMock()
            handlers.engine = AsyncMock()
            return handlers

    @pytest.mark.asyncio
    async def test_direct_filter_success(self, mock_handlers):
        """Direct filter expression should work on first try."""
        mock_task = MagicMock()
        mock_task.model_dump.return_value = {"id": 1, "title": "Test"}
        mock_handlers.vikunja.get_filtered_tasks.return_value = [mock_task]

        result = await mock_handlers.get_filtered_tasks(filter="done = false")

        assert result["message"] == "Filtered tasks retrieved successfully"
        assert result["summary"]["filter_type"] == "expression"
        assert result["summary"]["total_tasks"] == 1

    @pytest.mark.asyncio
    async def test_natural_language_success(self, mock_handlers):
        """Natural language filter should succeed on first try."""
        mock_task = MagicMock()
        mock_task.model_dump.return_value = {"id": 1, "title": "Test"}
        mock_handlers.engine.suggest_filter.return_value = "done = false"
        mock_handlers.vikunja.get_filtered_tasks.return_value = [mock_task]

        result = await mock_handlers.get_filtered_tasks(
            natural_request="show incomplete tasks"
        )

        assert result["summary"]["filter_type"] == "natural_language"
        assert "retry_attempts" not in result["summary"]

    @pytest.mark.asyncio
    async def test_natural_language_retry_success(self, mock_handlers):
        """Should retry with error context and succeed."""
        mock_task = MagicMock()
        mock_task.model_dump.return_value = {"id": 1, "title": "Test"}

        # First attempt fails, second succeeds
        mock_handlers.engine.suggest_filter.side_effect = [
            "invalid_filter",
            "done = false",
        ]
        mock_handlers.vikunja.get_filtered_tasks.side_effect = [
            ValueError("Parse error"),
            [mock_task],
        ]

        result = await mock_handlers.get_filtered_tasks(
            natural_request="show tasks"
        )

        assert result["summary"]["retry_attempts"] == 1
        assert len(result["summary"]["previous_errors"]) == 1
        assert "invalid_filter" in result["summary"]["previous_errors"][0]["filter"]

    @pytest.mark.asyncio
    async def test_natural_language_all_retries_fail(self, mock_handlers):
        """Should raise detailed error after all retries exhausted."""
        mock_handlers.engine.suggest_filter.return_value = "bad_filter"
        mock_handlers.vikunja.get_filtered_tasks.side_effect = ValueError("Parse error")

        with pytest.raises(ValueError) as exc_info:
            await mock_handlers.get_filtered_tasks(natural_request="show tasks")

        error_msg = str(exc_info.value)
        assert "Failed to generate valid filter" in error_msg
        assert "total_attempts" in error_msg
        assert "3" in error_msg  # max_retries

    @pytest.mark.asyncio
    async def test_requires_filter_or_natural_request(self, mock_handlers):
        """Should raise error if neither filter nor natural_request provided."""
        with pytest.raises(ValueError, match="Either 'filter' or 'natural_request'"):
            await mock_handlers.get_filtered_tasks()
