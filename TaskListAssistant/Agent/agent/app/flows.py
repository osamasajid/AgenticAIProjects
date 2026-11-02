"""Hero flows (Wave D) — compose connectors + the oversight gate.

Each flow gathers documents/context via the (mock) connectors, then routes the
irreversible send through the OversightService interrupt() gate. The gate owns
detect -> pause -> approve -> send; these flows own the "gather + prepare" half
and expose a two-step API: start() returns the pending approval, resolve()
finishes via the gate.

All three flows send ONLY to the fixed CPA destination (guardrail enforced in
the Tool Layer / gate / CPA connector).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import DEFAULT_WATCH_DAYS, cpa_destination
from .connectors.bank import STATEMENTS_READ_SCOPE, MockBankAggregatorConnector
from .connectors.drive import DRIVE_READ_SCOPE, MockDriveConnector
from .connectors.gmail import MockGmailConnector
from .connectors.oauth import MockOAuthConnector, ScopedToken
from .models import Permission, PermissionType, Watch
from .oversight import OversightService
from .store import Store


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class FlowStep:
    """A single step to display in the demo/UI narrative."""

    label: str
    detail: str = ""


@dataclass
class FlowResult:
    kind: str  # "pending-approval" | "refused" | "nothing-found"
    steps: list[FlowStep] = field(default_factory=list)
    thread_id: Optional[str] = None
    approval: Optional[dict] = None
    message: str = ""


# ---- Hero flow 1: send statements to CPA (T17) ----
class SendStatementsFlow:
    def __init__(self, oversight: OversightService, store: Store) -> None:
        self.oversight = oversight
        self.store = store
        self.oauth = MockOAuthConnector()
        self.drive = MockDriveConnector()

    def start(self, *, channel: str = "email", task_id: Optional[str] = None) -> FlowResult:
        steps = [FlowStep("Requested one-time access to your files (OAuth consent)")]
        # Mock consent auto-approved for the demo happy path.
        req = self.oauth.begin_consent("google", [DRIVE_READ_SCOPE])
        token = self.oauth.complete_consent(req.request_id, allow=True)
        steps.append(FlowStep("Consent granted", "scoped, one-time Drive read"))
        files = [f.name for f in self.drive.list_files(token) if f.name.startswith("Statement")]
        steps.append(FlowStep(f"Found {len(files)} statement file(s)", ", ".join(files)))
        d = cpa_destination()
        dest = d.email if channel == "email" else d.portal_url
        thread, approval = self.oversight.request_send(
            files=files, destination=dest, channel=channel, source="Google Drive (one-time)",
            task_id=task_id,
        )
        return FlowResult(
            kind="pending-approval", steps=steps, thread_id=thread, approval=approval,
            message="Ready to send — awaiting your approval.",
        )


# ---- Hero flow 2: email-watch -> detect -> pause -> approve -> send (T18) ----
class EmailWatchFlow:
    def __init__(self, oversight: OversightService, store: Store, gmail: MockGmailConnector) -> None:
        self.oversight = oversight
        self.store = store
        self.gmail = gmail

    def arm_watch(self, *, days: int = DEFAULT_WATCH_DAYS) -> Watch:
        watch = Watch(
            id=str(uuid.uuid4()),
            description="Watch inbox for the bank statement, then send to CPA",
            senderMatch="bank.com",
            subjectKeywords=["statement"],
            contentKeywords=["statement"],
            grantedAt=_now(),
            expiresAt=_now() + timedelta(days=days),
        )
        self.store.add_watch(watch)
        self.store.log("proposed", f"armed statement watch for {days} days", {"watchId": watch.id})
        return watch

    def on_email_arrived(self, watch: Watch, *, channel: str = "portal") -> FlowResult:
        # Expiry check.
        if watch.revoked or _now() > watch.expiresAt:
            return FlowResult(kind="nothing-found", message="Watch expired or revoked.")
        res = self.gmail.detect(
            sender_match=watch.senderMatch or "",
            subject_keywords=watch.subjectKeywords,
            content_keywords=watch.contentKeywords,
        )
        if not res.matched or res.email is None:
            return FlowResult(kind="nothing-found", message="No matching statement email yet.")
        steps = [
            FlowStep("Detected a candidate statement email", res.email.subject),
            FlowStep("Why I think it's the statement", "; ".join(res.reasons)),
        ]
        d = cpa_destination()
        dest = d.email if channel == "email" else d.portal_url
        thread, approval = self.oversight.request_send(
            files=res.email.attachments, destination=dest, channel=channel,
            source=f"email from {res.email.sender}",
        )
        # Enrich the approval card with detection reasoning (false-positive protection).
        if isinstance(approval, dict):
            approval["detection_reasons"] = res.reasons
        return FlowResult(
            kind="pending-approval", steps=steps, thread_id=thread, approval=approval,
            message="Found your statement — awaiting your approval before sending.",
        )


# ---- Hero flow 3: direct bank fetch (T19) ----
class DirectBankFetchFlow:
    def __init__(self, oversight: OversightService, store: Store) -> None:
        self.oversight = oversight
        self.store = store
        self.oauth = MockOAuthConnector()
        self.bank = MockBankAggregatorConnector()

    def start(self, *, channel: str = "portal") -> FlowResult:
        steps = [FlowStep("Opening your bank's OAuth page in the browser", "agent never sees credentials")]
        # Credential-less: browser OAuth returns a scoped READ-ONLY token.
        req = self.oauth.begin_consent(self.bank.provider, [STATEMENTS_READ_SCOPE])
        token: ScopedToken | None = self.oauth.complete_consent(req.request_id, allow=True)
        steps.append(FlowStep("Received read-only statements token", f"via {self.bank.provider}"))
        statements = self.bank.list_statements(token)
        latest = statements[-1]
        steps.append(FlowStep("Fetched latest statement", f"period {latest.period}"))
        d = cpa_destination()
        dest = d.email if channel == "email" else d.portal_url
        thread, approval = self.oversight.request_send(
            files=[f"Statement_{latest.period}.pdf"], destination=dest, channel=channel,
            source=f"{self.bank.provider} (read-only token)",
        )
        return FlowResult(
            kind="pending-approval", steps=steps, thread_id=thread, approval=approval,
            message="Fetched from your bank — awaiting your approval before sending.",
        )

    def grant_recurring(self, *, days: int = DEFAULT_WATCH_DAYS) -> Permission:
        perm = Permission(
            id=str(uuid.uuid4()),
            type=PermissionType.RECURRING_BANK_FETCH,
            description="Auto-fetch next statement and send to CPA (approve-gated each time)",
            grantedAt=_now(),
            expiresAt=_now() + timedelta(days=days),
        )
        self.store.add_permission(perm)
        self.store.log("proposed", "granted recurring bank-fetch permission", {"permId": perm.id})
        return perm
