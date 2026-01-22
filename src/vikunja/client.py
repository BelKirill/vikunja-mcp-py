"""Vikunja API client with retry logic."""

import logging
from typing import Any

import httpx

from ..config import get_settings
from ..models import Comment, PartialLabel, PartialProject, RawTask

logger = logging.getLogger(__name__)


class VikunjaClient:
    """HTTP client for Vikunja API."""

    def __init__(self, base_url: str | None = None, token: str | None = None):
        """Initialize the Vikunja client."""
        settings = get_settings()
        self.base_url = (base_url or settings.vikunja_url).rstrip("/")
        self.token = token or settings.vikunja_token
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "vikunja-mcp-py/0.2.0",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> Any:
        """Make an HTTP request with retry logic."""
        last_error: Exception | None = None

        for attempt in range(retries):
            try:
                response = await self._client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    last_error = e
                    logger.warning(f"Server error, retry {attempt + 1}/{retries}: {e}")
                    continue
                raise
            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Request error, retry {attempt + 1}/{retries}: {e}")
                continue

        raise last_error or Exception("Request failed after retries")

    # =========================================================================
    # Tasks
    # =========================================================================

    async def get_all_tasks(self, filter_expr: str | None = None) -> list[RawTask]:
        """Get all tasks, optionally filtered."""
        params: dict[str, Any] = {"per_page": 100}
        if filter_expr:
            params["filter"] = filter_expr

        all_tasks: list[RawTask] = []
        page = 1

        while True:
            params["page"] = page
            data = await self._request("GET", "/api/v1/tasks/all", params=params)

            if not data:
                break

            for task_data in data:
                all_tasks.append(RawTask.model_validate(task_data))

            if len(data) < 100:
                break
            page += 1

        logger.info(f"Fetched {len(all_tasks)} tasks from Vikunja")
        return all_tasks

    async def get_incomplete_tasks(self) -> list[RawTask]:
        """Get all incomplete tasks."""
        return await self.get_all_tasks(filter_expr="done = false")

    async def get_filtered_tasks(self, filter_expr: str) -> list[RawTask]:
        """Get tasks matching a filter expression."""
        return await self.get_all_tasks(filter_expr=filter_expr)

    async def get_task_by_id(self, task_id: int) -> RawTask:
        """Get a single task by ID."""
        data = await self._request("GET", f"/api/v1/tasks/{task_id}")
        return RawTask.model_validate(data)

    async def create_task(self, project_id: int, task: dict[str, Any]) -> RawTask:
        """Create a new task in a project."""
        data = await self._request(
            "PUT",
            f"/api/v1/projects/{project_id}/tasks",
            json=task,
        )
        return RawTask.model_validate(data)

    async def update_task(self, task_id: int, updates: dict[str, Any]) -> RawTask:
        """Update an existing task."""
        data = await self._request(
            "POST",
            f"/api/v1/tasks/{task_id}",
            json=updates,
        )
        return RawTask.model_validate(data)

    async def upsert_task(self, task: RawTask) -> RawTask:
        """Create or update a task."""
        if task.id == 0:
            # Create new task
            return await self.create_task(
                task.project_id,
                task.model_dump(exclude={"id", "created", "updated", "identifier"}),
            )
        else:
            # Update existing task
            return await self.update_task(
                task.id,
                task.model_dump(exclude={"created", "updated", "identifier"}),
            )

    # =========================================================================
    # Comments
    # =========================================================================

    async def get_task_comments(self, task_id: int) -> list[Comment]:
        """Get comments for a task."""
        data = await self._request("GET", f"/api/v1/tasks/{task_id}/comments")
        return [Comment.model_validate(c) for c in (data or [])]

    async def add_comment(self, task_id: int, comment: str) -> Comment:
        """Add a comment to a task."""
        data = await self._request(
            "PUT",
            f"/api/v1/tasks/{task_id}/comments",
            json={"comment": comment},
        )
        return Comment.model_validate(data)

    # =========================================================================
    # Projects
    # =========================================================================

    async def get_all_projects(self) -> list[PartialProject]:
        """Get all projects."""
        data = await self._request("GET", "/api/v1/projects")
        return [PartialProject.model_validate(p) for p in (data or [])]

    async def get_project(self, project_id: int) -> PartialProject:
        """Get a single project by ID."""
        data = await self._request("GET", f"/api/v1/projects/{project_id}")
        return PartialProject.model_validate(data)

    # =========================================================================
    # Labels
    # =========================================================================

    async def get_all_labels(self) -> list[PartialLabel]:
        """Get all available labels."""
        data = await self._request("GET", "/api/v1/labels")
        return [PartialLabel.model_validate(lbl) for lbl in (data or [])]

    async def add_labels_to_task(self, task_id: int, label_ids: list[int]) -> list[PartialLabel]:
        """Add labels to a task."""
        results: list[PartialLabel] = []
        for label_id in label_ids:
            data = await self._request(
                "PUT",
                f"/api/v1/tasks/{task_id}/labels",
                json={"label_id": label_id},
            )
            results.append(PartialLabel.model_validate(data))
        return results
