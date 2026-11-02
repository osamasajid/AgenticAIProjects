"""FastAPI app (T1). Health, a chat endpoint over the graph, task passthrough
to the legacy API, and the audit trail.
"""
from __future__ import annotations

import os
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel

from .config import LLM_MODE, cpa_destination
from .connectors.gmail import Email, MockGmailConnector
from .conversation import Conversation
from .flows import DirectBankFetchFlow, EmailWatchFlow, SendStatementsFlow
from .graph import build_graph
from .legacy_client import LegacyTaskClient
from .llm import get_llm
from .models import TaskCreate
from .oversight import OversightService
from .store import Store

app = FastAPI(title="Agentic Task Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = Store()
legacy = LegacyTaskClient()
graph = build_graph(tasks_provider=lambda: legacy.list_tasks())

# Oversight gate with a persistent SQLite checkpointer (interrupt/resume survives restarts).
_ckpt_conn = sqlite3.connect("oversight.db", check_same_thread=False)
oversight = OversightService(store, checkpointer=SqliteSaver(_ckpt_conn))


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/legacy-health")
def legacy_health() -> dict:
    try:
        return {"ok": legacy.health()}
    except Exception as e:  # noqa: BLE001 - surface connectivity issues plainly
        return {"ok": False, "error": str(e)}


@app.get("/api/tasks")
def tasks(status: str | None = None) -> list[dict]:
    return [t.model_dump() for t in legacy.list_tasks(status=status)]


class ChatIn(BaseModel):
    message: str
    sessionId: str = "default"


# Per-session conversation context (last task, intent) so follow-ups resolve.
_conversations: dict[str, Conversation] = {}


def _conversation(session_id: str) -> Conversation:
    if session_id not in _conversations:
        _conversations[session_id] = Conversation(
            get_llm(),
            lambda: legacy.list_tasks(),
            complete_cb=legacy.complete_task,
            create_cb=lambda title: legacy.create_task(TaskCreate(title=title)),
        )
    return _conversations[session_id]


@app.post("/api/chat")
def chat(body: ChatIn) -> dict:
    # LLM=ollama -> real ReAct loop with model-driven tool-calling.
    if LLM_MODE == "ollama":
        from .agent_tools import TaskTools
        from .react_agent import run_react

        tools_impl = TaskTools(
            legacy,
            start_send_statements=lambda: _flow_response(
                _send_flow.start(channel="email", task_id=_cpa_task_id())
            ),
        )
        history = _react_history.get(body.sessionId, [])
        out = run_react(body.message, tools_impl, extra_tools=_mcp_tools(), history=history)
        _react_history[body.sessionId] = out.get("history", [])
        store.log("proposed", f"react: {body.message[:80]}", {"steps": out["steps"]})
        resp: dict = {"reply": out["reply"], "category": "react", "steps": out["steps"]}
        if out.get("flow"):
            resp["flow"] = out["flow"]
        return resp

    # default: deterministic conversation layer (stub)
    convo = _conversation(body.sessionId)
    r = convo.handle(body.message)
    store.log("proposed", f"chat: {body.message[:80]}", {"category": r.category, "action": r.action})

    resp = {"category": r.category, "reply": r.reply, "action": r.action, "taskId": r.task_id}
    if r.action == "start-flow:send-statements":
        flow = _send_flow.start(channel="email", task_id=_cpa_task_id())
        resp["flow"] = _flow_response(flow)
    return resp


@app.get("/api/audit")
def audit() -> list[dict]:
    return [e.model_dump(mode="json") for e in store.audit_events()]


class SendRequest(BaseModel):
    files: list[str]
    destination: str
    channel: str = "email"
    source: str = ""


@app.post("/api/send/request")
def send_request(body: SendRequest) -> dict:
    """Start a gated financial-document send. Pauses at the approval gate and
    returns the Approval Card payload (nothing is sent yet)."""
    thread_id, payload = oversight.request_send(
        files=body.files, destination=body.destination, channel=body.channel, source=body.source
    )
    return {"threadId": thread_id, "approval": payload}


class ResolveRequest(BaseModel):
    threadId: str
    approved: bool


@app.post("/api/send/resolve")
def send_resolve(body: ResolveRequest) -> dict:
    """Resume the paused gate with the human decision (approve/deny).
    On approval, mark the linked legacy task done so both UIs stay in sync."""
    try:
        return oversight.resolve(
            body.threadId, approved=body.approved, complete_cb=legacy.complete_task
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e


def _cpa_task_id() -> str | None:
    """Find the legacy 'send bank statement to CPA' task, if present."""
    for t in legacy.list_tasks(status="open"):
        hay = f"{t.title} {t.description or ''}".lower()
        if "cpa" in hay or "statement" in hay:
            return t.id
    return None


# MCP tools (weather + booking) — opt-in via MCP=on, initialized once.
_mcp_provider = None
_mcp_loaded_tools: list = []

# Per-session ReAct conversation history (multi-turn planning for LLM=ollama).
_react_history: dict[str, list] = {}


def _mcp_tools() -> list:
    global _mcp_provider, _mcp_loaded_tools
    if os.environ.get("MCP", "off") != "on":
        return []
    if _mcp_provider is None:
        from .mcp_client import MCPToolProvider

        _mcp_provider = MCPToolProvider()
        raw = _mcp_provider.load()
        _mcp_loaded_tools = [_wrap_book_slot(t) for t in raw]
    return _mcp_loaded_tools


def _wrap_book_slot(tool):
    """When book_slot succeeds, also create a companion task in the legacy list,
    so a booked appointment leaves a trace on the user's task list. The booking
    MCP server stays decoupled from the task API — the agent does the recording."""
    from .agent_tools import Tool

    if tool.name != "book_slot":
        return tool

    inner_fn = tool.fn

    def fn(**kwargs):
        result = inner_fn(**kwargs)
        # book_slot returns e.g. "Booked cpa appointment 2026-10-01 11:00 (slot c1)."
        if isinstance(result, str) and result.lower().startswith("booked"):
            try:
                detail = result.rstrip(".")
                # nicer title: "Appointment: cpa 2026-10-01 11:00"
                body = detail[len("Booked "):]  # "cpa appointment 2026-10-01 11:00 (slot c1)"
                title = "Appointment: " + body.replace(" appointment", "").split(" (slot")[0]
                legacy.create_task(TaskCreate(title=title, category="routine"))
                result += " Added it to your task list."
            except Exception:  # noqa: BLE001
                result += " (Could not add a task record.)"
        return result

    return Tool(name=tool.name, description=tool.description, parameters=tool.parameters, fn=fn)


# ---- Hero flows (Wave D) ----
_gmail = MockGmailConnector()
_send_flow = SendStatementsFlow(oversight, store)
_watch_flow = EmailWatchFlow(oversight, store, _gmail)
_bank_flow = DirectBankFetchFlow(oversight, store)


def _flow_response(res) -> dict:
    return {
        "kind": res.kind,
        "message": res.message,
        "steps": [{"label": s.label, "detail": s.detail} for s in res.steps],
        "threadId": res.thread_id,
        "approval": res.approval,
    }


@app.post("/api/flows/send-statements")
def flow_send_statements(channel: str = "email") -> dict:
    return _flow_response(_send_flow.start(channel=channel, task_id=_cpa_task_id()))


class ArmWatchRequest(BaseModel):
    days: int = 30


@app.post("/api/flows/watch/arm")
def flow_arm_watch(body: ArmWatchRequest) -> dict:
    w = _watch_flow.arm_watch(days=body.days)
    return {"watchId": w.id, "expiresAt": w.expiresAt.isoformat()}


class InjectEmailRequest(BaseModel):
    sender: str
    subject: str
    body: str
    attachments: list[str] = []


@app.post("/api/flows/watch/inject")
def flow_inject_email(body: InjectEmailRequest) -> dict:
    """Demo control: simulate an email arriving, then run detection on all active watches."""
    _gmail.inject_email(
        Email(sender=body.sender, subject=body.subject, body=body.body, attachments=body.attachments)
    )
    results = []
    for w in store.list_watches():
        if w.revoked:
            continue
        results.append(_flow_response(_watch_flow.on_email_arrived(w)))
    return {"watchResults": results}


@app.post("/api/flows/bank-fetch")
def flow_bank_fetch(channel: str = "portal") -> dict:
    return _flow_response(_bank_flow.start(channel=channel))


@app.post("/api/flows/bank-fetch/recurring")
def flow_bank_recurring(days: int = 30) -> dict:
    p = _bank_flow.grant_recurring(days=days)
    return {"permissionId": p.id, "expiresAt": p.expiresAt.isoformat() if p.expiresAt else None}


# ---- Permissions & watches (view/revoke — T23 backend) ----
@app.get("/api/permissions")
def list_permissions() -> list[dict]:
    return [p.model_dump(mode="json") for p in store.list_permissions()]


@app.post("/api/permissions/{perm_id}/revoke")
def revoke_permission(perm_id: str) -> dict:
    ok = store.revoke_permission(perm_id)
    if not ok:
        raise HTTPException(status_code=404, detail="permission not found")
    store.log("proposed", "revoked permission", {"permId": perm_id})
    return {"revoked": True}


@app.get("/api/watches")
def list_watches() -> list[dict]:
    return [w.model_dump(mode="json") for w in store.list_watches()]


@app.post("/api/watches/{watch_id}/revoke")
def revoke_watch(watch_id: str) -> dict:
    ok = store.revoke_watch(watch_id)
    if not ok:
        raise HTTPException(status_code=404, detail="watch not found")
    store.log("proposed", "revoked watch", {"watchId": watch_id})
    return {"revoked": True}


@app.get("/api/config/cpa")
def cpa() -> dict:
    d = cpa_destination()
    return {"email": d.email, "portal_url": d.portal_url, "note": "fixed, read-only"}
