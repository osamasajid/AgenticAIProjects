# Agentic Task Assistant — Implementation Plan

**Design ref:** `/Users/sajosama/.kiro/crew/workspace/agentic-task-assistant-design.md`
**Stack (split):**
- **Agent/backend:** Python + **LangGraph** (agent graph, ReAct loop, human-in-the-loop `interrupt()` for the approval gate) · **FastAPI** (HTTP + WebSocket API) · **MCP Python SDK** (connectors exposed as MCP tools)
- **Frontend:** React + TypeScript (chat UI, Approval Cards, OAuth-in-browser popup, activity-log panel) — unchanged
- **Layout:** monorepo — `/legacy` (React + JS UI **and** Node/Express JS API — the standalone legacy task app, system of record), `/agent` (Python), `/web` (React/TS agentic frontend), `/shared` (JSON schemas / OpenAPI contract shared across the boundary)
**LLM:** Amazon Bedrock (Claude) via LangChain's Bedrock binding, behind an `LLMClient` seam with a deterministic stub
**Run target:** Local (localhost) first; clean boundary to deploy to AWS later
**Date:** 2026-09-25
**Rationale for the split:** Python + a real framework puts students on the production path they'll actually use (LangGraph's human-in-the-loop interrupt maps exactly onto our detect→pause→approve→send gate). React/TS is kept for the frontend because the Approval Cards and OAuth popup — the oversight showpiece — need real UI control that all-Python UIs can't render cleanly. Python-service + JS-frontend is also how real agent products are built.

---

## Guiding principles for the build

- **Security boundaries are code, not prompts.** The CPA-destination guardrail and the reasoning↔action split (design §4.2) are enforced in the Tool Layer and unit-tested. This is the demo's whole point.
- **Every external dependency is swappable for the real thing (hard requirement).** Each connector is a Python **MCP tool/server** with two implementations selected by config: `Mock*` (default) and `Real*` (stub now, fill in later). Swapping mock Google OAuth → real Google OAuth is a **config flip + implementing the real class only** — zero changes to the LangGraph agent, the MCP tool contract, or the React UI. The MCP tool contract is the interface; a shared conformance test (pytest) runs against both impls. Applies to OAuth, Gmail, Drive, Booking, Bank Aggregator, and CPA send.
- **The demo teaches core agentic-AI concepts on the production path (Python + LangGraph).** Each concept is a first-class, labeled piece of a real framework students will use in real projects:
  - **ReAct loop** — a LangGraph graph (reason→act→observe→repeat) with explicit nodes/edges and state.
  - **Human-in-the-loop** — LangGraph's native `interrupt()` / checkpoint-resume is the oversight primitive that implements detect→pause→approve→send (not hand-rolled).
  - **Tool calling** — Bedrock Claude native tool-use, surfaced as LangGraph tools.
  - **MCP (Model Context Protocol)** — connectors exposed via the **MCP Python SDK** and consumed by the LangGraph agent, so tools are called over a standard protocol.
  - **Memory** — short-term graph state + long-term persisted preferences/permissions (T21).
  - **RAG** — retrieval over past sessions/preferences and statement content (Bedrock Titan embeddings + a small vector store; T15/T20).
- **Deterministic demo.** LLM stub + injectable events (test email, test statement) make the hero flows repeatable on stage.
- **Vertical slices.** After the foundation, each capability is built end-to-end (backend + connector + UI + test) so every checkpoint shows something runnable.

---

## Task list

Each task: **ID · name · depends-on · output · success criteria.**

### Phase L — Legacy Task Manager (built FIRST; the demo's "before")
Design ref: `/Users/sajosama/.kiro/crew/workspace/legacy-task-manager-design.md`. Standalone React + JS UI + Node/Express JS API. No AI. This is the system of record the agent later calls.

**T29. Legacy Task API (Node/Express, JavaScript)**
- Depends on: —
- Output: REST API in `/legacy/api` implementing the contract (list/get/create/update/complete/reopen/delete + health); validation; SQLite/JSON store; seeded with the 4 life-admin sample tasks; CORS for the agent + legacy UI.
- Success: all endpoints work (integration tests); seed tasks present; `GET /api/health` → `{ok:true}`; contract documented (OpenAPI in `/shared`).

