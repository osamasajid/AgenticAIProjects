"""Mock Gmail connector (T10) — inbox + watch + inject + detection.

Provides a fake inbox, a background 'watch' the agent registers, an
'inject_email' control for deterministic demos, and a detector that matches on
sender AND subject AND parsed content (design FR-13) — so not every bank email
counts as the statement, and phishing look-alikes can be caught.

To go real: implement against the Gmail API (users.watch + history), keeping the
same detect() contract.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Email:
    sender: str
    subject: str
    body: str
    attachments: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class MatchResult:
    matched: bool
    reasons: list[str]
    email: Email | None = None


class MockGmailConnector:
    def __init__(self) -> None:
        self._inbox: list[Email] = []

    def inject_email(self, email: Email) -> None:
        """Demo control: simulate an email arriving."""
        self._inbox.append(email)

    def inbox(self) -> list[Email]:
        return list(self._inbox)

    def detect(
        self,
        *,
        sender_match: str,
        subject_keywords: list[str],
        content_keywords: list[str],
    ) -> MatchResult:
        """Return the best matching email. Requires sender AND subject AND content
        signals — a bank email that is not a statement will NOT match."""
        for email in self._inbox:
            reasons: list[str] = []
            if sender_match and sender_match.lower() in email.sender.lower():
                reasons.append(f"sender matches '{sender_match}'")
            else:
                continue
            subj_hit = any(k.lower() in email.subject.lower() for k in subject_keywords)
            if subj_hit:
                reasons.append("subject contains a statement keyword")
            else:
                continue
            text = (email.body + " " + " ".join(email.attachments)).lower()
            content_hit = any(k.lower() in text for k in content_keywords)
            if content_hit:
                reasons.append("content parsed as an account statement")
            else:
                continue
            return MatchResult(matched=True, reasons=reasons, email=email)
        return MatchResult(matched=False, reasons=["no email matched all signals"])
