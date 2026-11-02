# Agentic Task Assistant — High-Level Design

**Status:** Draft for review
**Author:** (owner) with Kiro
**Date:** 2026-09-25
**Purpose:** Reference design for a **demo** AI-agent chatbot that shows how to build an *autonomous agent with human oversight*.

---

## 1. Summary

### 1.1 What this is
A conversational assistant that replaces the classical "list of tasks → click to complete" UI for personal life-admin tasks (bills, appointments, sending documents). Instead of navigating a UI, the user talks to an agent that **prioritizes, advises, and — where permitted — acts on their behalf**, always inside explicit oversight boundaries.

**Relationship to the legacy app (system of record):** Tasks live in the **standalone Legacy Task Manager** (separate design: `/Users/sajosama/.kiro/crew/workspace/legacy-task-manager-design.md`, React + JS + Node/Express). This agentic assistant does **not** own a task store — it **calls the legacy Task REST API** to list, create, complete, and update tasks. The demo's arc is: *"here is our existing legacy task app; now we add an agentic AI over the same API and data, with human oversight."* Both interfaces share the same tasks, so an agent action shows up in the legacy UI and vice versa.

### 1.2 Why it exists (the teaching goal)
This is a **teaching demo**. The product it manages (a to-do list) is secondary. The real subject is the **human-oversight model for autonomous agents**: how an agent can be genuinely useful and take real actions, while keeping the human in control of anything with meaningful blast radius.

The design is organized around a **trust ladder** — every action is classified by how reversible and how consequential it is, and the level of human oversight scales to match:

| Category | Agent behavior | Oversight level |
|---|---|---|
| Financial **transactions** (pay a bill) | Advise only. Open the link. **Never initiates payment.** | Human does the action entirely |
| Financial **data movement** (send statements to CPA) | Agent acts, but **detect → pause → human approves → send**, to a **fixed destination that cannot be overridden**. | Human approves each irreversible send |
| **Routine tasks** (book appointment) | Agent automates under a **standing permission**. | Human grants permission once; can revoke |
| **General Q&A** (what should I do today?) | Conversational; reads state and memory. | No external action |
| **Off-topic / unsafe** (sports, profanity, illegal) | Refuse. | N/A |

### 1.3 Hero scenarios (what the demo shows)
1. **"Send my last 3 months of statements to my CPA."** — Demonstrates scoped one-time data access (mock OAuth), a mandatory **preview-and-approve** gate, and a **hard destination guardrail** that refuses any target other than the pre-configured CPA.
2. **"Watch my email for the bank statement; when it arrives, send it to my CPA."** — Demonstrates **proactive, event-triggered autonomy** with a **standing 30-day permission**, background detection with **false-positive protection** (sender + subject + file-content parsing), and the same **detect → pause → approve → send** gate applied later, when the user may not be present.
3. **"Fetch my statement directly from my bank and send it to my CPA."** — Demonstrates **credential-less delegated access**: the bank's OAuth page opens in the browser, the user authenticates there, and the agent **never sees the bank username/password** — it receives only a scoped, read-only token via an aggregator (Plaid/Finicity/MX). The agent pulls available statements by API, gets approval to submit to the CPA, and can be granted a standing (approve-gated) permission to fetch next month's statement.

### 1.4 Non-goals
- Not a production financial tool. No real money movement, ever.
- No real integrations in the demo: Gmail, Google Drive, OAuth, email arrival, and the CPA portal are all **mocked** (the *experience* is faithful; the backends are simulated).
- Not a general-purpose assistant — off-topic requests are refused by design.

---

## 2. User Stories

### Prioritization & guidance
- **US-1** As a busy user, I want the agent to tell me what to do first, so I don't have to weigh urgency myself.
- **US-2** As a user, I want the agent to *explain why* it ranked tasks the way it did (metadata + my history + its reasoning), so I can trust or correct it.
- **US-3** As a user, I want to override the agent's priority ranking, so the final call is mine.

