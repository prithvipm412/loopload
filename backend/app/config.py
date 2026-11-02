"""Shared constants for LoopLoad. Values match docs/CONTRACT.md section 3.
Owned by CC (Claude Code). Other agents receive CONFIG as a dict argument."""
import math

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


def cost_per_km(config: dict = CONFIG) -> float:
    """Diesel + toll cost per km in INR (27.5 with defaults)."""
    return config["diesel_inr_per_l"] / config["mileage_kmpl"] + config["toll_inr_per_km"]


def elapsed_h(drive_h: float, config: dict = CONFIG) -> float:
    """Wall-clock hours for a drive, adding a rest break after every max_drive_h_per_day of driving."""
    m = config["max_drive_h_per_day"]
    return drive_h + math.floor(drive_h / m) * (24 - m)
