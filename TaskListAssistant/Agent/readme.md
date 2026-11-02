# Agent Backend (Python + FastAPI + LangGraph)

The agentic AI layer. It does **not** own tasks — it calls the Legacy Task API
(system of record) for all task CRUD. LLM reasoning runs on Amazon Bedrock
(Claude) behind a seam, with a deterministic **stub** as the default so the demo
runs offline.

## Prerequisites
- Python 3.12 (`python3.12 --version`)
- The Legacy Task API running on `:4000` (see `../legacy/README.md`)

## Setup
```bash
cd agent
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- `GET  /api/health`        → `{ok:true}`
- `GET  /api/legacy-health` → checks the legacy API is reachable
- `GET  /api/tasks`         → tasks fetched from the legacy API
- `POST /api/chat`          → `{message}` → `{category, reply}` (via the LangGraph graph)
- `GET  /api/audit`         → audit trail
- `GET  /api/config/cpa`    → the fixed, read-only CPA destination

## Verify
```bash
source .venv/bin/activate
ruff check app tests      # lint
mypy                      # types
pytest -q                 # tests (legacy-client test auto-skips if :4000 is down)
```

## Config (env)
| Var | Default | Purpose |
|---|---|---|
| `LLM` | `stub` | `stub` (deterministic, offline) or `bedrock` (Claude) |
| `BEDROCK_MODEL_ID` | claude-3.5-sonnet | Bedrock model id |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `LEGACY_API_URL` | `http://127.0.0.1:4000` | legacy Task API |
| `CPA_EMAIL` / `CPA_PORTAL_URL` | demo values | **fixed** destination (guardrail root) |
| `AGENT_DB_PATH` | `agent.db` | agent-owned state (memory/permissions/watches/audit) |
| `DEFAULT_WATCH_DAYS` | `30` | default watch lifespan |

## What's built
- **T1** FastAPI app + health + CORS
- **T2** Pydantic domain models (`app/models.py`)
- **T3** agent-owned state store + **read-only CPA config** (`app/store.py`, `app/config.py`)
- **T4** LangGraph skeleton + Bedrock adapter + deterministic stub (`app/graph.py`, `app/llm.py`)
- **T31** Legacy Task API client (`app/legacy_client.py`)
- **T6** Tool/Action Layer + code-enforced CPA guardrail (`app/tools.py`)
- **T7** Approval gate via LangGraph `interrupt()` (`app/oversight.py`) + `/api/send/request`, `/api/send/resolve`
- **T20 (partial)** `/chat` answers "what are my open tasks?" / "what should I do next?" from live legacy tasks (`app/prioritize.py`)
- **Wave C connectors** (`app/connectors/`): OAuth+consent (T9), Gmail inbox+watch+detect (T10), Drive (T11),
  Bank aggregator — credential-less, read-only, no payment (T12), CPA send (T13), Booking (T14)
- **Wave D hero flows** (`app/flows.py`): send-statements-to-CPA (T17), email-watch→detect→pause→approve→send (T18),
  direct bank fetch + recurring permission (T19) — endpoints under `/api/flows/*`, plus permissions/watches
  view+revoke (`/api/permissions`, `/api/watches`)

Next: Wave E — the React agentic UI (chat, Approval Card, OAuth popup, activity log, permissions dashboard) + demo script.
