#!/usr/bin/env python3
"""Reset the demo to a known state via the running APIs (no DB file surgery):
  - Legacy tasks (:4000): delete all, re-create the 4 canonical life-admin tasks.
  - Booking slots (:4100): reset every slot to its seed availability.

Run AFTER the servers are up (start-all.sh). Usage: python3 reset-demo.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request

LEGACY = "http://127.0.0.1:4000"
BOOKING = "http://127.0.0.1:4100"


def _req(url: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"content-type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r) if r.status != 204 else None


def _iso(days: int) -> str:
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


CANONICAL_TASKS = [
    {"title": "Make payment to lawn-mower", "description": "Pay Ortega $150 for the September lawn service.",
     "priority": "high", "dueDate": _iso(1), "category": "financial"},
    {"title": "Book appointment with childcare nanny for next Saturday",
     "description": "Call Maria to book Saturday 9am–1pm. Bookings fill up fast.",
     "priority": "high", "dueDate": _iso(7), "category": "routine"},
    {"title": "See if electricity bill is available, pay it",
     "description": "Check the utility portal for this month's bill; pay if available.",
     "priority": "medium", "dueDate": None, "category": "financial"},
    {"title": "Send bank statement to CPA for tax filing",
     "description": "Send last 3 months of statements to the CPA for the tax return.",
     "priority": "medium", "dueDate": _iso(14), "category": "financial"},
]

SEED_SLOTS = {
    "d1": True, "d2": True, "d3": True, "d4": False,  # d4 pre-booked ("someone else")
    "c1": True, "c2": True, "c3": True,
}


def reset_tasks() -> None:
    existing = _req(f"{LEGACY}/api/tasks")
    for t in existing:
        _req(f"{LEGACY}/api/tasks/{t['id']}", method="DELETE")
    for spec in CANONICAL_TASKS:
        _req(f"{LEGACY}/api/tasks", method="POST", body=spec)
    print(f"tasks: deleted {len(existing)}, created {len(CANONICAL_TASKS)}")


def reset_slots() -> None:
    n = 0
    for slot_id, available in SEED_SLOTS.items():
        _req(f"{BOOKING}/slots/{slot_id}", method="PATCH",
             body={"available": available, "bookedBy": None if available else "someone else"})
        n += 1
    print(f"booking slots: reset {n}")


def main() -> int:
    try:
        reset_tasks()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR resetting tasks (is the legacy API on :4000?): {e}", file=sys.stderr)
        return 1
    try:
        reset_slots()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR resetting slots (is the booking mock on :4100?): {e}", file=sys.stderr)
        return 1
    print("Demo reset to known state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