**T30. Legacy Task Web UI (React + JavaScript)**
- Depends on: T29
- Output: classic task UI in `/legacy/web` — list with priority/due-date/status badges, sort/filter, add/edit modal, complete/reopen/delete; deliberately non-agentic. Polls the API so externally-made changes appear.
- Success: full CRUD works against T29 from the browser; the 4 seed tasks render; completing a task persists and re-renders.

**T31. Agent → Legacy Task API client**
- Depends on: T29, T2
- Output: a Python client in `/agent` wrapping the legacy REST contract (list/create/complete/update), mapping legacy JSON ↔ the agent's `Task` model; env `LEGACY_API_URL`. This replaces any local task store for the agent.
- Success: agent can list/create/complete tasks via the running legacy API (integration test); a task completed by the agent is visible via the legacy API (and UI); contract-conformance test passes.

### Phase 0 — Foundation

**T1. Monorepo scaffold & dev harness**
- Depends on: —
- Output: `/agent` (Python, FastAPI, LangGraph, `uv`/`poetry`, ruff+mypy), `/web` (Vite + React + TS), `/legacy` (React + JS UI + Node/Express JS API), `/shared` (OpenAPI/JSON-schema contract); root scripts to run all three apps; health-check endpoints; CORS wired for local dev.
- Success: one command starts all apps (`make dev` or `docker compose`); the agentic UI reads `GET /api/health` → `{ok:true}`; the legacy app runs on its own port; `ruff`+`mypy` clean on `/agent`, `tsc`+lint clean on `/web`, lint clean on `/legacy`.

**T2. Domain model & contract**
- Depends on: T1
- Output: Python (Pydantic) models for `Task`, `Category`, `Permission`, `Watch`, `ApprovalRequest`, `AuditEvent`, `ConnectorResult`; the API contract in `/shared` (OpenAPI) with TS types generated for the frontend; the `LLMClient` seam. Seed data for the 4 sample tasks.
- Success: Pydantic models validate; TS types generate from the shared contract and import in `/web`; seed tasks load; mypy strict passes on public interfaces.

**T3. Persistence layer (agent-owned state only)**
- Depends on: T2
- Output: local store (SQLite via SQLModel/SQLAlchemy, or JSON-file store) for **agent-owned state only** — memory, permissions/watches, audit log; **read-only config module holding the fixed CPA email + portal URL**; a LangGraph checkpointer (SQLite) so `interrupt()`/resume persists across the approval gate. **Tasks are NOT stored here** — they live in the legacy Task API (see T29/T30) and are reached via the legacy client (T31).
- Success: CRUD unit tests pass (pytest); CPA config is loaded from config and has no setter/API to change it at runtime (verified by a test); a graph can be interrupted and resumed from the checkpointer; no task table exists in the agent store (tasks are external).

### Phase 1 — Agent core & oversight spine

> **Agentic-AI concepts (Python + LangGraph, the production path):** T4–T7 build the agent as a **LangGraph graph** — the **ReAct loop** (nodes/edges + state), **tool calling** (Bedrock native tool-use) exposed as tools, connectors reached over **MCP** (Python SDK), and critically the **human-in-the-loop `interrupt()`** as the oversight primitive that implements detect→pause→approve→send. **Memory** (T21) and **RAG** (T15/T20) complete the set. These are the real, transferable skills students will use in production — not a bespoke loop.

**T4. LangGraph agent skeleton + Bedrock model + deterministic stub**
- Depends on: T2
- Output: base LangGraph `StateGraph` with the agent state schema; `ChatBedrock` (Claude) model binding reading creds from env/AWS profile; a `StubModel` returning scripted responses keyed to the demo scenarios; env flag `LLM=stub|bedrock` to switch; the graph compiled with the SQLite checkpointer from T3.
- Success: with stub, the graph runs the demo scenarios deterministically offline; with a valid AWS profile, a smoke invocation reaches Bedrock and returns a completion (documented, not required for CI).

