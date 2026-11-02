# Master prompt: Codex 1 (OPTIMISER)

You are building the **AI chain optimiser** for LoopLoad, a demo for an Ideathon tomorrow morning. It plans week-long chains of loaded trips for Indian trucks so they rarely drive empty. Three other agents are working in parallel in other worktrees.

**Read first:** `AGENTS.md`, `docs/CONTRACT.md` (the law: shapes, signatures, ownership) and `docs/FEATURES.md` (section B).

You work in `~/Projects/loopload-cx1` on branch `feat/optimizer`.
**You may only create or edit:** `backend/engine/optimizer.py`, `backend/engine/replan.py` and `backend/tests/test_optimizer.py` (plus fixtures under `backend/tests/fixtures/cx1_*`).
Commit after each working step. Never push to `main`.

---

## P0-1: Local fixture (first 10 min, so you don't wait on CX2)

Create `backend/tests/fixtures/cx1_scenario.json`: 6 cities from CONTRACT §2 (TPR, DEL, JAI, NAG, BLR, NSK), 5 trucks from 3 owners, and 20 loads that follow the Scenario shape exactly. Make a matching haversine × 1.3 matrix in `cx1_matrix.json` (duration = km ÷ 45). Design it so loop chains exist, for example TPR→DEL, DEL→JAI, JAI→NAG and NAG→BLR.

## P0-2: `plan_optimized(scenario, matrix, config, pooled=True, time_limit_s=None) -> Plan`

Use **Google OR-Tools routing (pickup and delivery with time windows)**:

- **Time unit:** integer minutes. Horizon = `config["horizon_h"] * 60`.
- **Nodes:** one start node per truck (its `start_city` at `available_from_h`), a pickup node and a delivery node per load, and one shared dummy end node (arc cost 0 into it, so routes end anywhere). Optionally add a small penalty of `distance_to_home × cost_per_km × 0.3` on the arc into the end node, to nudge trucks back towards home.
- **Arc cost (INR int):** `distance_km(city_i, city_j) × cost_per_km`, where `cost_per_km = diesel_inr_per_l / mileage_kmpl + toll_inr_per_km`. Compute it inline; don't import CC's files.
- **Transit time:** `elapsed_h(duration_h)` from CONTRACT §3 (adds rest after every 10 h of driving) plus `load_unload_h` service time at the pickup and delivery nodes. Express it in minutes.
- **Time windows:** pickup in `[pickup_start_h, pickup_end_h]`, delivery ≤ `deliver_by_h`, truck start ≥ `available_from_h`. Allow waiting (slack up to the horizon).
- **FTL:** a capacity dimension with capacity 1 per truck, demand +1 at pickup and −1 at delivery, so a truck carries one load at a time. Use `AddPickupAndDelivery`, same vehicle, and pickup cumul ≤ delivery cumul.
- **Compatibility:** `routing.VehicleVar(pickup).SetValues([...allowed vehicle indices, -1])`. A vehicle is allowed if `truck.type == load.truck_type` and `load.weight_t <= truck.capacity_t`.
- **Optional loads:** `AddDisjunction([pickup], penalty=load.freight_inr)` (and the same for delivery, or tie them). Dropping a load costs its revenue, so the solver maximises profit.
- **Search:** `PATH_CHEAPEST_ARC` first solution, `GUIDED_LOCAL_SEARCH` metaheuristic, time limit `time_limit_s or config["solver_time_limit_s"]`.
- **Pooling:** when `pooled=True`, solve all trucks together. When `pooled=False`, solve each owner separately on only their trucks, with the loads assigned greedily so they aren't shared (simplest: each owner solves on all loads, in owner order, removing loads already taken), and return mode `"ai_solo"`.
- **Output:** walk each vehicle's route. Each node-to-node move becomes a Leg. Pickup→its delivery is `kind:"loaded"` with `load_id` and `revenue_inr = freight_inr`. Any move between different cities otherwise is `kind:"empty"`. Skip zero-distance moves. Take `depart_h`/`arrive_h` from the time dimension. Fill `diesel_inr`, `toll_inr` and `co2_kg` (2.68 kg per litre). Leave `path: []`. Fill `unassigned_loads`, `solve_time_s` and `plan_id = "ai-" + uuid8`. Compute `metrics` inline with the same formulas (CC's `compute_metrics` will recompute later).
- **Fallback:** if there's no solution, retry once with all windows widened by 20%. If that also fails, run a greedy chain builder (each truck repeatedly takes the most profitable reachable next load, scored by `freight − empty_km × cost_per_km`) and set `"solver":"greedy_fallback"` in the plan.

## P0-3: `backend/tests/test_optimizer.py`

- On the fixture: the plan is feasible (no time-window or deadline violations, one load at a time, types match) and every leg follows the contract shape.
- AI `empty_km` is lower than a naive "deliver then drive home empty" plan on the same fixture.
- It runs in under 15 s.
- When `backend/data/generator.py` exists after you merge main, also test on `generate_scenario(42)`.

## After Checkpoint 1 (user says "merge main")

Run `git merge main`. Now `backend/data/` exists. Run on the real scenario: `generate_scenario(42)` and `get_matrix(scenario["cities"])`. **Target: AI empty km at least 50% lower than CC's baseline, with higher profit, in 10 s or less.** Tune the first-solution strategy, the home-return nudge and the time limit. Print a one-line summary for the user.

## P1-1: `replan(plan, event, scenario, matrix, config) -> Plan`

- Freeze every leg with `depart_h < event.at_h`. A leg in progress at `at_h` is completed, and the truck's new start is its `to` city at its `arrive_h`.
- Apply the event: `cancel_load` removes the load, `delay_truck` adds `delay_h` to that truck's start, and `new_load` adds a load.
- Re-solve only the remaining loads with a 5 s limit. Return a new Plan (new `plan_id`) whose legs are the frozen legs plus the new ones, and add `"replan_of": old_id` and `"changed_trucks": [...]`.

## P1-2: Pooling comparison

Make sure `plan_optimized(pooled=False)` works and that pooled profit ≥ solo profit on seed 42. Print both numbers.

## P2 (only if everything above passes)

Forecast-aware planning. Accept an optional `config["forecast_loads"]` list of Load-shaped dicts with a `probability` field, and add them as optional nodes with penalty `freight_inr × probability`, so trucks end the week near hot lanes.

---

When you finish each item, commit with a clear message and print a short status: what works, the numbers, and anything blocked.
