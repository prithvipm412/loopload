import scenarioJson from "./mocks/scenario.json";
import baselineJson from "./mocks/plan_baseline.json";
import aiJson from "./mocks/plan_ai.json";
import compareJson from "./mocks/compare.json";
import soloJson from "./mocks/plan_solo.json";
import forecastJson from "./mocks/forecast.json";
import type {
  Scenario,
  Plan,
  Mode,
  Compare,
  Truck,
  TruckPlan,
  Owner,
  Metrics,
  Forecast,
  ComplianceResult,
  ReplanEvent,
} from "./types";
const scenario = scenarioJson as Scenario,
  baseline = baselineJson as unknown as Plan,
  ai = aiJson as unknown as Plan;
const plans = new Map<string, Plan>([
  [baseline.plan_id, baseline],
  [ai.plan_id, ai],
]);
const base = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const mockMode = import.meta.env.VITE_USE_MOCKS === "true";
async function request<T>(
  path: string,
  fallback: () => T,
  body?: unknown,
  timeoutMs = 15000,
): Promise<T> {
  if (mockMode) return structuredClone(fallback());
  try {
    const r = await fetch(`${base}/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!r.ok) throw Error(`${r.status}`);
    return (await r.json()) as T;
  } catch {
    window.dispatchEvent(
      new CustomEvent("api-fallback", {
        detail: "API unavailable. Showing demo data.",
      }),
    );
    return structuredClone(fallback());
  }
}
const getMockPlan = (id: string) => plans.get(id) || ai;
const forecasts = forecastJson as Forecast[];
export const api = {
  health: () => request("/health", () => ({ ok: true })),
  scenario: () => request<Scenario>("/scenario", () => scenario),
  regenerate: (body: { seed: number; n_trucks: number; n_loads: number }) =>
    request<Scenario>("/scenario/regenerate", () => scenario, body),
  plan: async (mode: Mode) => {
    const p = await request<Plan>(
      "/plan",
      () => {
        if (mode !== "ai_solo") return mode === "baseline" ? baseline : ai;
        return soloJson as unknown as Plan;
      },
      { mode },
      mode === "ai_solo" ? 90000 : 45000,
    );
    plans.set(p.plan_id, p);
    return p;
  },
  getPlan: (id: string) => request<Plan>(`/plan/${id}`, () => getMockPlan(id)),
  compare: () =>
    request<Compare>(
      "/compare",
      () => compareJson as Compare,
      undefined,
      60000,
    ),
  replan: async (plan_id: string, event: ReplanEvent) => {
    const p = await request<Plan>(
      "/replan",
      () => {
        const p = structuredClone(getMockPlan(plan_id));
        p.plan_id = "ai-replan42";
        p.solve_time_s = 1.8;
        p.replan_of = plan_id;
        p.changed_trucks = [];
        if (event.type === "cancel_load") {
          for (const t of p.trucks) {
            for (const l of t.legs)
              if (l.load_id === event.load_id && l.depart_h >= event.at_h) {
                if (!p.changed_trucks!.includes(t.truck_id))
                  p.changed_trucks!.push(t.truck_id);
                l.kind = "empty";
                l.reason =
                  "Load cancelled; repositioning preserves the remaining schedule.";
                l.load_id = null;
                l.revenue_inr = 0;
                l.compliance = { ok: true, issues: [] };
              }
          }
          p.unassigned_loads.push(event.load_id);
        }
        recompute(p);
        const hero = p.trucks.find((t) => t.truck_id === "T01");
        p.highlights = [
          `T01: ${hero?.legs.filter((l) => l.kind === "loaded").length ?? 0} paying legs this week.`,
          `${p.metrics.loads_served} loads across ${p.metrics.trucks_used} active trucks.`,
          `${p.metrics.empty_pct.toLocaleString("en-IN", { maximumFractionDigits: 1 })}% empty fleet distance.`,
        ];
        return p;
      },
      { plan_id, event },
      45000,
    );
    plans.set(p.plan_id, p);
    return p;
  },
  truckWeek: (id: string, planId: string) =>
    request<{ truck: Truck; plan: TruckPlan }>(
      `/trucks/${id}/week?plan_id=${encodeURIComponent(planId)}`,
      () => ({
        truck: scenario.trucks.find((t) => t.id === id)!,
        plan: getMockPlan(planId).trucks.find((t) => t.truck_id === id)!,
      }),
    ),
  ownerSummary: (id: string, planId: string) =>
    request<{ owner: Owner; metrics: Metrics; trucks: TruckPlan[] }>(
      `/owners/${id}/summary?plan_id=${encodeURIComponent(planId)}`,
      () => {
        const trucks = getMockPlan(planId).trucks.filter(
          (t) =>
            scenario.trucks.find((x) => x.id === t.truck_id)?.owner_id === id,
        );
        const p = { ...getMockPlan(planId), trucks };
        recompute(p);
        return {
          owner: scenario.owners.find((o) => o.id === id)!,
          metrics: p.metrics,
          trucks,
        };
      },
    ),
  forecast: (lane?: string) =>
    request<Forecast[]>(
      `/forecast${lane ? `?lane=${encodeURIComponent(lane)}` : ""}`,
      () => forecasts.filter((f) => !lane || f.lane === lane),
    ),
  hotLanes: (n = 8) =>
    request<Forecast[]>(`/hot-lanes?n=${n}`, () => forecasts.slice(0, n)),
  compliance: (id: string, planId: string) =>
    request<ComplianceResult>(
      `/compliance/${id}?plan_id=${encodeURIComponent(planId)}`,
      () =>
        getMockPlan(planId)
          .trucks.flatMap((t) => t.legs)
          .find((l) => l.load_id === id)?.compliance || {
          ok: true,
          issues: [],
        },
    ),
};
function recompute(p: Plan) {
  const calc = (legs: TruckPlan["legs"]): Metrics => {
    const sum = (
      key: "distance_km" | "revenue_inr" | "diesel_inr" | "toll_inr" | "co2_kg",
    ) => legs.reduce((a, l) => a + l[key], 0);
    const total = sum("distance_km"),
      empty = legs
        .filter((l) => l.kind === "empty")
        .reduce((a, l) => a + l.distance_km, 0);
    return {
      total_km: total,
      loaded_km: total - empty,
      empty_km: empty,
      empty_pct: total ? (empty / total) * 100 : 0,
      revenue_inr: sum("revenue_inr"),
      diesel_inr: sum("diesel_inr"),
      toll_inr: sum("toll_inr"),
      profit_inr: sum("revenue_inr") - sum("diesel_inr") - sum("toll_inr"),
      co2_kg: sum("co2_kg"),
      co2_kg_per_load: legs.some((l) => l.kind === "loaded")
        ? sum("co2_kg") / legs.filter((l) => l.kind === "loaded").length
        : 0,
      loads_served: legs.filter((l) => l.kind === "loaded").length,
      loads_total: scenario.loads.length,
      trucks_used: new Set(legs.map((l) => l.truck_id)).size,
      idle_h: 0,
    };
  };
  p.trucks.forEach((t) => {
    t.totals = calc(t.legs);
    t.totals.idle_h = t.legs.reduce(
      (sum, leg, i) =>
        sum + (i ? Math.max(0, leg.depart_h - t.legs[i - 1].arrive_h) : 0),
      0,
    );
  });
  p.metrics = calc(p.trucks.flatMap((t) => t.legs));
  p.metrics.idle_h = p.trucks.reduce((s, t) => s + t.totals.idle_h, 0);
}
