# Legacy Task Manager — High-Level Design

**Status:** Draft for review
**Date:** 2026-09-25
**Purpose:** A **standalone, classic (non-AI) task management Web UI + API**. This is the *"before"* state for the agentic demo: users manage tasks by navigating a UI and clicking. No agents, no LLM, no automation.
**Relationship to the agentic demo:** This app owns the tasks. The agentic assistant (separate design: `/Users/sajosama/.kiro/crew/workspace/agentic-task-assistant-design.md`) is a **client of this API** — it reads, creates, and closes tasks here rather than keeping its own task store.

---

## 1. Summary

A conventional task manager: a list of tasks with title, priority, due date, status, and category; add / edit / complete / delete via buttons and forms. It is deliberately ordinary — the demo's opening line is *"this is our legacy existing task-management experience; we will turn it into an agentic AI with human oversight."* Its value is being a real, working baseline (and, later, the shared task backend the agent calls).

**Stack:** React + JavaScript (frontend) · Node.js + Express (JavaScript) REST API · local store (SQLite or JSON file).
**Explicitly no:** LLM, agent, automation, or oversight concepts. Just CRUD.

### Non-goals
- No AI/agent features (those live in the separate agentic app).
- No auth/multi-tenant complexity for the demo (single local user).
- Not production-hardened; it is a demo baseline.

---

## 2. User Stories

- **L-US-1** As a user, I want to see all my tasks with priority, due date, and status, so I know what's outstanding.
- **L-US-2** As a user, I want to add a task (title, priority, due date, category), so I can track it.
- **L-US-3** As a user, I want to edit a task's fields, so I can correct or reschedule it.
- **L-US-4** As a user, I want to mark a task complete (and reopen it), so the list reflects reality.
- **L-US-5** As a user, I want to delete a task, so I can remove mistakes.
- **L-US-6** As a user, I want to sort/filter by priority, due date, status, or category, so I can focus.

---

## 3. Requirements

### 3.1 Functional
- **L-FR-1** List tasks, with sort/filter by priority, due date, status, category.
- **L-FR-2** Create a task: `title` (required), `priority` (high/med/low), `dueDate` (optional), `category` (optional), `notes` (optional).
- **L-FR-3** Update any task field.
- **L-FR-4** Toggle status: `open` ↔ `done` (with `completedAt`).
- **L-FR-5** Delete a task.
- **L-FR-6** Persist tasks across restarts.
- **L-FR-7** Expose a clean REST API (the contract the agentic app will consume).

### 3.2 Non-Functional
- **L-NFR-1** Simple, conventional UX — intentionally "classic," no AI affordances.
- **L-NFR-2** Stable, documented REST contract (this is the integration surface for the agent).
- **L-NFR-3** Local-first; runs on localhost with one command. Deployable to AWS later.
- **L-NFR-4** CORS enabled so the separate agentic frontend/backend can call it in dev.

---

## 4. API Contract (the integration surface)

Base: `/api/tasks`

| Method | Path | Body / Query | Returns |
|---|---|---|---|
| `GET` | `/api/tasks` | `?status=&priority=&category=&sort=` | `Task[]` |
| `GET` | `/api/tasks/:id` | — | `Task` |
| `POST` | `/api/tasks` | `{title, priority?, dueDate?, category?, notes?}` | created `Task` |
| `PATCH` | `/api/tasks/:id` | any subset of fields | updated `Task` |
| `POST` | `/api/tasks/:id/complete` | — | `Task` (status=done, completedAt set) |
| `POST` | `/api/tasks/:id/reopen` | — | `Task` (status=open) |
| `DELETE` | `/api/tasks/:id` | — | `204` |
| `GET` | `/api/health` | — | `{ok:true}` |

**Task shape**
```json
{
  "id": "uuid",
  "title": "Make payment to lawn-mower",
  "priority": "high | medium | low",
  "dueDate": "2026-09-26",       // ISO date, nullable
  "category": "financial | routine | general | null",
  "status": "open | done",
  "notes": "string | null",
  "createdAt": "iso-datetime",
  "completedAt": "iso-datetime | null"
}
```

**Seed data** (same life-admin tasks as the agentic demo, so "before" and "after" show the *same* list):
1. Make payment to lawn-mower — financial, high, due tomorrow
2. Book appointment with childcare nanny for next Saturday — routine, high
3. See if electricity bill is available, pay it — financial, medium
4. Send bank statement to CPA for tax filing — financial, medium

---

## 5. High-Level Design

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│  Legacy Web UI (React + JS)  │        │  Legacy Task API (Node/Express│
│  • Task list (sort/filter)   │ HTTP   │   JavaScript)                 │
│  • Add / Edit form           │◄──────►│  • REST CRUD (§4)             │
│  • Complete / Reopen / Delete│  JSON  │  • Validation                 │
│  • Priority & due-date badges│        │  • Persistence adapter        │
└─────────────────────────────┘        └───────────────┬──────────────┘
                                                        │
                                              ┌─────────▼─────────┐
                                              │  Store (SQLite /   │
                                              │  JSON file)        │
                                              └────────────────────┘
```

- **Web UI (React + JS):** list view with priority/due-date/status badges, add/edit modal, complete/reopen/delete actions. Classic, form-and-button driven.
- **API (Node/Express, JS):** the REST contract in §4, input validation, and a persistence adapter.
- **Store:** SQLite (via better-sqlite3) or a JSON-file store — small and local.

### Deployment / layout
Standalone repo or a `/legacy` package in the monorepo, run independently on its own port (e.g. `:4000`). The agentic app points at `LEGACY_API_URL` (default `http://localhost:4000`).

---

## 6. Alternatives Considered

- **Fold tasks into the agent's own store (rejected):** would blur the "the AI plugs into your existing system" message. Keeping the legacy API as the **system of record** makes the demo's thesis literal.
- **Python API to match the agent (rejected):** the user wants the legacy app in JavaScript (React + JS) precisely to look like a typical existing web app, distinct from the Python/LangGraph agent.
- **No persistence / in-memory (rejected):** shared-state demo beats ("agent completed it, see it in the legacy UI") need durability across the two apps.

---

## 7. Open Questions

1. **Store choice:** SQLite vs. JSON file for the legacy app? (Recommend SQLite for realistic concurrent reads from both UI and agent.)
2. **Port / URL:** confirm `:4000` for the legacy API and the env var name (`LEGACY_API_URL`) the agent will use.
3. **Optimistic UI refresh:** should the legacy UI poll / use websockets so agent-made changes appear live, or refresh-on-focus? (Recommend simple polling for the demo so the "agent changed it too" beat is visible.)
4. **Category vocabulary:** align the legacy `category` values with the agent's intent categories, or keep them independent? (Recommend a light shared vocabulary: financial / routine / general.)