### Financial transactions (advise-only)
- **US-4** As a user, when a bill is due, I want the agent to tell me how to pay it and open the payment link, so I can complete payment myself.
- **US-5** As a user, I want the agent to **refuse to initiate any payment**, even if I ask it to, so I know it can never move my money.
- **US-6** As a user, I want the agent to check *whether* a bill is available (read-only) separately from paying it, so "is it here yet?" doesn't imply "pay it."

### Financial data movement (approve-gated)
- **US-7** As a user, I want to grant the agent **one-time, scoped** access to my files (via a consent screen), so it can fetch documents without standing access.
- **US-8** As a user, before anything is sent, I want to see **exactly what file(s), to whom, and from where**, and click Approve or Deny, so nothing leaves without my say-so.
- **US-9** As a user, I want the agent to be **physically unable to send my financial documents anywhere except my pre-configured CPA**, even if a message (mine or a malicious one) tells it to send elsewhere.

### Proactive email-watch (standing autonomy + gate)
- **US-10** As a user, I want to tell the agent "watch for my bank statement and send it to my CPA," so I don't have to remember to do it.
- **US-11** As a user, I want the agent to distinguish the *actual statement* from other emails from my bank (using sender + subject + file content), so it doesn't grab the wrong thing.
- **US-12** As a user, when the agent detects the statement, I want it to **pause and ask me to approve** before sending, so the irreversible action still crosses a human gate.
- **US-13** As a user, I want the watch to **expire after 30 days by default** and require me to re-extend it, so no permission runs forever silently.

### Direct bank fetch via secure OAuth (credential-less)
- **US-20** As a user, I want to choose to **securely fetch my statement directly from my bank** (as an alternative to email-watch or manual upload), so I get the authoritative document from the source.
- **US-21** As a user, I want the bank's **OAuth page to open in my browser** and to complete authentication there myself, so the **agent never sees my bank username or password**.
- **US-22** As a user, once authenticated, I want the agent to **pull my available statements from the bank via API** (using an aggregator like Plaid / Finicity / MX), so I don't hunt for the file.
- **US-23** As a user, I want the agent to **get my confirmation before submitting** the fetched statement(s) to my CPA, so the same approve-gate applies as every other send.
- **US-24** As a user, I want to optionally grant the agent a **standing permission to fetch next month's statement automatically** (still approve-gated before it goes to the CPA), so recurring filing is handled.

### Routine automation
- **US-14** As a user, I want to let the agent automate a routine task (e.g., book an appointment) under a permission I grant, so I don't do it manually.

### Memory & permissions control
- **US-15** As a user, I want the agent to remember my past instructions and preferences across sessions, so it gets more useful over time.
- **US-16** As a user, I want to **see and revoke** everything the agent remembers and every permission/watch it holds, so I stay in control of what it can do.

### Refusals
- **US-17** As a user, I want off-topic questions (sports, foreign policy) politely declined, so the agent stays in its lane.
- **US-18** As a user, I want profane / illegal requests refused, so the agent is safe.
- **US-19** As a user, I want *in-domain* refusals too ("pay it for me" / "send to my brother") clearly explained, so I understand the guardrails.

---

## 3. Requirements

### 3.1 Functional Requirements

**Conversation & guidance**
- **FR-1** The agent SHALL present tasks conversationally (no click-through UI required for core flows).
- **FR-2** The agent SHALL classify every user request into exactly one category: *financial-transaction, financial-data, routine-task, general-QA, off-topic, unsafe*.
- **FR-3** The agent SHALL rank pending tasks using (a) task metadata (due date, user-set priority), (b) the user's past history/preferences, and (c) its own reasoning about urgency vs. importance vs. external scarcity.
- **FR-4** The agent SHALL show a human-readable **explanation** of its ranking and SHALL allow the user to override it.

**Task system of record (legacy API integration)**
- **FR-28** The agent SHALL use the **Legacy Task Manager REST API** as the sole system of record for tasks — listing, creating, completing, reopening, and updating tasks via that API rather than any local task store. Task changes made by the agent SHALL be visible in the legacy Web UI, and changes in the legacy UI SHALL be visible to the agent.

