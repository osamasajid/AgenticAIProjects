#!/usr/bin/env bash
# Stop all demo servers (leaves Ollama running — it's a separate user service).
set -uo pipefail

echo "Stopping demo servers…"
pkill -f "legacy/api/src/server.js" 2>/dev/null && echo "  stopped legacy API"    || echo "  legacy API not running"
pkill -f "uvicorn app.main"          2>/dev/null && echo "  stopped agent"          || echo "  agent not running"
pkill -f "json-server"               2>/dev/null && echo "  stopped booking mock"   || echo "  booking mock not running"
pkill -f "vite"                      2>/dev/null && echo "  stopped web UI"         || echo "  web UI not running"
# MCP servers are child processes of the agent (stdio) and exit with it.
sleep 1
echo "Done."
