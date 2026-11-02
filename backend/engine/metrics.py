"""Metrics engine. Owned by CC. Plain dict/list in, plain dict/list out (CONTRACT §4/§6)."""


def leg_costs(distance_km: float, config: dict) -> dict:
    """Diesel INR, toll INR and CO2 kg for one leg of distance_km."""
    litres = distance_km / config["mileage_kmpl"]
    diesel_inr = litres * config["diesel_inr_per_l"]
    toll_inr = distance_km * config["toll_inr_per_km"]
    co2_kg = litres * config["co2_kg_per_l"]
    return {"diesel_inr": diesel_inr, "toll_inr": toll_inr, "co2_kg": co2_kg}


def compute_metrics(plan: dict, scenario: dict) -> dict:
    """Fill each truck's totals and the plan's fleet-wide metrics (Metrics shape, CONTRACT §4)."""
    total_km = loaded_km = empty_km = 0.0
    revenue_inr = diesel_inr = toll_inr = co2_kg = 0.0
    idle_h = 0.0
    served_load_ids = set()
    trucks_used = 0

    for truck_plan in plan["trucks"]:
        legs = sorted(truck_plan["legs"], key=lambda leg: leg["seq"])
        t_total_km = t_loaded_km = t_empty_km = 0.0
        t_revenue = t_diesel = t_toll = t_co2 = 0.0
        t_idle_h = 0.0

        prev_arrive_h = None
        for leg in legs:
            dist = leg["distance_km"]
            t_total_km += dist
            if leg["kind"] == "loaded":
                t_loaded_km += dist
                served_load_ids.add(leg["load_id"])
            else:
                t_empty_km += dist
            t_revenue += leg.get("revenue_inr", 0) or 0
            t_diesel += leg["diesel_inr"]
            t_toll += leg["toll_inr"]
            t_co2 += leg["co2_kg"]

            if prev_arrive_h is not None:
                gap = leg["depart_h"] - prev_arrive_h
                if gap > 0:
                    t_idle_h += gap
            prev_arrive_h = leg["arrive_h"]

        if legs:
            trucks_used += 1

        truck_plan["totals"] = {
            "total_km": round(t_total_km, 1),
            "loaded_km": round(t_loaded_km, 1),
            "empty_km": round(t_empty_km, 1),
            "empty_pct": round(100.0 * t_empty_km / t_total_km, 1) if t_total_km else 0.0,
            "revenue_inr": int(round(t_revenue)),
            "diesel_inr": int(round(t_diesel)),
            "toll_inr": int(round(t_toll)),
            "profit_inr": int(round(t_revenue - t_diesel - t_toll)),
            "co2_kg": round(t_co2, 1),
            "loads_served": sum(1 for leg in legs if leg["kind"] == "loaded"),
            "loads_total": len(scenario["loads"]),
            "trucks_used": 1 if legs else 0,
            "idle_h": round(t_idle_h, 1),
        }

        total_km += t_total_km
        loaded_km += t_loaded_km
        empty_km += t_empty_km
        revenue_inr += t_revenue
        diesel_inr += t_diesel
        toll_inr += t_toll
        co2_kg += t_co2
        idle_h += t_idle_h

    loads_total = len(scenario["loads"])
    metrics = {
        "total_km": round(total_km, 1),
        "loaded_km": round(loaded_km, 1),
        "empty_km": round(empty_km, 1),
        "empty_pct": round(100.0 * empty_km / total_km, 1) if total_km else 0.0,
        "revenue_inr": int(round(revenue_inr)),
        "diesel_inr": int(round(diesel_inr)),
        "toll_inr": int(round(toll_inr)),
        "profit_inr": int(round(revenue_inr - diesel_inr - toll_inr)),
        "co2_kg": round(co2_kg, 1),
        "loads_served": len(served_load_ids),
        "loads_total": loads_total,
        "trucks_used": trucks_used,
        "idle_h": round(idle_h, 1),
    }
    plan["metrics"] = metrics
    return metrics