**Financial transactions (advise-only)**
- **FR-5** For any payment task, the agent SHALL provide instructions and, where available, open the payment link.
- **FR-6** The agent SHALL NEVER initiate, authorize, or complete a payment under any circumstances. This is a hard constraint, not a preference.
- **FR-7** The agent SHALL treat "check if a bill is available" as a read-only action, distinct from payment.

**Financial data movement**
- **FR-8** The agent SHALL obtain **scoped, one-time** access to file sources (Gmail / Drive) via a consent flow before fetching any file.
- **FR-9** Before sending any financial document, the agent SHALL present an **Approval Card** stating: the exact file(s), the destination, the source, and the channel (email or portal), and SHALL send only on explicit Approve.
- **FR-10** The agent SHALL send financial documents **only** to the pre-configured CPA email address or CPA web-portal URL. This destination is fixed configuration and SHALL NOT be overridable by any user message, remembered instruction, or fetched content.
- **FR-11** Any attempt to redirect a financial document to a non-CPA destination SHALL be refused and surfaced as an in-domain refusal.

**Proactive email-watch**
- **FR-12** The agent SHALL support a **standing "watch" instruction**: monitor for a specific email and act when detected.
- **FR-13** The watch SHALL match on **sender (from) AND subject keywords AND parsed file/text content** — sender alone is insufficient (not every bank email is a statement).
- **FR-14** On detection, the agent SHALL **pause** and raise an Approval Card showing what it found *and why it believes this is the statement* (matched sender/subject/content signals), before any send.
- **FR-15** A watch SHALL have a **default lifespan of 30 days**, after which it expires; extension requires an explicit user action in a later session.
- **FR-16** Detection false-positives (wrong email, suspicious/phishing look-alike) SHALL be visible to the user in the Approval Card so they can Deny.

**Direct bank fetch via secure OAuth (credential-less)**
- **FR-22** The agent SHALL offer **three source options** for obtaining a statement: (a) direct bank fetch via OAuth, (b) email-watch, (c) manual upload — with direct bank fetch as the authoritative option.
- **FR-23** Direct bank fetch SHALL use a **financial data aggregator (e.g., Plaid / Finicity / MX)**. The bank's **OAuth authorization page SHALL open in the user's browser**, and the user SHALL complete authentication there. The agent SHALL NEVER receive, store, or handle the user's bank username or password — only a scoped access token issued by the aggregator.
- **FR-24** Using the aggregator API and the scoped token, the agent SHALL list/pull the user's **available statements** (read-only; statement retrieval only — no account modification or payment capability).
- **FR-25** Before submitting any fetched statement to the CPA, the agent SHALL raise the standard **Approval Card** (FR-9) and send only on explicit Approve, to the fixed CPA destination (FR-10).
- **FR-26** The agent SHALL offer an **optional standing permission** to auto-fetch the next statement (e.g., next month), subject to the same 30-day-default expiry model (FR-15) and the same approve-before-send gate (FR-25). The standing permission SHALL be visible and revocable via the Permissions & Memory surface (FR-19).
- **FR-27** The aggregator token SHALL be scoped to **statement read access only**; the demo SHALL mock the OAuth/aggregator experience faithfully (open-in-browser consent, scope display) without real bank credentials.

**Routine automation**
- **FR-17** The agent SHALL automate routine tasks (e.g., booking) only under a user-granted permission, and SHALL report the outcome.

**Memory & permissions**
- **FR-18** The agent SHALL persist user preferences, past instructions, standing permissions, and active watches across sessions.
- **FR-19** The agent SHALL provide a **Permissions & Memory** surface where the user can view and revoke each remembered item, permission, and watch.

**Refusals**
- **FR-20** The agent SHALL refuse off-topic requests, briefly redirecting to its purpose.
- **FR-21** The agent SHALL refuse profane, illegal, or otherwise unsafe requests.

### 3.2 Non-Functional Requirements

