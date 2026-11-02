"""Hand-written ReAct loop (reason -> act -> observe -> repeat).

This is the real thing, written explicitly so the mechanics are visible (the point
of the teaching demo) rather than hidden in a framework helper:

  1. Send the conversation + tool schemas to the model.
  2. If the model returns tool_calls, EXECUTE each locally, append the results as
     'tool' messages (the OBSERVATION), and loop.
  3. If the model returns a final answer (no tool calls), stop and return it.

Guards: a max-iteration cap (never spin forever) and tolerance for a small local
model occasionally emitting a malformed/empty tool call.

Backed by Ollama's OpenAI-compatible /v1 endpoint so any tool-calling model works.
Refusals (off-topic/unsafe) are enforced by the system prompt + the fixed toolset:
the model simply has no tool to do anything outside tasks, and irreversible sends
still pass through the human approval gate.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.request
from typing import Any

from .agent_tools import TaskTools
from .config import OLLAMA_URL, OLLAMA_MODEL

SYSTEM = (
    "You are a task assistant. Today's date is {today}. When the user says 'today', "
    "'tomorrow', 'this weekend', etc., convert it to an ISO date (YYYY-MM-DD) based on "
    "today's date before calling tools. You help ONLY with the user's task list: listing, "
    "prioritizing, adding, and completing tasks; checking weather for outdoor plans; "
    "finding and booking appointment slots; and starting the (human-approved) send-to-CPA "
    "flow. Use the provided tools to act.\n\n"
    "TOOL SELECTION RULES:\n"
    "- For a picnic, tennis game, outing, chore, errand, or ANY personal plan/event, use "
    "add_task with a descriptive title (e.g. 'Picnic with friends Saturday 11am-4pm'). "
    "Do NOT use list_slots or book_slot for these.\n"
    "- Only use list_slots / book_slot for a DOCTOR or CPA appointment with a provider.\n"
    "- Use get_weather before scheduling an OUTDOOR plan; if rain is likely and the user "
    "said not to schedule when raining, do not add it — say so instead.\n\n"
    "You never make payments and never send documents anywhere except via the "
    "approval-gated CPA tool. If the user asks about anything unrelated to their tasks or "
    "anything unsafe, briefly decline. Keep replies short."
)

MAX_ITERS = 5


def _chat(messages: list[dict], tools: list[dict]) -> dict:
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/v1/chat/completions", data=body,
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)["choices"][0]["message"]


def run_react(
    user_message: str,
    tools_impl: TaskTools,
    extra_tools: list | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict:
    """Run the ReAct loop for one user turn. Returns {reply, steps, flow, history}.

    `extra_tools` are additional Tool objects (e.g. discovered from MCP servers).
    `history` is prior conversation turns (user/assistant messages) so multi-turn
    planning works — e.g. "check weather" then "yes, book it" resolves against the
    earlier picnic context. The returned `history` is the updated transcript the
    caller should persist per session.
    """
    local = tools_impl.tools()
    all_tools = local + (extra_tools or [])
    schemas = [t.schema() for t in all_tools]
    registry = {t.name: t for t in all_tools}
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM.format(today=_dt.date.today().isoformat())},
    ]
    # replay prior turns (user/assistant only — tool scaffolding is not re-sent)
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_message})
    steps: list[str] = []

    def _finish(reply: str) -> dict:
        # persist just the clean user/assistant exchange for the next turn
        new_history = list(history or [])
        new_history.append({"role": "user", "content": user_message})
        new_history.append({"role": "assistant", "content": reply})
        # cap history so it doesn't grow unbounded (last ~12 messages)
        return {"reply": reply, "steps": steps, "flow": tools_impl.pending_flow,
                "history": new_history[-12:]}

    for _ in range(MAX_ITERS):
        msg = _chat(messages, schemas)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            reply = (msg.get("content") or "").strip()
            if not reply:
                # small model declined by emitting nothing (common for off-topic)
                reply = "I only help with your task list, so I'll skip that one."
            return _finish(reply)

        # append the assistant's tool-call message, then execute each call (OBSERVE)
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": tool_calls})
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool = registry.get(name)
            if tool is None:
                observation = f"error: no tool named '{name}'"
            else:
                try:
                    observation = tool.fn(**args)
                except TypeError:
                    observation = tool.fn()  # tolerate a bad-arg call from a small model
                except Exception as e:  # noqa: BLE001
                    observation = f"error: {e}"
            steps.append(f"{name}({args}) -> {observation}")
            messages.append({"role": "tool", "tool_call_id": call.get("id", name),
                             "name": name, "content": str(observation)})
        # if a flow started, stop here so the human can act on the Approval Card
        if tools_impl.pending_flow is not None:
            return _finish("Started the CPA send — awaiting your approval.")

    return _finish("I couldn't complete that in a few steps — try rephrasing.")
