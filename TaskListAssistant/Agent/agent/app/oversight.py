"""Approval & Oversight via LangGraph interrupt() (T7).

Implements the detect -> pause -> approve -> send gate. A gated action
(sending a financial document) runs as a graph that:
  1. prepares the ApprovalRequest,
  2. calls interrupt() to PAUSE and hand control to the human,
  3. on resume with {"approved": True}  -> sends via the Tool Layer (guarded),
     on resume with {"approved": False} -> aborts.

State persists in a SqliteSaver so the pause survives across the round-trip
(e.g. a background email-watch approving hours later). Also honours NFR-6:
on failure/ambiguity the graph stops rather than proceeding.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable, Optional, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .store import Store
from .tools import GuardrailError, assert_cpa_destination, send_financial_document


class SendState(TypedDict, total=False):
    files: list[str]
    destination: str
    channel: str
    summary: str
    source: str
    # outcome
    approved: bool
    result: str
    aborted: bool
    error: str


def _prepare(state: SendState) -> SendState:
    dest = state.get("destination", "")
    files = state.get("files", [])
    if not files:
        # NFR-6: ambiguity/failure -> stop, don't proceed.
        return {"error": "no files to send", "aborted": True}
    # FR-11: refuse a non-CPA destination UP FRONT — never present it as an
    # approvable action. The guardrail runs again at execution as defense-in-depth.
    try:
        assert_cpa_destination(dest, state.get("channel", "email"))
    except GuardrailError as e:
        return {"error": str(e), "result": f"refused: {e}", "aborted": True}
    summary = (
        f"Send {len(files)} document(s) to {dest} via {state.get('channel','email')}"
    )
    return {"summary": summary}


def _gate(state: SendState) -> SendState:
    if state.get("aborted"):
        return {}
    # PAUSE here. The value passed to interrupt() is what the UI shows in the
    # Approval Card. Execution resumes when the caller provides a Command(resume=...).
    decision = interrupt(
        {
            "action": "send-financial-document",
            "summary": state.get("summary", ""),
            "files": state.get("files", []),
            "destination": state.get("destination", ""),
            "channel": state.get("channel", "email"),
            "source": state.get("source", ""),
        }
    )
    approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
    return {"approved": approved}


def _execute(state: SendState) -> SendState:
    if state.get("aborted"):
        return {"result": "aborted", "aborted": True}
    if not state.get("approved"):
        return {"result": "denied", "aborted": True}
    try:
        res = send_financial_document(
            files=state.get("files", []),
            destination=state.get("destination", ""),
            channel=state.get("channel", "email"),
        )
        return {"result": res.detail, "aborted": False}
    except GuardrailError as e:
        # Guardrail refusal even after approval (e.g. destination tampered).
        return {"result": f"refused: {e}", "aborted": True, "error": str(e)}


def build_send_graph(checkpointer: Optional[SqliteSaver] = None):
    g: StateGraph = StateGraph(SendState)
    g.add_node("prepare", _prepare)
    g.add_node("gate", _gate)
    g.add_node("execute", _execute)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "gate")
    g.add_edge("gate", "execute")
    g.add_edge("execute", END)
    return g.compile(checkpointer=checkpointer)


class OversightService:
    """Thin wrapper coordinating the interrupt() gate with audit logging."""

    def __init__(self, store: Store, checkpointer: Optional[SqliteSaver] = None) -> None:
        self.store = store
        self.graph = build_send_graph(checkpointer=checkpointer)
        self._task_for_thread: dict[str, str] = {}

    def request_send(
        self, *, files: list[str], destination: str, channel: str, source: str = "",
        task_id: Optional[str] = None,
    ) -> tuple[str, dict]:
        """Start a gated send. Returns (thread_id, interrupt_payload).

        The graph runs until interrupt(); the payload is what the Approval Card renders.
        `task_id` (optional) links this send to a legacy task, completed on approval.
        """
        thread_id = str(uuid.uuid4())
        if task_id:
            self._task_for_thread[thread_id] = task_id
        config = {"configurable": {"thread_id": thread_id}}
        self.graph.invoke(
            {"files": files, "destination": destination, "channel": channel, "source": source},
            config=config,
        )
        state = self.graph.get_state(config)
        interrupts = state.tasks[0].interrupts if state.tasks else []
        if not interrupts:
            # No pause => the guardrail refused up front (or nothing to send).
            values = state.values
            refusal = values.get("result") or values.get("error") or "refused"
            self.store.log("refused", refusal, {"destination": destination, "channel": channel})
            return thread_id, {"refused": True, "reason": refusal}
        payload = interrupts[0].value
        self.store.save_approval_from_payload(thread_id, payload)
        self.store.log("proposed", payload.get("summary", "gated send"), payload)
        return thread_id, payload

    def resolve(
        self, thread_id: str, approved: bool,
        complete_cb: Optional[Callable[[str], object]] = None,
    ) -> dict:
        """Resume the paused graph with the human's decision.

        On a successful approval, if this send was linked to a legacy task and a
        `complete_cb` is provided, mark that task done — so the agentic UI and the
        legacy UI stay in sync (the demo's shared-source-of-truth point).
        """
        from langgraph.types import Command

        config = {"configurable": {"thread_id": thread_id}}
        self.graph.invoke(Command(resume={"approved": approved}), config=config)
        final = self.graph.get_state(config).values
        succeeded = approved and not final.get("aborted")
        kind = "executed" if succeeded else ("denied" if not approved else "refused")
        self.store.log(kind, final.get("result", ""), {"thread_id": thread_id})

        completed_task_id: Optional[str] = None
        if succeeded:
            task_id = self._task_for_thread.pop(thread_id, None)
            if task_id and complete_cb is not None:
                try:
                    complete_cb(task_id)
                    completed_task_id = task_id
                    self.store.log("executed", "marked task done", {"taskId": task_id})
                except Exception as e:  # noqa: BLE001
                    self.store.log("error", f"failed to complete task: {e}", {"taskId": task_id})
        return {
            "approved": approved,
            "result": final.get("result"),
            "aborted": final.get("aborted", False),
            "completedTaskId": completed_task_id,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
