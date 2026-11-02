"""Mock Booking connector (T14) — routine automation under permission.

Books an appointment only when a permission is granted. Returns a confirmation.

To go real: implement against a calendar/booking provider, same contract.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


class PermissionError_(Exception):
    pass


@dataclass
class BookingConfirmation:
    confirmation_id: str
    detail: str


class MockBookingConnector:
    def book(self, *, detail: str, has_permission: bool) -> BookingConfirmation:
        if not has_permission:
            raise PermissionError_("booking requires a granted permission")
        return BookingConfirmation(
            confirmation_id=f"bk-{uuid.uuid4().hex[:8]}",
            detail=f"Booked: {detail}",
        )
