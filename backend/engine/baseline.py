"""Baseline planner: how fleets work today, one trip at a time. Owned by CC."""
import heapq
import uuid
from datetime import datetime, timedelta, timezone

from app.config import cost_per_km, elapsed_h
from engine.metrics import compute_metrics, leg_costs

IST = timezone(timedelta(hours=5, minutes=30))

# Cities a dispatcher would reposition an idle truck toward, since demand is
# usually easiest to find at a major freight hub.
MAJOR_HUBS = ["DEL", "MUM", "BLR", "CHE", "HYD", "KOL", "AMD"]


def _now_iso() -> str:
    return datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S+05:30")


def _make_leg(truck_id, seq, kind, frm, to, load_id, depart_h, arrive_h, distance_km, revenue_inr, config) -> dict:
    costs = leg_costs(distance_km, config)
    return {
        "truck_id": truck_id,
        "seq": seq,
        "kind": kind,
        "from": frm,
        "to": to,
        "load_id": load_id,
        "depart_h": round(depart_h, 1),
        "arrive_h": round(arrive_h, 1),
        "distance_km": round(distance_km, 1),
        "revenue_inr": int(round(revenue_inr)),
        "diesel_inr": int(round(costs["diesel_inr"])),
        "toll_inr": int(round(costs["toll_inr"])),
        "co2_kg": round(costs["co2_kg"], 1),
        "path": [],
    }


