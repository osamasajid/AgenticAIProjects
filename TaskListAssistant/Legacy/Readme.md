# Legacy Task Manager

The **"before"** state for the agentic AI demo: a classic, click-through task manager with **no AI**. It is also the **system of record** — the agentic assistant (built later) reads and writes these same tasks via this REST API.

- `api/` — Node/Express (JavaScript) REST API + SQLite store (seeded with the 4 life-admin demo tasks)
- `web/` — React (JavaScript) UI: task list, priority/due-date badges, add/edit, complete/reopen/delete

## Prerequisites
Node 20 LTS (`node --version` → v20.x).

## Run

Two terminals (or use the root script below):

```bash
# 1) API on http://127.0.0.1:4000
cd api && npm install && npm run dev

# 2) Web UI on http://127.0.0.1:5173  (proxies /api → :4000)
cd web && npm install && npm run dev
```

Open http://127.0.0.1:5173.

### One command (from this folder)
```bash
./run.sh
```

## Test
```bash
cd api && npm test   # 9 integration tests over the full REST contract
```

## REST contract
Base `/api/tasks` — see `../../legacy-task-manager-design.md` §4.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/tasks` | list (filters: `status`, `priority`, `category`; `sort`) |
| GET | `/api/tasks/:id` | get one |
| POST | `/api/tasks` | create `{title, priority?, dueDate?, category?, notes?}` |
| PATCH | `/api/tasks/:id` | update any subset |
| POST | `/api/tasks/:id/complete` | mark done |
| POST | `/api/tasks/:id/reopen` | mark open |
| DELETE | `/api/tasks/:id` | delete |
| GET | `/api/health` | `{ok:true}` |

## Config
- `PORT` (API, default `4000`)
- `LEGACY_DB_PATH` (API SQLite file, default `api/tasks.db`)
- `LEGACY_API_URL` (web dev proxy target, default `http://127.0.0.1:4000`)

The agentic app will point its `LEGACY_API_URL` at this API (default `:4000`).
