# Agentic Task Assistant — Autonomous AI with Human Oversight

**Objective:** Demonstrate how to transform a classic click-through task manager into a conversational
AI agent that acts autonomously on life-admin tasks (bills, appointments, sending documents) while
keeping the human firmly in control of anything consequential — teaching the patterns that make agent
autonomy safe.

**Key take-aways:**
- **Trust ladder, not blanket autonomy** — advise-only for payments, human-approved for irreversible
  sends, standing-permission for routine tasks, refuse for off-topic/unsafe.
- **The AI plugs into the existing system** — the agent reads/writes tasks through the same legacy REST
  API the "before" UI uses; one source of truth.
- **Guardrails enforced in code, not prompts** — financial documents can go only to a fixed CPA
  destination in immutable config; a manipulated model, a malicious email, or a bad argument can't redirect them.
- **Human-in-the-loop is a first-class primitive** — irreversible actions pause on a LangGraph
  `interrupt()` gate (detect → pause → approve → send), with a full audit trail.

## Architecture (tiers)

```
 legacy/            React + JS UI (:5173)  +  Node/Express JS API (:4000)   ← system of record (tasks)
 agent/             Python + FastAPI + LangGraph (:8000)  ← agent brain
   app/react_agent  hand-written ReAct loop (reason→act→observe) over Ollama tool-calling
   app/mcp_client   MCP client: discovers + calls tools from the MCP servers
   mcp_servers/     weather (real Open-Meteo) + booking (calls the mock REST API) MCP servers
 mocks/booking/     json-server mock REST API (:4100) — external appointment-slot service
 web/               React + TS UI (:5174)   ← chat, Approval Cards, activity log, permissions dashboard
```

## Agentic concepts — what's actually implemented

| Concept | Status | Where |
|---|---|---|
| **External API** | ✅ | `legacy_client.py` (real HTTP to the task API), booking mock, real Open-Meteo weather |
| **Memory** | ✅ | agent state store + conversation context + LangGraph SQLite checkpointer |
| **Tool calling** | ✅ | model-driven via Ollama (`react_agent.py` sends schemas, executes chosen calls) |
| **ReAct** | ✅ | hand-written reason→act→observe loop; composes multiple tools |
| **MCP** | ✅ | `mcp_servers/` (weather + booking) discovered & called via `app/mcp_client.py` |

The hard **oversight** guarantees are enforced in code regardless of the model: fixed CPA
destination, human approval gate (LangGraph `interrupt()`), and irreversible actions (send, book)
routed through it.

## Run it

### Quick start (one command — recommended)
From the project root (`agentic-demo/`):
```bash
./demo.sh                 # stop → wipe agent state → start all 5 servers → seed a known state
# LLM=stub ./demo.sh      # offline deterministic mode (no model needed)
```
Prereqs for `LLM=ollama` (the default): Ollama running with `qwen2.5:3b` pulled (see step 3 below).
Scripts: `start-all.sh`, `stop-all.sh`, `reset-demo.py` (re-seed tasks + booking slots via the running APIs).

### Manual (five pieces, if you prefer)
Terminals (run `eval "$(/opt/homebrew/bin/brew shellenv)"` first if node/python aren't found):

```bash
# 1) Legacy API + UI (tasks system of record)
cd legacy && ./run.sh                 # API :4000, legacy UI :5173

# 2) Booking mock REST API (external appointment service)
cd mocks/booking && npm install && npm start   # :4100

# 3) Ollama (local LLM) — install once, then:
ollama serve &                        # :11434
ollama pull qwen2.5:3b                 # tool-calling capable (~2 GB)

# 4) Agent backend — real ReAct + tool-calling + MCP
cd agent && source .venv/bin/activate
LLM=ollama MCP=on uvicorn app.main:app --host 127.0.0.1 --port 8000

# 5) Agent UI
cd web && npm install && npm run dev  # :5174
```

Open **http://127.0.0.1:5174**. The agent UI at :5174 drives the ReAct agent; the legacy "before" is at :5173.

**LLM modes:** `LLM=ollama` (real ReAct + tool-calling, local), `LLM=bedrock` (Claude, needs AWS creds),
or unset for the deterministic **stub** (offline, no model). `MCP=on` starts the weather+booking MCP servers
(the agent spawns them over stdio). Leave `MCP` off to run with only the local task tools.

## Try in chat (with LLM=ollama MCP=on)
- "what should I do next?" → lists/ranks tasks
- "add a task to renew my passport" / "complete the electrician task"
- "plan a picnic Saturday 11am–4pm" → scheduled as a **task** (personal plans ≠ provider appointments)
- "can I do lawn work in Seattle today? check the weather" → **weather MCP** → forecast + outdoor verdict
- "block Saturday for tennis, but check weather first — don't book if raining" → multi-step: checks weather, declines if rain
- "find me a doctor appointment" → **booking MCP** → slots; booking also adds a companion task
- "send my statements to my CPA" → send flow → **Approval Card** (fixed CPA, human gate)

The chat keeps **per-session conversation memory**, so follow-ups like "yes, schedule it" / "show me the
link" resolve against the task under discussion.

## Demo flow (the "before → after" arc)
1. Show the **legacy UI** (:5173) — classic click-through task list. *"This is our existing experience."*
2. Switch to the **agent UI** (:5174). Ask *"what should I do next?"* — it reads the same tasks.
3. **Send statements to CPA** → watch the OAuth consent, then the **Approval Card** (locked to the CPA). Approve.
4. **Watch email → CPA** → arm the watch, **Inject test email** → detection reasons shown → approve.
5. **Fetch from bank → CPA** → credential-less OAuth → approve → grant the recurring permission.
6. Point at the **Activity log** (every action audited) and **Permissions & watches** (revocable).

## Test
```bash
cd legacy/api && npm test          # 11 legacy API tests
cd agent && source .venv/bin/activate && pytest -q   # 45 agent tests (ruff + mypy also clean)
cd web && npx tsc --noEmit         # frontend typecheck
```

## Notes
- LLM defaults to a deterministic **stub** (`LLM=stub`) so the demo runs offline. Set `LLM=bedrock` (+ AWS
  creds) to use Claude on Amazon Bedrock.
- Every external integration (OAuth, Gmail, Drive, Bank/Plaid, CPA portal) is **mocked but real-swappable**.
- Docker packaging and AWS deploy are deferred (local-first).
