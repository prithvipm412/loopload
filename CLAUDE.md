# Rules for Claude Code on LoopLoad

LoopLoad is an Ideathon demo. It's an AI planner that chains loaded truck trips across India so small fleet owners' trucks rarely drive empty. Claude Code is now the sole agent building and maintaining the whole project (backend and frontend) in this one worktree on `main`.

## Always
1. Read `docs/CONTRACT.md` before writing code. The JSON shapes and function signatures there are the law unless the user explicitly approves a change.
2. Commit after every working step: `git add -A && git commit -m "<what now works>"`.
3. P0 before P1. P1 before P2.
4. If the contract blocks you, stop and tell the user. Never silently rename fields, change numbers, baseline logic, or the scenario generator without asking first.
5. The user runs the API and frontend dev servers themselves (ports 8000/5173). Never start a server on those ports — use 8001/5175 for your own testing and shut them down afterward.

## Backend conventions
- Python 3.11 or 3.12 is preferred, because OR-Tools wheels may lag on the newest Python. If `python3 --version` is 3.13 or newer and OR-Tools fails to install, use `python3.12` (`brew install python@3.12`).
- Set up: `python3.12 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`
- Run from `backend/`: `cd backend && PYTHONPATH=. .venv/bin/pytest -q`
- Imports are relative to `backend/`, for example `from app.config import CONFIG, elapsed_h`, `from data.distance import get_matrix`, `from engine.compliance import check_leg`.
- Engine functions take and return plain dicts/lists in the contract shapes. No cross-module Pydantic.
- Everything is deterministic for a given seed (default 42).

## Frontend conventions
- Everything lives in `frontend/` (Vite + React + TS). It works offline from mocks when `VITE_USE_MOCKS=true`, but the live API is the default source of truth when it's reachable.
