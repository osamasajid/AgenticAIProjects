#!/usr/bin/env bash
# Start all demo servers. Agent runs with the local Ollama ReAct agent + MCP on.
# Override with: LLM=stub ./start-all.sh   (offline, no model) or LLM=bedrock (needs AWS).
set -uo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

# make brew tools (node/python) available in a fresh shell
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null)" || true

LLM_MODE="${LLM:-ollama}"
MCP_MODE="${MCP:-on}"

wait_for() {  # url, name
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null "$1" 2>/dev/null; then echo "  $2 up"; return 0; fi
    sleep 1
  done
  echo "  WARNING: $2 did not become ready ($1)"; return 1
}

echo "Starting demo servers (LLM=$LLM_MODE MCP=$MCP_MODE)…"

# 1) Legacy API :4000
( cd "$ROOT/legacy/api" && PORT=4000 node src/server.js > /tmp/legacy-api.log 2>&1 & )
# 1b) Legacy "before" UI :5173
( cd "$ROOT/legacy/web" && npm run dev > /tmp/legacy-web.log 2>&1 & )
# 2) Booking mock :4100
( cd "$ROOT/mocks/booking" && npm start > /tmp/booking-mock.log 2>&1 & )
# 3) Agent :8000
( cd "$ROOT/agent" && . .venv/bin/activate && LLM="$LLM_MODE" MCP="$MCP_MODE" \
    uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/agent.log 2>&1 & )
# 4) Web UI :5174
( cd "$ROOT/web" && npm run dev > /tmp/web.log 2>&1 & )

echo "Waiting for services…"
wait_for "http://127.0.0.1:4000/api/health" "legacy API :4000"
wait_for "http://127.0.0.1:4100/slots"      "booking mock :4100"
wait_for "http://127.0.0.1:8000/api/health" "agent :8000"
wait_for "http://127.0.0.1:5174/"           "web UI :5174"

if [ "$LLM_MODE" = "ollama" ]; then
  curl -s -o /dev/null "http://127.0.0.1:11434/api/tags" 2>/dev/null \
    && echo "  ollama up" \
    || echo "  WARNING: Ollama not reachable on :11434 — run 'ollama serve' and 'ollama pull qwen2.5:3b'"
fi

echo
echo "Open the agent UI:   http://127.0.0.1:5174"
echo "Legacy 'before' UI:  http://127.0.0.1:5173"
echo "Logs: /tmp/legacy-api.log /tmp/legacy-web.log /tmp/booking-mock.log /tmp/agent.log /tmp/web.log"
