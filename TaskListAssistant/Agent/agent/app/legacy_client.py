"""Legacy Task API client (T31).

The agent's ONLY source of tasks. Tasks live in the legacy Task Manager
(system of record); the agent reads/writes them over HTTP here. This is the
literal expression of the demo thesis: the AI plugs into the existing system.
"""
from __future__ import annotations

from typing import Optional

import httpx

from .config import LEGACY_API_URL
from .models import Task, TaskCreate


class LegacyTaskClient:
    def __init__(self, base_url: str = LEGACY_API_URL, client: Optional[httpx.Client] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=10.0)

    def health(self) -> bool:
        r = self._client.get(f"{self.base_url}/api/health")
        return r.status_code == 200 and r.json().get("ok") is True

    def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> list[Task]:
        params = {k: v for k, v in {
            "status": status, "priority": priority, "category": category, "sort": sort
        }.items() if v}
        r = self._client.get(f"{self.base_url}/api/tasks", params=params)
        r.raise_for_status()
        return [Task.model_validate(t) for t in r.json()]

    def get_task(self, task_id: str) -> Optional[Task]:
        r = self._client.get(f"{self.base_url}/api/tasks/{task_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return Task.model_validate(r.json())

    def create_task(self, task: TaskCreate) -> Task:
        r = self._client.post(
            f"{self.base_url}/api/tasks",
            json=task.model_dump(exclude_none=True),
        )
        r.raise_for_status()
        return Task.model_validate(r.json())

    def complete_task(self, task_id: str) -> Optional[Task]:
        r = self._client.post(f"{self.base_url}/api/tasks/{task_id}/complete")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return Task.model_validate(r.json())

    def reopen_task(self, task_id: str) -> Optional[Task]:
        r = self._client.post(f"{self.base_url}/api/tasks/{task_id}/reopen")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return Task.model_validate(r.json())

    def update_task(self, task_id: str, patch: dict) -> Optional[Task]:
        r = self._client.patch(f"{self.base_url}/api/tasks/{task_id}", json=patch)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return Task.model_validate(r.json())
