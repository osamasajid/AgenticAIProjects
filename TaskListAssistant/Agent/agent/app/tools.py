"""Tool / Action Layer (T6) — the single choke point for all external effects.

Security model (design §4.2, NFR-2/NFR-3):
  * The LLM/agent can only *request* an effect through here; it never calls a
    connector directly.
  * The CPA destination guardrail is enforced IN CODE against the frozen config
    (config.cpa_destination()). No argument, message, memory, or fetched content
    can redirect a financial document anywhere else.
  * Content fetched from emails/files is untrusted DATA. Any instruction embedded
    in it is ignored — it can never change the destination or grant permissions.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import cpa_destination


class GuardrailError(Exception):
    """Raised when an action violates a hard security boundary."""


@dataclass
class SendResult:
    ok: bool
    destination: str
    channel: str
    detail: str


def _cpa_targets() -> set[str]:
    d = cpa_destination()
    return {d.email.strip().lower(), d.portal_url.strip().lower()}


def assert_cpa_destination(destination: str, channel: str) -> None:
    """Code-enforced guardrail (FR-10/FR-11). Raise unless destination is the
    fixed CPA email (channel=email) or portal URL (channel=portal)."""
    d = cpa_destination()
    target = (destination or "").strip().lower()
    if channel == "email":
        allowed = target == d.email.strip().lower()
    elif channel == "portal":
        allowed = target == d.portal_url.strip().lower()
    else:
        raise GuardrailError(f"unknown channel '{channel}' (must be 'email' or 'portal')")
    if not allowed:
        raise GuardrailError(
            f"destination '{destination}' is not the configured CPA {channel}; "
            "financial documents can only be sent to the CPA."
        )


def send_financial_document(
    *,
    files: list[str],
    destination: str,
    channel: str,
) -> SendResult:
    """The ONLY egress for financial documents. Enforces the guardrail before sending.

    `destination` is accepted as an argument purely so the guardrail can VALIDATE
    it — a mismatch raises. The effective target is always the frozen config CPA.
    """
    assert_cpa_destination(destination, channel)  # raises on any non-CPA target
    d = cpa_destination()
    effective = d.email if channel == "email" else d.portal_url
    # Delegate the actual send to the CPA connector (defense-in-depth: it also
    # independently refuses any non-CPA destination).
    from .connectors.cpa import MockCpaSendConnector

    receipt = MockCpaSendConnector().send(files=files, destination=effective, channel=channel)
    return SendResult(
        ok=True,
        destination=receipt.destination,
        channel=receipt.channel,
        detail=f"sent {receipt.file_count} document(s) to CPA via {channel}",
    )


def sanitize_untrusted_content(content: str) -> str:
    """Untrusted content is DATA, not instructions (NFR-3).

    We never parse it for commands. This helper exists to make the boundary
    explicit and to strip nothing but return it as inert text for display/logging.
    Any 'send to X instead' text inside is irrelevant: the guardrail above only
    ever consults the frozen config, never this content.
    """
    return content
