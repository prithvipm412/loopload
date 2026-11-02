# LoopLoad: Shared Contract

**Every agent must follow this file.** It lets four agents build in parallel without waiting on each other.
If you need to change something here, stop and tell the user. Do not change it silently.

---

## 1. Conventions

- **Language:** Python 3.11+ for the backend; TypeScript + React for the frontend.
- **Engine functions take and return plain `dict`/`list` objects** with exactly the JSON shapes below. Do **not** import Pydantic models across modules. Only the API layer (CC) wraps them in Pydantic.
- **Time:** `float` hours from `scenario.week_start`. `0.0` is Monday 00:00 IST, and the planning horizon is `0–168` h.
- **Money:** `int` rupees (INR). **Distance:** `float` km, 1 decimal. **CO₂:** `float` kg.
- **IDs:** cities `"BLR"`, owners `"O1"`, trucks `"T01"`, loads `"L001"`, plans `"baseline-<uuid8>"` / `"ai-<uuid8>"`.
- **Coordinates** in paths are `[lon, lat]`, the deck.gl order.

## 2. Cities (fixed list, 25 hubs)

| code | name | state | lat | lon |
|---|---|---|---|---|
| DEL | Delhi | Delhi | 28.61 | 77.21 |
| MUM | Mumbai | Maharashtra | 19.08 | 72.88 |
| BLR | Bengaluru | Karnataka | 12.97 | 77.59 |
| CHE | Chennai | Tamil Nadu | 13.08 | 80.27 |
| HYD | Hyderabad | Telangana | 17.39 | 78.49 |
| KOL | Kolkata | West Bengal | 22.57 | 88.36 |
| AMD | Ahmedabad | Gujarat | 23.02 | 72.57 |
| PUN | Pune | Maharashtra | 18.52 | 73.86 |
| JAI | Jaipur | Rajasthan | 26.91 | 75.79 |
| NAG | Nagpur | Maharashtra | 21.15 | 79.09 |
| NSK | Nashik | Maharashtra | 19.99 | 73.79 |
| TPR | Tiruppur | Tamil Nadu | 11.11 | 77.34 |
| CBE | Coimbatore | Tamil Nadu | 11.02 | 76.96 |
| IDR | Indore | Madhya Pradesh | 22.72 | 75.86 |
| SRT | Surat | Gujarat | 21.17 | 72.83 |
| LDH | Ludhiana | Punjab | 30.90 | 75.86 |
| KNP | Kanpur | Uttar Pradesh | 26.45 | 80.33 |
| LKO | Lucknow | Uttar Pradesh | 26.85 | 80.95 |
| VTZ | Visakhapatnam | Andhra Pradesh | 17.69 | 83.22 |
| COK | Kochi | Kerala | 9.93 | 76.27 |
| RPR | Raipur | Chhattisgarh | 21.25 | 81.63 |
| BPL | Bhopal | Madhya Pradesh | 23.26 | 77.41 |
| RJK | Rajkot | Gujarat | 22.30 | 70.80 |
| MDU | Madurai | Tamil Nadu | 9.93 | 78.12 |
| VGA | Vijayawada | Andhra Pradesh | 16.51 | 80.65 |

## 3. Config constants (`backend/app/config.py`, owned by CC; others read via `from app.config import CONFIG` or receive it as a dict)

```python
CONFIG = {
  "week_start": "2026-11-09T00:00:00+05:30",
  "horizon_h": 168,
  "diesel_inr_per_l": 90,        # assumption, update from PPAC if time
  "mileage_kmpl": 4.0,           # loaded HCV assumption
  "toll_inr_per_km": 5,          # assumption
  "co2_kg_per_l": 2.68,          # standard diesel factor
  "avg_speed_kmph": 45,          # used only if OSRM durations missing
  "max_drive_h_per_day": 10,     # driver rest rule used by planners
  "load_unload_h": 3,            # service time at pickup and at delivery
  "baseline_wait_max_h": 48,     # baseline: how long a truck waits for a return load
  "baseline_search_radius_km": 150,
  "eway_threshold_inr": 50000,
  "eway_km_per_day": 200,
  "solver_time_limit_s": 10,
}
```

Derived: `cost_per_km = diesel_inr_per_l / mileage_kmpl + toll_inr_per_km` (= ₹27.5/km).

Driving-rest rule, used by both planners: `elapsed_h(drive_h) = drive_h + floor(drive_h / max_drive_h_per_day) * (24 - max_drive_h_per_day)`.

## 4. JSON shapes

