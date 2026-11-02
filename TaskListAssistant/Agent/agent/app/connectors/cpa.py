"""Mock CPA Send connector (T13) — the single egress for financial documents.

Only accepts the fixed CPA destination. The authoritative guardrail lives in the
Tool Layer (app/tools.py); this connector performs the mock send and independently
refuses any non-CPA target as defense-in-depth.

To go real: implement email (SES/SMTP) or portal upload, keeping the same
CPA-only guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import cpa_destination


class DestinationError(Exception):
    pass


@dataclass
class DeliveryReceipt:
    channel: str
    destination: str
    file_count: int


class MockCpaSendConnector:
    def send(self, *, files: list[str], destination: str, channel: str) -> DeliveryReceipt:
        d = cpa_destination()
        target = (destination or "").strip().lower()
        allowed = (
            (channel == "email" and target == d.email.strip().lower())
            or (channel == "portal" and target == d.portal_url.strip().lower())
        )
        if not allowed:
            raise DestinationError(
                f"CPA connector refuses non-CPA destination '{destination}' via {channel}"
            )
        effective = d.email if channel == "email" else d.portal_url
        return DeliveryReceipt(channel=channel, destination=effective, file_count=len(files))