- **NFR-1 (Safety / least privilege):** No action with irreversible or financial blast radius executes without a human gate. Permissions are scoped and time-bounded by default.
- **NFR-2 (Guardrail integrity):** The CPA destination guardrail SHALL be enforced in code at the tool/connector boundary, not by prompt instruction alone — so it holds even if the LLM is manipulated.
- **NFR-3 (Prompt-injection resistance):** Content fetched from emails/files is **untrusted data**; instructions embedded in it SHALL NOT alter agent behavior, destinations, or permissions.
- **NFR-4 (Auditability):** Every action, approval, denial, and refusal SHALL be logged in a human-readable activity trail — essential for a demo that's *about* oversight.
- **NFR-5 (Transparency):** The agent SHALL always be able to explain *why* it is proposing an action and *what* it will do before doing it.
- **NFR-6 (Reversibility bias):** When uncertain or on failure, the agent SHALL stop and hand control to the human rather than proceed.
- **NFR-7 (Mock fidelity):** Mocked integrations (OAuth, Gmail, Drive, email arrival, CPA portal) SHALL faithfully reproduce the *consent and action experience*; connector boundaries SHALL be clean enough to swap in real APIs later.
- **NFR-8 (Privacy):** Financial documents SHALL never be sent to any endpoint other than the fixed CPA destination; no third-party/off-domain calls with user data.
- **NFR-9 (Demo reliability):** Because integrations are mocked, hero scenarios SHALL be deterministic and repeatable (e.g., an "inject test email" control).

---

## 4. High-Level Design

### 4.1 Components

```
┌───────────────────────────────────────────────────────────────────────┐
│                            User (Chat UI)                               │
│   Conversation  ·  Approval Cards  ·  Permissions & Memory dashboard    │
└───────────────┬───────────────────────────────────────┬────────────────┘
                │                                         │
        ┌───────▼─────────┐                     ┌─────────▼──────────┐
        │  Orchestrator/   │                     │  Approval &        │
        │  Agent Core      │◄───── requests ────►│  Oversight Service │
        │  (LLM reasoning) │      approval        │  (gates, cards)    │
        └───┬─────┬─────┬──┘                     └─────────┬──────────┘
            │     │     │                                   │
     ┌──────▼┐ ┌──▼───┐ │                          ┌────────▼─────────┐
     │Intent │ │Prior-│ │                          │  Audit / Activity│
     │Classi-│ │itizer│ │                          │  Log             │
     │fier   │ └──────┘ │                          └──────────────────┘
     └───────┘          │
                 ┌───────▼────────────────────────────────────────┐
                 │            Tool / Action Layer                   │
                 │  (every external effect goes through here)       │
                 └─┬────────┬────────┬────────┬────────┬────────┬──┘
                   │        │        │        │        │        │
            ┌──────▼─┐ ┌────▼───┐ ┌──▼───┐ ┌──▼────┐ ┌─▼──────┐ ┌▼─────────┐
            │ Mock   │ │ Mock   │ │ Mock │ │ Mock  │ │ Mock   │ │ CPA Send │
            │ OAuth +│ │ Gmail  │ │ Drive│ │Booking│ │ Bank   │ │ Connector│
            │ Consent│ │(inbox +│ │(files│ │       │ │Aggre-  │ │(FIXED    │
            │        │ │ watch) │ │ )    │ │       │ │gator   │ │ dest     │
            │        │ │        │ │      │ │       │ │Plaid/  │ │ guardrail│
            │        │ │        │ │      │ │       │ │Finicity│ │ )        │
            │        │ │        │ │      │ │       │ │read-   │ │          │
            │        │ │        │ │      │ │       │ │only)   │ │          │
            └────────┘ └────────┘ └──────┘ └───────┘ └────────┘ └──────────┘

        ┌────────────────────────────────────────────────────────────┐
        │  Data                                                       │
        │  • Tasks → EXTERNAL: Legacy Task API (system of record)     │
        │            (agent calls REST: list/create/complete/update)  │
        │  • Memory store (preferences, past instructions)            │
        │  • Permission/Watch registry (scope, grant time, expiry)    │
        │  • Config (fixed CPA email + portal URL — read-only)        │
        └────────────────────────────────────────────────────────────┘
```

