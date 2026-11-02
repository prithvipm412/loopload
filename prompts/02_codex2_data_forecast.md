# Master prompt: Codex 2 (DATA, FORECASTING, COMPLIANCE)

You are building the **data layer, demand forecasting and compliance checks** for LoopLoad, a demo for an Ideathon tomorrow morning. It is an AI planner that chains loaded truck trips across Indian states. Other agents depend on your data, so **ship the scenario and matrix first**.

**Read first:** `AGENTS.md`, `docs/CONTRACT.md` (the law) and `docs/FEATURES.md` (sections A, C and D).

You work in `~/Projects/loopload-cx2` on branch `feat/data-forecast`.
**You may only create or edit:** `backend/data/**`, `backend/forecast/**`, `backend/engine/compliance.py`, `backend/tests/test_data.py` and `backend/tests/test_compliance.py`.
Commit after each working step. Never push to `main`.

---

## P0-1: Cities and matrix (first 25 min, highest priority)

- **`backend/data/cities.json`:** the 25 cities from CONTRACT §2, exactly as listed.
- **`backend/data/distance.py`:**
  - `get_matrix(cities)` returns the Matrix shape. Call the public OSRM table API once: `https://router.project-osrm.org/table/v1/driving/{lon,lat;...}?annotations=distance,duration`, then convert to km and hours. Cache to `backend/data/matrix.json` and return the cache on later calls. On any failure, use haversine × 1.3 km and duration = km ÷ 45, with `"source":"haversine"`. Commit `matrix.json`, so no one needs the network at demo time.
  - `get_path(a, b)` returns the OSRM route geometry from `/route/v1/driving/...?overview=simplified&geometries=geojson` as `[[lon,lat],...]`, simplified to at most 60 points. Cache it in `backend/data/paths.json` keyed `"A-B"`. Fall back to a straight line `[[lonA,latA],[lonB,latB]]`.
  - `prefetch_paths(pairs)` warms the path cache. Run it for every origin-destination pair in the generated scenario plus all city pairs within 1,500 km. Commit `paths.json`. Sleep 0.2 s between calls to be polite to the public server.
- **Commit now:** "cities + OSRM matrix + paths cache".

## P0-2: Scenario generator (next 30 min)

`backend/data/generator.py` provides `generate_scenario(seed=42, n_trucks=20, n_owners=6, n_loads=140) -> dict` (Scenario shape) and writes `backend/data/scenario.json`.

- **Owners:** realistic small Indian transport names (e.g. "Raju Transport", "Sri Murugan Logistics", "Balaji Roadways"). Home cities are spread across TPR, NSK, JAI, NAG, LDH and HYD, with 2–5 trucks each.
- **Trucks:** about 60% open_body, 30% container and 10% reefer. Capacity is 9, 16, 21 or 25 t. Registration numbers use the state code of the home city (TN, MH, RJ, PB, TS…). Driver names and languages match the region (ta, hi, kn, en). Start mostly at home, some at other hubs. `available_from_h` is 0–24.
- **Loads:** draw from the seasonal flows in CONTRACT §5, weighted for the week of 9 Nov (onions, cotton, oranges and festival FMCG are heavy).
  - Freight = distance × uniform ₹38–55 per km (rounded to ₹100).
  - Cargo value by commodity (onions ₹4–8 lakh, textiles ₹15–30 lakh, pharma ₹40–80 lakh, …).
  - Weight fits a typical truck.
  - Pickup windows are 8–24 h wide and spread across days 0–6.
  - `deliver_by_h = pickup_end_h + elapsed_h(duration_h) + 3 + slack(12–36 h)`, capped at 168.
  - Source is 70% broker and 30% shipper.
