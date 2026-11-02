"""Domain models (T2). Pydantic models shared across the agent.

Tasks are the legacy API's shape (system of record); everything else is
agent-owned state (memory, permissions, watches, approvals, audit).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---- Intent categories (design FR-2) ----
class Category(str, Enum):
    FINANCIAL_TRANSACTION = "financial-transaction"
    FINANCIAL_DATA = "financial-data"
    ROUTINE_TASK = "routine-task"
    GENERAL_QA = "general-qa"
    OFF_TOPIC = "off-topic"
    UNSAFE = "unsafe"


# ---- Task (mirrors the legacy Task API shape) ----
Priority = Literal["high", "medium", "low"]
TaskStatus = Literal["open", "done"]


class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    priority: Priority = "medium"
    dueDate: Optional[str] = None  # ISO date
    category: Optional[str] = None
    status: TaskStatus = "open"
    notes: Optional[str] = None
    createdAt: Optional[str] = None
    completedAt: Optional[str] = None


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Priority = "medium"
    dueDate: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


# ---- Permissions & Watches (agent-owned; design FR-18/19) ----
class PermissionType(str, Enum):
    RECURRING_BANK_FETCH = "recurring-bank-fetch"
    ROUTINE_AUTOMATION = "routine-automation"
    FILE_ACCESS = "file-access"


class Permission(BaseModel):
    id: str
    type: PermissionType
    description: str
    grantedAt: datetime
    expiresAt: Optional[datetime] = None  # None = one-time / no expiry
    revoked: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Watch(BaseModel):
    id: str
    description: str
    # matching signals (design FR-13): sender AND subject AND content
    senderMatch: Optional[str] = None
    subjectKeywords: list[str] = Field(default_factory=list)
    contentKeywords: list[str] = Field(default_factory=list)
    grantedAt: datetime
    expiresAt: datetime  # watches always expire (default 30 days)
    revoked: bool = False


# ---- Approval / Oversight (design FR-9, §4) ----
class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ApprovalRequest(BaseModel):
    id: str
    action: str  # e.g. "send-to-cpa"
    summary: str  # human-readable "what will happen"
    details: dict[str, Any] = Field(default_factory=dict)  # files, destination, source, channel
    status: ApprovalStatus = ApprovalStatus.PENDING
    createdAt: datetime


# ---- Audit (design NFR-4) ----
class AuditEvent(BaseModel):
    id: str
    at: datetime
    kind: str  # proposed | approved | denied | refused | executed | error
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
