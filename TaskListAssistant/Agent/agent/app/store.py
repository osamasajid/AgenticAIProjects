"""Persistence for AGENT-OWNED state only (T3).

Stores: memory (preferences/instructions), permissions, watches, audit log.
Tasks are NOT stored here — they live in the legacy Task API (T31).
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from .models import (
    ApprovalRequest,
    AuditEvent,
    Permission,
    Watch,
)

DB_PATH = os.environ.get("AGENT_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "agent.db"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Store:
    """SQLite-backed store for agent-owned state."""

    def __init__(self, path: str = DB_PATH) -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, updatedAt TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS permissions (
                id TEXT PRIMARY KEY, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS watches (
                id TEXT PRIMARY KEY, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id TEXT PRIMARY KEY, at TEXT NOT NULL, data TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    # ---- Memory ----
    def set_memory(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO memory(key,value,updatedAt) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updatedAt=excluded.updatedAt",
            (key, value, _now().isoformat()),
        )
        self.conn.commit()

    def get_memory(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM memory WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def all_memory(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT key,value FROM memory").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def delete_memory(self, key: str) -> bool:
        cur = self.conn.execute("DELETE FROM memory WHERE key=?", (key,))
        self.conn.commit()
        return cur.rowcount > 0

    # ---- Permissions ----
    def add_permission(self, perm: Permission) -> Permission:
        self.conn.execute(
            "INSERT INTO permissions(id,data) VALUES(?,?)",
            (perm.id, perm.model_dump_json()),
        )
        self.conn.commit()
        return perm

    def list_permissions(self) -> list[Permission]:
        rows = self.conn.execute("SELECT data FROM permissions").fetchall()
        return [Permission.model_validate_json(r["data"]) for r in rows]

    def revoke_permission(self, perm_id: str) -> bool:
        row = self.conn.execute("SELECT data FROM permissions WHERE id=?", (perm_id,)).fetchone()
        if not row:
            return False
        perm = Permission.model_validate_json(row["data"])
        perm.revoked = True
        self.conn.execute("UPDATE permissions SET data=? WHERE id=?", (perm.model_dump_json(), perm_id))
        self.conn.commit()
        return True

    # ---- Watches ----
    def add_watch(self, watch: Watch) -> Watch:
        self.conn.execute("INSERT INTO watches(id,data) VALUES(?,?)", (watch.id, watch.model_dump_json()))
        self.conn.commit()
        return watch

    def list_watches(self) -> list[Watch]:
        rows = self.conn.execute("SELECT data FROM watches").fetchall()
        return [Watch.model_validate_json(r["data"]) for r in rows]

    def revoke_watch(self, watch_id: str) -> bool:
        row = self.conn.execute("SELECT data FROM watches WHERE id=?", (watch_id,)).fetchone()
        if not row:
            return False
        watch = Watch.model_validate_json(row["data"])
        watch.revoked = True
        self.conn.execute("UPDATE watches SET data=? WHERE id=?", (watch.model_dump_json(), watch_id))
        self.conn.commit()
        return True

    # ---- Approvals ----
    def save_approval(self, appr: ApprovalRequest) -> ApprovalRequest:
        self.conn.execute(
            "INSERT INTO approvals(id,data) VALUES(?,?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
            (appr.id, appr.model_dump_json()),
        )
        self.conn.commit()
        return appr

    def get_approval(self, appr_id: str) -> Optional[ApprovalRequest]:
        row = self.conn.execute("SELECT data FROM approvals WHERE id=?", (appr_id,)).fetchone()
        return ApprovalRequest.model_validate_json(row["data"]) if row else None

    def save_approval_from_payload(self, appr_id: str, payload: dict) -> ApprovalRequest:
        appr = ApprovalRequest(
            id=appr_id,
            action=payload.get("action", "unknown"),
            summary=payload.get("summary", ""),
            details=payload,
            createdAt=_now(),
        )
        return self.save_approval(appr)

    # ---- Audit ----
    def log(self, kind: str, summary: str, details: Optional[dict] = None) -> AuditEvent:
        ev = AuditEvent(
            id=str(uuid.uuid4()), at=_now(), kind=kind, summary=summary, details=details or {}
        )
        self.conn.execute(
            "INSERT INTO audit(id,at,data) VALUES(?,?,?)",
            (ev.id, ev.at.isoformat(), ev.model_dump_json()),
        )
        self.conn.commit()
        return ev

    def audit_events(self) -> list[AuditEvent]:
        rows = self.conn.execute("SELECT data FROM audit ORDER BY at ASC").fetchall()
        return [AuditEvent.model_validate_json(r["data"]) for r in rows]