**Component responsibilities**

- **Agent Core (Orchestrator):** LLM-driven reasoning. Interprets requests, plans, calls the intent classifier and prioritizer, and — critically — **cannot cause an external effect directly**; it can only *request* actions through the Tool Layer, which enforces gates.
- **Intent Classifier:** Maps each request to one of the six categories (FR-2). Drives which oversight path applies.
- **Prioritizer:** Ranks tasks from metadata + history + reasoning (FR-3) and produces an explanation (FR-4).
- **Approval & Oversight Service:** Owns the **Approval Card** lifecycle (raise → await human → approve/deny). No gated action proceeds without an Approve from here.
- **Tool / Action Layer:** The single choke point for all external effects. Enforces guardrails **in code** (NFR-2), including the fixed CPA destination.
- **Mock connectors:** OAuth+consent, Gmail (inbox + background watch + "inject test email" control), Drive, Booking, the **Bank Aggregator connector** (Plaid/Finicity/MX-style, credential-less: OAuth-in-browser, read-only statement retrieval, no bank username/password ever reaches the agent), and the **CPA Send Connector** (the only egress for financial docs; destination is read-only config).
- **Legacy Task API client (real, not mocked):** the agent's task read/write goes through the **Legacy Task Manager REST API** (the system of record). List/create/complete/update tasks are HTTP calls to that service — the agent does not keep its own task store.
- **Audit/Activity Log:** Human-readable trail of every decision (NFR-4).
- **Persistent stores:** **Tasks live in the Legacy Task API (external system of record — not owned here).** The agent owns only: memory store (preferences, past instructions), permission/watch registry, audit log, and read-only config for the CPA destination.

### 4.2 Trust boundaries (what the demo is really teaching)

1. **Reasoning ↔ Action boundary.** The LLM reasons and *proposes*; it never *executes*. All effects cross the Tool Layer, which is deterministic code. → A manipulated LLM still can't bypass a guardrail.
2. **Untrusted-data boundary.** Email/file *content* is data, never instructions (NFR-3). Parsing it for detection is allowed; obeying instructions inside it is not.
3. **Fixed-destination boundary.** The CPA email/URL lives in read-only config, enforced at the CPA Send Connector. No message, memory, or fetched content can change it (FR-10, NFR-2).
4. **Human-gate boundary.** Irreversible/financial-data actions require an Approve from the Oversight Service (FR-9, FR-14).
5. **Time/scope boundary.** Permissions are scoped and expire (watches: 30 days; file access: one-time) (FR-8, FR-15).

> **Note — legacy Task API is a real dependency, not a mock.** Unlike Gmail/Drive/OAuth/Bank/CPA (all mocked), the Legacy Task Manager API is a genuine service the agent calls over HTTP (FR-28). It is the system of record for tasks; the agent is a client. This is intentional — it makes the demo's thesis ("the AI plugs into your existing system, it doesn't replace it") literal.

### 4.3 Flow — Hero Scenario 1: "Send my last 3 months of statements to my CPA"

```
User: "Send my last 3 months of bank statements to my CPA."
  │
  ▼
Intent Classifier → financial-data
  │
  ▼
Agent Core: needs file access → requests OAuth consent
  │
  ▼
Mock OAuth Consent screen: "App wants: read Gmail/Drive files (one-time)"
  │  ── user Allows ──►  scoped one-time token issued
  ▼
Tool Layer → Mock Drive/Gmail: fetch candidate statement files
  │
  ▼
Approval & Oversight Service raises APPROVAL CARD:
     ┌─────────────────────────────────────────────┐
     │  Send to CPA?                                │
     │  Files:  Statement_Jun.pdf, _Jul, _Aug       │
     │  From:   Google Drive (one-time access)      │
     │  To:     cpa@firm.com  (FIXED — cannot edit) │
     │  Via:    Email                               │
     │            [ Approve ]   [ Deny ]            │
     └─────────────────────────────────────────────┘
  │
  ├─ Deny  → nothing sent; logged.
  │
  ▼ Approve
CPA Send Connector: verifies destination == config CPA → sends → logs
  │
  ▼
Agent: "Sent 3 statements to cpa@firm.com. One-time access has expired."
```