**T5. Intent classifier node**
- Depends on: T4
- Output: a graph node mapping a message to one of six categories (design FR-2), using the model with a rules fallback for the demo phrases; routes the graph to the right subflow.
- Success: unit tests: each sample phrase → correct category, incl. off-topic and unsafe; the two in-domain refusal phrases classify correctly.

**T6. Tool/Action Layer (MCP tools) + guardrail enforcement**  ⟵ *security-critical*
- Depends on: T3
- Output: all external effects reached only via **MCP tools** the LangGraph agent calls (no direct connector calls from the model); **destination guardrail** in tool code that rejects any financial-doc send whose destination ≠ config CPA; untrusted-content rule (fetched content is data, never mutates destination/permissions).
- Success: unit tests prove (a) send to CPA passes, (b) send to *any* other address is rejected, (c) an instruction embedded in fetched content cannot change the destination. These tests are the demo's proof.

**T7. Approval & Oversight via LangGraph `interrupt()`**
- Depends on: T3
- Output: the gate implemented as a LangGraph **`interrupt()`** that pauses the graph, emits an `ApprovalRequest` to the frontend (over WebSocket), persists via the checkpointer, and **resumes** on approve or aborts on deny; emits audit events. Also covers **NFR-6 (reversibility bias)**: on failure or ambiguity (fetch fails, portal login fails, ambiguous request), the graph stops and hands control back to the human rather than proceeding.
- Success: a gated action cannot execute without a resume-with-approve; deny aborts and logs; the graph resumes correctly after a real pause (state restored from checkpointer); a simulated failure/ambiguity path stops and asks the human; transitions unit-tested.

**T8. Audit / Activity log service**
- Depends on: T3
- Output: append-only human-readable event log (action proposed, approved, denied, refused, executed) with a FastAPI endpoint for the UI.
- Success: every action in T6/T7 produces a log entry; `GET /api/audit` returns them ordered.

### Phase 2 — Mock connectors (parallelizable)

> **Swap-to-real requirement:** every connector below is a Python **MCP tool/server** with a `Mock*` impl (default) and a `Real*` impl (scaffolded/stubbed now), selected by config/env — e.g. `GOOGLE_OAUTH=mock|real`. Going live with real Google OAuth, Gmail, Drive, Plaid, or the CPA portal means implementing the `Real*` class and flipping the flag — **no changes to the LangGraph agent, the MCP tool contract, or the React UI**. Each connector ships a shared **conformance test** (pytest) its mock and real impls must both pass, plus a one-line "to go real:" note in its README (which API, which creds/scopes).

**T9. OAuth + consent connector (mock now, real-swappable)**
- Depends on: T6
- Output: simulated "Sign in with Google → scopes → Allow" flow returning a scoped one-time token; drives a browser popup/modal.
- Success: completing consent yields a token gated to the requested scope; declining yields no token; both logged.

**T10. Mock Gmail connector (inbox + watch + inject)**
- Depends on: T6
- Output: fake inbox; a **watch** registration; an **"inject test email"** control; detection helper matching sender AND subject AND parsed content (design FR-13).
- Success: injecting a matching email fires the watch; a bank email that isn't a statement does NOT match; results logged.

**T11. Mock Drive connector**
- Depends on: T6
- Output: fake file list incl. statement PDFs; fetch-by-id under a valid token.
- Success: fetch works only with a valid scoped token; returns the sample statements.

**T12. Mock Bank Aggregator connector (Plaid-style, credential-less)**
- Depends on: T6, T9
- Output: OAuth-in-browser link flow (agent never sees username/password), scoped **read-only** token, `listStatements()` / `getStatement()` API. No payment capability exists on this connector.
- Success: linking returns a read-only token; statement list/fetch works; connector exposes **no** payment method (verified by test/type); logged.

**T13. Mock CPA Send connector**
- Depends on: T6
- Output: send-via-email and submit-to-portal methods that **only** accept the config CPA destination (enforcement lives in T6; this is the egress).
- Success: send to CPA succeeds and is logged; connector refuses/ignores any caller-supplied alternate destination.

**T14. Mock Booking connector**
- Depends on: T6
- Output: simulated appointment booking under a granted permission; returns a confirmation.
- Success: booking runs only with permission; returns confirmation; logged.

### Phase 3 — Capability flows (vertical slices)

