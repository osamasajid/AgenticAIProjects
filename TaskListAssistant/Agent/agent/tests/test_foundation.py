"""Wave A foundation tests: config immutability, store, classifier, graph."""
from __future__ import annotations

import tempfile

import pytest

from app.config import cpa_destination
from app.graph import build_graph
from app.llm import StubLLMClient
from app.models import Category, Permission, PermissionType, Watch
from app.store import Store
from datetime import datetime, timedelta, timezone


def test_cpa_destination_is_frozen() -> None:
    d = cpa_destination()
    # Frozen dataclass: mutation must raise (this is the guardrail's config root).
    with pytest.raises(Exception):
        d.email = "attacker@evil.com"  # type: ignore[misc]


def test_store_memory_roundtrip() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        s = Store(path=f.name)
        s.set_memory("pref.tone", "concise")
        assert s.get_memory("pref.tone") == "concise"
        assert s.all_memory()["pref.tone"] == "concise"
        assert s.delete_memory("pref.tone") is True


def test_store_permission_and_watch_lifecycle() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        s = Store(path=f.name)
        now = datetime.now(timezone.utc)
        perm = Permission(
            id="p1", type=PermissionType.RECURRING_BANK_FETCH,
            description="auto-fetch next statement", grantedAt=now,
            expiresAt=now + timedelta(days=30),
        )
        s.add_permission(perm)
        assert len(s.list_permissions()) == 1
        assert s.revoke_permission("p1") is True
        assert s.list_permissions()[0].revoked is True

        watch = Watch(
            id="w1", description="watch for statement", senderMatch="bank",
            subjectKeywords=["statement"], grantedAt=now, expiresAt=now + timedelta(days=30),
        )
        s.add_watch(watch)
        assert len(s.list_watches()) == 1
        assert s.revoke_watch("w1") is True


def test_store_audit_ordering() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        s = Store(path=f.name)
        s.log("proposed", "a")
        s.log("approved", "b")
        kinds = [e.kind for e in s.audit_events()]
        assert kinds == ["proposed", "approved"]


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("Send my bank statement to my CPA", Category.FINANCIAL_DATA),
        ("Pay the electricity bill", Category.FINANCIAL_TRANSACTION),
        ("Book the nanny appointment", Category.ROUTINE_TASK),
        ("What should I focus on today?", Category.GENERAL_QA),
        ("What's the football score?", Category.OFF_TOPIC),
        ("how to hack a bank", Category.UNSAFE),
    ],
)
def test_stub_classifier(msg: str, expected: Category) -> None:
    assert StubLLMClient().classify(msg) == expected


def test_graph_runs_and_classifies() -> None:
    g = build_graph(llm=StubLLMClient())
    out = g.invoke({"message": "Send my statement to my CPA"})
    assert out["category"] == Category.FINANCIAL_DATA.value
    assert "approval" in out["reply"].lower() or "cpa" in out["reply"].lower()
