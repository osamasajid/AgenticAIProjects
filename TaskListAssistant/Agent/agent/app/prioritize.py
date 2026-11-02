"""Lightweight task ranking (seed for T15).

Deterministic, metadata-only ordering: priority first (high>medium>low), then
soonest due date, then oldest. No LLM yet — the full reasoning-based prioritizer
(with explanation + override) is T15. This keeps "what should I do next?" working
offline and predictably.
"""
from __future__ import annotations

from .models import Task

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def rank_tasks(tasks: list[Task]) -> list[Task]:
    def key(t: Task) -> tuple:
        return (
            _PRIORITY_RANK.get(t.priority, 3),
            t.dueDate or "9999-99-99",  # no due date sorts last
            t.createdAt or "",
        )

    return sorted(tasks, key=key)


def summarize_open_tasks(tasks: list[Task]) -> str:
    open_tasks = [t for t in tasks if t.status == "open"]
    if not open_tasks:
        return "You have no open tasks. 🎉"
    ranked = rank_tasks(open_tasks)
    lines = [f"You have {len(open_tasks)} open task(s):"]
    for i, t in enumerate(ranked, 1):
        due = f" (due {t.dueDate})" if t.dueDate else ""
        lines.append(f"  {i}. [{t.priority}] {t.title}{due}")
    return "\n".join(lines)


def next_action(tasks: list[Task]) -> str:
    open_tasks = [t for t in tasks if t.status == "open"]
    if not open_tasks:
        return "Nothing pending — you're all caught up. 🎉"
    top = rank_tasks(open_tasks)[0]
    due = f", due {top.dueDate}" if top.dueDate else ""
    detail = f" — {top.description}" if top.description else ""
    return f"I'd start with: “{top.title}” ({top.priority} priority{due}){detail}"