- **Design for the demo:** the scenario must contain natural **chains**, meaning loads whose origin is near where earlier loads end, but **not** right at the destination at the right time. A one-trip-at-a-time greedy planner then wastes km, while a week-level optimiser finds loops. Target: CC's baseline has **at least 30% empty km**. Include the hero chain **TPR→DEL (textiles), DEL→JAI (FMCG), JAI→NAG (marble), NAG→TPR or NAG→BLR (oranges)** for truck T01.
- **E-way bills:** required when `cargo_value_inr > 50,000`. Validity is ceil(distance ÷ 200) days from pickup_start (in hours). For about 5% of loads, make the bill missing, expiring too early, or with a different vehicle registration, so the compliance demo catches it.
- **Deterministic:** use `random.Random(seed)` only.
- **`backend/tests/test_data.py`:** the shapes match the contract, all city codes are valid, the windows make sense (pickup_start < pickup_end < deliver_by ≤ 168), it is deterministic for the same seed, and the matrix is 25×25 with a zero diagonal.
- **Commit:** "scenario generator". Then **tell the user it's ready for Checkpoint 1.**

## P0-3: Compliance (`backend/engine/compliance.py`)

- `check_leg(leg, load, truck, config) -> ComplianceResult` (CONTRACT §4 codes). Empty legs only check `PERMIT_EXPIRED`.
  - E-way bill is missing and value > threshold: `EWAY_MISSING` (error).
  - `valid_until_h < leg.arrive_h`: `EWAY_EXPIRES` (error).
  - `vehicle_reg` ≠ `truck.reg_no`: `EWAY_VEHICLE_MISMATCH` (warning, because Part B can be updated).
  - Weight > capacity: `OVER_CAPACITY`. Type mismatch: `TRUCK_TYPE_MISMATCH`. Permit date before the week start: `PERMIT_EXPIRED`.
- `check_plan(plan, scenario, config) -> {"T01#0": ComplianceResult, ...}`.
- **`backend/tests/test_compliance.py`:** at least one test per issue code.

## P0-4: Forecasting (`backend/forecast/forecaster.py`)

- **Lanes:** one per (origin, destination, commodity) in CONTRACT §5, about 40 lanes. Lane id `"NSK-DEL"`. If the same OD pair has two commodities, append the commodity, e.g. `"NSK-DEL-ONI"`.
- `build_history(seed)` generates **104 weekly points** ending the week before 2026-11-09:
  - base volume per lane (3–20 loads a week)
  - plus yearly seasonality for the commodity's peak months (smooth cosine bump)
  - plus a festival bump for FMCG (Sep–Nov)
  - plus mild trend and Poisson-like noise.
  - Cache it to `backend/forecast/history.json`.
- `forecast_lanes(weeks_ahead=4)`: per lane, fit `statsmodels.tsa.holtwinters.ExponentialSmoothing(trend="add", seasonal="add", seasonal_periods=52)`. If the fit fails, fall back to seasonal naive. The band is ±1.96 × residual std, clipped at 0. `change_pct` compares next week with the mean of the last 4 weeks. Return Forecast[] in the contract shape. Cache the result (`forecast.json`) so the API responds instantly.
- `hot_lanes(n=8)`: the top n by `forecast[0].loads`, with ties broken by `change_pct`. Onion lanes out of NSK and orange lanes out of NAG should rank near the top for the week of 9 Nov.
- Add a test for the shapes and to check that hot lanes is non-empty.

## P1: Forecast loads for the optimiser

`forecast_loads(week_start_h=168) -> list[Load]` returns 10–15 expected loads for next week from the hot lanes, with a `probability` field between 0 and 1. CX1 may use these.

## P1: Real fuel price

If PPAC or a reliable source is reachable, put the current Bengaluru diesel price in `backend/data/assumptions.json` as `{"diesel_inr_per_l": ..., "source": ..., "fetched": ...}`. Otherwise write 90 with source "assumption". **Do not edit `app/config.py`.** CC will read this file.

---

After each item, commit and print a short status: what works, key numbers (e.g. matrix source, number of loads per commodity), and anything blocked.
