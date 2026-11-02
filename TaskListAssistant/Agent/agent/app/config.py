"""Configuration (T3). Read-only where it matters.

The CPA destination is FIXED config (design FR-10, NFR-2). It is exposed only
as read-only properties — there is no setter and no API to change it at runtime.
The destination guardrail (T6) enforces that financial documents can go
*only* here, regardless of what the LLM or any message says.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CpaDestination:
    """Immutable (frozen) CPA destination. No runtime mutation possible."""

    email: str
    portal_url: str


# The single source of truth for where financial documents may be sent.
# Frozen dataclass => attempting to reassign a field raises at runtime.
_CPA = CpaDestination(
    email=os.environ.get("CPA_EMAIL", "cpa@firm.com"),
    portal_url=os.environ.get("CPA_PORTAL_URL", "https://portal.cpa-firm.example/upload"),
)


def cpa_destination() -> CpaDestination:
    """Return the fixed CPA destination (read-only)."""
    return _CPA


# ---- Other settings ----
LLM_MODE = os.environ.get("LLM", "stub")  # "stub" | "bedrock" | "ollama"
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
LEGACY_API_URL = os.environ.get("LEGACY_API_URL", "http://127.0.0.1:4000")
DEFAULT_WATCH_DAYS = int(os.environ.get("DEFAULT_WATCH_DAYS", "30"))