### Scenario (`backend/data/scenario.json`, from `generate_scenario`)
```json
{
  "week_start": "2026-11-09T00:00:00+05:30",
  "cities": [{"id":"BLR","name":"Bengaluru","state":"Karnataka","lat":12.97,"lon":77.59}],
  "owners": [{"id":"O1","name":"Raju Transport","home_city":"TPR","trucks":["T01","T02"]}],
  "trucks": [{
    "id":"T01","owner_id":"O1","reg_no":"TN39AB1234",
    "type":"open_body",                 // "open_body" | "container" | "reefer"
    "capacity_t":16,
    "home_city":"TPR","start_city":"TPR","available_from_h":0,
    "national_permit_valid_until":"2027-03-31",
    "driver":{"name":"Murugan","language":"ta"}   // "en"|"hi"|"kn"|"ta"
  }],
  "loads": [{
    "id":"L001","origin":"TPR","destination":"DEL",
    "commodity":"Textiles","weight_t":12,"truck_type":"open_body",
    "pickup_start_h":2,"pickup_end_h":20,"deliver_by_h":80,
    "freight_inr":96000,"cargo_value_inr":1800000,
    "source":"broker",                  // "broker" | "shipper"
    "eway_bill":{"number":"EWB1234567890","valid_until_h":96,"vehicle_reg":"TN39AB1234"}  // or null
  }]
}
```

### Matrix (`backend/data/matrix.json`)
```json
{"cities":["DEL","MUM",...],"distance_km":[[0,1415.2,...],...],"duration_h":[[0,24.1,...],...],"source":"osrm"}
```

### Leg
```json
{
  "truck_id":"T01","seq":0,
  "kind":"loaded",                      // "loaded" | "empty"
  "from":"TPR","to":"DEL","load_id":"L001",   // load_id null for empty legs
  "depart_h":5.0,"arrive_h":62.4,
  "distance_km":2385.4,
  "revenue_inr":96000,"diesel_inr":53672,"toll_inr":11927,"co2_kg":1598.2,
  "path":[[77.34,11.11],[77.21,28.61]],
  "compliance":{"ok":true,"issues":[]}  // filled by API using check_leg; engines may omit
}
```

### TruckPlan and Plan
```json
{
  "plan_id":"ai-3f9a1c2b","mode":"ai",          // "baseline" | "ai" | "ai_solo"
  "created_at":"2026-11-02T22:40:00+05:30",
  "solve_time_s":8.2,
  "trucks":[{"truck_id":"T01","legs":[/* Leg */],"totals":{/* Metrics for this truck */}}],
  "unassigned_loads":["L087","L101"],
  "metrics":{/* Metrics for whole fleet */}
}
```

### Metrics
```json
{"total_km":41230.5,"loaded_km":35110.0,"empty_km":6120.5,"empty_pct":14.8,
 "revenue_inr":1850000,"diesel_inr":927686,"toll_inr":206152,"profit_inr":716162,
 "co2_kg":27622.4,"loads_served":118,"loads_total":140,"trucks_used":20,"idle_h":312.0}
```

### Compare
```json
{"baseline":{/*Metrics*/},"ai":{/*Metrics*/},
 "delta":{"empty_km":-9800.2,"empty_pct":-22.1,"profit_inr":412000,"co2_kg":-6580.0,"loads_served":31}}
```

### Forecast
```json
{"lane":"NSK-DEL","origin":"NSK","destination":"DEL","commodity":"Onions",
 "history":[{"week":"2024-11-11","loads":14}],
 "forecast":[{"week":"2026-11-09","loads":22.4,"lower":17.1,"upper":27.7}],
 "change_pct":31.5}
```

### ComplianceResult
```json
{"ok":false,"issues":[{"code":"EWAY_EXPIRES","severity":"error",
  "message":"E-way bill expires at 96h but delivery is planned at 104h"}]}
```
Codes: `EWAY_MISSING`, `EWAY_EXPIRES`, `EWAY_VEHICLE_MISMATCH`, `OVER_CAPACITY`, `TRUCK_TYPE_MISMATCH`, `PERMIT_EXPIRED`. Severity: `error` | `warning`.

### Replan event
```json
{"type":"cancel_load","load_id":"L014","at_h":30}
{"type":"delay_truck","truck_id":"T05","delay_h":12,"at_h":30}
{"type":"new_load","load":{/* Load */},"at_h":30}
```

## 5. Seasonal flows for the generator (week of 9 Nov = peak onion/cotton/orange/festival season)

