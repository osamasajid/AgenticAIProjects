#!/usr/bin/env bash
# Start the Legacy Task Manager API (:4000) and Web UI (:5173).
set -euo pipefail
cd "$(dirname "$0")"

echo "Starting Legacy Task API on :4000 ..."
( cd api && npm install --silent && PORT=4000 node src/server.js ) &
API_PID=$!

echo "Starting Legacy Web UI on :5173 ..."
( cd web && npm install --silent && npm run dev ) &
WEB_PID=$!

trap 'echo; echo "Stopping..."; kill $API_PID $WEB_PID 2>/dev/null || true' INT TERM
echo "Open http://127.0.0.1:5173  (Ctrl-C to stop)"
wait
