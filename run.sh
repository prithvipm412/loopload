#!/usr/bin/env bash
# Starts the backend on :8000 and the frontend on :5173. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")"

(cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null' EXIT INT TERM
wait
