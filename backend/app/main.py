"""LoopLoad API. Owned by CC. Endpoints per docs/CONTRACT.md §7.

Modules owned by other agents (optimizer, replan, forecast, compliance, the real
data generator) are imported lazily. Until they land on main, the dependent
endpoints return HTTP 503 {"detail": "module not merged yet"}.
"""
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import CONFIG
from app.schemas import (
    Compare,
    Forecast,
    HealthResponse,
    OwnerSummaryResponse,
    Plan,
    PlanRequest,
    RegenerateRequest,
    ReplanRequest,
    Scenario,
    TruckWeekResponse,
)
from engine.baseline import plan_baseline
from engine.metrics import compute_metrics

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")

STATE = {"scenario": None, "matrix": None, "plans": {}, "latest_by_mode": {}}


def _load_mini_fixture():
    with open(os.path.join(FIXTURES_DIR, "mini_scenario.json")) as f:
        scenario = json.load(f)
    with open(os.path.join(FIXTURES_DIR, "mini_matrix.json")) as f:
        matrix = json.load(f)
    return scenario, matrix


def _load_scenario_and_matrix(seed: int = 42, n_trucks: int = 20, n_loads: int = 140):
    """Real data if CX2's generator/matrix are merged, else the local mini fixture."""
    try:
        from data.distance import get_matrix
        from data.generator import generate_scenario
    except ImportError:
        return _load_mini_fixture()
    scenario = generate_scenario(seed=seed, n_trucks=n_trucks, n_loads=n_loads)
    matrix = get_matrix(scenario["cities"])
    return scenario, matrix


