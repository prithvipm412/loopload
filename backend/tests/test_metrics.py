import json
import os

from app.config import CONFIG
from engine.baseline import plan_baseline
from engine.metrics import compute_metrics, leg_costs

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture():
    with open(os.path.join(FIXTURES, "mini_scenario.json")) as f:
        scenario = json.load(f)
    with open(os.path.join(FIXTURES, "mini_matrix.json")) as f:
        matrix = json.load(f)
    return scenario, matrix


def test_leg_costs_formula():
    costs = leg_costs(100.0, CONFIG)
    litres = 100.0 / CONFIG["mileage_kmpl"]
    assert costs["diesel_inr"] == litres * CONFIG["diesel_inr_per_l"]
    assert costs["toll_inr"] == 100.0 * CONFIG["toll_inr_per_km"]
    assert costs["co2_kg"] == litres * CONFIG["co2_kg_per_l"]


def test_compute_metrics_matches_plan_baseline_fixture():
    scenario, matrix = load_fixture()
    plan = plan_baseline(scenario, matrix, CONFIG)
    metrics = plan["metrics"]

    assert metrics["loads_total"] == len(scenario["loads"]) == 12
    assert metrics["loads_served"] == 12 - len(plan["unassigned_loads"])
    assert metrics["total_km"] == round(metrics["loaded_km"] + metrics["empty_km"], 1)
    if metrics["total_km"]:
        assert metrics["empty_pct"] == round(100.0 * metrics["empty_km"] / metrics["total_km"], 1)
    assert metrics["profit_inr"] == metrics["revenue_inr"] - metrics["diesel_inr"] - metrics["toll_inr"]

    for truck_plan in plan["trucks"]:
        totals = truck_plan["totals"]
        assert totals["loads_total"] == 12
        loaded_legs = [leg for leg in truck_plan["legs"] if leg["kind"] == "loaded"]
        assert totals["loads_served"] == len(loaded_legs)


def test_compute_metrics_recompute_is_idempotent():
    scenario, matrix = load_fixture()
    plan = plan_baseline(scenario, matrix, CONFIG)
    first = plan["metrics"]
    second = compute_metrics(plan, scenario)
    assert first == second
