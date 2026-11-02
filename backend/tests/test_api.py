"""Integration tests for the FastAPI app. Owned by CC (CONTRACT §8)."""
import pytest
from fastapi.testclient import TestClient

from app.main import STATE, app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_scenario(client):
    r = client.get("/api/scenario")
    assert r.status_code == 200
    body = r.json()
    assert "cities" in body and "trucks" in body and "loads" in body
    assert len(body["trucks"]) == len(STATE["scenario"]["trucks"])


def test_plan_baseline_shape(client):
    r = client.post("/api/plan", json={"mode": "baseline"})
    assert r.status_code == 200
    plan = r.json()
    assert plan["mode"] == "baseline"
    assert plan["plan_id"].startswith("baseline-")
    assert "metrics" in plan
    for truck_plan in plan["trucks"]:
        for leg in truck_plan["legs"]:
            assert "from" in leg and "to" in leg
            assert leg["kind"] in ("loaded", "empty")


def test_plan_ai_returns_503_until_optimizer_merged(client):
    try:
        import engine.optimizer  # noqa: F401
        pytest.skip("optimizer already merged; 503 path not applicable")
    except ImportError:
        pass
    r = client.post("/api/plan", json={"mode": "ai"})
    assert r.status_code == 503
    assert r.json() == {"detail": "module not merged yet"}


def test_get_plan_by_id_roundtrip(client):
    created = client.post("/api/plan", json={"mode": "baseline"}).json()
    r = client.get(f"/api/plan/{created['plan_id']}")
    assert r.status_code == 200
    assert r.json()["plan_id"] == created["plan_id"]


def test_get_plan_missing_404(client):
    r = client.get("/api/plan/does-not-exist")
    assert r.status_code == 404


def test_compare_baseline_vs_ai(client):
    r = client.get("/api/compare")
    try:
        import engine.optimizer  # noqa: F401
    except ImportError:
        assert r.status_code == 503
        return
    assert r.status_code == 200
    body = r.json()
    assert body["ai"]["empty_km"] < body["baseline"]["empty_km"]
    assert body["ai"]["profit_inr"] > body["baseline"]["profit_inr"]


def test_truck_week(client):
    truck_id = STATE["scenario"]["trucks"][0]["id"]
    r = client.get(f"/api/trucks/{truck_id}/week")
    assert r.status_code == 200
    body = r.json()
    assert body["truck"]["id"] == truck_id
    assert body["plan"]["truck_id"] == truck_id


def test_truck_week_unknown_truck_404(client):
    r = client.get("/api/trucks/NOPE/week")
    assert r.status_code == 404


def test_owner_summary(client):
    owner_id = STATE["scenario"]["owners"][0]["id"]
    r = client.get(f"/api/owners/{owner_id}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["owner"]["id"] == owner_id
    assert "metrics" in body and "trucks" in body


def test_forecast_503_until_merged(client):
    try:
        import forecast.forecaster  # noqa: F401
        pytest.skip("forecaster already merged; 503 path not applicable")
    except ImportError:
        pass
    r = client.get("/api/forecast")
    assert r.status_code == 503


def test_hot_lanes_503_until_merged(client):
    try:
        import forecast.forecaster  # noqa: F401
        pytest.skip("forecaster already merged; 503 path not applicable")
    except ImportError:
        pass
    r = client.get("/api/hot-lanes")
    assert r.status_code == 503


def test_compliance_503_until_merged(client):
    load_id = STATE["scenario"]["loads"][0]["id"]
    try:
        import engine.compliance  # noqa: F401
        pytest.skip("compliance already merged; 503 path not applicable")
    except ImportError:
        pass
    r = client.get(f"/api/compliance/{load_id}")
    assert r.status_code == 503


def test_compliance_unknown_load_404(client):
    r = client.get("/api/compliance/NOPE")
    assert r.status_code == 404


def test_replan_503_until_merged(client):
    try:
        import engine.replan  # noqa: F401
        pytest.skip("replan already merged; 503 path not applicable")
    except ImportError:
        pass
    created = client.post("/api/plan", json={"mode": "baseline"}).json()
    r = client.post("/api/replan", json={"plan_id": created["plan_id"], "event": {"type": "cancel_load", "load_id": "L001", "at_h": 10}})
    assert r.status_code == 503