def _apply_assumptions_override():
    """CX2 may drop backend/data/assumptions.json with a researched diesel price."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "assumptions.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        overrides = json.load(f)
    if "diesel_inr_per_l" in overrides:
        CONFIG["diesel_inr_per_l"] = overrides["diesel_inr_per_l"]


def _fill_paths_and_compliance(plan: dict) -> dict:
    """Fill leg.path (CX2 get_path) and leg.compliance (CX2 check_leg) if those modules exist yet."""
    try:
        from data.distance import get_path
    except ImportError:
        get_path = None
    try:
        from engine.compliance import check_leg
    except ImportError:
        check_leg = None

    if get_path is None and check_leg is None:
        return plan

    loads_by_id = {ld["id"]: ld for ld in STATE["scenario"]["loads"]}
    trucks_by_id = {t["id"]: t for t in STATE["scenario"]["trucks"]}
    for truck_plan in plan["trucks"]:
        truck = trucks_by_id.get(truck_plan["truck_id"])
        for leg in truck_plan["legs"]:
            if get_path is not None:
                leg["path"] = get_path(leg["from"], leg["to"])
            if check_leg is not None:
                load = loads_by_id.get(leg["load_id"]) if leg.get("load_id") else None
                leg["compliance"] = check_leg(leg, load, truck, CONFIG)
    return plan


def _build_plan(mode: str) -> dict:
    scenario, matrix = STATE["scenario"], STATE["matrix"]
    if mode == "baseline":
        plan = plan_baseline(scenario, matrix, CONFIG)
    elif mode in ("ai", "ai_solo"):
        try:
            from engine.optimizer import plan_optimized
        except ImportError:
            raise HTTPException(status_code=503, detail="module not merged yet")
        plan = plan_optimized(
            scenario, matrix, CONFIG, pooled=(mode == "ai"), time_limit_s=CONFIG["solver_time_limit_s"]
        )
    else:
        raise HTTPException(status_code=400, detail=f"unknown mode {mode!r}")
    return _fill_paths_and_compliance(plan)


def _get_or_create_plan(mode: str) -> dict:
    cached_id = STATE["latest_by_mode"].get(mode)
    if cached_id is not None and cached_id in STATE["plans"]:
        return STATE["plans"][cached_id]
    plan = _build_plan(mode)
    STATE["plans"][plan["plan_id"]] = plan
    STATE["latest_by_mode"][mode] = plan["plan_id"]
    return plan


def _resolve_plan(plan_id: Optional[str], default_mode: str = "baseline") -> dict:
    if plan_id:
        plan = STATE["plans"].get(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="plan not found")
        return plan
    return _get_or_create_plan(default_mode)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _apply_assumptions_override()
    scenario, matrix = _load_scenario_and_matrix()
    STATE["scenario"] = scenario
    STATE["matrix"] = matrix
    STATE["plans"] = {}
    STATE["latest_by_mode"] = {}
    yield


app = FastAPI(title="LoopLoad API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def get_health():
    return {"ok": True}


@app.get("/api/scenario", response_model=Scenario)
def get_scenario():
    return STATE["scenario"]


@app.post("/api/scenario/regenerate", response_model=Scenario)
def post_regenerate_scenario(req: RegenerateRequest):
    try:
        from data.distance import get_matrix
        from data.generator import generate_scenario
    except ImportError:
        raise HTTPException(status_code=503, detail="module not merged yet")
    scenario = generate_scenario(seed=req.seed, n_trucks=req.n_trucks, n_loads=req.n_loads)
    matrix = get_matrix(scenario["cities"])
    STATE["scenario"] = scenario
    STATE["matrix"] = matrix
    STATE["plans"] = {}
    STATE["latest_by_mode"] = {}
    return scenario


@app.post("/api/plan", response_model=Plan)
def post_plan(req: PlanRequest):
    return _get_or_create_plan(req.mode)


@app.get("/api/plan/{plan_id}", response_model=Plan)
def get_plan(plan_id: str):
    plan = STATE["plans"].get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    return plan


@app.get("/api/compare", response_model=Compare)
def get_compare():
    baseline_plan = _get_or_create_plan("baseline")
    ai_plan = _get_or_create_plan("ai")
    baseline_metrics = baseline_plan["metrics"]
    ai_metrics = ai_plan["metrics"]
    delta = {
        "empty_km": ai_metrics["empty_km"] - baseline_metrics["empty_km"],
        "empty_pct": round(ai_metrics["empty_pct"] - baseline_metrics["empty_pct"], 1),
        "profit_inr": ai_metrics["profit_inr"] - baseline_metrics["profit_inr"],
        "co2_kg": round(ai_metrics["co2_kg"] - baseline_metrics["co2_kg"], 1),
        "loads_served": ai_metrics["loads_served"] - baseline_metrics["loads_served"],
    }
    return {"baseline": baseline_metrics, "ai": ai_metrics, "delta": delta}


@app.post("/api/replan", response_model=Plan)
def post_replan(req: ReplanRequest):
    try:
        from engine.replan import replan
    except ImportError:
        raise HTTPException(status_code=503, detail="module not merged yet")
    plan = STATE["plans"].get(req.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    new_plan = replan(plan, req.event, STATE["scenario"], STATE["matrix"], CONFIG)
    _fill_paths_and_compliance(new_plan)
    STATE["plans"][new_plan["plan_id"]] = new_plan
    STATE["latest_by_mode"][new_plan["mode"]] = new_plan["plan_id"]
    return new_plan


@app.get("/api/trucks/{truck_id}/week", response_model=TruckWeekResponse)
def get_truck_week(truck_id: str, plan_id: Optional[str] = None):
    truck = next((t for t in STATE["scenario"]["trucks"] if t["id"] == truck_id), None)
    if truck is None:
        raise HTTPException(status_code=404, detail="truck not found")
    plan = _resolve_plan(plan_id)
    truck_plan = next((tp for tp in plan["trucks"] if tp["truck_id"] == truck_id), None)
    if truck_plan is None:
        raise HTTPException(status_code=404, detail="truck has no plan for this plan_id")
    return {"truck": truck, "plan": truck_plan}


@app.get("/api/owners/{owner_id}/summary", response_model=OwnerSummaryResponse)
def get_owner_summary(owner_id: str, plan_id: Optional[str] = None):
    owner = next((o for o in STATE["scenario"]["owners"] if o["id"] == owner_id), None)
    if owner is None:
        raise HTTPException(status_code=404, detail="owner not found")
    plan = _resolve_plan(plan_id)
    truck_plans = [tp for tp in plan["trucks"] if tp["truck_id"] in owner["trucks"]]
    sub_plan = {"trucks": [dict(tp, totals={}) for tp in truck_plans], "metrics": {}}
    metrics = compute_metrics(sub_plan, STATE["scenario"])
    return {"owner": owner, "metrics": metrics, "trucks": sub_plan["trucks"]}


@app.get("/api/forecast", response_model=list[Forecast])
def get_forecast(lane: Optional[str] = None):
    try:
        from forecast.forecaster import forecast_lanes
    except ImportError:
        raise HTTPException(status_code=503, detail="module not merged yet")
    forecasts = forecast_lanes()
    if lane:
        forecasts = [f for f in forecasts if f["lane"] == lane]
    return forecasts


@app.get("/api/hot-lanes", response_model=list[Forecast])
def get_hot_lanes(n: int = 8):
    try:
        from forecast.forecaster import hot_lanes
    except ImportError:
        raise HTTPException(status_code=503, detail="module not merged yet")
    return hot_lanes(n)


@app.get("/api/compliance/{load_id}")
def get_compliance(load_id: str, plan_id: Optional[str] = None):
    load = next((ld for ld in STATE["scenario"]["loads"] if ld["id"] == load_id), None)
    if load is None:
        raise HTTPException(status_code=404, detail="load not found")
    try:
        from engine.compliance import check_leg
    except ImportError:
        raise HTTPException(status_code=503, detail="module not merged yet")
    plan = _resolve_plan(plan_id)
    leg = next(
        (leg for tp in plan["trucks"] for leg in tp["legs"] if leg.get("load_id") == load_id),
        None,
    )
    if leg is None:
        return {"ok": True, "issues": []}
    truck = next((t for t in STATE["scenario"]["trucks"] if t["id"] == leg["truck_id"]), None)
    return check_leg(leg, load, truck, CONFIG)
