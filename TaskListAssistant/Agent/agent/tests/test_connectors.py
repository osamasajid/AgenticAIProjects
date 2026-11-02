"""Wave C connector conformance tests."""
from __future__ import annotations

import pytest

from app.config import cpa_destination
from app.connectors.bank import (
    STATEMENTS_READ_SCOPE,
    MockBankAggregatorConnector,
    TokenError as BankTokenError,
)
from app.connectors.booking import MockBookingConnector, PermissionError_
from app.connectors.cpa import DestinationError, MockCpaSendConnector
from app.connectors.drive import DRIVE_READ_SCOPE, MockDriveConnector, TokenError
from app.connectors.gmail import Email, MockGmailConnector
from app.connectors.oauth import MockOAuthConnector


# ---- T9 OAuth ----
def test_oauth_allow_yields_scoped_token() -> None:
    o = MockOAuthConnector()
    req = o.begin_consent("google", ["drive.readonly"])
    tok = o.complete_consent(req.request_id, allow=True)
    assert tok and tok.allows("drive.readonly")
    assert not tok.allows("drive.write")  # scope is limited


def test_oauth_decline_yields_no_token() -> None:
    o = MockOAuthConnector()
    req = o.begin_consent("google", ["drive.readonly"])
    assert o.complete_consent(req.request_id, allow=False) is None


# ---- T10 Gmail ----
def _gmail_with_statement() -> MockGmailConnector:
    g = MockGmailConnector()
    g.inject_email(Email(
        sender="statements@bank.com", subject="Your July statement is ready",
        body="Your account statement is attached.", attachments=["Statement_Jul.pdf"],
    ))
    return g


def test_gmail_detects_statement() -> None:
    g = _gmail_with_statement()
    res = g.detect(sender_match="bank.com", subject_keywords=["statement"],
                   content_keywords=["statement"])
    assert res.matched and len(res.reasons) == 3


def test_gmail_ignores_non_statement_bank_email() -> None:
    g = MockGmailConnector()
    g.inject_email(Email(
        sender="marketing@bank.com", subject="New credit card offer!",
        body="Apply now for rewards.", attachments=[],
    ))
    res = g.detect(sender_match="bank.com", subject_keywords=["statement"],
                   content_keywords=["statement"])
    assert res.matched is False


# ---- T11 Drive ----
def test_drive_requires_scope() -> None:
    d = MockDriveConnector()
    with pytest.raises(TokenError):
        d.list_files(None)


def test_drive_lists_with_scope() -> None:
    from app.connectors.oauth import ScopedToken
    tok = ScopedToken(token="t", scopes=(DRIVE_READ_SCOPE,), provider="google", one_time=False)
    files = MockDriveConnector().list_files(tok)
    assert any("Statement" in f.name for f in files)


# ---- T12 Bank aggregator ----
def test_bank_requires_scope() -> None:
    with pytest.raises(BankTokenError):
        MockBankAggregatorConnector().list_statements(None)


def test_bank_lists_statements_read_only() -> None:
    from app.connectors.oauth import ScopedToken
    tok = ScopedToken(token="t", scopes=(STATEMENTS_READ_SCOPE,), provider="Plaid", one_time=False)
    stmts = MockBankAggregatorConnector().list_statements(tok)
    assert len(stmts) == 3


def test_bank_has_no_payment_capability() -> None:
    # The credential-less connector must expose NO way to move money.
    bank = MockBankAggregatorConnector()
    for forbidden in ("make_payment", "transfer", "pay", "send_money"):
        assert not hasattr(bank, forbidden)


# ---- T13 CPA send ----
def test_cpa_send_to_cpa_email_ok() -> None:
    d = cpa_destination()
    rec = MockCpaSendConnector().send(files=["s.pdf"], destination=d.email, channel="email")
    assert rec.file_count == 1 and rec.destination == d.email


def test_cpa_send_refuses_other_destination() -> None:
    with pytest.raises(DestinationError):
        MockCpaSendConnector().send(files=["s.pdf"], destination="x@evil.com", channel="email")


# ---- T14 Booking ----
def test_booking_requires_permission() -> None:
    with pytest.raises(PermissionError_):
        MockBookingConnector().book(detail="nanny Sat 9am", has_permission=False)


def test_booking_with_permission() -> None:
    conf = MockBookingConnector().book(detail="nanny Sat 9am", has_permission=True)
    assert conf.confirmation_id.startswith("bk-")
