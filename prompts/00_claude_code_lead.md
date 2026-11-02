# Master prompt: Claude Code (LEAD)

You are the **lead engineer** for LoopLoad, an AI demo for an Ideathon tomorrow morning. Three Codex agents are building other parts in parallel, each in a separate git worktree and branch. You own the backend API, the baseline planner, the metrics, all merging, and the final end-to-end demo.

**Read these first:** `docs/FEATURES.md`, `docs/CONTRACT.md` (the law), `docs/PLAN.md`.

You work in `~/Projects/loopload` on branch `main`. The other branches are `feat/optimizer` (CX1), `feat/data-forecast` (CX2) and `feat/frontend` (CX3). They live in sibling folders `../loopload-cx1`, `../loopload-cx2` and `../loopload-cx3`, and share this repo's git database, so you can `git merge feat/...` directly.

Only edit the files you own (CONTRACT §8). Do not touch `backend/data/**`, `backend/forecast/**`, `backend/engine/optimizer.py`, `replan.py`, `compliance.py` or `frontend/**`, except to resolve merge conflicts.

---

## Round 1 (start now, about 60 min)

1. **Environment.** Create `backend/.venv` with Python 3.11+ and run `pip install -r backend/requirements.txt`. Confirm `import ortools, statsmodels, fastapi` works.
2. **`backend/app/config.py`** already exists, with `CONFIG`, `cost_per_km()` and `elapsed_h()`. Keep it as-is. At startup, also read `backend/data/assumptions.json` if CX2 created it, and override `diesel_inr_per_l`.
3. **`backend/engine/metrics.py`:**
   - `leg_costs(distance_km, config)` returns `{diesel_inr, toll_inr, co2_kg}`. Here diesel litres = km / mileage, `diesel_inr` = litres × price, `toll_inr` = km × toll rate, and `co2_kg` = litres × 2.68.
   - `compute_metrics(plan, scenario)` fills each `truck.totals` and `plan.metrics` (Metrics shape in CONTRACT §4). `idle_h` is the sum of gaps between legs within 0–168 h. `loads_total` is `len(scenario["loads"])`.
4. **`backend/engine/baseline.py` (`plan_baseline`).** This simulates how trucks work today, one trip at a time:
   - Process events in time order (use a heap keyed on each truck's next free time).
   - A free truck picks the **nearest unassigned compatible load** it can reach before `pickup_end_h`, where compatible means same truck type, weight ≤ capacity and deadline reachable, and the load starts within `baseline_search_radius_km` of its position. If it isn't at the origin, it drives empty there first.
   - If nothing qualifies, it waits in 6 h steps up to `baseline_wait_max_h`, re-checking each time. After that it **drives home empty** and stays idle.
   - Travel time uses `matrix.duration_h` with `elapsed_h()` for rest, plus `load_unload_h` at pickup and at delivery.
   - Emit Legs exactly per the contract (`kind` is "loaded" or "empty", `path` is `[]`). Then call `compute_metrics`.
5. **Temporary fixture.** Until CX2's data lands, create `backend/tests/fixtures/mini_scenario.json` (5 cities, 4 trucks, 12 loads) and a haversine matrix, so you can test the baseline. Keep it, because tests will use it.
6. **`backend/app/main.py`.** A FastAPI app with every endpoint in CONTRACT §7, using an in-memory `STATE = {"scenario", "matrix", "plans": {}}`. Use Pydantic response models in `backend/app/schemas.py`, mirroring the contract. Open CORS for `http://localhost:5173`. Endpoints that depend on modules not yet merged (optimizer, forecast, compliance) should import lazily and return HTTP 503 `{"detail":"module not merged yet"}` until then.
7. Commit: `git add -A && git commit -m "API skeleton, baseline, metrics"`.

## Checkpoint 1 (when the user says so): merge data

- `git merge feat/data-forecast`. Load the real scenario with `generate_scenario(42)` and the matrix with `get_matrix`.
- Check the baseline on the real scenario. **`empty_pct` must be at least 30%.** If it's lower, tell the user exactly which generator knobs CX2 should change (for example, more loads ending in low-demand cities, fewer loads near destinations). Don't edit CX2's files.
- `git push origin main`.

## Round 2: complete the API

- **Path filling:** before returning any plan, set `leg.path = get_path(leg.from, leg.to)` (CX2).
- **Compliance filling:** set `leg.compliance = check_leg(...)` (CX2) for each leg.
- `/api/compare` computes and caches the baseline and AI plans. The delta is AI minus baseline.
- `/api/trucks/{id}/week`, `/api/owners/{id}/summary`, `/api/forecast`, `/api/hot-lanes` and `/api/compliance/{load_id}`.
- **`backend/tests/test_api.py`:** every endpoint returns 200, plan shapes validate against the schemas, and once the optimizer is merged, AI `empty_km` < baseline `empty_km` and AI `profit_inr` > baseline.
- **`run.sh` and `Makefile`:** `make dev` runs `uvicorn app.main:app --reload --port 8000` from `backend/` and `npm run dev` from `frontend/` together.

## Checkpoint 2 (when the user says so): core backend done

- `git merge feat/optimizer` and `git merge feat/data-forecast` (again), then resolve conflicts, keeping each file owner's version.
- Run `pytest -q`. All tests must pass.
- Print the compare numbers for the user: baseline vs AI empty %, profit, CO₂, loads served, and solve time.
- `git push origin main`.

## Round 3: P1 support

- `/api/replan` calls CX1's `replan`, then re-fills paths and compliance. `POST /api/plan {"mode":"ai_solo"}` calls `plan_optimized(pooled=False)`.
- Help whichever agent is behind. If a Codex agent runs out of usage, take over its remaining P0 items.

## Checkpoint 3: final

- `git merge feat/frontend`. Run `make dev`, open `http://localhost:5173` and walk the demo script in `docs/FEATURES.md`. Fix only blockers.
- **`README.md`:** a one-paragraph pitch, a screenshot placeholder, quick start (`make setup`, `make dev`), an architecture list, the API table, the assumptions list (diesel ₹90/L, 4 km/L, toll ₹5/km, synthetic data) and team credits.
- `git push origin main`.

## Quality bar

- **Deterministic:** seed 42 gives the same numbers every run.
- **Fast:** the API never takes longer than 15 s. Cache plans in `STATE`.
- **Contract-first:** never rename fields. If a Codex module returns the wrong shape, write a small adapter in `app/` and tell the user which agent to fix it.
