"""Mock Bank Aggregator connector (T12) — Plaid-style, credential-less.

The bank's OAuth happens in the browser; the agent NEVER sees the username or
password — it receives only a scoped READ-ONLY token via the aggregator. This
connector deliberately exposes NO payment/transfer method: statement retrieval
is the entire surface (design FR-24). That absence is asserted by test.

To go real: implement against Plaid/Finicity/MX Link + statements endpoints,
keeping the read-only token and the same list/get contract.
"""
from __future__ import annotations

from dataclasses import dataclass

from .oauth import ScopedToken

STATEMENTS_READ_SCOPE = "bank.statements.readonly"


@dataclass
class BankStatement:
    id: str
    period: str  # e.g. "2026-08"
    content: str


class TokenError(Exception):
    pass


class MockBankAggregatorConnector:
    """Read-only statements only. No payment capability exists here by design."""

    def __init__(self, provider: str = "Plaid") -> None:
        self.provider = provider
        self._statements = [
            BankStatement(id="b1", period="2026-06", content="Chase account statement 2026-06"),
            BankStatement(id="b2", period="2026-07", content="Chase account statement 2026-07"),
            BankStatement(id="b3", period="2026-08", content="Chase account statement 2026-08"),
        ]

    def _check(self, token: ScopedToken | None) -> None:
        if token is None or not token.allows(STATEMENTS_READ_SCOPE):
            raise TokenError("missing or insufficient statements-read scope")

    def list_statements(self, token: ScopedToken | None) -> list[BankStatement]:
        self._check(token)
        return list(self._statements)

    def get_statement(self, token: ScopedToken | None, statement_id: str) -> BankStatement | None:
        self._check(token)
        return next((s for s in self._statements if s.id == statement_id), None)

    # NOTE: intentionally NO make_payment / transfer method — see test.
