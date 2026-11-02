#!/usr/bin/env bash
# One command to bring the whole demo up in a KNOWN state:
#   stop everything -> wipe agent-owned state -> start all servers -> seed tasks & slots.
# Usage: ./demo.sh            (agent uses local Ollama + MCP)
#        LLM=stub ./demo.sh   (offline deterministic, no model)
set -uo pipefail
cd "$(dirname "$0")"
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null)" || true

echo "== 1/4 stop =="
./stop-all.sh

echo "== 2/4 wipe agent-owned state (memory/permissions/watches/audit/checkpoints) =="
rm -f agent/agent.db agent/oversight.db
echo "  cleared agent/agent.db, agent/oversight.db"

echo "== 3/4 start =="
./start-all.sh

echo "== 4/4 seed known state =="
python3 reset-demo.py

echo
echo "Demo is up in a known state. Open http://127.0.0.1:5174"
