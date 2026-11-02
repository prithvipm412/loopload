# Rules for every coding agent on LoopLoad

LoopLoad is an Ideathon demo. It's an AI planner that chains loaded truck trips across India so small fleet owners' trucks rarely drive empty. Four agents build it in parallel, each in its own git worktree and branch.

## Always
1. Read `docs/CONTRACT.md` before writing code. The JSON shapes, function signatures and file ownership there are the law.
2. Only edit files your role owns (CONTRACT §8). Your role is in the prompt file you were given under `prompts/`.
3. Commit on your own branch after every working step: `git add -A && git commit -m "<what now works>"`. Never push to `main`; only Claude Code (the lead) merges and pushes.
4. P0 before P1. P1 before P2.
5. If the contract blocks you, stop and tell the user. Never silently rename fields.
6. Do not create `backend/tests/conftest.py` (the lead owns it). Load your fixtures inside your own test files.

## Backend conventions
- Python 3.11 or 3.12 is preferred, because OR-Tools wheels may lag on the newest Python. If `python3 --version` is 3.13 or newer and OR-Tools fails to install, use `python3.12` (`brew install python@3.12`).
- Set up in your worktree: `python3.12 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`
- Run from `backend/`: `cd backend && PYTHONPATH=. .venv/bin/pytest -q`
- Imports are relative to `backend/`, for example `from app.config import CONFIG, elapsed_h`, `from data.distance import get_matrix`, `from engine.compliance import check_leg`.
- Engine functions take and return plain dicts/lists in the contract shapes. No cross-module Pydantic.
- Everything is deterministic for a given seed (default 42).

## Frontend conventions
- Everything lives in `frontend/` (Vite + React + TS). It works offline from mocks when `VITE_USE_MOCKS=true`.