**T15. Prioritization + explanation + override**
- Depends on: T4, T5, T2, T31
- Output: ranker combining metadata + memory/history + LLM reasoning; produces ordered list **with an explanation**; user override API (design FR-3/4). Tasks are read from the **legacy API via T31**; completing/reprioritizing writes back through T31.
- Success: sample tasks (from the legacy API) return a ranked list with per-item rationale; user override persists and re-orders; a task completed here shows as done in the legacy UI.

**T16. Financial-transaction (advise-only) flow**
- Depends on: T5, T8
- Output: for a payment task, agent gives instructions + opens link; **never** initiates payment; "is the bill available?" handled as read-only.
- Success: no code path can trigger a payment; "pay it for me" → in-domain refusal; check-availability works read-only.

**T17. Hero flow 1 — Send statements to CPA (one-time)**
- Depends on: T9, T11, T13, T7
- Output: end-to-end: request → mock OAuth → fetch from Drive → **Approval Card** → send to fixed CPA → report; access revoked after.
- Success: full happy path runs; "send to my brother" is refused; deny aborts; all steps logged.

**T18. Hero flow 2 — Email-watch → detect → pause → approve → send**
- Depends on: T10, T13, T7, and permissions (T21)
- Output: register 30-day watch; on injected email, detect (sender+subject+content), pause, raise Approval Card showing **why it matched**, send on approve.
- Success: matching email triggers gated send; non-statement bank email ignored; watch expiry honored; logged.

**T19. Hero flow 3 — Direct bank fetch (credential-less) → approve → send + recurring option**
- Depends on: T12, T13, T7, T21
- Output: source choice → OAuth-in-browser → read-only token → list/fetch statement → Approval Card → send to CPA → offer standing recurring-fetch permission (approve-gated, 30-day default).
- Success: full path runs; agent never handles bank credentials; recurring permission is created, visible, and revocable; logged.

**T20. General Q&A + refusals**
- Depends on: T5, T15, T22
- Output: conversational answers ("what should I focus on today?") built on memory; off-topic + unsafe refusals; in-domain refusals surfaced with plain reasons.
- Success: Q&A uses memory/history; sports/foreign-policy declined; profane/illegal refused; refusal reasons shown.

### Phase 4 — Memory, permissions UI, polish

**T21. Persistent memory + permission/watch registry**
- Depends on: T3, T7
- Output: persistence + APIs for preferences, standing permissions, active watches, with grant-time/expiry.
- Success: permissions/watches survive restart; expiry enforced; audited.

**T22. Chat UI shell + Approval Card + OAuth popup components**
- Depends on: T1, T7
- Output: chat interface; reusable **Approval Card** component; OAuth consent popup; loading/deny states. (Built early enough to back T17–T20.)
- Success: chat renders; Approval Card shows file/dest/source/channel + Approve/Deny wired to T7; OAuth popup completes the consent flow.

**T23. Permissions & Memory dashboard (view + revoke)**
- Depends on: T21, T22
- Output: UI listing remembered items, permissions, watches; revoke actions (design FR-19).
- Success: user sees all standing items and can revoke each; revoke reflected in backend + audit.

**T24. Activity log UI**
- Depends on: T8, T22
- Output: user-visible audit trail panel.
- Success: every action/approval/refusal appears live in the panel.

**T25. Demo script, seed reset, README**
- Depends on: T17, T18, T19, T20, T23, T24
- Output: a "run the demo" walkthrough, a one-click seed/reset, and setup/run docs (incl. Bedrock env config + stub toggle).
- Success: a fresh clone runs the **three hero flows (T17–T19) plus the Q&A/refusal flow (T20)** from the script with the stub LLM; reset returns to a clean state.

### Phase 5 — (deferred, not now) AWS deploy
**T26. Deploy boundary to AWS** — depends on T25. Deferred until you're happy with the local demo.

---

## Dependency graph (text)