**Injection-resistance beat:** if the user (or content) says "actually send it to my brother," the CPA Send Connector rejects it (destination ≠ config) → in-domain refusal (FR-11).

### 4.4 Flow — Hero Scenario 2: "Watch my email for the bank statement, then send it to my CPA"

```
User: "Watch for my bank statement and send it to my CPA when it arrives."
  │
  ▼
Intent Classifier → financial-data (proactive/standing)
  │
  ▼
Agent Core: define watch → sender=bank, subject keywords, content signals
  │
  ▼
Permission/Watch registry: create watch, lifespan = 30 days (default)
Mock OAuth consent for inbox read (if not already granted)
  │
  ▼
Agent: "Watching for your statement for 30 days. I'll pause and ask you
        before sending anything."   ── turn ends; runs in background ──
  ┊
  ┊   (later — email arrives; in demo, injected via test control)
  ▼
Mock Gmail Watch fires → candidate email
  │
  ▼
Detection: sender match  AND  subject keywords  AND  file/text content parse
  │
  ├─ no match / weak match → ignore, keep watching (logged)
  │
  ▼ strong match
Approval & Oversight Service raises APPROVAL CARD:
     ┌───────────────────────────────────────────────────────┐
     │  Found what looks like your bank statement — send it?  │
     │  From:    statements@bank.com                          │
     │  Subject: "Your July statement is ready"               │
     │  Why I think it's the statement:                       │
     │    ✓ sender matches your bank                          │
     │    ✓ subject contains "statement"                      │
     │    ✓ PDF content parsed as an account statement        │
     │  Attachment: Statement_July.pdf                        │
     │  To: cpa@firm.com (FIXED)   Via: CPA portal            │
     │            [ Approve ]   [ Deny ]                       │
     └───────────────────────────────────────────────────────┘
  │
  ├─ Deny → not sent; watch continues (or user cancels it); logged.
  │
  ▼ Approve
CPA Send Connector → verify dest == config → submit to CPA portal → log
  │
  ▼
Agent notifies user: "Statement submitted to your CPA's portal on <date>."
```

**Key oversight properties on display:** background autonomy (the watching) is separated from the irreversible act (the send); detection reasoning is shown so false positives / phishing look-alikes can be caught by the human; the permission self-expires.

### 4.5 Flow — Hero Scenario 3: "Fetch my statement directly from my bank, then send it to my CPA"

```
User: "Get my latest statement straight from my bank and send it to my CPA."
  │
  ▼
Intent Classifier → financial-data (direct bank fetch)
  │
  ▼
Agent offers source choice → user picks "Fetch from bank (secure)"
  │
  ▼
Bank Aggregator connector (Plaid/Finicity/MX) starts OAuth link flow
  │
  ▼
Bank's OAuth page OPENS IN BROWSER  ── user logs in AT THE BANK ──
     (agent never sees username/password; bank returns a scoped token
      for statement READ ONLY — no payment, no account changes)
  │
  ▼
Aggregator issues scoped read-only token → agent lists available statements
  │
  ▼
Approval & Oversight Service raises APPROVAL CARD:
     ┌───────────────────────────────────────────────────────┐
     │  Send this bank-fetched statement to your CPA?         │
     │  Source:  Chase • via Plaid (read-only token)          │
     │  File:    Statement_2026-08.pdf                        │
     │  To:      cpa@firm.com  (FIXED — cannot edit)          │
     │  Via:     CPA portal                                   │
     │            [ Approve ]   [ Deny ]                       │
     └───────────────────────────────────────────────────────┘
  │
  ├─ Deny → nothing sent; token discarded; logged.
  │
  ▼ Approve
CPA Send Connector → verify dest == config → submit → log
  │
  ▼
Agent: "Submitted your August statement to your CPA's portal.
        Want me to auto-fetch next month's statement too?"
  │
  ├─ No  → token discarded; done.
  │
  ▼ Yes → standing permission (30-day default), still approve-gated before
          each send; visible + revocable in Permissions & Memory.
```

