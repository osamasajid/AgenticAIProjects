"""Test the booking->task wrap in isolation (no MCP servers, no live legacy DB)."""
from __future__ import annotations

from app.agent_tools import Tool


def test_wrap_book_slot_creates_task(monkeypatch) -> None:
    import app.main as main

    created: list[str] = []

    class FakeLegacy:
        def create_task(self, task):
            created.append(task.title)
            return task

    monkeypatch.setattr(main, "legacy", FakeLegacy())

    raw = Tool(
        name="book_slot", description="book", parameters={"type": "object", "properties": {}},
        fn=lambda **kw: "Booked cpa appointment 2026-10-01 11:00 (slot c1).",
    )
    wrapped = main._wrap_book_slot(raw)
    out = wrapped.fn(slot_id="c1")
    assert "Added it to your task list" in out
    assert created and "Appointment: cpa 2026-10-01 11:00" in created[0]


def test_wrap_ignores_non_booking_tools() -> None:
    import app.main as main

    raw = Tool(name="get_weather", description="w", parameters={}, fn=lambda **kw: "sunny")
    assert main._wrap_book_slot(raw) is raw  # unchanged


def test_wrap_no_task_when_booking_fails(monkeypatch) -> None:
    import app.main as main

    created: list[str] = []
    monkeypatch.setattr(main, "legacy", type("L", (), {"create_task": lambda self, t: created.append(t.title)})())

    raw = Tool(name="book_slot", description="book", parameters={}, fn=lambda **kw: "Slot c1 is no longer available.")
    out = main._wrap_book_slot(raw).fn(slot_id="c1")
    assert "no longer available" in out
    assert created == []  # nothing added on failure
