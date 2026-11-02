"""Integration test for the agent's legacy Task API client (T31).

Skipped automatically if the legacy API isn't running on LEGACY_API_URL.
Proves the agent reads/writes tasks through the legacy system of record.
"""
from __future__ import annotations

import pytest

from app.legacy_client import LegacyTaskClient
from app.models import TaskCreate

client = LegacyTaskClient()


def _legacy_up() -> bool:
    try:
        return client.health()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _legacy_up(), reason="legacy API not running")


def test_list_seed_tasks() -> None:
    tasks = client.list_tasks()
    assert len(tasks) >= 4
    assert any("lawn-mower" in t.title for t in tasks)
    # description field flows through
    lawn = next(t for t in tasks if "lawn-mower" in t.title)
    assert lawn.description and "Ortega" in lawn.description


def test_create_complete_reopen_cycle() -> None:
    created = client.create_task(TaskCreate(title="Agent test task", priority="low"))
    assert created.id
    done = client.complete_task(created.id)
    assert done and done.status == "done"
    reopened = client.reopen_task(created.id)
    assert reopened and reopened.status == "open"
    # cleanup via update->done is fine; leave state tidy by completing
    client.complete_task(created.id)
