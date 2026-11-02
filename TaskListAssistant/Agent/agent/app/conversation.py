"""Conversational layer (completes T20 + conversational half of T15).

Adds what the thin /chat stub lacked:
  * per-session CONTEXT — remembers the last-discussed task and last intent, so
    follow-ups like "let's do it" / "show me the link" / "pay it" resolve.
  * referent resolution — "it", "that", "the first one", or a task named by a
    keyword maps to a concrete task.
  * real advise-only financial replies — surfaces the task's description + a
    (mock) pay link, and refuses to pay itself.
  * free-text -> hero-flow routing — "send my statements to my CPA" starts the
    send-statements flow and returns an Approval Card, not a stub sentence.

Deterministic (stub LLM) so it runs offline and is repeatable on stage. The same
logic gets smarter unchanged when LLM=bedrock, because intent classification goes
through the LLMClient seam.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .llm import LLMClient
from .models import Category, Task
from .prioritize import next_action, rank_tasks, summarize_open_tasks

TaskProvider = Callable[[], list[Task]]

_PAY_WORDS = ("pay", "link", "how do i", "show me", "do it", "let's do", "lets do", "go ahead")
_REFERENTS = ("it", "that", "this", "the first", "that one", "this one")


@dataclass
class SessionContext:
    last_task_id: Optional[str] = None
    last_task_title: Optional[str] = None
    last_intent: Optional[str] = None
    pending_flow: Optional[str] = None  # e.g. "send-statements" awaiting confirm


@dataclass
class ChatReply:
    reply: str
    category: str
    action: Optional[str] = None  # e.g. "start-flow:send-statements" for the API to run
    task_id: Optional[str] = None
    steps: list[str] = field(default_factory=list)


class Conversation:
    """One per session. Holds context and turns messages into replies/actions."""

    def __init__(
        self,
        llm: LLMClient,
        tasks_provider: TaskProvider,
        complete_cb: Optional[Callable[[str], object]] = None,
        create_cb: Optional[Callable[[str], object]] = None,
    ) -> None:
        self.llm = llm
        self.tasks = tasks_provider
        self.complete_cb = complete_cb
        self.create_cb = create_cb
        self.ctx = SessionContext()

    # ---- referent resolution ----
    def _resolve_task(self, message: str) -> Optional[Task]:
        m = message.lower()
        tasks = [t for t in self.tasks() if t.status == "open"]
        if not tasks:
            return None
        # "the first one" / ordinal-ish
        if "first" in m:
            return rank_tasks(tasks)[0]
        # keyword match against titles/descriptions
        for t in tasks:
            hay = f"{t.title} {t.description or ''}".lower()
            if any(w in hay for w in m.split() if len(w) > 3):
                return t
        # bare referent -> the last-discussed task
        if any(r in m for r in _REFERENTS) and self.ctx.last_task_id:
            return next((t for t in tasks if t.id == self.ctx.last_task_id), None)
        return None

    def _pay_link(self, task: Task) -> str:
        # mock link derived from the task (advise-only; agent never pays)
        slug = task.title.lower().split()[0]
        return f"https://pay.example/{slug}?ref={task.id[:8]}"

    def handle(self, message: str) -> ChatReply:
        cat = self.llm.classify(message)
        m = message.lower()

        # ---- Add-a-task intent (e.g. "add a task to call the plumber", "remind me to X", "new task: X") ----
        add_title = self._extract_new_task_title(message)
        if add_title is not None:
            if self.create_cb is None:
                return ChatReply(reply="I can't add tasks right now.", category=Category.GENERAL_QA.value)
            if not add_title.strip():
                return ChatReply(reply="What should the task be? Give me a short title.",
                                 category=Category.GENERAL_QA.value)
            try:
                created = self.create_cb(add_title.strip())
            except Exception as e:  # noqa: BLE001
                return ChatReply(reply=f"I couldn't add that ({e}).", category=Category.GENERAL_QA.value)
            tid = getattr(created, "id", None)
            return ChatReply(
                reply=f"➕ Added “{add_title.strip()}” to your task list.",
                category=Category.GENERAL_QA.value,
                action="created-task",
                task_id=tid,
            )

        # ---- Complete-a-task intent (e.g. "complete X", "mark X done", "finish it") ----
        if any(w in m for w in ("complete", "mark done", "mark it done", "done with", "finish", "close")):
            target = self._resolve_task(self._strip_complete_verbs(message)) or self._resolve_task(message)
            if target is None and self.ctx.last_task_id:
                target = self._task_by_id(self.ctx.last_task_id)
            if target is None:
                return ChatReply(
                    reply="Which task should I mark done? Tell me its name.",
                    category=Category.GENERAL_QA.value,
                )
            if self.complete_cb is not None:
                try:
                    self.complete_cb(target.id)
                except Exception as e:  # noqa: BLE001
                    return ChatReply(reply=f"I couldn't complete that ({e}).",
                                     category=Category.GENERAL_QA.value)
            self.ctx.last_task_id = None
            return ChatReply(
                reply=f"✅ Marked “{target.title}” as done.",
                category=Category.GENERAL_QA.value,
                action="completed-task",
                task_id=target.id,
            )

        # A bare confirmation/link request with no new content -> use context.
        wants_pay_detail = any(w in m for w in _PAY_WORDS)
        referenced = self._resolve_task(message)
        task = referenced or (
            self._task_by_id(self.ctx.last_task_id) if wants_pay_detail else None
        )

        # If the user is following up on a financial-transaction task, advise + link.
        if task and (cat == Category.FINANCIAL_TRANSACTION or wants_pay_detail) and _is_payment(task):
            self._remember(task, Category.FINANCIAL_TRANSACTION.value)
            link = self._pay_link(task)
            detail = f" ({task.description})" if task.description else ""
            return ChatReply(
                reply=(
                    f"Here's how to pay “{task.title}”{detail}:\n"
                    f"  → Open the payment link: {link}\n"
                    "I've opened it for you to complete. I never make the payment myself — "
                    "you finish it on the provider's page."
                ),
                category=Category.FINANCIAL_TRANSACTION.value,
                action="open-link",
                task_id=task.id,
            )

        # Free-text routing into the CPA send flow.
        if cat == Category.FINANCIAL_DATA and any(w in m for w in ("send", "statement", "cpa")):
            self.ctx.last_intent = Category.FINANCIAL_DATA.value
            return ChatReply(
                reply="This sends your financial documents — I'll gather them and ask for your "
                      "approval before anything goes out, and only to your CPA.",
                category=Category.FINANCIAL_DATA.value,
                action="start-flow:send-statements",
            )

        # Routine automation routing.
        if cat == Category.ROUTINE_TASK:
            t = referenced
            if t:
                self._remember(t, Category.ROUTINE_TASK.value)
            return ChatReply(
                reply="I can handle this routine task with your permission. Say the word and I'll book it.",
                category=Category.ROUTINE_TASK.value,
                action="routine",
                task_id=t.id if t else None,
            )

        # A referenced payment task mentioned fresh (e.g. "Make payment to Ortega").
        if task and _is_payment(task):
            self._remember(task, Category.FINANCIAL_TRANSACTION.value)
            link = self._pay_link(task)
            detail = f" ({task.description})" if task.description else ""
            return ChatReply(
                reply=(
                    f"“{task.title}”{detail} is a payment. I can show you how and open the link "
                    f"({link}), but I never make payments myself. Want the link?"
                ),
                category=Category.FINANCIAL_TRANSACTION.value,
                action="advise",
                task_id=task.id,
            )

        # General Q&A over tasks.
        if cat == Category.GENERAL_QA:
            tasks = self.tasks()
            if _wants_next(m):
                nxt = rank_tasks([t for t in tasks if t.status == "open"])
                if nxt:
                    self._remember(nxt[0], Category.GENERAL_QA.value)
                return ChatReply(reply=next_action(tasks), category=cat.value)
            return ChatReply(reply=summarize_open_tasks(tasks), category=cat.value)

        # Refusals.
        if cat == Category.OFF_TOPIC:
            return ChatReply(reply="I only help with your task list, so I'll skip that one.", category=cat.value)
        if cat == Category.UNSAFE:
            return ChatReply(reply="I can't help with that.", category=cat.value)

        return ChatReply(reply="Here's what I can help with — your tasks. Ask what to do next, or pick an action.",
                         category=cat.value)

    # ---- helpers ----
    def _remember(self, task: Task, intent: str) -> None:
        self.ctx.last_task_id = task.id
        self.ctx.last_task_title = task.title
        self.ctx.last_intent = intent

    def _task_by_id(self, task_id: Optional[str]) -> Optional[Task]:
        if not task_id:
            return None
        return next((t for t in self.tasks() if t.id == task_id), None)

    @staticmethod
    def _strip_complete_verbs(message: str) -> str:
        out = message
        for verb in ("complete", "mark", "as done", "done", "finish", "close", "the task", "task"):
            out = out.replace(verb, " ").replace(verb.capitalize(), " ")
        return out.strip()

    @staticmethod
    def _extract_new_task_title(message: str) -> Optional[str]:
        """Return the task title if this is an add-task request, else None.

        Recognizes: "add [a] task [to/:] X", "create [a] task [to/:] X",
        "new task [:] X", "remind me to X", "add X to my [task] list".
        """
        m = message.strip()
        low = m.lower()
        # avoid colliding with complete/list intents
        if any(w in low for w in ("complete", "mark ", "finish", "what ", "list", "show me my")):
            return None
        import re

        patterns = [
            r"^\s*add (?:a )?task(?: to| :|:)?\s+(.*)$",
            r"^\s*create (?:a )?task(?: to| :|:)?\s+(.*)$",
            r"^\s*new task(?: :|:)?\s+(.*)$",
            r"^\s*remind me to\s+(.*)$",
            r"^\s*add\s+(.*?)\s+to my (?:task )?list\s*$",
        ]
        for p in patterns:
            mt = re.match(p, m, flags=re.IGNORECASE)
            if mt:
                return mt.group(1).strip().rstrip(".")
        return None


def _is_payment(task: Task) -> bool:
    hay = f"{task.title} {task.description or ''} {task.category or ''}".lower()
    return any(w in hay for w in ("pay", "payment", "bill", "financial"))


def _wants_next(m: str) -> bool:
    return any(p in m for p in ("what next", "what should i do", "focus", "prioriti", "first"))