**Key oversight properties on display:** *credential-less delegated access* (the agent gets a scoped read-only token, never the bank password); authentication happens on the bank's own page in the user's browser; the scope is statement-read-only (no payment power); and the same fixed-destination + approve-before-send gates apply as every other financial-data send.

### 4.6 Refusal handling (FR-20/21, US-17/18/19)

- **Off-topic** → brief redirect: "I only help with your task list."
- **Unsafe** (profane/illegal) → firm refusal.
- **In-domain refusals** (the interesting ones):
  - "Just pay the lawn-mower for me." → refused: agent never initiates payment (FR-6).
  - "Send my statements to my brother." → refused: destination guardrail (FR-11).
  - These are surfaced with a plain-language reason, reinforcing the oversight thesis.

---

## 5. Alternatives Considered

### 5.1 Autonomy model for the email-watch: send-then-notify vs. detect-pause-approve-send
- **Send-then-notify (rejected):** Agent sends automatically on detection, tells the user after.
  - *Pros:* Most "hands-off"; fewest interruptions.
  - *Cons:* Irreversible financial-data egress with **no human gate**; a false-positive/phishing match sends the wrong file; directly contradicts the demo's oversight thesis.
- **Detect → pause → approve → send (CHOSEN):**
  - *Pros:* Autonomous where it's safe (watching/detecting), human-gated where it's irreversible (sending); catches false positives; textbook oversight pattern.
  - *Cons:* Requires the user to act when notified; a genuine statement waits until approved. Acceptable for this use case.

### 5.2 CPA destination source: chat-derived vs. pre-configured fixed
- **Extract destination from conversation (rejected):**
  - *Pros:* Flexible; no setup.
  - *Cons:* Prompt-injectable — the single biggest risk in the whole design. A malicious email/message could redirect financial documents.
- **Pre-configured, read-only, enforced at connector (CHOSEN):**
  - *Pros:* Guardrail holds even if the LLM is fooled; demonstrable "cannot be overridden."
  - *Cons:* Less flexible; changing the CPA is a config action, not a chat action. Correct trade-off here.

### 5.3 Guardrail enforcement: prompt-only vs. code-enforced
- **Prompt-only (rejected):** Tell the LLM "only send to the CPA."
  - *Cons:* LLMs can be talked out of instructions; not a real boundary.
- **Code-enforced at the Tool Layer (CHOSEN):** The connector rejects any non-config destination regardless of what the LLM decided.
  - *Pros:* True security boundary; matches NFR-2. *Cons:* Slightly more plumbing.

### 5.4 Prioritization: metadata-only vs. agent-reasoning vs. blend
- **Metadata-only (rejected):** Deterministic but blind to context ("bookings fill up fast").
- **Agent-reasoning-only (rejected):** Rich but can confidently hallucinate priorities.
- **Blend with visible explanation + user override (CHOSEN):** Metadata + history + reasoning, always explained, always overridable (FR-3/4). Best mix of usefulness and trust.

### 5.5 Integrations: real vs. mocked
- **Real Gmail/Drive/OAuth/portal (rejected for demo):** High effort, fragile, credential/security burden, non-deterministic demos.
- **Mocked with faithful consent/action experience (CHOSEN):** Reliable, safe, repeatable; clean connector boundaries so real APIs can be swapped in later (NFR-7). The *OAuth experience* is mocked, not skipped, because the scoped-consent moment is itself part of the lesson.

### 5.6 Memory: stateless vs. persistent
- **Stateless (rejected):** Simpler, but loses US-15 and can't hold standing permissions/watches.
- **Persistent with a view/revoke surface (CHOSEN):** Enables standing permissions and "builds on past sessions," while keeping the user in control (FR-18/19).

