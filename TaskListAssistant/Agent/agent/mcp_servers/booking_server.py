"""Booking MCP server (calls the json-server mock REST API at :4100).

Exposes list_slots and book_slot as MCP tools. Demonstrates an MCP server fronting
a real (mock-backed) external REST service, and a stateful multi-step capability
(check availability -> book). Booking is irreversible, so in the agent the
book_slot result is surfaced for human approval before it is treated as final
(the agent/client owns the oversight gate, not this server).

Run: python -m mcp_servers.booking_server   (stdio transport)
"""
from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("booking")

BOOKING_API = os.environ.get("BOOKING_API_URL", "http://127.0.0.1:4100")


@mcp.tool()
def list_slots(provider: str, date: str | None = None) -> str:
    """List available appointment slots for a provider ('doctor' or 'cpa'),
    optionally filtered to an ISO date (YYYY-MM-DD)."""
    params: dict[str, str | bool] = {"provider": provider, "available": True}
    if date:
        params["date"] = date
    try:
        with httpx.Client(timeout=15.0) as c:
            slots = c.get(f"{BOOKING_API}/slots", params=params).json()
        if not slots:
            return f"No available {provider} slots" + (f" on {date}." if date else ".")
        return "; ".join(f"{s['id']}: {s['date']} {s['time']}" for s in slots)
    except Exception as e:  # noqa: BLE001
        return f"Slot lookup failed: {e}"


@mcp.tool()
def book_slot(slot_id: str, booked_by: str = "user") -> str:
    """Book an appointment slot by id. This is irreversible — the agent must have
    obtained the user's approval before calling this."""
    try:
        with httpx.Client(timeout=15.0) as c:
            # verify it's still available
            slot = c.get(f"{BOOKING_API}/slots/{slot_id}").json()
            if not slot or slot.get("available") is False:
                return f"Slot {slot_id} is no longer available."
            c.patch(
                f"{BOOKING_API}/slots/{slot_id}",
                json={"available": False, "bookedBy": booked_by},
            )
            return f"Booked {slot['provider']} appointment {slot['date']} {slot['time']} (slot {slot_id})."
    except Exception as e:  # noqa: BLE001
        return f"Booking failed: {e}"


if __name__ == "__main__":
    mcp.run()