def plan_baseline(scenario: dict, matrix: dict, config: dict) -> dict:
    """Greedy, one-trip-at-a-time simulation of how a small fleet operates without pooling."""
    city_idx = {c: i for i, c in enumerate(matrix["cities"])}
    distance_m = matrix["distance_km"]
    duration_m = matrix["duration_h"]

    def dist(a, b):
        return distance_m[city_idx[a]][city_idx[b]]

    def dur(a, b):
        return duration_m[city_idx[a]][city_idx[b]]

    horizon_h = config["horizon_h"]
    load_unload_h = config["load_unload_h"]
    wait_max_h = config["baseline_wait_max_h"]
    search_radius_km = config["baseline_search_radius_km"]
    cpk = cost_per_km(config)

    loads_by_id = {ld["id"]: ld for ld in scenario["loads"]}
    unassigned = set(loads_by_id.keys())

    hubs_in_matrix = [h for h in MAJOR_HUBS if h in city_idx] or list(city_idx)

    def nearest_major_hub(pos):
        return min(hubs_in_matrix, key=lambda h: dist(pos, h))

    def unassigned_origin_count(city):
        return sum(1 for lid in unassigned if loads_by_id[lid]["origin"] == city)

    trucks_state = {}
    heap = []
    for truck in scenario["trucks"]:
        trucks_state[truck["id"]] = {
            "truck": truck,
            "pos": truck["start_city"],
            "free_h": float(truck["available_from_h"]),
            "wait_h": 0.0,
            "legs": [],
            "seq": 0,
        }
        heapq.heappush(heap, (float(truck["available_from_h"]), truck["id"]))

    def feasible(state, load):
        truck = state["truck"]
        if truck["type"] != load["truck_type"]:
            return None
        if load["weight_t"] > truck["capacity_t"]:
            return None
        pos = state["pos"]
        t = state["free_h"]
        if pos == load["origin"]:
            d_empty = 0.0
            arrive_origin = t
        else:
            d_empty = dist(pos, load["origin"])
            if d_empty > search_radius_km:
                return None
            arrive_origin = t + elapsed_h(dur(pos, load["origin"]), config)
        if arrive_origin > load["pickup_end_h"]:
            return None
        pickup_begin = max(arrive_origin, load["pickup_start_h"])
        if pickup_begin > load["pickup_end_h"]:
            return None
        loaded_depart = pickup_begin + load_unload_h
        loaded_arrive = loaded_depart + elapsed_h(dur(load["origin"], load["destination"]), config)
        if loaded_arrive > load["deliver_by_h"]:
            return None
        d_loaded = dist(load["origin"], load["destination"])
        delivery_complete = loaded_arrive + load_unload_h

        # Only take trips that are profitable on their own (a real dispatcher
        # would not drive a loss-making lane), ranked by profit per hour busy
        # rather than by nearest origin.
        trip_profit = load["freight_inr"] - cpk * (d_empty + d_loaded)
        if trip_profit <= 0:
            return None
        hours_busy = delivery_complete - t
        score = trip_profit / hours_busy if hours_busy > 0 else trip_profit

        return {
            "d_empty": d_empty,
            "empty_depart": t,
            "empty_arrive": arrive_origin,
            "loaded_depart": loaded_depart,
            "loaded_arrive": loaded_arrive,
            "delivery_complete": delivery_complete,
            "d_loaded": d_loaded,
            "trip_profit": trip_profit,
            "score": score,
        }

    while heap:
        free_h, truck_id = heapq.heappop(heap)
        state = trucks_state[truck_id]
        if free_h != state["free_h"]:
            continue
        if state["free_h"] >= horizon_h:
            continue

        best_load, best_plan = None, None
        for lid in sorted(unassigned):
            plan_info = feasible(state, loads_by_id[lid])
            if plan_info is None:
                continue
            if best_plan is None or plan_info["score"] > best_plan["score"]:
                best_load, best_plan = loads_by_id[lid], plan_info

        if best_load is not None:
            pos = state["pos"]
            if best_plan["d_empty"] > 0:
                state["legs"].append(_make_leg(
                    truck_id, state["seq"], "empty", pos, best_load["origin"], None,
                    best_plan["empty_depart"], best_plan["empty_arrive"], best_plan["d_empty"], 0, config))
                state["seq"] += 1
            state["legs"].append(_make_leg(
                truck_id, state["seq"], "loaded", best_load["origin"], best_load["destination"], best_load["id"],
                best_plan["loaded_depart"], best_plan["loaded_arrive"], best_plan["d_loaded"],
                best_load["freight_inr"], config))
            state["seq"] += 1
            state["pos"] = best_load["destination"]
            state["free_h"] = best_plan["delivery_complete"]
            state["wait_h"] = 0.0
            unassigned.discard(best_load["id"])
            heapq.heappush(heap, (state["free_h"], truck_id))
            continue

        if state["wait_h"] + 6.0 <= wait_max_h and state["free_h"] + 6.0 <= horizon_h:
            state["wait_h"] += 6.0
            state["free_h"] += 6.0
            heapq.heappush(heap, (state["free_h"], truck_id))
            continue

        # Wait budget spent with nothing profitable found: reposition to
        # wherever demand looks better (a major hub) rather than reflexively
        # going home, then keep searching for the rest of the week.
        truck = state["truck"]
        pos = state["pos"]
        home = truck["home_city"]
        hub = nearest_major_hub(pos)
        target = hub if unassigned_origin_count(hub) > unassigned_origin_count(home) else home
        if pos != target:
            d_move = dist(pos, target)
            depart = state["free_h"]
            arrive = depart + elapsed_h(dur(pos, target), config)
            state["legs"].append(_make_leg(
                truck_id, state["seq"], "empty", pos, target, None, depart, arrive, d_move, 0, config))
            state["seq"] += 1
            state["pos"] = target
            state["free_h"] = arrive

        # Only stop for good once there is truly no horizon time left to fit
        # even one more 6h wait step (otherwise this would requeue forever
        # once parked with nothing to do).
        state["wait_h"] = 0.0
        if state["free_h"] + 6.0 > horizon_h:
            continue
        heapq.heappush(heap, (state["free_h"], truck_id))

    trucks_out = [
        {"truck_id": truck["id"], "legs": trucks_state[truck["id"]]["legs"], "totals": {}}
        for truck in scenario["trucks"]
    ]

    plan = {
        "plan_id": f"baseline-{uuid.uuid4().hex[:8]}",
        "mode": "baseline",
        "created_at": _now_iso(),
        "solve_time_s": 0.0,
        "trucks": trucks_out,
        "unassigned_loads": sorted(unassigned),
        "metrics": {},
    }
    compute_metrics(plan, scenario)
    return plan