### 5.7 Statement source: manual upload vs. email-watch vs. direct bank fetch
- **Manual upload only (rejected as sole option):** Simple, but puts all the work on the user and depends on them already having the file.
- **Email-watch only (insufficient alone):** Convenient, but the emailed document may be a summary/notice rather than the authoritative statement, and email is spoofable (phishing risk).
- **Direct bank fetch via OAuth aggregator (CHOSEN as the authoritative option, offered alongside the other two):**
  - *Pros:* Authoritative source; **credential-less** (agent never sees bank password — OAuth-in-browser + scoped read-only token via Plaid/Finicity/MX); scope is statement-read-only so the connector has no payment power; supports a clean recurring-fetch permission.
  - *Cons:* Requires aggregator integration (mocked for the demo); OAuth linking is an extra step; not every bank is supported by every aggregator in reality. Acceptable — and the credential-less delegation is itself a key oversight lesson.

### 5.8 Bank aggregator choice (Plaid vs. Finicity vs. MX vs. direct bank APIs)
- **Direct per-bank APIs (rejected):** No standard; every bank differs; large, fragile integration surface.
- **Aggregator (Plaid / Finicity / MX) (CHOSEN):** Single integration, standardized OAuth + read-only data access, broad coverage. The demo mocks the aggregator behind a clean connector so any real provider can be swapped in later. (Provider selection deferred — see Open Questions.)

---

## 6. Open Questions

> **Resolved (decided during planning):**
> - ~~Delivery format~~ → **Building a runnable demo** (see implementation plan).
> - ~~Model / runtime~~ → **Amazon Bedrock (Claude)**, agent in **Python + LangGraph**, React/TS frontend.

1. **Approval notification channel for background watches.** When a watch fires while the user isn't in the chat, how do they get the Approval Card — in-app only, or also a notification (email/push/Slack)? For a demo, in-app on next open may suffice.
2. **Watch expiry UX.** At day 30, does the watch expire silently (user must notice), or does the agent proactively prompt "your statement watch expires today — extend?" (Recommend the proactive prompt.)
3. **Detection confidence threshold.** Do we want a visible confidence level in the Approval Card ("high/medium confidence this is the statement"), and should low-confidence matches be surfaced for review or silently ignored?
4. **Multiple candidate matches.** If two emails plausibly match (e.g., statement + a "statement is ready" reminder with no attachment), does the agent show both and let the user pick, or auto-select the best?
5. **One-time file access scope.** Does "one-time" mean one task, one session, or a single fetch? (Recommend: scoped to the single approved send, then revoked.)
6. **Standing permission for routine automation.** Should routine-task automation (booking) also carry a 30-day expiry like watches, or a per-task grant? (Recommend per-task for the demo.)
7. **Audit visibility.** Should the activity/audit log be user-visible in the demo (it strongly reinforces the oversight theme) or purely internal? (Implementation plan T24 currently builds it user-visible.)
8. **Failure handling depth (NFR-6).** How much of the "agent stops and hands back on failure/ambiguity" do we script into the demo vs. describe? (e.g., file not found, portal login fails, ambiguous "pay it.") Currently folded into T7's scope.
9. **Aggregator provider for the mock.** Which provider should the mock model after (Plaid / Finicity / MX)? Affects the naming and scope labels shown in the OAuth consent screen. (Recommend Plaid — most recognizable for a demo.)
10. **Recurring bank-fetch cadence.** For the "auto-fetch next month's statement" standing permission (FR-26), is the trigger date-based (e.g., 3rd of each month) or availability-based (fetch when the bank publishes a new statement)? (Recommend availability-based, still approve-gated before send.)
11. **Aggregator token lifespan.** Real aggregator tokens can persist for ongoing access. For the demo, should the token be discarded after each approved send (re-link each time) or held for the standing recurring-fetch permission? (Recommend: discard for one-shot fetch; hold only when the recurring permission is explicitly granted, and show it in Permissions & Memory.)
