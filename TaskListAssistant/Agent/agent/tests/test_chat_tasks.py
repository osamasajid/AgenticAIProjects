"""Tests for /chat general-QA answering with live tasks (T20 seed)."""
from __future__ import annotations

from app.graph import build_graph
from app.llm import StubLLMClient
from app.models import Task


def _tasks() -> list[Task]:
    return [
        Task(id="1", title="Make payment to lawn-mower", description="Pay Ortega $150",
             priority="high", dueDate="2026-09-26", status="open"),
        Task(id="2", title="Book nanny", priority="high", dueDate="2026-10-02", status="open"),
        Task(id="3", title="Old done thing", priority="low", status="done"),
    ]


def test_chat_lists_open_tasks() -> None:
    g = build_graph(llm=StubLLMClient(), tasks_provider=_tasks)
    out = g.invoke({"message": "What are my open tasks?"})
    reply = out["reply"]
    assert "2 open task" in reply
    assert "lawn-mower" in reply and "Book nanny" in reply
    assert "Old done thing" not in reply  # done tasks excluded


def test_chat_recommends_next_action() -> None:
    g = build_graph(llm=StubLLMClient(), tasks_provider=_tasks)
    out = g.invoke({"message": "What should I do next?"})
    reply = out["reply"]
    assert "I'd start with" in reply
    # highest priority + soonest due date wins
    assert "lawn-mower" in reply


def test_chat_handles_no_tasks() -> None:
    g = build_graph(llm=StubLLMClient(), tasks_provider=lambda: [])
    out = g.invoke({"message": "What are my open tasks?"})
    assert "no open tasks" in out["reply"].lower()


def test_chat_provider_error_is_graceful() -> None:
    def boom() -> list[Task]:
        raise RuntimeError("legacy API down")

    g = build_graph(llm=StubLLMClient(), tasks_provider=boom)
    out = g.invoke({"message": "What are my open tasks?"})
    assert "couldn't reach" in out["reply"].lower()
