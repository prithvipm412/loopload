"""Pydantic response models mirroring docs/CONTRACT.md §4. Owned by CC.
Only this API layer uses Pydantic; engine modules stay on plain dict/list (CONTRACT §1)."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class City(BaseModel):
    id: str
    name: str
    state: str
    lat: float
    lon: float


class Driver(BaseModel):
    name: str
    language: str


class Truck(BaseModel):
    id: str
    owner_id: str
    reg_no: str
    type: Literal["open_body", "container", "reefer"]
    capacity_t: float
    home_city: str
    start_city: str
    available_from_h: float
    national_permit_valid_until: str
    driver: Driver


class Owner(BaseModel):
    id: str
    name: str
    home_city: str
    trucks: list[str]


class EwayBill(BaseModel):
    number: str
    valid_until_h: float
    vehicle_reg: str


class Load(BaseModel):
    id: str
    origin: str
    destination: str
    commodity: str
    weight_t: float
    truck_type: Literal["open_body", "container", "reefer"]
    pickup_start_h: float
    pickup_end_h: float
    deliver_by_h: float
    freight_inr: int
    cargo_value_inr: int
    source: Literal["broker", "shipper"]
    eway_bill: Optional[EwayBill] = None


class Scenario(BaseModel):
    week_start: str
    cities: list[City]
    owners: list[Owner]
    trucks: list[Truck]
    loads: list[Load]


class Matrix(BaseModel):
    cities: list[str]
    distance_km: list[list[float]]
    duration_h: list[list[float]]
    source: str


class ComplianceIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str


class ComplianceResult(BaseModel):
    ok: bool
    issues: list[ComplianceIssue] = []


class Leg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    truck_id: str
    seq: int
    kind: Literal["loaded", "empty"]
    from_: str = Field(alias="from")
    to: str
    load_id: Optional[str] = None
    depart_h: float
    arrive_h: float
    distance_km: float
    revenue_inr: int
    diesel_inr: int
    toll_inr: int
    co2_kg: float
    path: list[list[float]] = []
    compliance: Optional[ComplianceResult] = None
    reason: Optional[str] = None


class Metrics(BaseModel):
    total_km: float
    loaded_km: float
    empty_km: float
    empty_pct: float
    revenue_inr: int
    diesel_inr: int
    toll_inr: int
    profit_inr: int
    co2_kg: float
    loads_served: int
    loads_total: int
    trucks_used: int
    idle_h: float


class TruckPlan(BaseModel):
    truck_id: str
    legs: list[Leg]
    totals: Metrics


class Plan(BaseModel):
    plan_id: str
    mode: Literal["baseline", "ai", "ai_solo"]
    created_at: str
    solve_time_s: float
    trucks: list[TruckPlan]
    unassigned_loads: list[str]
    metrics: Metrics
    replan_of: Optional[str] = None
    changed_trucks: Optional[list[str]] = None
    highlights: Optional[list[str]] = None


class Compare(BaseModel):
    baseline: Metrics
    ai: Metrics
    delta: dict[str, float]


class ForecastPoint(BaseModel):
    week: str
    loads: float


class ForecastPrediction(BaseModel):
    week: str
    loads: float
    lower: float
    upper: float


class Forecast(BaseModel):
    lane: str
    origin: str
    destination: str
    commodity: str
    history: list[ForecastPoint]
    forecast: list[ForecastPrediction]
    change_pct: float


class PlanRequest(BaseModel):
    mode: Literal["baseline", "ai", "ai_solo"] = "baseline"


class RegenerateRequest(BaseModel):
    seed: int = 42
    n_trucks: int = 20
    n_loads: int = 140


class ReplanRequest(BaseModel):
    plan_id: str
    event: dict


class TruckWeekResponse(BaseModel):
    truck: Truck
    plan: TruckPlan


class OwnerSummaryResponse(BaseModel):
    owner: Owner
    metrics: Metrics
    trucks: list[TruckPlan]


class HealthResponse(BaseModel):
    ok: bool
