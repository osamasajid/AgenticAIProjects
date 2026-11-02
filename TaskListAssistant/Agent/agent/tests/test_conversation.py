"""Conversational layer tests (session context, referents, pay link, routing)."""
from __future__ import annotations

from app.conversation import Conversation
from app.llm import StubLLMClient
from app.models import Category, Task


def _tasks() -> list[Task]:
    return [
        Task(id="t-lawn", title="Make payment to lawn-mower", description="Pay Ortega $150",
             priority="high", dueDate="2026-09-26", category="financial", status="open"),
        Task(id="t-nanny", title="Book appointment with childcare nanny", priority="high",
             dueDate="2026-10-02", category="routine", status="open"),
        Task(id="t-cpa", title="Send bank statement to CPA", priority="medium",
             category="financial", status="open"),
    ]


def _convo() -> Conversation:
    return Conversation(StubLLMClient(), _tasks)


def test_next_action_then_lets_do_it_resolves_context() -> None:
    c = _convo()
    r1 = c.handle("what should I do next?")
    assert "lawn-mower" in r1.reply
    # "let's do it" should resolve to the lawn-mower payment, not re-list tasks
    r2 = c.handle("ok let's do it")
    assert r2.category == Category.FINANCIAL_TRANSACTION.value
    assert "pay.example" in r2.reply
    assert r2.task_id == "t-lawn"


def test_show_me_the_link_uses_context() -> None:
    c = _convo()
    c.handle("what should I do next?")          # sets context to lawn-mower
    r = c.handle("show me the link")
    assert "pay.example" in r.reply
    assert "never make the payment" in r.reply.lower() or "never make payments" in r.reply.lower()


def test_named_payment_task_advises_not_pays() -> None:
    c = _convo()
    r = c.handle("Make payment to Ortega for the lawn")
    assert r.category == Category.FINANCIAL_TRANSACTION.value
    assert "Ortega" in r.reply
    # agent advises + opens link but never pays itself
    assert "never make" in r.reply.lower() and "myself" in r.reply.lower()


def test_send_statements_routes_to_flow() -> None:
    c = _convo()
    r = c.handle("send my bank statement to my CPA")
    assert r.category == Category.FINANCIAL_DATA.value
    assert r.action == "start-flow:send-statements"


def test_off_topic_refused() -> None:
    c = _convo()
    r = c.handle("what's the football score?")
    assert r.category == Category.OFF_TOPIC.value


def test_first_one_referent() -> None:
    c = _convo()
    r = c.handle("pay the first one")
    assert r.task_id == "t-lawn"
    assert "pay.example" in r.reply


def test_complete_task_by_name() -> None:
    completed: list[str] = []
    c = Conversation(StubLLMClient(), _tasks, complete_cb=lambda tid: completed.append(tid))
    r = c.handle("complete the nanny appointment")
    assert r.action == "completed-task"
    assert r.task_id == "t-nanny"
    assert completed == ["t-nanny"]
    assert "done" in r.reply.lower()


def test_complete_uses_context_when_bare() -> None:
    completed: list[str] = []
    c = Conversation(StubLLMClient(), _tasks, complete_cb=lambda tid: completed.append(tid))
    c.handle("what should I do next?")   # context -> lawn-mower
    r = c.handle("mark it done")
    assert r.task_id == "t-lawn"
    assert completed == ["t-lawn"]


def test_complete_without_target_asks() -> None:
    c = Conversation(StubLLMClient(), _tasks, complete_cb=lambda _tid: None)
    r = c.handle("complete")
    assert "which task" in r.reply.lower()


def test_add_task_variants() -> None:
    created: list[str] = []

    def mk(title: str):
        created.append(title)
        return Task(id="new", title=title, status="open")

    for msg, expected in [
        ("add a task to call the plumber", "call the plumber"),
        ("create task: renew passport", "renew passport"),
        ("remind me to water the plants", "water the plants"),
        ("new task book dentist", "book dentist"),
    ]:
        c = Conversation(StubLLMClient(), _tasks, create_cb=mk)
        r = c.handle(msg)
        assert r.action == "created-task", msg
        assert created[-1].lower() == expected, (msg, created[-1])


def test_add_task_does_not_collide_with_list_or_complete() -> None:
    c = Conversation(StubLLMClient(), _tasks, create_cb=lambda t: Task(id="x", title=t, status="open"),
                     complete_cb=lambda _t: None)
    assert c.handle("what are my tasks?").action != "created-task"
    assert c.handle("complete the nanny appointment").action == "completed-task"
