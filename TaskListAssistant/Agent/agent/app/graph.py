"""LangGraph agent skeleton (T4/T5) + general-QA task answering (T20 seed).

classify -> route. The general-QA path now reads live tasks from the legacy API
(via an injected provider) so the agent can answer "what are my open tasks?" and
"what should I do next?". Financial/routine handlers land fully in Wave D.
"""
from __future__ import annotations

from typing import Callable, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .llm import LLMClient, get_llm
from .models import Category, Task
from .prioritize import next_action, summarize_open_tasks

# A provider returns the current tasks. Injected so tests don't need a live server.
TaskProvider = Callable[[], list[Task]]


class AgentState(TypedDict, total=False):
    message: str
    category: str
    reply: str


def _classify_node(state: AgentState, llm: LLMClient) -> AgentState:
    cat = llm.classify(state.get("message", ""))
    return {"category": cat.value}


def _wants_next_action(message: str) -> bool:
    m = message.lower()
    return any(p in m for p in ("what next", "what should i do", "focus", "prioriti", "first"))


def _respond_node(state: AgentState, tasks_provider: Optional[TaskProvider]) -> AgentState:
    cat = state.get("category", Category.GENERAL_QA.value)

    if cat == Category.GENERAL_QA.value and tasks_provider is not None:
        try:
            tasks = tasks_provider()
        except Exception as e:  # noqa: BLE001 - surface connectivity plainly
            return {"reply": f"I couldn't reach your task list right now ({e})."}
        if _wants_next_action(state.get("message", "")):
            return {"reply": next_action(tasks)}
        return {"reply": summarize_open_tasks(tasks)}

    replies = {
        Category.FINANCIAL_TRANSACTION.value:
            "I can show you how to pay and open the link, but I never make payments myself.",
        Category.FINANCIAL_DATA.value:
            "This involves your financial documents — I'll ask for your approval before sending anything, and only to your CPA.",
        Category.ROUTINE_TASK.value:
            "I can handle this routine task with your permission.",
        Category.GENERAL_QA.value:
            "Here's what I found about your tasks.",
        Category.OFF_TOPIC.value:
            "I only help with your task list, so I'll skip that one.",
        Category.UNSAFE.value:
            "I can't help with that.",
    }
    return {"reply": replies.get(cat, replies[Category.GENERAL_QA.value])}


def build_graph(
    llm: Optional[LLMClient] = None,
    checkpointer: Optional[MemorySaver] = None,
    tasks_provider: Optional[TaskProvider] = None,
):
    llm = llm or get_llm()
    g: StateGraph = StateGraph(AgentState)
    g.add_node("classify", lambda s: _classify_node(s, llm))
    g.add_node("respond", lambda s: _respond_node(s, tasks_provider))
    g.add_edge(START, "classify")
    g.add_edge("classify", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer)
