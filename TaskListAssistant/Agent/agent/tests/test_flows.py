"""Wave D hero-flow tests: send-to-CPA, email-watch, direct bank fetch."""
from __future__ import annotations

import sqlite3
import tempfile

from langgraph.checkpoint.sqlite import SqliteSaver

from app.connectors.gmail import Email, MockGmailConnector
from app.flows import DirectBankFetchFlow, EmailWatchFlow, SendStatementsFlow
from app.models import PermissionType
from app.oversight import OversightService
from app.store import Store


def _svc() -> tuple[OversightService, Store]:
    store = Store(path=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
    conn = sqlite3.connect(tempfile.NamedTemporaryFile(suffix=".db", delete=False).name, check_same_thread=False)
    return OversightService(store, checkpointer=SqliteSaver(conn)), store


# ---- T17 ----
def test_send_statements_flow_pauses_then_sends() -> None:
    ov, store = _svc()
    flow = SendStatementsFlow(ov, store)
    res = flow.start(channel="email")
    assert res.kind == "pending-approval"
    assert res.approval and "cpa@firm.com" in res.approval["destination"]
    # 3 statement files discovered from Drive
    assert any("statement" in s.label.lower() for s in res.steps)
    out = ov.resolve(res.thread_id, approved=True)
    assert out["aborted"] is False and "sent" in out["result"]


# ---- T18 ----
def _armed_watch_flow():
    ov, store = _svc()
    gmail = MockGmailConnector()
    flow = EmailWatchFlow(ov, store, gmail)
    watch = flow.arm_watch(days=30)
    return ov, store, gmail, flow, watch


def test_email_watch_ignores_non_statement() -> None:
    ov, store, gmail, flow, watch = _armed_watch_flow()
    gmail.inject_email(Email(sender="marketing@bank.com", subject="Card offer", body="apply"))
    res = flow.on_email_arrived(watch)
    assert res.kind == "nothing-found"


def test_email_watch_detects_pauses_and_sends() -> None:
    ov, store, gmail, flow, watch = _armed_watch_flow()
    gmail.inject_email(Email(
        sender="statements@bank.com", subject="Your statement is ready",
        body="account statement attached", attachments=["Statement_Jul.pdf"],
    ))
    res = flow.on_email_arrived(watch, channel="portal")
    assert res.kind == "pending-approval"
    assert res.approval["detection_reasons"]  # shown for false-positive protection
    out = ov.resolve(res.thread_id, approved=True)
    assert out["aborted"] is False and "sent" in out["result"]


def test_email_watch_expiry_blocks() -> None:
    ov, store, gmail, flow, watch = _armed_watch_flow()
    watch.revoked = True
    res = flow.on_email_arrived(watch)
    assert res.kind == "nothing-found"


# ---- T19 ----
def test_direct_bank_fetch_flow() -> None:
    ov, store = _svc()
    flow = DirectBankFetchFlow(ov, store)
    res = flow.start(channel="portal")
    assert res.kind == "pending-approval"
    # never-sees-credentials step is present
    assert any("never sees credentials" in s.detail for s in res.steps)
    out = ov.resolve(res.thread_id, approved=True)
    assert out["aborted"] is False and "sent" in out["result"]


def test_direct_bank_fetch_recurring_permission() -> None:
    ov, store = _svc()
    flow = DirectBankFetchFlow(ov, store)
    perm = flow.grant_recurring(days=30)
    assert perm.type == PermissionType.RECURRING_BANK_FETCH
    perms = store.list_permissions()
    assert len(perms) == 1 and perms[0].expiresAt is not None
