"""Agent tools for the ReAct loop.

These are the actions the MODEL may choose (real tool-calling): list/add/complete
tasks, and start the CPA send flow (which returns an Approval Card — the human gate
still applies). Each tool is a plain callable plus a JSON schema; the ReAct loop
binds the schemas to the model and dispatches the model's chosen call here.

Kept framework-light so the loop is explicit and swap-safe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .legacy_client import LegacyTaskClient
from .models import TaskCreate
from .prioritize import next_action, rank_tasks


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., str]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class TaskTools:
    """Builds the tool set over a legacy client (+ optional flow starter)."""

    def __init__(
        self,
        legacy: LegacyTaskClient,
        start_send_statements: Callable[[], dict] | None = None,
    ) -> None:
        self.legacy = legacy
        self.start_send_statements = start_send_statements
        # populated by the loop when a flow starts, so the API can surface the card
        self.pending_flow: dict | None = None

    # ---- tool implementations (return short strings the model observes) ----
    def _list_tasks(self, status: str = "open") -> str:
        tasks = self.legacy.list_tasks(status=status or None)
        if not tasks:
            return "No tasks."
        ranked = rank_tasks(tasks)
        return "; ".join(
            f"[{t.priority}] {t.title}" + (f" (due {t.dueDate})" if t.dueDate else "")
            for t in ranked
        )

    def _next_action(self) -> str:
        return next_action(self.legacy.list_tasks())

    def _add_task(self, title: str) -> str:
        t = self.legacy.create_task(TaskCreate(title=title))
        return f"Added task: {t.title}"

    def _complete_task(self, title: str) -> str:
        tasks = self.legacy.list_tasks(status="open")
        match = next(
            (t for t in tasks if any(w in f"{t.title} {t.description or ''}".lower()
                                     for w in title.lower().split() if len(w) > 3)),
            None,
        )
        if not match:
            return f"No open task matching '{title}'."
        self.legacy.complete_task(match.id)
        return f"Completed: {match.title}"

    def _send_statements_to_cpa(self) -> str:
        if self.start_send_statements is None:
            return "Send flow unavailable."
        self.pending_flow = self.start_send_statements()
        return ("Started the CPA send. It is paused at a human approval gate — the user must "
                "approve the Approval Card before anything is sent, and it can only go to the CPA.")

    # ---- registry ----
    def tools(self) -> list[Tool]:
        return [
            Tool("list_tasks", "List the user's tasks (default open).",
                 {"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "done"]}}},
                 lambda status="open": self._list_tasks(status)),
            Tool("next_action", "Recommend the single most important task to do next.",
                 {"type": "object", "properties": {}}, lambda: self._next_action()),
            Tool("add_task", "Add a new task, reminder, or personal plan to the list "
                 "(e.g. a picnic, tennis game, errand, chore, or any event that is NOT a "
                 "doctor/CPA appointment). Use this to schedule personal activities.",
                 {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
                 lambda title: self._add_task(title)),
            Tool("complete_task", "Mark a task done by (part of) its title.",
                 {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
                 lambda title: self._complete_task(title)),
            Tool("send_statements_to_cpa",
                 "Begin sending the user's bank statements to their CPA (pauses for human approval).",
                 {"type": "object", "properties": {}}, lambda: self._send_statements_to_cpa()),
        ]

    def by_name(self) -> dict[str, Tool]:
        return {t.name: t for t in self.tools()}