```
Legacy app:  T29 → T30 ;  T29 + T2 → T31
T1 → T2 → {T3, T4}
T3 → {T6, T7, T8, T21}
T4 → {T5, T15}
T6 → {T9, T10, T11, T12, T13, T14}   (connectors)
T9 → T12
T7 → {T17, T18, T19, T22}
T22 → {T23, T24}
Capability slices:
  T17 ← {T9, T11, T13, T7, T22}
  T18 ← {T10, T13, T7, T21}
  T19 ← {T12, T13, T7, T21}
  T20 ← {T5, T15, T22}
  T15 ← {T4, T5, T2, T31}
  T16 ← {T5, T8}
T25 ← all hero flows + T23 + T24
```

---

## What can run in parallel

Sub-agents/streams that touch different files and have their deps met can run together.

- **Wave 0 (legacy app, parallelizable + independent):** T29 → T30 (legacy API then its UI). Fully independent of the agent stack — can be built by a separate stream in parallel with Wave A. **T31 (agent's legacy client)** follows once T29 + T2 exist.
- **Wave A (foundation, mostly serial):** T1 → T2 → T3 & T4 (T3 and T4 parallel once T2 is done).
- **Wave B (spine + UI shell, parallel after Phase 0):** T5, T6, T7, T8, T22 — largely independent modules (classifier, tool layer, oversight, audit, UI shell). *These form Checkpoint 1.*
- **Wave C (connectors, highly parallel after T6):** T9, T10, T11, T13, T14 in parallel; **T12 after T9**. Each is an isolated connector module + its tests.
- **Wave D (capability slices, parallel after their connectors):** T15 & T16 can start once T4/T5/T8 exist; T17, T18, T19 run in parallel once their respective connectors + T7 + T22 are ready; T21 alongside.
- **Wave E (UX + docs):** T23, T24 parallel after T22/T21/T8; then T25 last (serial, integrates everything).

Rule of thumb: connectors (Wave C) and capability slices (Wave D) are the big parallel wins — they're isolated modules. The spine (T6/T7) is on the critical path and gates almost everything, so it's built first and carefully.

---

## Checkpoints (you review before I continue)

**✅ Checkpoint 0 — Legacy app runs (the demo's "before") (after Wave 0)**
You see: the standalone Legacy Task Manager (React + JS) running on its own port with the 4 seed life-admin tasks; full manual CRUD (add / edit / complete / delete) against the legacy API; the REST contract documented. This is the baseline the demo opens on — *"here's our existing task app; now we'll add an agentic AI over it."*
Why here: locks the system-of-record contract before the agent integrates against it (T31), and gives you the "before" state to sign off on.

**✅ Checkpoint 1 — Foundation & oversight spine (after Wave A + B)**
You see: app runs locally; intent classifier categorizes the demo phrases; the **guardrail unit tests pass** (send-to-CPA allowed, send-elsewhere rejected, injected-instruction can't change destination); Approval Card renders and Approve/Deny drives the oversight service; audit log records events.
Why here: this proves the security model *before* we build features on top of it. If the boundary is wrong, we fix it now, not at the end.

**✅ Checkpoint 2 — Mock connectors (after Wave C)**
You see: mock OAuth consent popup works; Gmail inject+watch+detect works; Drive fetch under token; Bank Aggregator OAuth-in-browser returns a read-only token with **no payment method**; CPA send only accepts the fixed destination.
Why here: confirms every external boundary behaves before wiring the hero flows.

**✅ Checkpoint 3 — Hero flow 1 + prioritization (after first capability slices)**
You see: "send my statements to my CPA" runs end-to-end with the Approval Card and the destination refusal; task prioritization with visible reasoning + override.
Why here: the first full vertical slice — validates the whole stack top-to-bottom on one scenario before replicating the pattern.

**✅ Checkpoint 4 — All hero flows + memory/permissions (after Wave D)**
You see: email-watch flow, direct-bank-fetch flow (incl. recurring permission), general Q&A + all refusal types, and the Permissions & Memory dashboard with revoke.
Why here: everything functional is now demonstrable; remaining work is polish/docs.

**✅ Checkpoint 5 — Demo-ready (after Wave E)**
You see: activity-log UI, one-click reset, demo script; a clean run of the three hero flows (T17–T19) plus the Q&A/refusal flow from a fresh state.
Then: decide whether to proceed to AWS deploy (T26).

---

## How I'll execute

I'll build Wave A serially myself, then fan out Waves B–D to parallel sub-agents where tasks are genuinely independent (connectors and capability slices are the natural split), integrating and running tests at each checkpoint. I'll **stop at each checkpoint and show you what's built** before continuing.

---

## Traceability matrix (design → tasks)

Every design requirement, component, and flow maps to at least one task. Kept here so the two docs stay verifiably in sync.

**Functional requirements**

| FR | Covered by |
|---|---|
| FR-1 conversational UI | T22 |
| FR-2 six-category classification | T5 |
| FR-3 prioritization (metadata+history+reasoning) | T15 |
| FR-4 explanation + override | T15 |
| FR-5 advise + open link | T16 |
| FR-6 never initiate payment | T16 (+ guardrail intent in T6) |
| FR-7 check-availability read-only | T16 |
| FR-8 scoped one-time file access | T9, T17 |
| FR-9 Approval Card before send | T7, T22 |
| FR-10 fixed CPA destination | T6, T13 |
| FR-11 refuse non-CPA destination | T6, T13, T17 |
| FR-12 standing watch | T10, T18, T21 |
| FR-13 sender+subject+content match | T10 |
| FR-14 pause + why-matched card | T7, T18 |
| FR-15 30-day watch expiry | T21, T18 |
| FR-16 false-positive visible | T18, T22 |
| FR-17 routine automation under permission | T14, T21 |
| FR-18 persist prefs/permissions/watches | T21 |
| FR-19 view/revoke surface | T23 |
| FR-20 off-topic refusal | T5, T20 |
| FR-21 unsafe refusal | T5, T20 |
| FR-22 three source options | T19 (+ T10, T11) |
| FR-23 credential-less bank OAuth | T12 |
| FR-24 read-only statement pull | T12 |
| FR-25 approve before CPA submit | T7, T19 |
| FR-26 recurring-fetch permission | T19, T21 |
| FR-27 read-only scoped token, mocked | T12 |
| FR-28 legacy Task API = system of record | T29, T31 (+ T15 uses it) |

**Non-functional requirements**

| NFR | Covered by |
|---|---|
| NFR-1 least privilege / human gate | T6, T7, T21 |
| NFR-2 code-enforced guardrail | T6 |
| NFR-3 prompt-injection resistance | T6 |
| NFR-4 auditability | T8, T24 |
| NFR-5 transparency (explain before act) | T7, T15, T22 |
| NFR-6 reversibility bias (stop on failure) | T7 |
| NFR-7 mock fidelity + swappable | T9–T14 (swap-to-real note) |
| NFR-8 privacy (CPA-only egress) | T6, T13 |
| NFR-9 deterministic demo | T4 (stub), T10 (inject), T25 |

**Components (design §4.1) & hero flows (§4.3–4.5)**

| Design element | Covered by |
|---|---|
| Agent Core / ReAct loop | T4 |
| Intent Classifier | T5 |
| Prioritizer | T15 |
| Approval & Oversight Service | T7 |
| Tool / Action Layer | T6 |
| Audit / Activity Log | T8, T24 |
| Mock OAuth+consent | T9 |
| Mock Gmail (inbox/watch/inject) | T10 |
| Mock Drive | T11 |
| Mock Bank Aggregator | T12 |
| Mock CPA Send | T13 |
| Mock Booking | T14 |
| Persistent stores (tasks/memory/perms/config) | T3 (memory/perms/config) · T29/T31 (tasks — external) |
| Legacy Task API (system of record) | T29 |
| Legacy Task Web UI (the "before") | T30 |
| Agent → Legacy Task API client | T31 |
| Chat UI / Approval Card / OAuth popup | T22 |
| Permissions & Memory dashboard | T23 |
| Hero flow 1 (send to CPA) | T17 |
| Hero flow 2 (email-watch) | T18 |
| Hero flow 3 (direct bank fetch) | T19 |
| Refusals (§4.6) | T20 |

**User stories:** US-1..3 → T15; US-4..6 → T16; US-7..9 → T17; US-10..13 → T18; US-14 → T14; US-15..16 → T21/T23; US-17..19 → T20; US-20..24 → T19. All covered.
