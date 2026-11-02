import json
import os

from app.config import CONFIG
from engine.baseline import plan_baseline

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture():
    with open(os.path.join(FIXTURES, "mini_scenario.json")) as f:
        scenario = json.load(f)
    with open(os.path.join(FIXTURES, "mini_matrix.json")) as f:
        matrix = json.load(f)
    return scenario, matrix


def test_plan_shape():
    scenario, matrix = load_fixture()
    plan = plan_baseline(scenario, matrix, CONFIG)

    assert plan["mode"] == "baseline"
    assert plan["plan_id"].startswith("baseline-")
    assert len(plan["trucks"]) == len(scenario["trucks"])
    truck_ids = {tp["truck_id"] for tp in plan["trucks"]}
    assert truck_ids == {t["id"] for t in scenario["trucks"]}
    for truck_plan in plan["trucks"]:
        for i, leg in enumerate(truck_plan["legs"]):
            assert leg["seq"] == i
            assert leg["kind"] in ("loaded", "empty")
            assert leg["path"] == []
            if leg["kind"] == "empty":
                assert leg["load_id"] is None
            else:
                assert leg["load_id"] is not None


def test_deterministic_across_runs():
    scenario, matrix = load_fixture()
    plan1 = plan_baseline(scenario, matrix, CONFIG)
    plan2 = plan_baseline(scenario, matrix, CONFIG)
    assert plan1["unassigned_loads"] == plan2["unassigned_loads"]
    for tp1, tp2 in zip(plan1["trucks"], plan2["trucks"]):
        legs1 = [(leg["kind"], leg["from"], leg["to"], leg["load_id"]) for leg in tp1["legs"]]
        legs2 = [(leg["kind"], leg["from"], leg["to"], leg["load_id"]) for leg in tp2["legs"]]
        assert legs1 == legs2


def test_rejects_wrong_truck_type_and_overweight_loads():
    scenario, matrix = load_fixture()
    plan = plan_baseline(scenario, matrix, CONFIG)
    assigned_load_ids = {
        leg["load_id"]
        for tp in plan["trucks"]
        for leg in tp["legs"]
        if leg["kind"] == "loaded"
    }
    # L009 (30t, exceeds every truck's capacity) and L010 (reefer, no such truck) must never be assigned.
    assert "L009" not in assigned_load_ids
    assert "L010" not in assigned_load_ids
    assert "L009" in plan["unassigned_loads"]
    assert "L010" in plan["unassigned_loads"]


def test_each_truck_chain_is_time_consistent():
    scenario, matrix = load_fixture()
    plan = plan_baseline(scenario, matrix, CONFIG)
    for truck_plan in plan["trucks"]:
        legs = truck_plan["legs"]
        for leg in legs:
            assert leg["depart_h"] <= leg["arrive_h"]
        for prev, nxt in zip(legs, legs[1:]):
            assert prev["to"] == nxt["from"]
            assert nxt["depart_h"] >= prev["arrive_h"]
