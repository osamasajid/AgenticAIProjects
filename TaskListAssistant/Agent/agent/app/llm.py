"""LLM seam (T4): a small interface with a deterministic Stub and a Bedrock adapter.

Default is the Stub so the demo runs offline and deterministically. Set LLM=bedrock
(plus AWS creds) to use Claude on Amazon Bedrock. Kept behind an interface so the
agent graph never depends on a concrete model.
"""
from __future__ import annotations

from typing import Protocol

from .config import AWS_REGION, BEDROCK_MODEL_ID, LLM_MODE
from .models import Category


class LLMClient(Protocol):
    def classify(self, message: str) -> Category: ...
    def complete(self, prompt: str) -> str: ...


# ---- Deterministic stub ----
class StubLLMClient:
    """Rule-based, deterministic responses keyed to the demo scenarios.

    Enough to drive intent routing and canned replies with no network/model.
    """

    def classify(self, message: str) -> Category:
        m = message.lower()

        unsafe_markers = ("kill", "bomb", "how to hack", "buy drugs", "launder")
        if any(w in m for w in unsafe_markers) or _has_profanity(m):
            return Category.UNSAFE

        off_topic = ("weather", "sports", "football", "foreign policy", "election", "movie", "recipe")
        task_markers = ("task", "pay", "bill", "statement", "cpa", "appointment",
                        "book", "nanny", "watch", "bank", "todo", "to-do", "due", "priorit")
        if any(w in m for w in off_topic) and not any(w in m for w in task_markers):
            return Category.OFF_TOPIC

        if "statement" in m or "cpa" in m or "bank" in m:
            return Category.FINANCIAL_DATA
        if "pay" in m or "bill" in m or "payment" in m:
            return Category.FINANCIAL_TRANSACTION
        if "book" in m or "appointment" in m or "nanny" in m or "schedule" in m:
            return Category.ROUTINE_TASK
        return Category.GENERAL_QA

    def complete(self, prompt: str) -> str:
        return "[stub] " + prompt[:200]


def _has_profanity(text: str) -> bool:
    # tiny placeholder list for the demo
    return any(w in text for w in ("damn it all", "f***", "s***"))


# ---- Bedrock adapter ----
class BedrockLLMClient:
    """Claude on Amazon Bedrock via langchain-aws. Constructed lazily."""

    def __init__(self) -> None:
        from langchain_aws import ChatBedrock  # imported lazily so stub mode needs no AWS

        self._model = ChatBedrock(model=BEDROCK_MODEL_ID, region=AWS_REGION)

    def classify(self, message: str) -> Category:
        prompt = (
            "Classify the user's request into exactly one of: "
            "financial-transaction, financial-data, routine-task, general-qa, off-topic, unsafe. "
            "Reply with only the label.\n\nRequest: " + message
        )
        raw = self.complete(prompt).strip().lower()
        for c in Category:
            if c.value in raw:
                return c
        return Category.GENERAL_QA

    def complete(self, prompt: str) -> str:
        resp = self._model.invoke(prompt)
        return str(getattr(resp, "content", resp))


def get_llm() -> LLMClient:
    if LLM_MODE == "bedrock":
        return BedrockLLMClient()
    return StubLLMClient()