| Commodity | Origins → Destinations | Truck type | Season peak |
|---|---|---|---|
| Onions | NSK → DEL, KOL, CHE, BLR, HYD | open_body | Oct–Jan |
| Cotton bales | RJK, AMD → TPR, CBE | open_body | Oct–Mar |
| Textiles | TPR, SRT → DEL, MUM, KOL, JAI | container | all year |
| Oranges | NAG → DEL, BLR, HYD, CHE | open_body | Nov–Feb |
| Marble | JAI → BLR, HYD, MUM, PUN | open_body | all year |
| Machinery / auto parts | PUN, CHE → DEL, BLR, AMD, LDH | container | all year |
| FMCG | MUM, DEL, KOL → all | container | Sep–Nov (festival) |
| Steel | RPR, VTZ → HYD, BLR, CHE, NAG | open_body | all year |
| Wheat | LDH, KNP → BLR, HYD, MUM | open_body | Apr–Jun |
| Spices | COK → DEL, MUM, AMD | container | all year |
| Pharma | HYD, AMD → all | reefer | all year |

## 6. Python function signatures (who owns what)

```python
# CX2 — backend/data/distance.py
def get_matrix(cities: list[dict]) -> dict                    # Matrix shape; cached
def get_path(a: str, b: str) -> list[list[float]]             # [[lon,lat],...]; cached

# CX2 — backend/data/generator.py
def generate_scenario(seed: int = 42, n_trucks: int = 20, n_owners: int = 6, n_loads: int = 140) -> dict

# CX2 — backend/forecast/forecaster.py
def build_history(seed: int = 42) -> dict[str, list[dict]]     # lane -> [{week, loads}]
def forecast_lanes(weeks_ahead: int = 4) -> list[dict]         # Forecast[]
def hot_lanes(n: int = 8) -> list[dict]                        # Forecast[] sorted by forecast[0].loads

# CX2 — backend/engine/compliance.py
def check_leg(leg: dict, load: dict | None, truck: dict, config: dict) -> dict   # ComplianceResult
def check_plan(plan: dict, scenario: dict, config: dict) -> dict  # {leg_key: ComplianceResult}

# CX1 — backend/engine/optimizer.py
def plan_optimized(scenario: dict, matrix: dict, config: dict,
                   pooled: bool = True, time_limit_s: int | None = None) -> dict   # Plan, mode "ai" or "ai_solo"

# CX1 — backend/engine/replan.py
def replan(plan: dict, event: dict, scenario: dict, matrix: dict, config: dict) -> dict  # new Plan

# CC — backend/engine/baseline.py
def plan_baseline(scenario: dict, matrix: dict, config: dict) -> dict   # Plan, mode "baseline"

# CC — backend/engine/metrics.py  (CX1 may import it read-only)
def leg_costs(distance_km: float, config: dict) -> dict         # {diesel_inr, toll_inr, co2_kg}
def compute_metrics(plan: dict, scenario: dict) -> dict          # Metrics; also fills truck totals
```

The engines leave `path` empty (`[]`). The API fills paths with `get_path` before responding, so the engines stay fast.

## 7. REST API (CC, FastAPI, base `/api`, port 8000)

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/health` | | `{"ok":true}` |
| GET | `/api/scenario` | | Scenario |
| POST | `/api/scenario/regenerate` | `{"seed":42,"n_trucks":20,"n_loads":140}` | Scenario |
| POST | `/api/plan` | `{"mode":"baseline"\|"ai"\|"ai_solo"}` | Plan (with paths + compliance) |
| GET | `/api/plan/{plan_id}` | | Plan |
| GET | `/api/compare` | | Compare (computes and caches both plans if missing) |
| POST | `/api/replan` | `{"plan_id":"ai-…","event":{…}}` | Plan |
| GET | `/api/trucks/{truck_id}/week` | `?plan_id=` | `{"truck":Truck,"plan":TruckPlan}` |
| GET | `/api/owners/{owner_id}/summary` | `?plan_id=` | `{"owner":Owner,"metrics":Metrics,"trucks":[TruckPlan]}` |
| GET | `/api/forecast` | `?lane=NSK-DEL` (optional) | Forecast[] |
| GET | `/api/hot-lanes` | `?n=8` | Forecast[] |
| GET | `/api/compliance/{load_id}` | `?plan_id=` | ComplianceResult |

## 8. File ownership (do not edit files you don't own)

| Path | Owner |
|---|---|
| `backend/app/**`, `backend/engine/baseline.py`, `backend/engine/metrics.py`, `backend/tests/test_api.py`, `run.sh`, `Makefile`, `README.md`, `docs/**` | **CC** |
| `backend/engine/optimizer.py`, `backend/engine/replan.py`, `backend/tests/test_optimizer.py` | **CX1** |
| `backend/data/**`, `backend/forecast/**`, `backend/engine/compliance.py`, `backend/tests/test_data.py`, `backend/tests/test_compliance.py` | **CX2** |
| `frontend/**` | **CX3** |
| `backend/requirements.txt` | CC only. Others ask the user to request new packages. |
