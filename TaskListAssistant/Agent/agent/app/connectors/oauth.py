"""OAuth + consent connector (T9) — mock now, real-swappable.

Simulates the "Sign in with Google -> these scopes -> Allow" experience and the
credential-less bank OAuth (T12 uses this). Returns a SCOPED token; the consent
moment (which scopes are requested) is part of the lesson, so it's modelled, not
skipped. No real credentials are ever handled.

To go real: implement RealOAuthConnector against Google OAuth 2.0 / Plaid Link,
returning a token with the granted scopes. Select via GOOGLE_OAUTH=real.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ScopedToken:
    token: str
    scopes: tuple[str, ...]
    provider: str
    one_time: bool = True
    used: bool = False

    def allows(self, scope: str) -> bool:
        return (not self.used or not self.one_time) and scope in self.scopes


@dataclass
class ConsentRequest:
    """What the mock consent screen would display."""

    provider: str
    scopes: tuple[str, ...]
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class OAuthConnector(Protocol):
    def begin_consent(self, provider: str, scopes: list[str]) -> ConsentRequest: ...
    def complete_consent(self, request_id: str, allow: bool) -> ScopedToken | None: ...


class MockOAuthConnector:
    """In-memory mock. Consent must be explicitly 'allowed' to yield a token."""

    def __init__(self) -> None:
        self._pending: dict[str, ConsentRequest] = {}

    def begin_consent(self, provider: str, scopes: list[str]) -> ConsentRequest:
        req = ConsentRequest(provider=provider, scopes=tuple(scopes))
        self._pending[req.request_id] = req
        return req

    def complete_consent(self, request_id: str, allow: bool) -> ScopedToken | None:
        req = self._pending.pop(request_id, None)
        if req is None:
            return None
        if not allow:
            return None  # user declined -> no token
        return ScopedToken(
            token=f"mock-{uuid.uuid4().hex}",
            scopes=req.scopes,
            provider=req.provider,
        )
